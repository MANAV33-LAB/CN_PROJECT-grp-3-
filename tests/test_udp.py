import time
import socket
import json
import pytest

from backend.app.config import settings
from backend.app.networking.udp_server import UDPServer
from backend.app.networking.protocol import (
    build_udp_packet,
    parse_udp_packet,
    ProtocolError
)
from backend.app.database import engine, Base, SessionLocal
from backend.app.models.user import User
from backend.app.utils.auth import get_password_hash

TEST_UDP_PORT = 9889

@pytest.fixture(scope="module")
def setup_udp_server():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for uid, uname in [(201, "udp_user_1"), (202, "udp_user_2")]:
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

    server = UDPServer(host="127.0.0.1", port=TEST_UDP_PORT)
    server.start()
    time.sleep(0.3)

    yield server

    server.stop()

def test_udp_heartbeat_and_ack(setup_udp_server):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    # Send heartbeat
    packet = build_udp_packet("HEARTBEAT", user_id=201, username="udp_user_1", seq=1)
    sock.sendto(packet, ("127.0.0.1", TEST_UDP_PORT))

    # Await ACK
    resp_data, _ = sock.recvfrom(4096)
    parsed = parse_udp_packet(resp_data)
    assert parsed.get("type") == "HEARTBEAT_ACK"
    assert parsed.get("user_id") == 201

    # Check server registry
    assert setup_udp_server.is_user_online(201) is True
    sock.close()

def test_udp_typing_notification(setup_udp_server):
    sock_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_receiver.settimeout(2.0)

    # Register receiver with heartbeat so server knows its address
    hb = build_udp_packet("HEARTBEAT", user_id=202, username="udp_user_2", seq=1)
    sock_receiver.sendto(hb, ("127.0.0.1", TEST_UDP_PORT))
    sock_receiver.recvfrom(4096) # Read ACK

    # Send typing event from 201 targeting 202
    typing_pkt = build_udp_packet(
        "TYPING",
        user_id=201,
        username="udp_user_1",
        payload={"target_type": "user", "target_id": 202, "is_typing": True}
    )
    sock_sender.sendto(typing_pkt, ("127.0.0.1", TEST_UDP_PORT))

    # Receiver should get typing datagram
    data, _ = sock_receiver.recvfrom(4096)
    notif = parse_udp_packet(data)
    assert notif.get("type") == "TYPING_NOTIFICATION"
    assert notif.get("user_id") == 201
    assert notif.get("payload", {}).get("is_typing") is True

    sock_sender.close()
    sock_receiver.close()

def test_udp_malformed_packets(setup_udp_server):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    initial_dropped = setup_udp_server.dropped_malformed_packets

    # Send non-JSON binary garbage
    sock.sendto(b"\x00\xff\xee\xdd\xcc\xbb", ("127.0.0.1", TEST_UDP_PORT))
    time.sleep(0.2)

    # Send JSON missing mandatory fields
    sock.sendto(json.dumps({"some_random_key": "val"}).encode('utf-8'), ("127.0.0.1", TEST_UDP_PORT))
    time.sleep(0.2)

    assert setup_udp_server.dropped_malformed_packets >= initial_dropped + 2
    # Ensure server did not crash and is still accepting valid packets
    valid_ping = build_udp_packet("PING", user_id=201, username="udp_user_1")
    sock.sendto(valid_ping, ("127.0.0.1", TEST_UDP_PORT))
    sock.settimeout(1.0)
    resp, _ = sock.recvfrom(4096)
    assert b"PONG" in resp

    sock.close()

def test_udp_heartbeat_timeout(setup_udp_server):
    """
    Verifies that if a user stops sending heartbeats, the server detects inactivity
    and marks the user offline.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    hb = build_udp_packet("HEARTBEAT", user_id=201, username="udp_user_1", seq=5)
    sock.sendto(hb, ("127.0.0.1", TEST_UDP_PORT))
    time.sleep(0.2)
    assert setup_udp_server.is_user_online(201) is True

    # Artificially age the heartbeat timestamp in registry to simulate timeout
    with setup_udp_server.lock:
        if 201 in setup_udp_server.online_registry:
            setup_udp_server.online_registry[201]["last_heartbeat"] = time.time() - 20.0

    # Wait for monitor thread tick
    time.sleep(2.5)
    assert setup_udp_server.is_user_online(201) is False
    sock.close()
