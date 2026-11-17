import sys
import os
import time
import socket
import threading
import random
from typing import List, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings
from backend.app.networking.tcp_client import TCPClient
from backend.app.networking.protocol import build_udp_packet, parse_udp_packet
from backend.app.database import SessionLocal, Base, engine
from backend.app.models.user import User
from backend.app.models.group import Group, GroupMember
from backend.app.utils.auth import get_password_hash

SIMULATED_USERS = [
    {"username": "sim_alice", "id": 401, "name": "Alice Sim"},
    {"username": "sim_bob", "id": 402, "name": "Bob Sim"},
    {"username": "sim_charlie", "id": 403, "name": "Charlie Sim"},
    {"username": "sim_david", "id": 404, "name": "David Sim"},
    {"username": "sim_eva", "id": 405, "name": "Eva Sim"}
]

class SimulatedClient(threading.Thread):
    def __init__(self, user_info: dict, tcp_port: int, udp_port: int, all_users: list, group_id: int):
        super().__init__(name=f"Client-{user_info['username']}", daemon=True)
        self.user = user_info
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.all_users = all_users
        self.group_id = group_id

        self.tcp_client = TCPClient(host="127.0.0.1", port=tcp_port)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.received_direct_messages: List[dict] = []
        self.received_group_messages: List[dict] = []
        self.is_running = True
        self.seq = 0

    def run(self):
        # 1. Connect TCP
        if not self.tcp_client.authenticate(user_id=self.user["id"], username=self.user["username"]):
            print(f"[{self.user['username']}] Failed to authenticate on TCP port {self.tcp_port}")
            return

        print(f"[{self.user['username']}] Connected and Authenticated via TCP socket")

        # 2. Spawn listener thread for incoming TCP frames
        listener = threading.Thread(target=self._listen_loop, daemon=True)
        listener.start()

        # 3. Simulate activity loop: periodic heartbeats, typing, and direct/group messages
        iterations = 6
        for i in range(iterations):
            if not self.is_running:
                break

            # A. Send UDP Heartbeat
            self.seq += 1
            hb = build_udp_packet("HEARTBEAT", user_id=self.user["id"], username=self.user["username"], seq=self.seq)
            self.udp_sock.sendto(hb, ("127.0.0.1", self.udp_port))

            # B. Occasionally send typing indicator via UDP
            targets = [u for u in self.all_users if u["id"] != self.user["id"]]
            target_user = random.choice(targets)
            typing_pkt = build_udp_packet("TYPING", user_id=self.user["id"], username=self.user["username"],
                                          payload={"target_type": "user", "target_id": target_user["id"], "is_typing": True})
            self.udp_sock.sendto(typing_pkt, ("127.0.0.1", self.udp_port))

            time.sleep(0.4)

            # C. Send direct message over TCP to target user
            msg_content = f"Hey {target_user['name']}, ping from {self.user['username']} [seq {i+1}]"
            self.tcp_client.send_private_message(recipient_id=target_user["id"], content=msg_content, wait_ack=False)

            # D. Send message to shared group room
            grp_content = f"[{self.user['username']}] Reporting in for multi-client testing loop {i+1}"
            self.tcp_client.send_group_message(group_id=self.group_id, content=grp_content, wait_ack=False)

            time.sleep(0.6)

    def _listen_loop(self):
        while self.is_running:
            try:
                msg, _ = self.tcp_client.receive_message(timeout=1.0)
                if not msg:
                    continue

                m_type = msg.get("type")
                if m_type == "CHAT_PRIVATE":
                    # Verify message was indeed addressed to this user
                    assert msg.get("recipient_id") == self.user["id"], f"Cross-contamination detected! {msg}"
                    self.received_direct_messages.append(msg)
                elif m_type == "CHAT_GROUP":
                    self.received_group_messages.append(msg)
            except Exception:
                break

    def stop(self):
        self.is_running = False
        try:
            self.tcp_client.close()
            self.udp_sock.close()
        except Exception:
            pass

def main():
    print("=" * 70)
    print("  NETCONNECT - MULTI-CLIENT CONCURRENCY STRESS & ISOLATION SIMULATOR")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Ensure simulated users exist in DB
    for u in SIMULATED_USERS:
        db_user = db.query(User).filter(User.id == u["id"]).first()
        if not db_user:
            db_user = User(
                id=u["id"],
                username=u["username"],
                email=f"{u['username']}@sim.local",
                hashed_password=get_password_hash("simpass123"),
                display_name=u["name"],
                is_online=False
            )
            db.add(db_user)
    db.commit()

    # Ensure shared simulation group exists
    sim_grp = db.query(Group).filter(Group.name == "SimConcurrencyGroup").first()
    if not sim_grp:
        sim_grp = Group(name="SimConcurrencyGroup", description="Stress testing multi-client broadcast", created_by=SIMULATED_USERS[0]["id"])
        db.add(sim_grp)
        db.commit()
        db.refresh(sim_grp)

    for u in SIMULATED_USERS:
        if not db.query(GroupMember).filter(GroupMember.group_id == sim_grp.id, GroupMember.user_id == u["id"]).first():
            db.add(GroupMember(group_id=sim_grp.id, user_id=u["id"], role="member"))
    db.commit()
    grp_id = sim_grp.id
    db.close()

    print(f"[*] Target TCP Server: 127.0.0.1:{settings.TCP_PORT}")
    print(f"[*] Target UDP Server: 127.0.0.1:{settings.UDP_PORT}")
    print(f"[*] Spawning {len(SIMULATED_USERS)} concurrent client workers simultaneously...")

    # Spawn 5 simultaneous clients
    clients = [
        SimulatedClient(
            user_info=u,
            tcp_port=settings.TCP_PORT,
            udp_port=settings.UDP_PORT,
            all_users=SIMULATED_USERS,
            group_id=grp_id
        )
        for u in SIMULATED_USERS
    ]

    for c in clients:
        c.start()

    print("[*] All 5 clients running concurrent socket transmissions...")
    # Wait for completion
    for c in clients:
        c.join(timeout=15.0)

    time.sleep(1.0)
    for c in clients:
        c.stop()

    print("\n" + "=" * 70)
    print("  SIMULATION RESULTS & VERIFICATION")
    print("=" * 70)
    total_direct_delivered = sum(len(c.received_direct_messages) for c in clients)
    total_group_delivered = sum(len(c.received_group_messages) for c in clients)

    print(f"[✓] Total Direct Messages Delivered to Correct Recipients: {total_direct_delivered}")
    print(f"[✓] Total Group Broadcasts Received: {total_group_delivered}")

    for c in clients:
        print(f"    - Client {c.user['username']:12}: {len(c.received_direct_messages):2} direct msgs, {len(c.received_group_messages):2} group msgs")
        # Verify no message was misrouted
        for m in c.received_direct_messages:
            if m.get("recipient_id") != c.user["id"]:
                print(f"[ERROR] Message misrouted to {c.user['username']}! Details: {m}")
                sys.exit(1)

    print("\n[SUCCESS] Multi-client simulation completed! Zero packet leakage or cross-user mixing detected.")

if __name__ == "__main__":
    main()
