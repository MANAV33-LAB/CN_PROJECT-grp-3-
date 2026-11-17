import sys
import os
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, SessionLocal, Base
from backend.app.models.user import User
from backend.app.models.group import Group, GroupMember
from backend.app.models.message import Message
from backend.app.utils.auth import get_password_hash

def init_demo_data():
    print("Creating database tables if not exist...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    demo_users = [
        {"username": "alice", "email": "alice@netconnect.local", "display_name": "Alice Cooper", "bio": "Computer Networks TA & TCP enthusiast", "password": "password123"},
        {"username": "bob", "email": "bob@netconnect.local", "display_name": "Bob Dylan", "bio": "Building packet analyzers with Python sockets", "password": "password123"},
        {"username": "charlie", "email": "charlie@netconnect.local", "display_name": "Charlie Brown", "bio": "UDP streaming fan | Low latency matters", "password": "password123"},
        {"username": "david", "email": "david@netconnect.local", "display_name": "David Bowie", "bio": "Full-stack networks developer", "password": "password123"},
        {"username": "eva", "email": "eva@netconnect.local", "display_name": "Eva Green", "bio": "Socket programming researcher", "password": "password123"}
    ]

    created_users = {}
    for u_info in demo_users:
        user = db.query(User).filter(User.username == u_info["username"]).first()
        if not user:
            user = User(
                username=u_info["username"],
                email=u_info["email"],
                hashed_password=get_password_hash(u_info["password"]),
                display_name=u_info["display_name"],
                avatar_url=f"https://api.dicebear.com/7.x/bottts/svg?seed={u_info['username']}",
                bio=u_info["bio"],
                is_online=False
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created demo user: {user.username} (password: {u_info['password']})")
        else:
            print(f"User {user.username} already exists.")
        created_users[user.username] = user

    # Create Demo Group
    group_name = "Computer-Networks-Lab"
    group = db.query(Group).filter(Group.name == group_name).first()
    if not group:
        group = Group(
            name=group_name,
            description="Welcome to CS 455 Computer Networks! Discussion of TCP/UDP sockets, framing, and routing.",
            avatar_url="https://api.dicebear.com/7.x/identicon/svg?seed=Networks",
            created_by=created_users["alice"].id
        )
        db.add(group)
        db.commit()
        db.refresh(group)

        # Add all demo users as members
        for u in created_users.values():
            role = "admin" if u.username == "alice" else "member"
            db.add(GroupMember(group_id=group.id, user_id=u.id, role=role))
        db.commit()
        print(f"Created demo group '{group.name}' with members.")

        # Seed welcome group message
        welcome_msg = Message(
            sender_id=created_users["alice"].id,
            group_id=group.id,
            content="Welcome to the NetConnect lab! This chat system is running on low-level TCP sockets with UDP presence heartbeats.",
            message_type="text",
            status="sent",
            created_at=datetime.now(timezone.utc)
        )
        db.add(welcome_msg)
        db.commit()

    db.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    init_demo_data()
