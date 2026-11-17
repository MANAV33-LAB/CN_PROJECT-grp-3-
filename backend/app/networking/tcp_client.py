import os
import time
import socket
import logging
import base64
from typing import Optional, Dict, Any, Tuple

from backend.app.config import settings
from backend.app.networking.protocol import (
    send_framed_message,
    recv_framed_message,
    ConnectionClosedError,
    ProtocolError
)

logger = logging.getLogger("NetConnect.TCPClient")

class TCPClient:
    """
    Client interface for interacting with the NetConnect TCP Server.
    Uses socket.socket(socket.AF_INET, socket.SOCK_STREAM) with
    the custom length-prefixed framing protocol.
    """

    def __init__(self, host: str = settings.TCP_HOST, port: int = settings.TCP_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.user_id: Optional[int] = None
        self.username: Optional[str] = None
        self.is_connected = False

    def connect(self, timeout: float = 5.0) -> bool:
        """Establishes TCP connection to the server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect((self.host, self.port))
            # Set socket to reasonable default timeout to prevent deadlocks
            self.sock.settimeout(5.0)
            self.is_connected = True
            return True
        except Exception as e:
            logger.error(f"TCP connection failed to {self.host}:{self.port}: {e}")
            self.is_connected = False
            return False

    def authenticate(self, user_id: int, username: str = "") -> bool:
        """Sends AUTH frame and waits for AUTH_SUCCESS."""
        if not self.is_connected:
            if not self.connect():
                return False

        auth_payload = {
            "type": "AUTH",
            "user_id": user_id,
            "username": username
        }
        send_framed_message(self.sock, auth_payload)

        # Wait for reply
        reply, _ = recv_framed_message(self.sock)
        if isinstance(reply, dict) and reply.get("type") == "AUTH_SUCCESS":
            self.user_id = user_id
            self.username = username
            return True
        else:
            logger.warning(f"Auth failed: {reply}")
            return False

    def send_private_message(self, recipient_id: int, content: str, client_msg_id: str = "", wait_ack: bool = True) -> Optional[dict]:
        """Sends a private direct message over TCP and returns server status/ACK if wait_ack is True."""
        payload = {
            "type": "CHAT_PRIVATE",
            "recipient_id": recipient_id,
            "content": content,
            "client_msg_id": client_msg_id or f"msg_{time.time()}"
        }
        send_framed_message(self.sock, payload)
        if wait_ack:
            reply, _ = recv_framed_message(self.sock)
            return reply
        return None

    def send_group_message(self, group_id: int, content: str, client_msg_id: str = "", wait_ack: bool = True) -> Optional[dict]:
        """Sends a group room message over TCP and returns server status/ACK if wait_ack is True."""
        payload = {
            "type": "CHAT_GROUP",
            "group_id": group_id,
            "content": content,
            "client_msg_id": client_msg_id or f"grp_{time.time()}"
        }
        send_framed_message(self.sock, payload)
        if wait_ack:
            reply, _ = recv_framed_message(self.sock)
            return reply
        return None

    def send_file(self, file_path: str, recipient_id: Optional[int] = None, group_id: Optional[int] = None,
                  chunk_size: int = settings.TCP_CHUNK_SIZE, progress_callback=None) -> dict:
        """
        Transfers a file chunk-by-chunk over TCP using framing.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        total_chunks = (file_size + chunk_size - 1) // chunk_size if file_size > 0 else 1
        transfer_id = f"tx_{int(time.time() * 1000)}"

        # 1. Send FILE_START
        start_payload = {
            "type": "FILE_START",
            "file_transfer_id": transfer_id,
            "filename": filename,
            "file_size": file_size,
            "mime_type": "application/octet-stream",
            "recipient_id": recipient_id,
            "group_id": group_id,
            "total_chunks": total_chunks
        }
        send_framed_message(self.sock, start_payload)
        resp, _ = recv_framed_message(self.sock)
        if resp.get("type") != "FILE_READY":
            raise ProtocolError(f"Server rejected file transfer: {resp}")

        # 2. Transmit Chunks
        with open(file_path, "rb") as f:
            chunk_idx = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                chunk_b64 = base64.b64encode(chunk).decode('ascii')
                chunk_payload = {
                    "type": "FILE_CHUNK",
                    "file_transfer_id": transfer_id,
                    "chunk_index": chunk_idx,
                    "data": chunk_b64
                }
                send_framed_message(self.sock, chunk_payload)
                ack, _ = recv_framed_message(self.sock)

                chunk_idx += 1
                if progress_callback:
                    progress_callback(chunk_idx, total_chunks, file_size)

        # 3. Send FILE_COMPLETE
        complete_payload = {
            "type": "FILE_COMPLETE",
            "file_transfer_id": transfer_id
        }
        send_framed_message(self.sock, complete_payload)
        final_resp, _ = recv_framed_message(self.sock)
        return final_resp

    def receive_message(self, timeout: Optional[float] = None) -> Tuple[Optional[dict], int]:
        """Receives next framed message from the TCP socket."""
        if not self.sock:
            return None, 0
        if timeout:
            self.sock.settimeout(timeout)
        try:
            data, n_bytes = recv_framed_message(self.sock)
            return data, n_bytes
        except (socket.timeout, TimeoutError):
            return None, 0
        finally:
            if timeout:
                self.sock.settimeout(5.0)

    def close(self):
        """Closes TCP connection cleanly."""
        if self.sock:
            try:
                send_framed_message(self.sock, {"type": "CLOSE"})
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.is_connected = False
