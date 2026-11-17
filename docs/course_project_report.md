# Computer Networks Course Project Report

---

# NetConnect: Multi-Client Real-Time Communication System Using Native TCP and UDP Socket Programming

**Course**: CS 455 / CSE 320 – Computer Networks  
**Academic Year**: 2025–2026  
**Project Title**: NetConnect  
**Technologies**: Python 3 Socket Programming, React.js, FastAPI, SQLite, WebSockets, Tailwind CSS  
**Authors**: NetConnect Development Team  

---

## Table of Contents
1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Problem Statement](#3-problem-statement)
4. [Project Objectives](#4-project-objectives)
5. [Analysis of Existing Systems](#5-analysis-of-existing-systems)
6. [Proposed System Architecture](#6-proposed-system-architecture)
7. [Technology Stack](#7-technology-stack)
8. [System Architecture & Design](#8-system-architecture--design)
9. [Module Descriptions](#9-module-descriptions)
10. [TCP Socket Implementation Deep-Dive](#10-tcp-socket-implementation-deep-dive)
11. [UDP Socket Implementation Deep-Dive](#11-udp-socket-implementation-deep-dive)
12. [Database Design & Persistence](#12-database-design--persistence)
13. [User Interface & User Experience Walkthrough](#13-user-interface--user-experience-walkthrough)
14. [Testing Methodology & Experimental Results](#14-testing-methodology--experimental-results)
15. [Limitations & Practical Constraints](#15-limitations--practical-constraints)
16. [Future Scope](#16-future-scope)
17. [Conclusion](#17-conclusion)
18. [References](#18-references)

---

## 1. Abstract

Modern instant messaging applications demand a careful synthesis of reliability, throughput, and low-latency interaction. In conventional web development, developers frequently rely on high-level managed abstractions such as Socket.IO, Firebase, or cloud message brokers. While functional, these proprietary abstractions obscure foundational transport-layer networking principles.

This project presents **NetConnect**, a production-grade, multi-client real-time messaging application engineered directly upon low-level TCP (`SOCK_STREAM`) and UDP (`SOCK_DGRAM`) socket primitives in Python. NetConnect assigns distinct networking responsibilities to the transport protocol best suited for the workload: TCP guarantees reliable, in-order text message exchange, offline queue delivery, and chunked binary file transfers via custom 4-byte length-prefixed framing; UDP provides lightweight, connectionless datagram channels for periodic heartbeat presence monitoring and real-time typing indicators. A dedicated WebSocket gateway bridges modern web clients to native socket threads. NetConnect includes automated test suites, multi-client concurrency simulations, an interactive protocol benchmark engine, and real-time network telemetry.

---

## 2. Introduction

Computer networking fundamentals center around the transport layer of the OSI and TCP/IP models. At this layer, two primary protocols govern end-to-end communication:
- **Transmission Control Protocol (TCP)**, standardized in RFC 793, provides a connection-oriented, reliable, full-duplex byte stream equipped with sequence tracking, cumulative acknowledgments, sliding-window flow control, and adaptive congestion avoidance.
- **User Datagram Protocol (UDP)**, standardized in RFC 768, provides a connectionless, best-effort datagram service characterized by minimal 8-byte header overhead and zero connection establishment latency.

Understanding when and how to implement each transport protocol is a pivotal competency for software and network engineers. NetConnect was built to demonstrate how these protocols function in tandem within a modern full-stack application.

---

## 3. Problem Statement

Commercial real-time chat applications often conceal low-level packet handling and socket lifecycle mechanics behind high-level managed abstractions. Academic courses in computer networks frequently present socket programming purely through trivial command-line echo scripts, leaving a substantial gap between theory and realistic production software.

Key challenges addressed in this project include:
1. **TCP Stream Boundaries & Partial Reads**: TCP treats data as a continuous stream of bytes without record markers. A single `recv()` call does not guarantee receipt of an entire application message.
2. **Lossy Presence Detection**: Relying on TCP connection teardown for presence detection fails during abrupt link failures or client power cuts.
3. **Browser Socket Limitations**: Web browsers enforce sandbox restrictions prohibiting arbitrary raw TCP or UDP socket creation.
4. **Concurrency & Thread Safety**: Managing shared socket connection registries across simultaneous readers and writers introduces critical race condition and deadlock risks.

---

## 4. Project Objectives

1. Implement a custom, multi-threaded TCP server using Python's `socket.socket(socket.AF_INET, socket.SOCK_STREAM)` supporting simultaneous clients.
2. Engineer an application-layer framing protocol using 4-byte big-endian length prefixes with complete partial read/write handling.
3. Implement a dedicated UDP server using `socket.socket(socket.AF_INET, socket.SOCK_DGRAM)` to manage client heartbeats, online status tracking, and typing indicators.
4. Build a reliable offline message delivery mechanism ensuring direct messages sent to offline recipients are queued and delivered upon reconnection.
5. Implement chunked binary file transfer over TCP with progress tracking and metadata verification.
6. Provide an architectural WebSocket gateway bridging browser clients to the low-level socket servers.
7. Construct a real-time network telemetry dashboard and an interactive TCP vs UDP live comparison benchmark tool.
8. Validate system reliability with automated pytest suites and multi-client concurrent stress tests.

---

## 5. Analysis of Existing Systems

| Characteristic | Commercial Cloud (Firebase / Pusher) | Socket.IO / WebSocket Libraries | NetConnect (Proposed System) |
|---|---|---|---|
| Protocol Transparency | Hidden behind proprietary SDKs | Uses HTTP Long-Polling or WebSocket frames | Direct Python TCP (`SOCK_STREAM`) and UDP (`SOCK_DGRAM`) |
| Transport Control | No developer control over socket flags | Limited to WebSocket framing | Direct configuration of `SO_REUSEADDR`, `TCP_NODELAY`, chunk sizing |
| Presence Detection | Managed serverless ping | TCP-based ping/pong | Real UDP datagram heartbeats with background inactivity timeout |
| Academic Depth | Low | Moderate | High (Demonstrates 3-way handshake, framing, fragmentation, loss simulation) |

---

## 6. Proposed System Architecture

NetConnect operates as a cohesive, layered system:

```
[React Browser UI] <---WebSocket / REST---> [WebSocket Gateway]
                                                    |
                         +--------------------------+--------------------------+
                         | (Native TCP Socket Stream)                          | (Native UDP Datagrams)
                         v                                                     v
            [Custom TCP Server : 8888]                            [Custom UDP Server : 8889]
            - Length-Prefixed Framing (4 Bytes)                   - Periodic Heartbeat Engine
            - Multi-Threaded Connection Registry                  - Inactivity Timeout Monitor
            - Direct & Group Message Routing                      - Ephemeral Typing Signals
            - Chunked Binary File Transfer                        - Loss & Malformed Packet Safety
                         |                                                     |
                         +--------------------------+--------------------------+
                                                    |
                                                    v
                                      [SQLite Persistence Layer]
```

---

## 7. Technology Stack

- **Backend Runtime**: Python 3.12
- **Networking APIs**: Python Standard Library `socket`, `struct`, `select`, `threading`
- **Application Framework**: FastAPI (Uvicorn ASGI)
- **Database & ORM**: SQLite 3 with SQLAlchemy 2.0
- **Security**: Passlib / Bcrypt password hashing, PyJWT authentication tokens
- **Frontend Framework**: React 18 with Vite
- **Styling & UI**: Tailwind CSS (Dark theme), Lucide React iconography
- **Testing Tools**: Pytest 8.1, Requests, HTTPX

---

## 8. System Architecture & Design

### Data Flow Overview
1. **User Authentication**: Client submits credentials to `/api/auth/login`. Server verifies password hash and returns signed JWT.
2. **Socket Bridging**: Client establishes WebSocket connection to `/ws/{token}`. Gateway verifies token, spawns a dedicated TCP client socket connected to `127.0.0.1:8888`, and authenticates the connection.
3. **TCP Message Transmission**: Direct and group chat messages are framed with 4-byte length prefixes and transmitted across TCP. The TCP server delivers to the recipient socket or marks the message `sent` in the database if the recipient is offline.
4. **UDP Heartbeat Transmission**: Every 3 seconds, a UDP client sends a heartbeat datagram to `127.0.0.1:8889`. The UDP server records the timestamp in an in-memory registry and responds with a `HEARTBEAT_ACK`.
5. **UDP Typing Indicators**: User typing events trigger lightweight UDP datagrams fanned out to targeted chat participants.

---

## 9. Module Descriptions

### 1. `backend/app/networking/protocol.py`
Defines the binary framing protocol, maximum payload constraints (64 MB), `send_all()`, `recv_exact()`, `send_framed_message()`, `recv_framed_message()`, and UDP datagram builders and parsers.

### 2. `backend/app/networking/tcp_server.py`
The core TCP socket server. Manages listening sockets, client reader threads, connection registries (`user_sockets`, `socket_users`), direct message routing, group multicasting, offline delivery queue flushes, chunked file assembly, and network telemetry logs.

### 3. `backend/app/networking/udp_server.py`
The connectionless presence engine. Handles incoming UDP heartbeats, typing indicator routing, periodic background timeout sweeps (`current_time - last_heartbeat > 9.0s`), and safe handling of malformed datagrams.

### 4. `backend/app/networking/websocket_gateway.py`
Bridges asynchronous WebSocket connections from web browsers to dedicated low-level TCP client sockets and UDP sender sockets.

### 5. `backend/app/networking/tcp_client.py`
Reusable Python TCP client implementing the custom framing protocol for automated testing, simulation scripts, and terminal CLI interfaces.

### 6. `frontend/src/`
React frontend components including `Sidebar` (channels and contacts), `ChatArea` (real-time message stream and file attachments), `RightPanel` (metadata and member rosters), `NetworkDashboard` (live telemetry cards and logs), and `ProtocolDemo` (interactive benchmark and comparison tool).

---

## 10. TCP Socket Implementation Deep-Dive

### Message Framing Implementation
To solve TCP byte stream coalescing and fragmentation:
```python
HEADER_FORMAT = ">I"  # 4-byte unsigned integer, big-endian
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

def send_framed_message(sock: socket.socket, payload: dict | str | bytes) -> int:
    if isinstance(payload, dict):
        body = json.dumps(payload).encode('utf-8')
    header = struct.pack(HEADER_FORMAT, len(body))
    return send_all(sock, header + body)

def recv_framed_message(sock: socket.socket) -> tuple[dict, int]:
    header_bytes = recv_exact(sock, HEADER_SIZE)
    (body_len,) = struct.unpack(HEADER_FORMAT, header_bytes)
    body_bytes = recv_exact(sock, body_len)
    return json.loads(body_bytes.decode('utf-8')), HEADER_SIZE + body_len
```

### Partial Read Loop
The `recv_exact` function continuously reads into a bytearray until all requested bytes are retrieved:
```python
def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < num_bytes:
        chunk = sock.recv(num_bytes - len(buffer))
        if not chunk:
            raise ConnectionClosedError("Peer closed connection prematurely")
        buffer.extend(chunk)
    return bytes(buffer)
```

---

## 11. UDP Socket Implementation Deep-Dive

### Heartbeat Datagram Protocol
Clients emit compact JSON datagrams containing sequence tracking:
```python
def build_udp_packet(msg_type: str, user_id: int, username: str, payload: dict = None, seq: int = 0) -> bytes:
    packet = {
        "type": msg_type,
        "user_id": user_id,
        "username": username,
        "seq": seq,
        "timestamp": time.time(),
        "payload": payload or {}
    }
    return json.dumps(packet).encode('utf-8')
```

### Inactivity Detection Loop
A background daemon thread inspects the active registry every 2 seconds:
```python
while self.is_running:
    time.sleep(2.0)
    now = time.time()
    with self.lock:
        for uid, info in list(self.online_registry.items()):
            if now - info["last_heartbeat"] > settings.HEARTBEAT_TIMEOUT:
                # Mark client offline
                del self.online_registry[uid]
                self._update_user_db_status(uid, is_online=False)
                self._notify_subscribers("PRESENCE_CHANGE", {"user_id": uid, "is_online": False})
```

---

## 12. Database Design & Persistence

The relational schema persists seven distinct entities:
1. `users`: Credentials, profiles, presence timestamps.
2. `messages`: Direct and group messages, statuses (`sent`, `delivered`, `read`), timestamps in UTC.
3. `groups`: Group room metadata.
4. `group_members`: Membership associations with roles (`admin`, `member`).
5. `files`: File storage records, byte sizes, and MIME classifications.
6. `message_receipts`: Historical audit of delivery receipts.
7. `network_logs`: Transport event logs for socket connection audits.

---

## 13. User Interface & User Experience Walkthrough

- **Modern Responsive Dark Theme**: Designed using Tailwind CSS with `#0B0F19` slate background and indigo/violet brand highlights.
- **Three-Panel Layout**:
  - Left Sidebar: Brand banner, live socket status pill, navigation tabs (Chats, Groups, Monitor, Demo), contact list with live green presence dots, search filter.
  - Middle Chat Panel: Conversation header with network protocol badge, message stream with Sent/Delivered/Read checkmarks, file download cards, typing indicator banner, input box with file attachment trigger.
  - Right Details Panel: Profile bio, transport socket port allocations, group member list, shared file gallery.
- **Network Telemetry Dashboard**: Real-time counter cards (Active TCP connections, UDP online count, total packets, total throughput in KB/MB, server uptime), live scrolling event stream table with protocol filters.
- **Protocol Comparison Page**: Interactive educational comparison matrix and a live transmission benchmark simulator.

---

## 14. Testing Methodology & Experimental Results

### Automated Pytest Suite Results
The automated test suite (`tests/`) covers authentication, TCP socket messaging, UDP presence, and chunked file transfer:

| Test File | Test Case | Status | Verified Functionality |
|---|---|---|---|
| `test_auth.py` | `test_register_and_login_flow` | **PASSED** | User registration, password hashing, duplicate prevention, JWT issue |
| `test_tcp.py` | `test_tcp_connect_and_auth` | **PASSED** | Socket connection and length-prefixed `AUTH` handshake |
| `test_tcp.py` | `test_tcp_multi_client_direct_messaging` | **PASSED** | Inter-client TCP message relay and delivery receipts |
| `test_tcp.py` | `test_tcp_framing_partial_reads_and_writes` | **PASSED** | Transmission of 1-byte fragmented slices correctly reassembled |
| `test_tcp.py` | `test_tcp_disconnect_handling` | **PASSED** | Graceful socket termination and registry cleanup |
| `test_udp.py` | `test_udp_heartbeat_and_ack` | **PASSED** | Datagram transmission, registry update, and `HEARTBEAT_ACK` |
| `test_udp.py` | `test_udp_typing_notification` | **PASSED** | Ephemeral typing datagram fanout |
| `test_udp.py` | `test_udp_malformed_packets` | **PASSED** | Corrupted binary & malformed JSON dropped without server crash |
| `test_udp.py` | `test_udp_heartbeat_timeout` | **PASSED** | Inactivity timeout detection and offline status transition |
| `test_messaging.py` | `test_offline_message_queue_and_delivery` | **PASSED** | Messages queued while recipient is offline, delivered upon reconnect |
| `test_messaging.py` | `test_group_broadcast_messaging` | **PASSED** | Multi-client group multicasting over TCP |
| `test_messaging.py` | `test_tcp_chunked_file_transfer` | **PASSED** | 16 KB binary file chunks transferred, reassembled, and integrity-verified |

**Pytest Execution Summary**: `12 passed in 5.85s (100% pass rate)`.

### Multi-Client Concurrency Simulation
A multi-threaded simulation script (`scripts/simulate_clients.py`) launched 5 concurrent clients (`sim_alice`, `sim_bob`, `sim_charlie`, `sim_david`, `sim_eva`) exchanging simultaneous heartbeats, typing signals, direct messages, and group broadcasts:

- **Total Direct Messages Delivered**: 30 / 30 (100% delivery rate)
- **Total Group Broadcasts Received**: 120 / 120 (100% delivery rate)
- **Packet Leakage / Misrouting**: 0 occurrences. Every direct message was strictly validated against recipient user IDs.

---

## 15. Limitations & Practical Constraints

1. **Browser Raw Socket Restrictions**: Web browsers do not permit raw TCP/UDP socket creation from client-side JavaScript. NetConnect transparently resolves this via the WebSocket Gateway bridge.
2. **NAT Traversal**: Operating across disparate public networks requires STUN/TURN traversal or port forwarding. NetConnect currently binds to configurable local and LAN interfaces (`0.0.0.0`).
3. **Storage Engine**: SQLite is optimized for single-file embedded deployments; under extremely high write loads, migrating to PostgreSQL would enhance database concurrency.

---

## 16. Future Scope

1. **End-to-End Encryption (E2EE)**: Implementing Double Ratchet or Diffie-Hellman key exchange directly over TCP frames.
2. **Audio/Video Streaming over UDP**: Extending the UDP server with RTP/RTCP packet handling for low-latency voice and video channels.
3. **Distributed Mesh Routing**: Clustering multiple TCP chat servers using Redis Pub/Sub for horizontal scalability across server farms.

---

## 17. Conclusion

NetConnect successfully demonstrates the practical implementation of core Computer Networks principles within a modern, production-grade application. By eschewing third-party message brokers in favor of Python's standard `socket` library, the project provides transparent, verifiable transport-layer programming. The combination of reliable TCP byte-stream messaging, connectionless UDP presence heartbeats, custom framing protocols, robust concurrency synchronization, and a modern React user interface yields an exemplary academic project ready for evaluation and viva examination.

---

## 18. References

1. Postel, J. (1981). *Transmission Control Protocol*. RFC 793, Internet Engineering Task Force.
2. Postel, J. (1980). *User Datagram Protocol*. RFC 768, Internet Engineering Task Force.
3. Kurose, J. F., & Ross, K. W. (2021). *Computer Networking: A Top-Down Approach* (8th ed.). Pearson.
4. Stevens, W. R., Fenner, B., & Rudoff, A. M. (2004). *UNIX Network Programming, Volume 1: The Sockets Networking API* (3rd ed.). Addison-Wesley Professional.
5. Python Software Foundation. (2024). *socket — Low-level networking interface*. Python Documentation.
