from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.utils.auth import get_current_user
from backend.app.networking.connection_manager import network_manager

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("")
def list_users(
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(User).filter(User.id != current_user.id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter((User.username.ilike(term)) | (User.display_name.ilike(term)))

    users = query.order_by(User.username.asc()).all()
    udp_online_ids = set(network_manager.udp_server.get_online_users())

    result = []
    for u in users:
        d = u.to_dict()
        # Overlay real-time UDP presence
        d["is_online"] = (u.id in udp_online_ids) or u.is_online
        result.append(d)

    return result

@router.get("/{user_id}")
def get_user_detail(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    d = user.to_dict()
    d["is_online"] = network_manager.udp_server.is_user_online(user.id) or user.is_online
    return d
