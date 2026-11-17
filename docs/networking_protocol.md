# NetConnect Networking Protocol Specification

This document provides a formal specification of the application-layer network protocol engineered for **NetConnect**, operating over native Python TCP (`SOCK_STREAM`) and UDP (`SOCK_DGRAM`) sockets.

---

## 1. Transport Layer Selection Rationale

### Why TCP for Chat Messaging and File Transfers?
1. **Connection-Oriented Byte Stream**: TCP guarantees reliable in-order byte delivery. In a chat application, losing messages or receiving words out of order is unacceptable.
2. **Error Detection & Retransmission (ARQ)**: TCP computes checksums and requires cumulative ACKs. If a packet is corrupted or dropped by router queue overflow, TCP automatically retransmits the missing segment.
3. **Flow Control & Congestion Avoidance**: TCP's sliding window prevents sender buffer overruns, while algorithms like TCP Reno/Cubic prevent network congestion collapse during large file transfers.

### Why UDP for Heartbeats and Typing Indicators?
1. **Zero Connection Setup Overhead**: UDP does not require a 3-way handshake (`SYN` -> `SYN-ACK` -> `ACK`), allowing instant datagram delivery with minimum latency.
2. **No Head-of-Line Blocking**: Heartbeats and typing notices are transient states. If a heartbeat packet is lost in transit, retransmitting an obsolete heartbeat is counterproductive; the client will simply send the next fresh heartbeat 3 seconds later.
3. **Minimal Header Overhead**: UDP headers are fixed at 8 bytes (compared to TCP's 20–60 bytes), conserving network bandwidth.

---

## 2. TCP Message Framing Protocol

TCP is a stream-oriented protocol without inherent message boundaries; `socket.recv(1024)` may return a partial message, an entire message, or multiple merged messages (fragmentation and coalescing).

To guarantee strict message demarcation, NetConnect implements **4-Byte Length-Prefixed Framing**.

### Frame Structure

```
+---------------------------+-----------------------------------------------+
|  Payload Length (4 Bytes) |         Application Payload (JSON / Binary)   |
|     Big-Endian ('>I')     |              Variable Length (N Bytes)        |
+---------------------------+-----------------------------------------------+
| 0x00 | 0x00 | 0x01 | 0x2A | {"type": "CHAT_PRIVATE", "content": "Hi"} ... |
+---------------------------+-----------------------------------------------+
```

1. **Header**: Exactly 4 bytes (`struct.pack('>I', payload_length)`), representing an unsigned 32-bit integer in Big-Endian network byte order.
2. **Payload**: UTF-8 encoded JSON string (or raw chunked bytes) of length $N$.
3. **Safety Limit**: Maximum message length is enforced at `64 MB` to protect against denial-of-service memory exhaustion.

### Handling Partial Reads and Writes

The protocol implements reusable loops to ensure all bytes are fully sent and received:

```python
def send_all(sock, data: bytes) -> int:
    total_sent = 0
    while total_sent < len(data):
        sent = sock.send(data[total_sent:])
        if sent == 0:
            raise ConnectionClosedError("Socket closed during send")
        total_sent += sent
    return total_sent

def recv_exact(sock, num_bytes: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < num_bytes:
        chunk = sock.recv(num_bytes - len(buffer))
        if not chunk:
            raise ConnectionClosedError("Connection closed before all bytes received")
        buffer.extend(chunk)
    return bytes(buffer)
```

---

## 3. TCP Protocol Message Types

| Message Type | Direction | Payload Fields | Description |
|---|---|---|---|
| `AUTH` | Client -> Server | `user_id`, `username` | Registers and associates socket with user ID |
| `AUTH_SUCCESS` | Server -> Client | `user_id`, `username`, `message` | Acknowledges socket authentication |
| `CHAT_PRIVATE` | Bi-directional | `recipient_id`, `content`, `client_msg_id` | Direct 1-to-1 message |
| `CHAT_GROUP` | Bi-directional | `group_id`, `content`, `client_msg_id` | Room broadcast message |
| `MSG_STATUS` | Bi-directional | `message_id`, `status` (`sent`/`delivered`/`read`) | Delivery status acknowledgment |
| `FILE_START` | Client -> Server | `filename`, `file_size`, `total_chunks` | Initiates chunked file transfer |
| `FILE_CHUNK` | Client -> Server | `chunk_index`, `data` (base64) | Transmits a 16KB binary chunk |
| `FILE_COMPLETE` | Client -> Server | `file_transfer_id` | Finalizes file and triggers routing |
| `PING` / `PONG` | Bi-directional | `seq`, `timestamp` | Keep-alive and latency measurement |
| `CLOSE` | Client -> Server | — | Graceful connection termination request |

---

## 4. UDP Presence & Datagram Format

UDP packets are transmitted as compact JSON objects serialized into UTF-8 bytes:

```json
{
  "type": "HEARTBEAT",
  "user_id": 101,
  "username": "alice",
  "seq": 42,
  "timestamp": 1794932850.123,
  "payload": {
    "status": "active"
  }
}
```

### Inactivity State Machine
- **Heartbeat Interval**: Clients transmit a `HEARTBEAT` datagram every `3 seconds`.
- **Server Response**: Server updates `online_registry[user_id]` with timestamp and replies with `HEARTBEAT_ACK`.
- **Timeout Threshold**: A background monitor scans active users every `2 seconds`. If `current_time - last_heartbeat > 9.0 seconds` (3 missed heartbeats), the user is transitioned to `offline` and a `PRESENCE_CHANGE` event is broadcast.

---

## 5. Security & Packet Sanitation

- **No Passwords or Secrets in UDP**: UDP datagrams are unencrypted and subject to network eavesdropping; sensitive credentials and JWT secrets are strictly prohibited from UDP payloads.
- **Malformed Packet Rejection**: The UDP server wraps datagram parsing in exception blocks. Corrupted JSON, truncated datagrams, or missing protocol fields are safely discarded and tallied in `dropped_malformed_packets` without disrupting the server thread.
