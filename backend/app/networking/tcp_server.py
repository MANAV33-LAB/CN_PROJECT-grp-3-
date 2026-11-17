import os
import time
import socket
import select
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from collections import deque

from backend.app.config import settings
from backend.app.networking.protocol import (
    send_framed_message,
    recv_framed_message,
    ConnectionClosedError,
    ProtocolError
)
from backend.app.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.message import Message, MessageReceipt
from backend.app.models.group import Group, GroupMember
from backend.app.models.file import FileRecord
from backend.app.models.network_log import NetworkLog

logger = logging.getLogger("NetConnect.TCPServer")

class TCPServer:
    """
    Custom multi-threaded TCP Server for NetConnect.
    Demonstrates low-level socket programming, connection management,
    framing, reliable message routing, and chunked file transfer.
    """

    def __init__(self, host: str = settings.TCP_HOST, port: int = settings.TCP_PORT):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.is_running = False

        # Concurrency & Registries
        self.lock = threading.RLock()
        # user_id -> socket
        self.user_sockets: Dict[int, socket.socket] = {}
        # socket -> user_id
        self.socket_users: Dict[socket.socket, int] = {}
        # user_id -> metadata
        self.user_metadata: Dict[int, dict] = {}
        # Active in-flight file transfers: file_id -> file_handle / metadata
        self.active_file_transfers: Dict[str, dict] = {}

        # Threads
        self.accept_thread: Optional[threading.Thread] = None
        self.client_threads: List[threading.Thread] = []

        # Server Telemetry & Metrics
        self.start_time: float = 0.0
        self.total_connections_served = 0
        self.total_messages_relayed = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.recent_events = deque(maxlen=200)

        # Callbacks (e.g. for WebSocket gateway bridging or event listeners)
        self.event_subscribers = []

    def log_network_event(self, event_type: str, details: str, client_ip: str = "127.0.0.1",
                          client_port: int = 0, user_id: Optional[int] = None, bytes_count: int = 0):
        event = {
            "protocol": "TCP",
            "event_type": event_type,
            "details": details,
            "client_ip": client_ip,
            "client_port": client_port,
            "user_id": user_id,
            "bytes_transferred": bytes_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with self.lock:
            self.recent_events.append(event)

        for sub in list(self.event_subscribers):
            try:
                sub(event)
            except Exception:
                pass

        # Also persist asynchronously to database to avoid slowing down socket thread
        threading.Thread(target=self._persist_log, args=(event,), daemon=True).start()

    def _persist_log(self, event: dict):
        db = SessionLocal()
        try:
            log_entry = NetworkLog(
                protocol=event["protocol"],
                event_type=event["event_type"],
                client_ip=event["client_ip"],
                client_port=event["client_port"],
                user_id=event["user_id"],
                bytes_transferred=event["bytes_transferred"],
                details=event["details"]
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            db.rollback()
        finally:
            db.close()

    def start(self):
        """Initializes and starts the TCP server on a background thread."""
        if self.is_running:
            logger.warning("TCP server is already running")
            return

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Disable Nagle's algorithm for low-latency chat messaging
        try:
            self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except (AttributeError, OSError):
            pass

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(128)
        self.is_running = True
        self.start_time = time.time()

        self.accept_thread = threading.Thread(target=self._accept_loop, name="TCPServer-Accept", daemon=True)
        self.accept_thread.start()
        logger.info(f"TCP Server successfully bound and listening on {self.host}:{self.port}")
        self.log_network_event("SERVER_START", f"TCP server listening on {self.host}:{self.port}")

    def stop(self):
        """Gracefully shuts down the TCP server and closes all active connections."""
        if not self.is_running:
            return

        logger.info("Initiating graceful shutdown of TCP Server...")
        self.is_running = False

        # Close all active client sockets
        with self.lock:
            for uid, sock in list(self.user_sockets.items()):
                try:
                    send_framed_message(sock, {"type": "SERVER_SHUTDOWN", "message": "Server shutting down"})
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                finally:
                    sock.close()
            self.user_sockets.clear()
            self.socket_users.clear()
            self.user_metadata.clear()

        # Close the listening socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

        logger.info("TCP Server shut down cleanly.")

    def _accept_loop(self):
        """Main listening loop to accept incoming client connections."""
        while self.is_running:
            try:
                # Use select with timeout so accept loop can exit when is_running becomes False
                readable, _, _ = select.select([self.server_socket], [], [], 1.0)
                if not readable or not self.is_running:
                    continue

                client_sock, client_addr = self.server_socket.accept()
                with self.lock:
                    self.total_connections_served += 1

                ip, port = client_addr
                self.log_network_event("CONNECT", f"TCP Connection established with {ip}:{port}", client_ip=ip, client_port=port)
                logger.info(f"Accepted TCP connection from {ip}:{port}")

                # Spawn worker thread for this client
                client_thread = threading.Thread(
                    target=self._client_handler_loop,
                    args=(client_sock, client_addr),
                    name=f"TCPClient-{ip}:{port}",
                    daemon=True
                )
                client_thread.start()

            except OSError:
                break
            except Exception as e:
                logger.error(f"Error in TCP accept loop: {e}", exc_info=True)

    def _client_handler_loop(self, client_sock: socket.socket, client_addr: Tuple[str, int]):
        """Dedicated reader thread loop for an individual connected TCP client."""
        client_ip, client_port = client_addr
        user_id: Optional[int] = None

        try:
            while self.is_running:
                # Receive framed message
                data, bytes_received = recv_framed_message(client_sock, parse_json=True)
                with self.lock:
                    self.total_bytes_received += bytes_received

                if not isinstance(data, dict):
                    logger.warning(f"Malformed non-dictionary message received from {client_ip}:{client_port}")
                    continue

                msg_type = data.get("type")
                if not msg_type:
                    continue

                # Route message based on protocol type
                if msg_type == "AUTH":
                    user_id = self._handle_auth(client_sock, client_addr, data)
                elif msg_type == "CHAT_PRIVATE":
                    self._handle_private_message(client_sock, user_id, data, bytes_received)
                elif msg_type == "CHAT_GROUP":
                    self._handle_group_message(client_sock, user_id, data, bytes_received)
                elif msg_type == "MSG_STATUS":
                    self._handle_status_update(client_sock, user_id, data)
                elif msg_type == "FILE_START":
                    self._handle_file_start(client_sock, user_id, data)
                elif msg_type == "FILE_CHUNK":
                    self._handle_file_chunk(client_sock, user_id, data, bytes_received)
                elif msg_type == "FILE_COMPLETE":
                    self._handle_file_complete(client_sock, user_id, data)
                elif msg_type == "PING":
                    self._send_to_socket(client_sock, {"type": "PONG", "timestamp": time.time()})
                elif msg_type == "CLOSE":
                    logger.info(f"Client {client_ip}:{client_port} requested graceful close.")
                    break
                else:
                    logger.warning(f"Unrecognized message type '{msg_type}' from user {user_id}")

        except ConnectionClosedError:
            logger.info(f"TCP Client {client_ip}:{client_port} (User: {user_id}) disconnected.")
        except Exception as e:
            logger.warning(f"Socket exception for client {client_ip}:{client_port} (User: {user_id}): {e}")
        finally:
            self._cleanup_client(client_sock, user_id, client_ip, client_port)

    def _cleanup_client(self, client_sock: socket.socket, user_id: Optional[int], client_ip: str, client_port: int):
        """Cleans up client state, removes from registries, and closes socket."""
        with self.lock:
            if user_id and self.user_sockets.get(user_id) == client_sock:
                del self.user_sockets[user_id]
                self.user_metadata.pop(user_id, None)
            if client_sock in self.socket_users:
                del self.socket_users[client_sock]

        try:
            client_sock.close()
        except Exception:
            pass

        self.log_network_event("DISCONNECT", f"TCP connection closed for user {user_id or 'unauthenticated'}",
                               client_ip=client_ip, client_port=client_port, user_id=user_id)

        # Notify presence if no other TCP sockets exist for this user
        if user_id:
            self._check_and_mark_user_offline(user_id)

    def _check_and_mark_user_offline(self, user_id: int):
        with self.lock:
            if user_id in self.user_sockets:
                return

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.is_online = False
                user.last_seen = datetime.now(timezone.utc)
                db.commit()
        except Exception as e:
            db.rollback()
        finally:
            db.close()

    def _handle_auth(self, client_sock: socket.socket, client_addr: Tuple[str, int], data: dict) -> Optional[int]:
        """Authenticates client socket and registers it into active connections."""
        user_id = data.get("user_id")
        username = data.get("username", "")

        if not user_id:
            self._send_to_socket(client_sock, {"type": "AUTH_FAILURE", "error": "user_id is required"})
            return None

        # Verify user exists in DB
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                self._send_to_socket(client_sock, {"type": "AUTH_FAILURE", "error": "User does not exist"})
                return None

            user.is_online = True
            user.last_seen = datetime.now(timezone.utc)
            db.commit()
            username = user.username
        except Exception as e:
            db.rollback()
            self._send_to_socket(client_sock, {"type": "AUTH_FAILURE", "error": str(e)})
            return None
        finally:
            db.close()

        with self.lock:
            # If an existing socket exists for this user, close old socket gracefully
            old_sock = self.user_sockets.get(user_id)
            if old_sock and old_sock != client_sock:
                try:
                    self._send_to_socket(old_sock, {"type": "SESSION_REPLACED", "message": "New connection established"})
                    old_sock.close()
                except Exception:
                    pass

            self.user_sockets[user_id] = client_sock
            self.socket_users[client_sock] = user_id
            self.user_metadata[user_id] = {
                "username": username,
                "addr": client_addr,
                "connected_at": time.time()
            }

        self.log_network_event("AUTH", f"User {username} (ID: {user_id}) authenticated successfully",
                               client_ip=client_addr[0], client_port=client_addr[1], user_id=user_id)

        # Send ACK back to client
        self._send_to_socket(client_sock, {
            "type": "AUTH_SUCCESS",
            "user_id": user_id,
            "username": username,
            "message": "TCP Connection Authenticated"
        })

        # Deliver pending offline messages for this user
        self._deliver_offline_messages(user_id, client_sock)
        return user_id

    def _deliver_offline_messages(self, user_id: int, client_sock: socket.socket):
        """Retrieves and delivers messages sent while the user was offline."""
        db = SessionLocal()
        try:
            # Pending direct messages where user is recipient
            pending_msgs = db.query(Message).filter(
                Message.recipient_id == user_id,
                Message.status == "sent"
            ).order_by(Message.created_at.asc()).all()

            for msg in pending_msgs:
                msg_payload = {
                    "type": "CHAT_PRIVATE",
                    "id": msg.id,
                    "client_msg_id": msg.client_msg_id,
                    "sender_id": msg.sender_id,
                    "sender_username": msg.sender.username if msg.sender else "unknown",
                    "sender_name": msg.sender.display_name if msg.sender else "User",
                    "recipient_id": user_id,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "file": msg.file.to_dict() if msg.file else None,
                    "status": "delivered",
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "is_offline_delivery": True
                }
                self._send_to_socket(client_sock, msg_payload)
                msg.status = "delivered"
                msg.delivered_at = datetime.now(timezone.utc)

                # Notify sender that message has now been delivered
                with self.lock:
                    sender_sock = self.user_sockets.get(msg.sender_id)
                if sender_sock:
                    self._send_to_socket(sender_sock, {
                        "type": "MSG_STATUS",
                        "message_id": msg.id,
                        "client_msg_id": msg.client_msg_id,
                        "status": "delivered",
                        "delivered_at": msg.delivered_at.isoformat()
                    })

            db.commit()
            if pending_msgs:
                logger.info(f"Delivered {len(pending_msgs)} pending offline messages to user {user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error delivering offline messages to user {user_id}: {e}")
        finally:
            db.close()

    def _handle_private_message(self, sender_sock: socket.socket, sender_id: Optional[int], data: dict, bytes_count: int):
        """Processes and routes private direct messages reliably via TCP."""
        if not sender_id:
            self._send_to_socket(sender_sock, {"type": "ERROR", "error": "Unauthenticated TCP connection"})
            return

        recipient_id = data.get("recipient_id")
        content = data.get("content", "").strip()
        client_msg_id = data.get("client_msg_id")

        if not recipient_id or not content:
            self._send_to_socket(sender_sock, {"type": "ERROR", "error": "Invalid recipient or empty content"})
            return

        db = SessionLocal()
        created_msg = None
        try:
            # Check if recipient is currently connected over TCP
            with self.lock:
                recipient_sock = self.user_sockets.get(recipient_id)

            initial_status = "delivered" if recipient_sock else "sent"
            now = datetime.now(timezone.utc)

            created_msg = Message(
                client_msg_id=client_msg_id,
                sender_id=sender_id,
                recipient_id=recipient_id,
                content=content,
                message_type="text",
                status=initial_status,
                delivered_at=now if initial_status == "delivered" else None,
                created_at=now
            )
            db.add(created_msg)
            db.commit()
            db.refresh(created_msg)

            # Sender info
            sender_user = db.query(User).filter(User.id == sender_id).first()
            sender_username = sender_user.username if sender_user else "unknown"
            sender_name = sender_user.display_name if sender_user else "User"

            payload_out = {
                "type": "CHAT_PRIVATE",
                "id": created_msg.id,
                "client_msg_id": client_msg_id,
                "sender_id": sender_id,
                "sender_username": sender_username,
                "sender_name": sender_name,
                "recipient_id": recipient_id,
                "content": content,
                "message_type": "text",
                "status": initial_status,
                "created_at": created_msg.created_at.isoformat()
            }

            # If recipient is online, deliver immediately over TCP
            if recipient_sock:
                self._send_to_socket(recipient_sock, payload_out)
                self.log_network_event("MSG_RELAY", f"Direct message {created_msg.id} delivered from {sender_id} to {recipient_id}",
                                       user_id=sender_id, bytes_count=bytes_count)
            else:
                self.log_network_event("MSG_QUEUED", f"Recipient {recipient_id} offline. Message {created_msg.id} queued for later delivery.",
                                       user_id=sender_id, bytes_count=bytes_count)

            # Send ACK back to sender
            self._send_to_socket(sender_sock, {
                "type": "MSG_STATUS",
                "message_id": created_msg.id,
                "client_msg_id": client_msg_id,
                "status": initial_status,
                "delivered_at": created_msg.delivered_at.isoformat() if created_msg.delivered_at else None,
                "created_at": created_msg.created_at.isoformat()
            })

            with self.lock:
                self.total_messages_relayed += 1

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing private message: {e}", exc_info=True)
            self._send_to_socket(sender_sock, {"type": "ERROR", "error": f"Failed to persist message: {e}"})
        finally:
            db.close()

    def _handle_group_message(self, sender_sock: socket.socket, sender_id: Optional[int], data: dict, bytes_count: int):
        """Processes and broadcasts group messages to all connected room members."""
        if not sender_id:
            self._send_to_socket(sender_sock, {"type": "ERROR", "error": "Unauthenticated connection"})
            return

        group_id = data.get("group_id")
        content = data.get("content", "").strip()
        client_msg_id = data.get("client_msg_id")

        if not group_id or not content:
            self._send_to_socket(sender_sock, {"type": "ERROR", "error": "Invalid group or empty content"})
            return

        db = SessionLocal()
        try:
            # Verify sender is member of group
            membership = db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == sender_id
            ).first()

            if not membership:
                self._send_to_socket(sender_sock, {"type": "ERROR", "error": "You are not a member of this group"})
                return

            now = datetime.now(timezone.utc)
            created_msg = Message(
                client_msg_id=client_msg_id,
                sender_id=sender_id,
                group_id=group_id,
                content=content,
                message_type="text",
                status="sent",
                created_at=now
            )
            db.add(created_msg)
            db.commit()
            db.refresh(created_msg)

            sender_user = db.query(User).filter(User.id == sender_id).first()
            sender_username = sender_user.username if sender_user else "unknown"
            sender_name = sender_user.display_name if sender_user else "User"

            payload_out = {
                "type": "CHAT_GROUP",
                "id": created_msg.id,
                "client_msg_id": client_msg_id,
                "sender_id": sender_id,
                "sender_username": sender_username,
                "sender_name": sender_name,
                "group_id": group_id,
                "content": content,
                "message_type": "text",
                "status": "sent",
                "created_at": created_msg.created_at.isoformat()
            }

            # Query all group members
            members = db.query(GroupMember.user_id).filter(GroupMember.group_id == group_id).all()
            member_ids = [m[0] for m in members]

            # Broadcast to all connected members (excluding sender socket if desired or including with ACK)
            delivered_count = 0
            with self.lock:
                for mid in member_ids:
                    if mid == sender_id:
                        continue
                    sock = self.user_sockets.get(mid)
                    if sock:
                        self._send_to_socket(sock, payload_out)
                        delivered_count += 1

            # Send ACK to sender
            self._send_to_socket(sender_sock, {
                "type": "MSG_STATUS",
                "message_id": created_msg.id,
                "client_msg_id": client_msg_id,
                "status": "sent",
                "delivered_count": delivered_count,
                "created_at": created_msg.created_at.isoformat()
            })

            with self.lock:
                self.total_messages_relayed += 1

            self.log_network_event("GROUP_BROADCAST", f"Group message {created_msg.id} relayed to {delivered_count} active members in group {group_id}",
                                   user_id=sender_id, bytes_count=bytes_count)

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing group message: {e}", exc_info=True)
            self._send_to_socket(sender_sock, {"type": "ERROR", "error": str(e)})
        finally:
            db.close()

    def _handle_status_update(self, client_sock: socket.socket, user_id: Optional[int], data: dict):
        """Updates message delivery or read receipts and relays to original sender."""
        message_id = data.get("message_id")
        new_status = data.get("status") # 'delivered' or 'read'

        if not message_id or new_status not in ["delivered", "read"]:
            return

        db = SessionLocal()
        try:
            msg = db.query(Message).filter(Message.id == message_id).first()
            if not msg:
                return

            now = datetime.now(timezone.utc)
            if new_status == "delivered" and msg.status == "sent":
                msg.status = "delivered"
                msg.delivered_at = now
            elif new_status == "read":
                msg.status = "read"
                msg.read_at = now

            db.commit()

            # Relay receipt to original sender if connected
            with self.lock:
                sender_sock = self.user_sockets.get(msg.sender_id)

            if sender_sock:
                self._send_to_socket(sender_sock, {
                    "type": "MSG_STATUS",
                    "message_id": msg.id,
                    "client_msg_id": msg.client_msg_id,
                    "status": new_status,
                    "timestamp": now.isoformat()
                })
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating message status: {e}")
        finally:
            db.close()

    # ---- Chunked TCP File Transfer Implementation ----
    def _handle_file_start(self, client_sock: socket.socket, sender_id: Optional[int], data: dict):
        """Prepares server buffer for chunked TCP file upload."""
        if not sender_id:
            return

        file_transfer_id = data.get("file_transfer_id")
        filename = os.path.basename(data.get("filename", "upload.bin"))
        file_size = data.get("file_size", 0)
        mime_type = data.get("mime_type", "application/octet-stream")
        recipient_id = data.get("recipient_id")
        group_id = data.get("group_id")
        total_chunks = data.get("total_chunks", 1)

        import uuid
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        target_path = os.path.join(settings.UPLOAD_DIR, unique_name)

        try:
            f_handle = open(target_path, "wb")
            with self.lock:
                self.active_file_transfers[file_transfer_id] = {
                    "handle": f_handle,
                    "path": target_path,
                    "filename": filename,
                    "stored_filename": unique_name,
                    "file_size": file_size,
                    "mime_type": mime_type,
                    "sender_id": sender_id,
                    "recipient_id": recipient_id,
                    "group_id": group_id,
                    "total_chunks": total_chunks,
                    "received_chunks": 0,
                    "bytes_written": 0
                }

            self._send_to_socket(client_sock, {
                "type": "FILE_READY",
                "file_transfer_id": file_transfer_id,
                "message": "Ready to receive chunks"
            })
            self.log_network_event("FILE_START", f"Starting TCP file transfer for '{filename}' ({file_size} bytes)", user_id=sender_id)
        except Exception as e:
            logger.error(f"Failed to initiate file transfer: {e}")
            self._send_to_socket(client_sock, {"type": "ERROR", "error": f"File initiation failed: {e}"})

    def _handle_file_chunk(self, client_sock: socket.socket, sender_id: Optional[int], data: dict, bytes_count: int):
        """Writes incoming chunk over TCP stream and updates progress."""
        file_transfer_id = data.get("file_transfer_id")
        chunk_index = data.get("chunk_index")
        import base64
        chunk_b64 = data.get("data", "")

        with self.lock:
            transfer = self.active_file_transfers.get(file_transfer_id)

        if not transfer:
            self._send_to_socket(client_sock, {"type": "ERROR", "error": "Invalid or expired file transfer ID"})
            return

        try:
            chunk_bytes = base64.b64decode(chunk_b64)
            transfer["handle"].write(chunk_bytes)
            transfer["bytes_written"] += len(chunk_bytes)
            transfer["received_chunks"] += 1

            # Acknowledge chunk
            self._send_to_socket(client_sock, {
                "type": "FILE_CHUNK_ACK",
                "file_transfer_id": file_transfer_id,
                "chunk_index": chunk_index,
                "bytes_written": transfer["bytes_written"]
            })
        except Exception as e:
            logger.error(f"Error writing chunk {chunk_index}: {e}")
            self._send_to_socket(client_sock, {"type": "ERROR", "error": f"Failed writing chunk {chunk_index}: {e}"})

    def _handle_file_complete(self, client_sock: socket.socket, sender_id: Optional[int], data: dict):
        """Finalizes chunked file transfer, commits record to DB, and routes message."""
        file_transfer_id = data.get("file_transfer_id")

        with self.lock:
            transfer = self.active_file_transfers.pop(file_transfer_id, None)

        if not transfer:
            return

        try:
            transfer["handle"].close()
        except Exception:
            pass

        db = SessionLocal()
        try:
            file_record = FileRecord(
                original_name=transfer["filename"],
                stored_filename=transfer["stored_filename"],
                file_size=transfer["bytes_written"],
                mime_type=transfer["mime_type"],
                file_path=transfer["path"],
                uploaded_by=transfer["sender_id"]
            )
            db.add(file_record)
            db.commit()
            db.refresh(file_record)

            now = datetime.now(timezone.utc)
            # Create corresponding message for the file
            msg = Message(
                sender_id=transfer["sender_id"],
                recipient_id=transfer["recipient_id"],
                group_id=transfer["group_id"],
                content=f"Shared a file: {transfer['filename']}",
                message_type="file",
                file_id=file_record.id,
                status="sent",
                created_at=now
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)

            # Route message with file attachment
            file_dict = file_record.to_dict()
            sender_user = db.query(User).filter(User.id == transfer["sender_id"]).first()
            sender_username = sender_user.username if sender_user else "unknown"
            sender_name = sender_user.display_name if sender_user else "User"

            if transfer["recipient_id"]:
                payload = {
                    "type": "CHAT_PRIVATE",
                    "id": msg.id,
                    "sender_id": transfer["sender_id"],
                    "sender_username": sender_username,
                    "sender_name": sender_name,
                    "recipient_id": transfer["recipient_id"],
                    "content": msg.content,
                    "message_type": "file",
                    "file": file_dict,
                    "status": "delivered",
                    "created_at": now.isoformat()
                }
                with self.lock:
                    recip_sock = self.user_sockets.get(transfer["recipient_id"])
                if recip_sock:
                    self._send_to_socket(recip_sock, payload)
                    msg.status = "delivered"
                    db.commit()

            elif transfer["group_id"]:
                payload = {
                    "type": "CHAT_GROUP",
                    "id": msg.id,
                    "sender_id": transfer["sender_id"],
                    "sender_username": sender_username,
                    "sender_name": sender_name,
                    "group_id": transfer["group_id"],
                    "content": msg.content,
                    "message_type": "file",
                    "file": file_dict,
                    "status": "sent",
                    "created_at": now.isoformat()
                }
                members = db.query(GroupMember.user_id).filter(GroupMember.group_id == transfer["group_id"]).all()
                with self.lock:
                    for (mid,) in members:
                        if mid != transfer["sender_id"]:
                            sock = self.user_sockets.get(mid)
                            if sock:
                                self._send_to_socket(sock, payload)

            # ACK upload completion to sender
            self._send_to_socket(client_sock, {
                "type": "FILE_COMPLETED",
                "file_transfer_id": file_transfer_id,
                "file": file_dict,
                "message_id": msg.id
            })

            self.log_network_event("FILE_COMPLETE", f"File '{transfer['filename']}' ({transfer['bytes_written']} bytes) saved & routed",
                                   user_id=transfer["sender_id"], bytes_count=transfer["bytes_written"])

        except Exception as e:
            db.rollback()
            logger.error(f"Error completing file transfer: {e}", exc_info=True)
            self._send_to_socket(client_sock, {"type": "ERROR", "error": f"Failed finalizing file: {e}"})
        finally:
            db.close()

    def _send_to_socket(self, sock: socket.socket, payload: dict) -> bool:
        """Internal helper to frame and send a JSON payload reliably to a socket."""
        try:
            bytes_sent = send_framed_message(sock, payload)
            with self.lock:
                self.total_bytes_sent += bytes_sent
            return True
        except (ConnectionClosedError, OSError) as e:
            logger.debug(f"Failed sending to socket: {e}")
            return False

    def send_to_user(self, user_id: int, payload: dict) -> bool:
        """Sends a framed payload directly to a connected user by user_id."""
        with self.lock:
            sock = self.user_sockets.get(user_id)
        if sock:
            return self._send_to_socket(sock, payload)
        return False

    def get_stats(self) -> dict:
        """Returns snapshot of live TCP networking metrics."""
        with self.lock:
            active_conns = len(self.user_sockets)
            online_uids = list(self.user_sockets.keys())
            served = self.total_connections_served
            relayed = self.total_messages_relayed
            sent_b = self.total_bytes_sent
            recv_b = self.total_bytes_received
            recent = list(self.recent_events)

        uptime = time.time() - self.start_time if self.is_running else 0
        return {
            "is_running": self.is_running,
            "host": self.host,
            "port": self.port,
            "uptime_seconds": int(uptime),
            "active_connections": active_conns,
            "connected_user_ids": online_uids,
            "total_connections_served": served,
            "total_messages_relayed": relayed,
            "total_bytes_sent": sent_b,
            "total_bytes_received": recv_b,
            "total_bytes_transferred": sent_b + recv_b,
            "recent_events": recent[-50:]
        }
