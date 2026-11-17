# NetConnect System Architecture Documentation

NetConnect is a multi-client real-time communication platform built to demonstrate transport-layer and application-layer Computer Networks concepts using Python's standard `socket` module.

---

## 1. High-Level Architectural Overview

NetConnect adheres to a hybrid client-server topology designed to bridge low-level networking primitives with modern web clients:

1. **Web Frontend (React / Vite / Tailwind)**: Delivers an interactive user experience in web browsers. Communicates with the backend via REST API (JSON over HTTP) and a persistent duplex WebSocket connection.
2. **WebSocket Gateway**: Acts as an application-layer proxy bridge. For every connected browser user, the gateway instantiates a dedicated native TCP client socket and a UDP datagram socket, routing browser events into real socket frames.
3. **Dedicated TCP Server (`socket.AF_INET, socket.SOCK_STREAM`)**:
   - Listens on TCP Port `8888`.
   - Handles connection establishment, persistent duplex byte-streams, length-prefixed framing, reliable direct messaging, group multi-casting, offline message queueing, and chunked file transfers.
4. **Dedicated UDP Server (`socket.AF_INET, socket.SOCK_DGRAM`)**:
   - Listens on UDP Port `8889`.
   - Handles connectionless datagram processing, periodic heartbeats, real-time presence detection, timeout pruning, and lightweight typing notifications.
5. **Database Layer (SQLite + SQLAlchemy)**: Persists user identities, conversation metadata, offline message queues, file storage records, and network telemetry logs.

```mermaid
flowchart TD
    subgraph ClientLayer["Client Layer"]
        B1["Browser Client 1 (Alice)"]
        B2["Browser Client 2 (Bob)"]
        CLI["CLI Terminal Client (Charlie)"]
    end

    subgraph GatewayLayer["Application Gateway"]
        WSG["WebSocket Gateway (FastAPI /ws)"]
        REST["REST API Server (Port 5001)"]
    end

    subgraph NetworkEngines["Socket Network Engines (Python Socket)"]
        TCP["Custom TCP Server (Port 8888)\n• Length-Prefixed Framing\n• Reliable Messaging\n• Chunked File Transfer"]
        UDP["Custom UDP Server (Port 8889)\n• Connectionless Datagrams\n• Heartbeat Registry\n• Typing Notifications"]
    end

    subgraph DataStorage["Persistence Layer"]
        DB[("SQLite Database\n(SQLAlchemy ORM)")]
        FS["File Storage Directory\n(backend/uploads/)"]
    end

    B1 <-->|HTTP / WebSockets| WSG
    B2 <-->|HTTP / WebSockets| WSG
    B1 <-->|REST API| REST
    B2 <-->|REST API| REST

    WSG <-->|TCP Socket Stream| TCP
    WSG <-->|UDP Datagrams| UDP

    CLI <-->|Raw TCP Socket (8888)| TCP
    CLI <-->|Raw UDP Socket (8889)| UDP

    TCP <--> DB
    UDP <--> DB
    TCP <--> FS
```

---

## 2. TCP Communication Flow

The TCP Server maintains active socket descriptors in a thread-safe registry (`user_sockets: Dict[int, socket.socket]`). Each client socket runs in a dedicated reader thread.

### Direct Messaging Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Alice as Alice (Client 1)
    participant Server as TCP Server (Port 8888)
    participant Bob as Bob (Client 2)
    participant DB as SQLite DB

    Alice->>Server: TCP 3-Way Handshake (SYN -> SYN-ACK -> ACK)
    Alice->>Server: Frame [AUTH: user_id=1, username="alice"]
    Server-->>Alice: Frame [AUTH_SUCCESS]
    
    Bob->>Server: TCP 3-Way Handshake & Frame [AUTH: user_id=2]
    Server-->>Bob: Frame [AUTH_SUCCESS]

    Note over Alice,Server: Alice sends direct message to Bob
    Alice->>Server: Frame [CHAT_PRIVATE: recipient=2, "Hello Bob!"]
    Server->>DB: Persist Message (status="delivered")
    Server->>Bob: Frame [CHAT_PRIVATE: sender=1, "Hello Bob!"]
    Server-->>Alice: Frame [MSG_STATUS: status="delivered"]

    Note over Bob,Alice: Bob reads message
    Bob->>Server: Frame [MSG_STATUS: message_id=42, status="read"]
    Server->>DB: Update Message (status="read", read_at=now)
    Server-->>Alice: Frame [MSG_STATUS: message_id=42, status="read"]
```

---

## 3. UDP Communication Flow

UDP is connectionless and does not require a 3-way handshake or teardown sequence. Clients periodically send heartbeat datagrams to the UDP server.

```mermaid
sequenceDiagram
    autonumber
    participant Client as Client (Alice)
    participant UDPServer as UDP Server (Port 8889)
    participant Monitor as Background Inactivity Thread
    participant DB as Database

    loop Every 3 Seconds
        Client->>UDPServer: UDP Datagram [HEARTBEAT: user_id=1, seq=N]
        UDPServer->>UDPServer: Update online_registry[user_id] = (addr, timestamp)
        UDPServer-->>Client: UDP Datagram [HEARTBEAT_ACK: seq=N]
    end

    Note over Client,UDPServer: Typing Indicator Broadcast
    Client->>UDPServer: UDP Datagram [TYPING: target_type="user", target_id=2, is_typing=true]
    UDPServer->>UDPServer: Rate-limit and fan out to target
    UDPServer-->>Client: (No ACK required - Best effort delivery)

    Note over Monitor,UDPServer: Client closes or loses connectivity
    loop Every 2 Seconds
        Monitor->>Monitor: Check (now - last_heartbeat) > 9.0 seconds
        Monitor->>UDPServer: Inactivity timeout reached for user_id=1
        UDPServer->>DB: Update User (is_online=false, last_seen=now)
        UDPServer->>UDPServer: Broadcast PRESENCE_CHANGE (offline)
    end
```

---

## 4. Chunked File Transfer Architecture

Files are transferred reliably across TCP by splitting the binary payload into configurable 16 KB chunks:

```mermaid
sequenceDiagram
    autonumber
    participant Sender as Sending Client
    participant Server as TCP Server
    participant Receiver as Receiving Client
    participant Disk as Local Disk (uploads/)

    Sender->>Server: Frame [FILE_START: filename="report.pdf", size=32768, chunks=2]
    Server->>Disk: Allocate unique file descriptor
    Server-->>Sender: Frame [FILE_READY: file_transfer_id="tx_123"]

    Sender->>Server: Frame [FILE_CHUNK: id="tx_123", idx=0, data=<bytes>]
    Server->>Disk: Write Chunk 0 (16,384 bytes)
    Server-->>Sender: Frame [FILE_CHUNK_ACK: idx=0, written=16384]

    Sender->>Server: Frame [FILE_CHUNK: id="tx_123", idx=1, data=<bytes>]
    Server->>Disk: Write Chunk 1 (16,384 bytes)
    Server-->>Sender: Frame [FILE_CHUNK_ACK: idx=1, written=32768]

    Sender->>Server: Frame [FILE_COMPLETE: id="tx_123"]
    Server->>Disk: Flush and close file handle
    Server-->>Sender: Frame [FILE_COMPLETED: file_id=5, status="success"]
    Server->>Receiver: Frame [CHAT_PRIVATE / FILE: file_id=5, name="report.pdf"]
```

---

## 5. Concurrency and Synchronization

- **Socket Concurrency**: Handled with dedicated worker threads per connected TCP client.
- **Shared Registry Protection**: Both `TCPServer` and `UDPServer` utilize `threading.RLock()` to ensure thread-safe read/write operations when routing frames or registering active socket descriptors.
- **Asynchronous WebSocket Pumping**: The FastAPI WebSocket gateway runs asynchronous event loops using Python's `asyncio` and dispatches blocking socket I/O to background executor pools via `loop.run_in_executor()`, ensuring zero event-loop stalls.
