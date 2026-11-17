# NetConnect – Multi-Client Chat Application Using TCP and UDP

[![Computer Networks](https://img.shields.io/badge/Course-Computer%20Networks%20Project-blue.svg)](docs/course_project_report.md)
[![Python Sockets](https://img.shields.io/badge/Transport-Native%20TCP%20%26%20UDP-green.svg)](docs/networking_protocol.md)
[![React 18](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite-61dafb.svg)](frontend/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20Gateway-009688.svg)](backend/)
[![Tests](https://img.shields.io/badge/Tests-12%20Passed%20(Pytest)-brightgreen.svg)](tests/)

**NetConnect** is a production-quality, multi-client real-time messaging application engineered to demonstrate foundational Computer Networks and transport-layer socket programming concepts. 

Unlike conventional projects that use third-party libraries (e.g., Socket.IO, Firebase, Supabase), NetConnect uses **raw TCP and UDP sockets implemented via Python's standard `socket` module**:

- **TCP Server (`socket.AF_INET, socket.SOCK_STREAM`) on Port 8888**: Handles connection establishment, 4-byte length-prefixed framing, reliable 1-on-1 private messaging, group multicasting, offline message queuing, and chunked binary file transfers.
- **UDP Server (`socket.AF_INET, socket.SOCK_DGRAM`) on Port 8889**: Handles connectionless datagram processing, periodic heartbeats, real-time presence detection, background inactivity timeout pruning, and lightweight typing indicators.
- **WebSocket Gateway (Port 5001)**: Bridges browser clients to the low-level socket servers.
- **Interactive Protocol Demonstration**: Live in-browser benchmark comparing TCP reliable byte stream vs UDP lossy datagrams.

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph Clients["Clients"]
        W1["Browser Client 1 (Alice)"]
        W2["Browser Client 2 (Bob)"]
        CLI["CLI Terminal Client"]
    end

    subgraph Gateway["Application Layer Gateway"]
        WS["WebSocket Gateway (FastAPI /ws)"]
        REST["REST API Server (Port 5001)"]
    end

    subgraph SocketServers["Low-Level Python Socket Engines"]
        TCP["Custom TCP Server (Port 8888)\n• SOCK_STREAM\n• Length-Prefixed Framing\n• Reliable Messaging & Chunks"]
        UDP["Custom UDP Server (Port 8889)\n• SOCK_DGRAM\n• Periodic Heartbeats\n• Typing Notifications"]
    end

    subgraph Storage["Storage Layer"]
        DB[("SQLite Database\n(SQLAlchemy 2.0)")]
        FS["Uploads Directory\n(uploads/)"]
    end

    W1 <-->|WebSocket| WS
    W2 <-->|WebSocket| WS
    W1 <-->|REST API| REST
    W2 <-->|REST API| REST

    WS <-->|Native TCP Stream| TCP
    WS <-->|Native UDP Datagrams| UDP

    CLI <-->|Raw TCP Socket (8888)| TCP
    CLI <-->|Raw UDP Socket (8889)| UDP

    TCP <--> DB
    UDP <--> DB
    TCP <--> FS
```

---

## Features

### 1. User Authentication & Profile Management
- User registration and secure login.
- Password hashing with **Bcrypt**.
- Session authentication via **JWT (JSON Web Tokens)**.
- User profiles with display names, avatars, bios, and online presence tracking.

### 2. Reliable Private Messaging (TCP)
- Direct 1-on-1 chat with real-time delivery over TCP.
- Message status indicators: **Sent** (single check), **Delivered** (double check), and **Read** (double blue check).
- **Offline Message Queuing**: Messages sent to offline users are stored as `sent` and delivered immediately upon reconnection.

### 3. Multi-Client Group Chat Rooms (TCP)
- Create group rooms, invite members, and join/leave channels.
- Multicast room broadcasts over TCP to all connected members.
- Group member rosters displaying real-time online status.

### 4. Online/Offline Presence via UDP Heartbeats
- Dedicated UDP socket server on Port 8889.
- Clients send lightweight heartbeat datagrams every 3 seconds.
- Background monitor detects inactive clients (timeout = 9 seconds) and marks them offline.
- Handles unexpected disconnects, packet drops, and malformed datagrams gracefully.

### 5. Ephemeral Typing Indicators (UDP)
- Real-time "User is typing..." indicator triggered over UDP.
- Rate-limited and auto-clearing after 3.5 seconds of inactivity.

### 6. Chunked File Transfer (TCP)
- Upload, stream, and download images, PDFs, and documents.
- Files divided into 16 KB chunks over TCP with sequence acknowledgments.
- Progress bar indicator during in-flight file transmission.

### 7. Real-Time Network Monitoring Dashboard
- Displays active TCP connections, UDP online count, total packets, total bytes transferred, and uptime.
- Live scrolling network packet event stream with protocol filter (`ALL`, `TCP`, `UDP`).

### 8. Interactive TCP vs UDP Protocol Demonstration Page
- Educational comparison matrix explaining connection states, reliability, ordering, and header overhead.
- Live benchmark simulation tool firing simultaneous TCP vs UDP packets to visualize RTT, delivery rate, and simulated packet drops.

---

## Project Structure

```
NetConnect/
|-- backend/
|   |-- app/
|   |   |-- config.py                 # Configuration settings (ports, timeouts, keys)
|   |   |-- database.py               # SQLAlchemy database session & engine
|   |   |-- main.py                   # FastAPI app, lifespan hooks, WebSocket route
|   |   |-- models/                   # SQLAlchemy ORM models (User, Message, Group, File, Log)
|   |   |-- routes/                   # REST API endpoints (Auth, Users, Convs, Groups, Files, Network)
|   |   |-- networking/
|   |   |   |-- protocol.py           # 4-byte framing, partial read/write loops, UDP builders
|   |   |   |-- tcp_server.py         # Multi-threaded TCP socket server (Port 8888)
|   |   |   |-- udp_server.py         # Connectionless UDP presence server (Port 8889)
|   |   |   |-- tcp_client.py         # Reusable Python TCP client wrapper
|   |   |   |-- connection_manager.py # Server orchestration singletons
|   |   |   |-- websocket_gateway.py  # Asynchronous WebSocket-to-Socket bridge
|   |   |-- utils/
|   |       |-- auth.py               # Bcrypt password hashing & JWT token tools
|   |-- uploads/                      # Safely stored uploaded files
|   |-- requirements.txt              # Python dependencies
|
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |   |-- Sidebar.jsx           # Channels, direct messages, online indicators
|   |   |   |-- ChatArea.jsx          # Message stream, status checks, file downloads, input
|   |   |   |-- RightPanel.jsx        # User/group details, member list, shared files
|   |   |   |-- NetworkDashboard.jsx  # Live telemetry cards & scrolling packet log
|   |   |   |-- ProtocolDemo.jsx      # Interactive TCP vs UDP benchmark & matrix
|   |   |   |-- SettingsModal.jsx     # Profile edit & audio notification toggle
|   |   |   |-- CreateGroupModal.jsx  # Group room creation with multi-select members
|   |   |-- context/
|   |   |   |-- AuthContext.jsx       # Authentication state provider
|   |   |   |-- SocketContext.jsx     # WebSocket & Audio chime provider
|   |   |-- services/
|   |   |   |-- api.js                # REST API client
|   |   |-- App.jsx                   # Main layout
|   |   |-- main.jsx                  # React DOM mount point
|   |-- package.json                  # Frontend dependencies
|   |-- vite.config.js                # Vite proxy & build configuration
|   |-- tailwind.config.js            # Dark theme Tailwind styling
|
|-- tests/
|   |-- test_auth.py                  # Pytest: Registration, login, JWT validation
|   |-- test_tcp.py                   # Pytest: Socket connect, framing, fragmentation, disconnect
|   |-- test_udp.py                   # Pytest: Heartbeats, timeout detection, malformed packets
|   |-- test_messaging.py             # Pytest: Offline queue, group broadcast, chunked file transfer
|
|-- docs/
|   |-- architecture.md               # Detailed architectural specification & sequence diagrams
|   |-- networking_protocol.md        # Framing specification & protocol deep-dive
|   |-- database_schema.md            # Entity-Relationship diagram & table definitions
|   |-- course_project_report.md      # Formal 18-section academic project report
|
|-- scripts/
|   |-- run_server.py                 # Master server startup script
|   |-- create_test_users.py          # Seeds database with demo accounts & groups
|   |-- simulate_clients.py           # Concurrency test launching 5 simultaneous clients
|   |-- python_tcp_udp_client.py      # Standalone Terminal CLI socket client
|
|-- .env.example                      # Template environment variables
|-- README.md                         # Project documentation
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+ (Tested on Python 3.12)
- Node.js 18+ and npm

### 1. Backend Setup
```bash
# Navigate to project root
cd /path/to/xv6-os-assignment

# Create and activate virtual environment
python3 -m venv backend/venv
source backend/venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Seed database with initial test users
python3 scripts/create_test_users.py
```

### 2. Frontend Setup
```bash
# Navigate to frontend folder
cd frontend

# Install dependencies
npm install

# Test build
npm run build
```

---

## Running the Application

### Step 1: Start the Backend & Socket Servers
In Terminal 1 (from project root):
```bash
./backend/venv/bin/python3 scripts/run_server.py
```
This automatically boots:
- **FastAPI REST API & WebSocket Gateway** on `http://localhost:5001`
- **Low-level TCP Socket Server** on `127.0.0.1:8888`
- **Low-level UDP Socket Server** on `127.0.0.1:8889`
- **Interactive Swagger Documentation** at `http://localhost:5001/docs`

### Step 2: Start the React Frontend
In Terminal 2:
```bash
cd frontend
npm run dev
```
Open your browser at `http://localhost:3000`.

---

## Demo User Credentials

The database comes pre-seeded with 5 demo accounts. You can sign in manually or click the **1-Click Quick Demo Sign-In** buttons on the login page:

| Username | Password | Display Name | Role |
|---|---|---|---|
| `alice` | `password123` | Alice Cooper | Networks TA / Admin |
| `bob` | `password123` | Bob Dylan | Socket Developer |
| `charlie` | `password123` | Charlie Brown | UDP Enthusiast |
| `david` | `password123` | David Bowie | Full-Stack Tester |
| `eva` | `password123` | Eva Green | Network Researcher |

> **Tip for Multi-User Testing**: Open `http://localhost:3000` in a normal browser window (logged in as Alice) and in an Incognito/Private window (logged in as Bob) to observe instant real-time messaging, typing indicators, and UDP presence updates!

---

## Running the Standalone Terminal Socket Client

To test the socket servers directly from the terminal without using the browser:
```bash
./backend/venv/bin/python3 scripts/python_tcp_udp_client.py
```
Type `/msg <user_id> <text>` to send direct TCP messages, `/grp <group_id> <text>` for group broadcasts, or `/typing <user_id>` for UDP typing signals.

---

## Running Automated Tests

NetConnect includes 12 automated unit and integration tests covering socket protocols, framing fragmentation, UDP timeouts, and chunked file transfer:

```bash
# Run full automated pytest suite
./backend/venv/bin/pytest tests/ -v
```

### Run 5-Client Simultaneous Stress Simulation
```bash
./backend/venv/bin/python3 scripts/simulate_clients.py
```
This spawns 5 simultaneous clients transmitting concurrent heartbeats, typing signals, direct messages, and group room messages, verifying zero packet leakage and 100% delivery.

---

## Academic Documentation Links
- [System Architecture & Sequence Diagrams](docs/architecture.md)
- [Networking Protocol & Framing Specification](docs/networking_protocol.md)
- [Database Schema & ER Diagrams](docs/database_schema.md)
- [Complete Formal Course Project Report](docs/course_project_report.md)
