# NetConnect Database Schema Specification

NetConnect utilizes an SQLite relational database managed via the SQLAlchemy 2.0 Object-Relational Mapper (ORM).

---

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    USERS ||--o{ MESSAGES : "sends / receives"
    USERS ||--o{ GROUP_MEMBERS : "joins"
    USERS ||--o{ FILES : "uploads"
    USERS ||--o{ MESSAGE_RECEIPTS : "acknowledges"
    GROUPS ||--o{ GROUP_MEMBERS : "contains"
    GROUPS ||--o{ MESSAGES : "hosts"
    MESSAGES ||--o| FILES : "attaches"
    MESSAGES ||--o{ MESSAGE_RECEIPTS : "tracks"

    USERS {
        int id PK
        string username UK
        string email UK
        string hashed_password
        string display_name
        string avatar_url
        string bio
        boolean is_online
        datetime last_seen
        datetime created_at
    }

    GROUPS {
        int id PK
        string name
        string description
        string avatar_url
        int created_by FK
        datetime created_at
    }

    GROUP_MEMBERS {
        int id PK
        int group_id FK
        int user_id FK
        string role
        datetime joined_at
    }

    MESSAGES {
        int id PK
        string client_msg_id
        int sender_id FK
        int recipient_id FK
        int group_id FK
        text content
        string message_type
        int file_id FK
        string status
        datetime delivered_at
        datetime read_at
        datetime created_at
    }

    FILES {
        int id PK
        string original_name
        string stored_filename UK
        bigint file_size
        string mime_type
        string file_path
        int uploaded_by FK
        datetime created_at
    }

    MESSAGE_RECEIPTS {
        int id PK
        int message_id FK
        int user_id FK
        string status
        datetime timestamp
    }

    NETWORK_LOGS {
        int id PK
        string protocol
        string event_type
        string client_ip
        int client_port
        int user_id
        bigint bytes_transferred
        text details
        datetime timestamp
    }
```

---

## 2. Table Definitions

### Table: `users`
Stores user identities, authentication credentials, and presence metadata.
- `id`: Integer, Primary Key, Auto-increment.
- `username`: String(50), Unique, Indexed, Not Null. Lowercase username.
- `email`: String(100), Unique, Indexed, Not Null.
- `hashed_password`: String(255), Not Null. Passwords hashed using bcrypt.
- `display_name`: String(100), Not Null.
- `avatar_url`: String(255), Nullable.
- `bio`: String(255), Default status bio.
- `is_online`: Boolean, Default `False`.
- `last_seen`: DateTime (UTC).
- `created_at`: DateTime (UTC).

### Table: `groups`
Stores multi-client group chat rooms.
- `id`: Integer, Primary Key.
- `name`: String(100), Not Null.
- `description`: Text, Nullable.
- `avatar_url`: String(255), Nullable.
- `created_by`: Integer, Foreign Key -> `users.id`.
- `created_at`: DateTime (UTC).

### Table: `group_members`
Association table linking users to groups with permission roles.
- `id`: Integer, Primary Key.
- `group_id`: Integer, Foreign Key -> `groups.id` (Cascade on delete).
- `user_id`: Integer, Foreign Key -> `users.id`.
- `role`: String(20), Default `'member'` (`'admin'` or `'member'`).
- `joined_at`: DateTime (UTC).

### Table: `messages`
Stores direct messages and group room messages with status tracking.
- `id`: Integer, Primary Key, Auto-increment.
- `client_msg_id`: String(100), Indexed. Prevents duplication.
- `sender_id`: Integer, Foreign Key -> `users.id`.
- `recipient_id`: Integer, Foreign Key -> `users.id`, Nullable (Null for group chat).
- `group_id`: Integer, Foreign Key -> `groups.id`, Nullable (Null for direct chat).
- `content`: Text, Not Null.
- `message_type`: String(20), Default `'text'` (`'text'`, `'file'`, `'system'`).
- `file_id`: Integer, Foreign Key -> `files.id`, Nullable.
- `status`: String(20), Default `'sent'` (`'sent'`, `'delivered'`, `'read'`).
- `delivered_at`: DateTime (UTC), Nullable.
- `read_at`: DateTime (UTC), Nullable.
- `created_at`: DateTime (UTC), Indexed.

### Table: `files`
Stores metadata for files uploaded or transferred over TCP.
- `id`: Integer, Primary Key.
- `original_name`: String(255), Not Null.
- `stored_filename`: String(255), Unique, Not Null.
- `file_size`: BigInteger (Bytes), Not Null.
- `mime_type`: String(100), Default `'application/octet-stream'`.
- `file_path`: String(500), Not Null.
- `uploaded_by`: Integer, Foreign Key -> `users.id`.
- `created_at`: DateTime (UTC).

### Table: `network_logs`
Stores low-level transport events for auditing and the network monitoring dashboard.
- `id`: Integer, Primary Key.
- `protocol`: String(10), `'TCP'` or `'UDP'`.
- `event_type`: String(50), e.g. `'CONNECT'`, `'DISCONNECT'`, `'MSG_RELAY'`, `'HEARTBEAT'`, `'TIMEOUT'`, `'FILE_CHUNK'`.
- `client_ip`: String(50), Nullable.
- `client_port`: Integer, Nullable.
- `user_id`: Integer, Nullable.
- `bytes_transferred`: BigInteger, Default 0.
- `details`: Text, Nullable.
- `timestamp`: DateTime (UTC), Indexed.
