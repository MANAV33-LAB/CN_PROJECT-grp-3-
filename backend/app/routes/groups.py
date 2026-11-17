from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.group import Group, GroupMember
from backend.app.models.message import Message
from backend.app.utils.auth import get_current_user

router = APIRouter(prefix="/api/groups", tags=["Groups"])

class CreateGroupRequest(BaseModel):
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    initial_member_ids: Optional[List[int]] = []

class AddMemberRequest(BaseModel):
    user_id: int

@router.get("")
def list_groups(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lists all groups the current user is a member of, plus general groups."""
    user_group_ids = db.query(GroupMember.group_id).filter(GroupMember.user_id == current_user.id).all()
    group_ids = [g[0] for g in user_group_ids]

    groups = db.query(Group).filter(Group.id.in_(group_ids)).all()
    results = []
    for g in groups:
        d = g.to_dict()
        # Find last message
        last_msg = db.query(Message).filter(Message.group_id == g.id).order_by(Message.created_at.desc()).first()
        d["last_message"] = last_msg.to_dict() if last_msg else None
        results.append(d)
    return results

@router.get("/discover")
def discover_groups(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lists groups available to join."""
    user_group_ids = db.query(GroupMember.group_id).filter(GroupMember.user_id == current_user.id).all()
    joined_ids = set([g[0] for g in user_group_ids])

    all_groups = db.query(Group).all()
    return [{**g.to_dict(), "is_member": g.id in joined_ids} for g in all_groups]

@router.post("")
def create_group(req: CreateGroupRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Group name is required")

    group = Group(
        name=req.name.strip(),
        description=req.description.strip() if req.description else "",
        avatar_url=req.avatar_url or f"https://api.dicebear.com/7.x/identicon/svg?seed={req.name}",
        created_by=current_user.id
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # Add creator as admin member
    admin_member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role="admin"
    )
    db.add(admin_member)

    # Add initial members
    for uid in (req.initial_member_ids or []):
        if uid != current_user.id:
            member = GroupMember(group_id=group.id, user_id=uid, role="member")
            db.add(member)

    db.commit()
    return group.to_dict()

@router.get("/{group_id}")
def get_group_details(group_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    d = group.to_dict()
    d["members"] = [m.to_dict() for m in members]
    return d

@router.get("/{group_id}/messages")
def get_group_messages(group_id: int, limit: int = Query(50, ge=1, le=200),
                       current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify membership
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")

    messages = db.query(Message).filter(Message.group_id == group_id).order_by(Message.created_at.asc()).limit(limit).all()
    return [m.to_dict() for m in messages]

@router.post("/{group_id}/join")
def join_group(group_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    if existing:
        return {"message": "Already a member"}

    member = GroupMember(group_id=group_id, user_id=current_user.id, role="member")
    db.add(member)
    db.commit()
    return {"message": f"Successfully joined {group.name}"}

@router.post("/{group_id}/leave")
def leave_group(group_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=400, detail="Not a member of this group")

    db.delete(member)
    db.commit()
    return {"message": "Left group successfully"}
