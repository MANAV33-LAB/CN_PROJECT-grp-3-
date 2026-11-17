import json
import struct
import socket
import logging
from typing import Optional, Tuple, Dict, Any, Union

logger = logging.getLogger("NetConnect.Protocol")

# Header format: 4-byte unsigned integer in big-endian network byte order
HEADER_FORMAT = ">I"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_MESSAGE_SIZE = 64 * 1024 * 1024  # 64 MB max payload safety limit

class ProtocolError(Exception):
    pass

class ConnectionClosedError(Exception):
    pass

def send_all(sock: socket.socket, data: bytes) -> int:
    """
    Reliably sends all bytes across a TCP socket, handling partial writes.
    Loops until all data has been transmitted.
    """
    total_sent = 0
    total_len = len(data)
    while total_sent < total_len:
        try:
            sent = sock.send(data[total_sent:])
            if sent == 0:
                raise ConnectionClosedError("Socket connection closed during send")
            total_sent += sent
        except (BlockingIOError, InterruptedError):
            continue
        except (ConnectionResetError, BrokenPipeError) as e:
            raise ConnectionClosedError(f"Connection reset/broken during send: {e}")
    return total_sent

def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Reliably receives an exact number of bytes from a TCP socket.
    Handles partial TCP reads by looping until the requested byte count is filled.
    Raises ConnectionClosedError if the peer closes the connection before completion.
    """
    buffer = bytearray()
    while len(buffer) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(buffer))
            if not chunk:
                # EOF reached: Peer performed graceful shutdown or connection dropped
                if len(buffer) == 0:
                    raise ConnectionClosedError("Connection gracefully closed by peer")
                else:
                    raise ConnectionClosedError(f"Connection closed prematurely (received {len(buffer)}/{num_bytes} bytes)")
            buffer.extend(chunk)
        except (BlockingIOError, InterruptedError):
            continue
        except (socket.timeout, TimeoutError):
            raise TimeoutError("Socket recv timed out")
        except (ConnectionResetError, BrokenPipeError) as e:
            raise ConnectionClosedError(f"Socket error during recv: {e}")
    return bytes(buffer)

def send_framed_message(sock: socket.socket, payload: Union[dict, str, bytes]) -> int:
    """
    Frames a message with a 4-byte big-endian length prefix and transmits it.
    If payload is a dict or str, it is serialized to UTF-8 JSON bytes.
    """
    if isinstance(payload, dict):
        body = json.dumps(payload).encode('utf-8')
    elif isinstance(payload, str):
        body = payload.encode('utf-8')
    elif isinstance(payload, bytes):
        body = payload
    else:
        raise ValueError(f"Unsupported payload type: {type(payload)}")

    body_len = len(body)
    if body_len > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Message size {body_len} exceeds maximum allowed {MAX_MESSAGE_SIZE} bytes")

    header = struct.pack(HEADER_FORMAT, body_len)
    total_bytes = send_all(sock, header + body)
    return total_bytes

def recv_framed_message(sock: socket.socket, parse_json: bool = True) -> Tuple[Union[dict, bytes], int]:
    """
    Receives a 4-byte length-prefixed framed message from a TCP socket.
    Returns (parsed_data, total_bytes_received).
    """
    header_bytes = recv_exact(sock, HEADER_SIZE)
    (body_len,) = struct.unpack(HEADER_FORMAT, header_bytes)

    if body_len > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Incoming message size {body_len} exceeds maximum allowed {MAX_MESSAGE_SIZE} bytes")

    body_bytes = recv_exact(sock, body_len)
    total_bytes = HEADER_SIZE + body_len

    if parse_json:
        try:
            data = json.loads(body_bytes.decode('utf-8'))
            return data, total_bytes
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to decode message as JSON: {e}")
            return body_bytes, total_bytes
    else:
        return body_bytes, total_bytes

# UDP Packet helpers
def build_udp_packet(msg_type: str, user_id: int, username: str, payload: Optional[Dict[str, Any]] = None, seq: int = 0) -> bytes:
    """
    Builds a structured UDP datagram payload.
    Does not include sensitive information like passwords or auth tokens.
    """
    import time
    packet = {
        "type": msg_type,
        "user_id": user_id,
        "username": username,
        "seq": seq,
        "timestamp": time.time(),
        "payload": payload or {}
    }
    return json.dumps(packet).encode('utf-8')

def parse_udp_packet(data: bytes) -> Dict[str, Any]:
    """
    Validates and parses a raw UDP datagram.
    Raises ProtocolError if malformed or missing required protocol fields.
    """
    try:
        packet = json.loads(data.decode('utf-8'))
    except Exception as e:
        raise ProtocolError(f"Malformed UDP datagram (not valid JSON): {e}")

    if not isinstance(packet, dict):
        raise ProtocolError("UDP datagram must be a JSON object")

    if "type" not in packet or "user_id" not in packet:
        raise ProtocolError("UDP datagram missing mandatory fields ('type', 'user_id')")

    return packet
