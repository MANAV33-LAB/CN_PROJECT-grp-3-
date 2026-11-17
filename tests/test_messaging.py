import os
import time
import tempfile
import pytest

from backend.app.config import settings
from backend.app.networking.tcp_server import TCPServer
from backend.app.networking.tcp_client import TCPClient
from backend.app.database import engine, Base, SessionLocal
from backend.app.models.user import User
from backend.app.models.group import Group, GroupMember
from backend.app.models.message import Message
from backend.app.utils.auth import get_password_hash

INTEG_PORT = 9890

@pytest.fixture(scope="module")
def setup_environment():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    u1 = db.query(User).filter(User.username == "integ_alice").first()
    if not u1:
        u1 = User(id=301, username="integ_alice", email="alice@integ.local",
                  hashed_password=get_password_hash("pass123"), display_name="Alice")
        db.add(u1)
        db.commit()
        db.refresh(u1)

    u2 = db.query(User).filter(User.username == "integ_bob").first()
    if not u2:
        u2 = User(id=302, username="integ_bob", email="bob@integ.local",
                  hashed_password=get_password_hash("pass123"), display_name="Bob")
        db.add(u2)
        db.commit()
        db.refresh(u2)

    # Create test group
    grp = db.query(Group).filter(Group.name == "IntegGroup").first()
    if not grp:
        grp = Group(name="IntegGroup", description="Test Group", created_by=u1.id)
        db.add(grp)
        db.commit()
        db.refresh(grp)

    for uid in [u1.id, u2.id]:
        if not db.query(GroupMember).filter(GroupMember.group_id == grp.id, GroupMember.user_id == uid).first():
            db.add(GroupMember(group_id=grp.id, user_id=uid, role="admin" if uid == u1.id else "member"))
    db.commit()

    grp_id = grp.id
    db.close()

    server = TCPServer(host="127.0.0.1", port=INTEG_PORT)
    server.start()
    time.sleep(0.5)

    yield {"server": server, "group_id": grp_id}

    server.stop()

def test_offline_message_queue_and_delivery(setup_environment):
    """
    Test sending a message to an offline recipient, verifying it is stored,
    and then delivered immediately when the recipient connects.
    """
    alice = TCPClient(host="127.0.0.1", port=INTEG_PORT)
    assert alice.authenticate(user_id=301, username="integ_alice") is True

    # Bob is currently offline. Alice sends a message to Bob.
    ack = alice.send_private_message(recipient_id=302, content="Are you there Bob?")
    assert ack.get("type") == "MSG_STATUS"
    assert ack.get("status") == "sent" # Marked 'sent' because recipient was offline

    # Now Bob connects and authenticates
    bob = TCPClient(host="127.0.0.1", port=INTEG_PORT)
    assert bob.authenticate(user_id=302, username="integ_bob") is True

    # Bob should receive the queued offline message
    delivered_msg, _ = bob.receive_message(timeout=2.0)
    assert delivered_msg is not None
    assert delivered_msg.get("type") == "CHAT_PRIVATE"
    assert delivered_msg.get("content") == "Are you there Bob?"
    assert delivered_msg.get("sender_id") == 301
    assert delivered_msg.get("is_offline_delivery") is True

    alice.close()
    bob.close()

def test_group_broadcast_messaging(setup_environment):
    grp_id = setup_environment["group_id"]
    alice = TCPClient(host="127.0.0.1", port=INTEG_PORT)
    bob = TCPClient(host="127.0.0.1", port=INTEG_PORT)

    assert alice.authenticate(user_id=301, username="integ_alice") is True
    assert bob.authenticate(user_id=302, username="integ_bob") is True

    # Alice sends message to group
    ack = alice.send_group_message(group_id=grp_id, content="Hello group members!")
    assert ack.get("type") == "MSG_STATUS"
    assert ack.get("status") == "sent"

    # Bob receives the group message
    grp_msg, _ = bob.receive_message(timeout=2.0)
    assert grp_msg is not None
    assert grp_msg.get("type") == "CHAT_GROUP"
    assert grp_msg.get("group_id") == grp_id
    assert grp_msg.get("sender_id") == 301
    assert grp_msg.get("content") == "Hello group members!"

    alice.close()
    bob.close()

def test_tcp_chunked_file_transfer(setup_environment):
    """
    Tests transferring a binary file chunk-by-chunk over TCP socket.
    """
    alice = TCPClient(host="127.0.0.1", port=INTEG_PORT)
    bob = TCPClient(host="127.0.0.1", port=INTEG_PORT)

    assert alice.authenticate(user_id=301, username="integ_alice") is True
    assert bob.authenticate(user_id=302, username="integ_bob") is True

    # Create dummy test file (e.g. 16 KB of test bytes)
    test_content = b"NetConnect-TCP-Chunked-Test-Data" * 512
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        tmp.write(test_content)
        tmp_path = tmp.name

    try:
        res = alice.send_file(file_path=tmp_path, recipient_id=302, chunk_size=4096)
        assert res.get("type") == "FILE_COMPLETED"
        assert res.get("file", {}).get("file_size") == len(test_content)

        # Bob receives incoming file notification message
        incoming_file_msg, _ = bob.receive_message(timeout=2.0)
        assert incoming_file_msg is not None
        assert incoming_file_msg.get("message_type") == "file"
        assert incoming_file_msg.get("file", {}).get("file_size") == len(test_content)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        alice.close()
        bob.close()
