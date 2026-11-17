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
    build_udp_packet,
    parse_udp_packet,
    ProtocolError
)
from backend.app.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.group import GroupMember
from backend.app.models.network_log import NetworkLog

logger = logging.getLogger("NetConnect.UDPServer")

class UDPServer:
    """
    Custom UDP Server for NetConnect.
    Demonstrates connectionless datagram communication, periodic heartbeats,
    presence detection, typing indicators, and handling lossy/malformed packets.
    """

    def __init__(self, host: str = settings.UDP_HOST, port: int = settings.UDP_PORT):
        self.host = host
        self.port = port
        self.udp_socket: Optional[socket.socket] = None
        self.is_running = False

        # Concurrency & Registries
        self.lock = threading.RLock()
        # user_id -> {"addr": (ip, port), "username": str, "last_heartbeat": float, "last_seq": int}
        self.online_registry: Dict[int, dict] = {}
        # In-memory typing state: (user_id, target_type, target_id) -> timestamp
        self.active_typing: Dict[Tuple[int, str, int], float] = {}

        # Worker threads
        self.recv_thread: Optional[threading.Thread] = None
        self.monitor_thread: Optional[threading.Thread] = None

        # Server Telemetry & Metrics
        self.start_time: float = 0.0
        self.total_datagrams_received = 0
        self.total_datagrams_sent = 0
        self.total_heartbeats = 0
        self.total_typing_events = 0
        self.dropped_malformed_packets = 0
        self.total_udp_bytes_received = 0
        self.total_udp_bytes_sent = 0
        self.recent_events = deque(maxlen=200)

        # Callbacks (for pushing presence events to WebSocket gateway or TCP server)
        self.presence_subscribers = []

    def add_presence_subscriber(self, callback):
        """Allows WebSocket gateway or others to receive presence/typing events."""
        self.presence_subscribers.append(callback)

    def _notify_subscribers(self, event_type: str, data: dict):
        for sub in list(self.presence_subscribers):
            try:
                sub(event_type, data)
            except Exception as e:
                logger.debug(f"Subscriber callback error: {e}")

    def log_network_event(self, event_type: str, details: str, client_ip: str = "127.0.0.1",
                          client_port: int = 0, user_id: Optional[int] = None, bytes_count: int = 0):
        event = {
            "protocol": "UDP",
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

        # Persist log asynchronously
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
        except Exception:
            db.rollback()
        finally:
            db.close()

    def start(self):
        """Initializes and starts the UDP server."""
        if self.is_running:
            return

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allow multiple sockets to bind on same port if needed (helpful in dev/testing)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind((self.host, self.port))
        self.is_running = True
        self.start_time = time.time()

        self.recv_thread = threading.Thread(target=self._receive_loop, name="UDPServer-Recv", daemon=True)
        self.recv_thread.start()

        self.monitor_thread = threading.Thread(target=self._heartbeat_monitor_loop, name="UDPServer-Monitor", daemon=True)
        self.monitor_thread.start()

        logger.info(f"UDP Server bound and listening on {self.host}:{self.port}")
        self.log_network_event("SERVER_START", f"UDP server listening on {self.host}:{self.port}")

    def stop(self):
        """Gracefully shuts down the UDP server."""
        if not self.is_running:
            return

        logger.info("Stopping UDP server...")
        self.is_running = False

        if self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception:
                pass
            self.udp_socket = None

        logger.info("UDP server stopped cleanly.")

    def _receive_loop(self):
        """Main listening loop for incoming UDP datagrams."""
        while self.is_running:
            try:
                # Use select with 1s timeout to check is_running
                readable, _, _ = select.select([self.udp_socket], [], [], 1.0)
                if not readable or not self.is_running:
                    continue

                raw_data, addr = self.udp_socket.recvfrom(65535)
                recv_len = len(raw_data)
                client_ip, client_port = addr

                with self.lock:
                    self.total_datagrams_received += 1
                    self.total_udp_bytes_received += recv_len

                # Parse and validate datagram packet
                try:
                    packet = parse_udp_packet(raw_data)
                except ProtocolError as pe:
                    with self.lock:
                        self.dropped_malformed_packets += 1
                    logger.debug(f"Dropped malformed UDP datagram from {client_ip}:{client_port}: {pe}")
                    self.log_network_event("MALFORMED_PACKET", f"Dropped invalid UDP packet: {pe}",
                                           client_ip=client_ip, client_port=client_port, bytes_count=recv_len)
                    continue

                msg_type = packet.get("type")
                user_id = packet.get("user_id")
                username = packet.get("username", "")
                seq = packet.get("seq", 0)
                payload = packet.get("payload", {})

                if msg_type == "HEARTBEAT":
                    self._handle_heartbeat(addr, user_id, username, seq, recv_len)
                elif msg_type == "TYPING":
                    self._handle_typing(addr, user_id, username, payload, recv_len)
                elif msg_type == "PRESENCE_QUERY":
                    self._handle_presence_query(addr, user_id)
                elif msg_type == "PING":
                    self._send_udp(addr, build_udp_packet("PONG", user_id, username, {"recv_time": time.time()}))
                elif msg_type == "OFFLINE_NOTICE":
                    self._mark_user_offline(user_id, reason="Client shutdown notice")
                else:
                    logger.debug(f"Unrecognized UDP packet type '{msg_type}' from {addr}")

            except OSError:
                break
            except Exception as e:
                logger.error(f"Error in UDP receive loop: {e}", exc_info=True)

    def _send_udp(self, addr: Tuple[str, int], data: bytes) -> bool:
        """Sends a raw datagram to the specified address."""
        if not self.udp_socket or not self.is_running:
            return False
        try:
            sent_len = self.udp_socket.sendto(data, addr)
            with self.lock:
                self.total_datagrams_sent += 1
                self.total_udp_bytes_sent += sent_len
            return True
        except Exception as e:
            logger.debug(f"Failed to send UDP datagram to {addr}: {e}")
            return False

    def _handle_heartbeat(self, addr: Tuple[str, int], user_id: int, username: str, seq: int, bytes_count: int):
        """Processes a heartbeat datagram and marks or refreshes user online status."""
        now = time.time()
        was_offline = False

        with self.lock:
            self.total_heartbeats += 1
            if user_id not in self.online_registry:
                was_offline = True
            self.online_registry[user_id] = {
                "addr": addr,
                "username": username,
                "last_heartbeat": now,
                "last_seq": seq
            }

        # If user was not previously known as online, update database and broadcast
        if was_offline:
            self._update_user_db_status(user_id, is_online=True)
            self._notify_subscribers("PRESENCE_CHANGE", {
                "user_id": user_id,
                "username": username,
                "is_online": True,
                "last_seen": datetime.now(timezone.utc).isoformat()
            })
            self.log_network_event("HEARTBEAT_INITIAL", f"User {username} (ID: {user_id}) joined via UDP heartbeat",
                                   client_ip=addr[0], client_port=addr[1], user_id=user_id, bytes_count=bytes_count)
        else:
            self.log_network_event("HEARTBEAT", f"Heartbeat seq #{seq} from user {username} (ID: {user_id})",
                                   client_ip=addr[0], client_port=addr[1], user_id=user_id, bytes_count=bytes_count)

        # Send ACK datagram back to client
        ack_data = build_udp_packet("HEARTBEAT_ACK", user_id, username, {"seq": seq, "server_time": now})
        self._send_udp(addr, ack_data)

    def _handle_typing(self, addr: Tuple[str, int], user_id: int, username: str, payload: dict, bytes_count: int):
        """Processes and fans out lightweight typing notification datagrams."""
        target_type = payload.get("target_type", "user") # 'user' or 'group'
        target_id = payload.get("target_id")
        is_typing = payload.get("is_typing", True)

        if not target_id:
            return

        with self.lock:
            self.total_typing_events += 1
            key = (user_id, target_type, target_id)
            if is_typing:
                self.active_typing[key] = time.time()
            else:
                self.active_typing.pop(key, None)

        typing_event_payload = {
            "user_id": user_id,
            "username": username,
            "target_type": target_type,
            "target_id": target_id,
            "is_typing": is_typing,
            "timestamp": time.time()
        }

        # Broadcast typing status via UDP to target recipient(s) if their UDP address is known
        with self.lock:
            recipients_to_send: List[Tuple[str, int]] = []
            if target_type == "user":
                target_client = self.online_registry.get(target_id)
                if target_client:
                    recipients_to_send.append(target_client["addr"])
            elif target_type == "group":
                # For groups, we could fan out to group members whose UDP addrs are known
                pass

        datagram = build_udp_packet("TYPING_NOTIFICATION", user_id, username, typing_event_payload)
        for r_addr in recipients_to_send:
            self._send_udp(r_addr, datagram)

        # Notify WebSocket gateway subscribers so web browsers receive typing notifications
        self._notify_subscribers("TYPING", typing_event_payload)

        self.log_network_event("TYPING", f"User {username} {'is typing...' if is_typing else 'stopped typing'} to {target_type} {target_id}",
                               client_ip=addr[0], client_port=addr[1], user_id=user_id, bytes_count=bytes_count)

    def _handle_presence_query(self, addr: Tuple[str, int], requesting_user_id: int):
        """Replies to a UDP query with list of current online user IDs."""
        with self.lock:
            online_ids = list(self.online_registry.keys())

        resp = build_udp_packet("PRESENCE_RESPONSE", requesting_user_id, "", {"online_user_ids": online_ids})
        self._send_udp(addr, resp)

    def _heartbeat_monitor_loop(self):
        """
        Background monitoring thread that periodically checks for inactive clients.
        If a client fails to send a heartbeat within HEARTBEAT_TIMEOUT seconds,
        it is marked offline.
        """
        while self.is_running:
            time.sleep(2.0)
            now = time.time()
            timed_out_users = []

            with self.lock:
                for uid, info in list(self.online_registry.items()):
                    elapsed = now - info["last_heartbeat"]
                    if elapsed > settings.HEARTBEAT_TIMEOUT:
                        timed_out_users.append((uid, info["username"], info["addr"], elapsed))
                        del self.online_registry[uid]

            for uid, uname, addr, elapsed in timed_out_users:
                logger.info(f"User {uname} (ID: {uid}) timed out after {elapsed:.1f}s without UDP heartbeat.")
                self.log_network_event("TIMEOUT", f"User {uname} timed out ({elapsed:.1f}s without heartbeat)",
                                       client_ip=addr[0], client_port=addr[1], user_id=uid)
                self._update_user_db_status(uid, is_online=False)
                self._notify_subscribers("PRESENCE_CHANGE", {
                    "user_id": uid,
                    "username": uname,
                    "is_online": False,
                    "last_seen": datetime.now(timezone.utc).isoformat()
                })

            # Also cleanup stale typing indicators older than TYPING_TIMEOUT
            with self.lock:
                stale_keys = [k for k, t in self.active_typing.items() if now - t > settings.TYPING_TIMEOUT]
                for k in stale_keys:
                    del self.active_typing[k]

    def _mark_user_offline(self, user_id: int, reason: str = "Client notice"):
        with self.lock:
            info = self.online_registry.pop(user_id, None)

        if info:
            uname = info["username"]
            self._update_user_db_status(user_id, is_online=False)
            self._notify_subscribers("PRESENCE_CHANGE", {
                "user_id": user_id,
                "username": uname,
                "is_online": False,
                "last_seen": datetime.now(timezone.utc).isoformat()
            })
            self.log_network_event("OFFLINE", f"User {uname} marked offline: {reason}", user_id=user_id)

    def _update_user_db_status(self, user_id: int, is_online: bool):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.is_online = is_online
                user.last_seen = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def get_online_users(self) -> List[int]:
        """Returns list of user IDs currently deemed online via UDP."""
        with self.lock:
            return list(self.online_registry.keys())

    def is_user_online(self, user_id: int) -> bool:
        with self.lock:
            return user_id in self.online_registry

    def get_stats(self) -> dict:
        """Returns snapshot of live UDP networking metrics."""
        with self.lock:
            online_count = len(self.online_registry)
            online_uids = list(self.online_registry.keys())
            d_recv = self.total_datagrams_received
            d_sent = self.total_datagrams_sent
            hb_count = self.total_heartbeats
            typing_count = self.total_typing_events
            dropped = self.dropped_malformed_packets
            b_recv = self.total_udp_bytes_received
            b_sent = self.total_udp_bytes_sent
            recent = list(self.recent_events)

        uptime = time.time() - self.start_time if self.is_running else 0
        return {
            "is_running": self.is_running,
            "host": self.host,
            "port": self.port,
            "uptime_seconds": int(uptime),
            "online_users_count": online_count,
            "online_user_ids": online_uids,
            "total_datagrams_received": d_recv,
            "total_datagrams_sent": d_sent,
            "total_heartbeats": hb_count,
            "total_typing_events": typing_count,
            "dropped_malformed_packets": dropped,
            "total_bytes_received": b_recv,
            "total_bytes_sent": b_sent,
            "total_bytes_transferred": b_recv + b_sent,
            "recent_events": recent[-50:]
        }
