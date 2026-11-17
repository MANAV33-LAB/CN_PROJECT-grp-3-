import json
import time
import socket
import asyncio
import logging
import threading
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect

from backend.app.config import settings
from backend.app.networking.protocol import (
    send_framed_message,
    recv_framed_message,
    build_udp_packet,
    parse_udp_packet,
    ConnectionClosedError
)
from backend.app.networking.connection_manager import network_manager

logger = logging.getLogger("NetConnect.WebSocketGateway")

class ClientBridgeSession:
    """
    Manages an active WebSocket client session, bridging it to dedicated
    low-level TCP and UDP sockets.
    """

    def __init__(self, websocket: WebSocket, user_id: int, username: str):
        self.websocket = websocket
        self.user_id = user_id
        self.username = username
        self.tcp_sock: Optional[socket.socket] = None
        self.udp_sock: Optional[socket.socket] = None
        self.is_active = True
        self.heartbeat_seq = 0
        self.tasks = []

    async def initialize_networking(self) -> bool:
        """Connects TCP socket to TCP server and sets up UDP heartbeat socket."""
        loop = asyncio.get_running_loop()

        # 1. Connect TCP socket
        try:
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Run blocking connect in executor
            await loop.run_in_executor(None, self.tcp_sock.connect, (settings.TCP_HOST, settings.TCP_PORT))

            # Send AUTH message
            auth_payload = {
                "type": "AUTH",
                "user_id": self.user_id,
                "username": self.username
            }
            await loop.run_in_executor(None, send_framed_message, self.tcp_sock, auth_payload)

            # Wait for AUTH_SUCCESS
            reply, _ = await loop.run_in_executor(None, recv_framed_message, self.tcp_sock, True)
            if not isinstance(reply, dict) or reply.get("type") != "AUTH_SUCCESS":
                logger.error(f"TCP Auth failed for user {self.user_id}: {reply}")
                return False

        except Exception as e:
            logger.error(f"Failed to bridge TCP socket for user {self.user_id}: {e}")
            return False

        # 2. Setup UDP socket for heartbeats & typing
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Send initial heartbeat immediately
            self.send_udp_heartbeat()
        except Exception as e:
            logger.warning(f"Failed to create UDP socket for user {self.user_id}: {e}")

        return True

    def send_udp_heartbeat(self):
        """Sends a UDP heartbeat datagram to the UDP server."""
        if not self.udp_sock or not self.is_active:
            return
        self.heartbeat_seq += 1
        packet = build_udp_packet(
            msg_type="HEARTBEAT",
            user_id=self.user_id,
            username=self.username,
            seq=self.heartbeat_seq
        )
        try:
            self.udp_sock.sendto(packet, (settings.UDP_HOST, settings.UDP_PORT))
        except Exception as e:
            logger.debug(f"Error sending UDP heartbeat: {e}")

    def send_udp_typing(self, target_type: str, target_id: int, is_typing: bool):
        """Sends lightweight typing indicator datagram via UDP."""
        if not self.udp_sock or not self.is_active:
            return
        packet = build_udp_packet(
            msg_type="TYPING",
            user_id=self.user_id,
            username=self.username,
            payload={
                "target_type": target_type,
                "target_id": target_id,
                "is_typing": is_typing
            }
        )
        try:
            self.udp_sock.sendto(packet, (settings.UDP_HOST, settings.UDP_PORT))
        except Exception as e:
            logger.debug(f"Error sending UDP typing notice: {e}")

    def close(self):
        """Tears down TCP and UDP connections."""
        self.is_active = False

        # Send offline notice over UDP
        if self.udp_sock:
            try:
                offline_pkt = build_udp_packet("OFFLINE_NOTICE", self.user_id, self.username)
                self.udp_sock.sendto(offline_pkt, (settings.UDP_HOST, settings.UDP_PORT))
                self.udp_sock.close()
            except Exception:
                pass
            self.udp_sock = None

        # Close TCP socket
        if self.tcp_sock:
            try:
                send_framed_message(self.tcp_sock, {"type": "CLOSE"})
                self.tcp_sock.close()
            except Exception:
                pass
            self.tcp_sock = None


class WebSocketGateway:
    """
    Central gateway mapping active WebSocket browser connections to backend
    network infrastructure.
    """

    def __init__(self):
        self.active_sessions: Dict[int, ClientBridgeSession] = {}
        self.active_websockets: Dict[WebSocket, int] = {}
        self.lock = asyncio.Lock()

        # Register callback with UDP server to broadcast presence & typing to WebSockets
        network_manager.udp_server.add_presence_subscriber(self._on_udp_server_event)

    def _on_udp_server_event(self, event_type: str, data: dict):
        """Called by UDP server thread to push presence/typing to connected WebSockets."""
        asyncio.run_coroutine_threadsafe(self._broadcast_to_websockets(event_type, data), asyncio.get_event_loop())

    async def _broadcast_to_websockets(self, event_type: str, data: dict):
        """Broadcasts presence or typing event to all or relevant WebSocket clients."""
        payload = {"type": event_type, "data": data}
        text = json.dumps(payload)

        async with self.lock:
            sessions = list(self.active_sessions.values())

        for session in sessions:
            if not session.is_active:
                continue
            try:
                # If typing event, only send to relevant recipient or room members
                if event_type == "TYPING":
                    target_type = data.get("target_type")
                    target_id = data.get("target_id")
                    user_id = data.get("user_id")
                    if session.user_id == user_id:
                        continue # Don't send typing echo back to self
                    if target_type == "user" and session.user_id != target_id:
                        continue # Not intended for this user
                await session.websocket.send_text(text)
            except Exception:
                pass

    async def connect_client(self, websocket: WebSocket, user_id: int, username: str) -> Optional[ClientBridgeSession]:
        """Accepts WebSocket connection and establishes TCP/UDP bridge."""
        await websocket.accept()

        session = ClientBridgeSession(websocket, user_id, username)
        success = await session.initialize_networking()
        if not success:
            await websocket.close(code=1011, reason="Network bridge initialization failed")
            return None

        async with self.lock:
            # If user already had a session, close it
            old_session = self.active_sessions.get(user_id)
            if old_session:
                old_session.close()
            self.active_sessions[user_id] = session
            self.active_websockets[websocket] = user_id

        # Start background tasks for this session
        session.tasks.append(asyncio.create_task(self._tcp_to_ws_pump(session)))
        session.tasks.append(asyncio.create_task(self._heartbeat_pump(session)))

        logger.info(f"WebSocket client connected and bridged to TCP/UDP: {username} (ID: {user_id})")
        return session

    async def disconnect_client(self, websocket: WebSocket):
        """Cleans up session upon WebSocket disconnect."""
        async with self.lock:
            user_id = self.active_websockets.pop(websocket, None)
            session = self.active_sessions.pop(user_id, None) if user_id else None

        if session:
            for t in session.tasks:
                t.cancel()
            session.close()
            logger.info(f"WebSocket client disconnected: User ID {user_id}")

    async def _tcp_to_ws_pump(self, session: ClientBridgeSession):
        """Reads framed messages from TCP socket and forwards to browser WebSocket."""
        loop = asyncio.get_running_loop()
        while session.is_active:
            try:
                # Blocking recv framed message run in executor thread
                data, _ = await loop.run_in_executor(None, recv_framed_message, session.tcp_sock, True)
                if isinstance(data, dict):
                    await session.websocket.send_text(json.dumps(data))
            except (ConnectionClosedError, OSError):
                break
            except Exception as e:
                logger.debug(f"TCP pump error for user {session.user_id}: {e}")
                break

    async def _heartbeat_pump(self, session: ClientBridgeSession):
        """Sends periodic UDP heartbeats for the browser client session."""
        while session.is_active:
            try:
                await asyncio.sleep(settings.HEARTBEAT_INTERVAL)
                session.send_udp_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat pump error: {e}")

    async def handle_ws_message(self, session: ClientBridgeSession, raw_message: str):
        """Handles incoming messages from the browser WebSocket."""
        try:
            data = json.loads(raw_message)
        except Exception:
            return

        action = data.get("action") or data.get("type")

        # Typing indicator over UDP
        if action == "typing":
            target_type = data.get("target_type", "user")
            target_id = data.get("target_id")
            is_typing = data.get("is_typing", True)
            if target_id:
                session.send_udp_typing(target_type, int(target_id), bool(is_typing))

        # Direct / Group Chat message over TCP
        elif action in ["chat_private", "chat_group", "msg_status"]:
            loop = asyncio.get_running_loop()
            tcp_payload = dict(data)
            if action == "chat_private":
                tcp_payload["type"] = "CHAT_PRIVATE"
            elif action == "chat_group":
                tcp_payload["type"] = "CHAT_GROUP"
            elif action == "msg_status":
                tcp_payload["type"] = "MSG_STATUS"

            if session.tcp_sock:
                await loop.run_in_executor(None, send_framed_message, session.tcp_sock, tcp_payload)

        # Heartbeat trigger
        elif action == "heartbeat":
            session.send_udp_heartbeat()

websocket_gateway = WebSocketGateway()
