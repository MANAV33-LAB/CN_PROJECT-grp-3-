from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from typing import List, Optional

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.message import Message
from backend.app.utils.auth import get_current_user
from backend.app.networking.connection_manager import network_manager

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

@router.get("")
def get_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns list of direct conversations with last message, unread count,
    and user online status.
    """
    # Find all users with whom current_user has exchanged direct messages
    sent_to = db.query(Message.recipient_id).filter(
        Message.sender_id == current_user.id,
        Message.recipient_id.isnot(None)
    ).distinct().all()

    received_from = db.query(Message.sender_id).filter(
        Message.recipient_id == current_user.id,
        Message.recipient_id.isnot(None)
    ).distinct().all()

    other_user_ids = set([r[0] for r in sent_to if r[0]] + [r[0] for r in received_from if r[0]])
    udp_online_ids = set(network_manager.udp_server.get_online_users())

    conversations = []
    for other_id in other_user_ids:
        other_user = db.query(User).filter(User.id == other_id).first()
        if not other_user:
            continue

        # Get last message
        last_msg = db.query(Message).filter(
            or_(
                and_(Message.sender_id == current_user.id, Message.recipient_id == other_id),
                and_(Message.sender_id == other_id, Message.recipient_id == current_user.id)
            )
        ).order_by(desc(Message.created_at)).first()

        # Count unread messages
        unread_count = db.query(Message).filter(
            Message.sender_id == other_id,
            Message.recipient_id == current_user.id,
            Message.status != "read"
        ).count()

        u_dict = other_user.to_dict()
        u_dict["is_online"] = (other_id in udp_online_ids) or other_user.is_online

        conversations.append({
            "user": u_dict,
            "last_message": last_msg.to_dict() if last_msg else None,
            "unread_count": unread_count,
            "updated_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else other_user.created_at.isoformat()
        })

    # Sort conversations by latest activity
    conversations.sort(key=lambda x: x["updated_at"], reverse=True)
    return conversations

@router.get("/direct/{other_user_id}/messages")
def get_direct_messages(
    other_user_id: int,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches chat history between current user and specified other user."""
    messages = db.query(Message).filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == other_user_id),
            and_(Message.sender_id == other_user_id, Message.recipient_id == current_user.id)
        )
    ).order_by(Message.created_at.asc()).limit(limit).all()

    # Automatically mark received unread messages as read
    unreads = [m for m in messages if m.recipient_id == current_user.id and m.status != "read"]
    if unreads:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for m in unreads:
            m.status = "read"
            m.read_at = now
        db.commit()

    return [m.to_dict() for m in messages]
