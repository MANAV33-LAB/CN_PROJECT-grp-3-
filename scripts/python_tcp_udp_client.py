#!/usr/bin/env python3
"""
NetConnect CLI – Pure Python Terminal Socket Client
Connects directly to NetConnect's TCP Server (port 8888) and UDP Server (port 8889)
Demonstrating direct command-line socket communication.
"""

import sys
import os
import time
import socket
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings
from backend.app.networking.tcp_client import TCPClient
from backend.app.networking.protocol import build_udp_packet, parse_udp_packet

def main():
    print("=" * 65)
    print("  NETCONNECT – RAW TCP & UDP TERMINAL CLIENT")
    print("=" * 65)

    host = settings.TCP_HOST
    tcp_port = settings.TCP_PORT
    udp_port = settings.UDP_PORT

    username = input("Enter username [alice/bob/charlie]: ").strip() or "alice"
    user_id_map = {"alice": 1, "bob": 2, "charlie": 3, "david": 4, "eva": 5}
    user_id = user_id_map.get(username.lower(), 1)

    print(f"Connecting TCP socket to {host}:{tcp_port}...")
    client = TCPClient(host=host, port=tcp_port)
    if not client.authenticate(user_id=user_id, username=username):
        print("Failed to authenticate with TCP server.")
        return

    print(f"[✓] TCP Connection established and authenticated as {username} (ID: {user_id})")

    # Setup UDP socket for presence heartbeats
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    is_running = True

    # Background Heartbeat Thread
    def heartbeat_worker():
        seq = 0
        while is_running:
            seq += 1
            hb = build_udp_packet("HEARTBEAT", user_id=user_id, username=username, seq=seq)
            try:
                udp_sock.sendto(hb, (host, udp_port))
            except Exception:
                break
            time.sleep(3)

    hb_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    hb_thread.start()

    # Background TCP Listener Thread
    def listener_worker():
        while is_running:
            try:
                msg, _ = client.receive_message(timeout=1.0)
                if not msg:
                    continue
                m_type = msg.get("type")
                if m_type == "CHAT_PRIVATE":
                    sender = msg.get("sender_name") or msg.get("sender_username")
                    content = msg.get("content")
                    print(f"\n[Direct Msg from @{sender}]: {content}\n> ", end="", flush=True)
                elif m_type == "CHAT_GROUP":
                    sender = msg.get("sender_name") or msg.get("sender_username")
                    grp_id = msg.get("group_id")
                    content = msg.get("content")
                    print(f"\n[Group #{grp_id} from @{sender}]: {content}\n> ", end="", flush=True)
                elif m_type == "MSG_STATUS":
                    status = msg.get("status")
                    mid = msg.get("message_id")
                    print(f"\n[ACK]: Message {mid} status: {status}\n> ", end="", flush=True)
            except Exception:
                break

    l_thread = threading.Thread(target=listener_worker, daemon=True)
    l_thread.start()

    print("\nCommands:")
    print("  /msg <user_id> <text>  - Send direct message via TCP")
    print("  /grp <group_id> <text> - Send group message via TCP")
    print("  /typing <user_id>      - Send UDP typing signal")
    print("  /quit                  - Exit client cleanly\n")

    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue
            if cmd == "/quit":
                break
            elif cmd.startswith("/msg "):
                parts = cmd.split(" ", 2)
                if len(parts) >= 3:
                    recip_id = int(parts[1])
                    text = parts[2]
                    client.send_private_message(recipient_id=recip_id, content=text, wait_ack=False)
                else:
                    print("Usage: /msg <user_id> <content>")
            elif cmd.startswith("/grp "):
                parts = cmd.split(" ", 2)
                if len(parts) >= 3:
                    grp_id = int(parts[1])
                    text = parts[2]
                    client.send_group_message(group_id=grp_id, content=text, wait_ack=False)
                else:
                    print("Usage: /grp <group_id> <content>")
            elif cmd.startswith("/typing "):
                parts = cmd.split(" ", 1)
                if len(parts) >= 2:
                    target_id = int(parts[1])
                    typing_pkt = build_udp_packet("TYPING", user_id=user_id, username=username,
                                                  payload={"target_type": "user", "target_id": target_id, "is_typing": True})
                    udp_sock.sendto(typing_pkt, (host, udp_port))
                    print(f"[UDP] Typing signal transmitted to user {target_id}")
            else:
                print("Unknown command. Use /msg, /grp, /typing, or /quit")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        is_running = False
        client.close()
        udp_sock.close()
        print("\nDisconnected.")

if __name__ == "__main__":
    main()
