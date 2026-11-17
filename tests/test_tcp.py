import time
import socket
import struct
import pytest
import threading

from backend.app.config import settings
from backend.app.networking.tcp_server import TCPServer
from backend.app.networking.tcp_client import TCPClient
from backend.app.networking.protocol import (
    send_framed_message,
    recv_framed_message,
    HEADER_FORMAT,
    HEADER_SIZE
)
from backend.app.database import engine, Base, SessionLocal
from backend.app.models.user import User
from backend.app.utils.auth import get_password_hash

TEST_TCP_PORT = 9888

@pytest.fixture(scope="module")
def setup_server():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Create test users if needed
    for uid, uname in [(101, "tcp_user_1"), (102, "tcp_user_2"), (103, "tcp_user_3")]:
        if not db.query(User).filter(User.id == uid).first():
            db.add(User(
                id=uid,
                username=uname,
                email=f"{uname}@test.local",
                hashed_password=get_password_hash("pass123"),
                display_name=uname.upper()
            ))
    db.commit()
    db.close()

    server = TCPServer(host="127.0.0.1", port=TEST_TCP_PORT)
    server.start()
    time.sleep(0.5)

    yield server

    server.stop()

def test_tcp_connect_and_auth(setup_server):
    client = TCPClient(host="127.0.0.1", port=TEST_TCP_PORT)
    assert client.connect() is True
    assert client.authenticate(user_id=101, username="tcp_user_1") is True
    client.close()

def test_tcp_multi_client_direct_messaging(setup_server):
    client1 = TCPClient(host="127.0.0.1", port=TEST_TCP_PORT)
    client2 = TCPClient(host="127.0.0.1", port=TEST_TCP_PORT)

    assert client1.authenticate(user_id=101, username="tcp_user_1") is True
    assert client2.authenticate(user_id=102, username="tcp_user_2") is True

    # Client 1 sends to Client 2
    ack = client1.send_private_message(recipient_id=102, content="Hello from TCP Client 1!")
    assert ack.get("type") == "MSG_STATUS"
    assert ack.get("status") == "delivered"

    # Client 2 receives the message
    msg, _ = client2.receive_message(timeout=2.0)
    assert msg is not None
    assert msg.get("type") == "CHAT_PRIVATE"
    assert msg.get("sender_id") == 101
    assert msg.get("content") == "Hello from TCP Client 1!"

    client1.close()
    client2.close()

def test_tcp_framing_partial_reads_and_writes(setup_server):
    """
    Verifies that the framing protocol correctly handles fragmented byte streams
    where header and body are transmitted in partial chunks.
    """
    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_sock.connect(("127.0.0.1", TEST_TCP_PORT))

    import json
    msg_dict = {"type": "PING", "seq": 42, "payload": "fragmentation_test"}
    body_bytes = json.dumps(msg_dict).encode('utf-8')
    header_bytes = struct.pack(HEADER_FORMAT, len(body_bytes))
    full_packet = header_bytes + body_bytes

    # Send 1 byte at a time with tiny delays to simulate severe fragmentation
    for i in range(len(full_packet)):
        raw_sock.send(full_packet[i:i+1])
        time.sleep(0.002)

    # Server should successfully receive, reassemble, and respond with PONG
    reply, _ = recv_framed_message(raw_sock)
    assert isinstance(reply, dict)
    assert reply.get("type") == "PONG"

    raw_sock.close()

def test_tcp_disconnect_handling(setup_server):
    client = TCPClient(host="127.0.0.1", port=TEST_TCP_PORT)
    assert client.authenticate(user_id=103, username="tcp_user_3") is True
    assert 103 in setup_server.user_sockets

    client.close()
    time.sleep(0.3)
    assert 103 not in setup_server.user_sockets
