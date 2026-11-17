from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import re

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.utils.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

class LoginRequest(BaseModel):
    username_or_email: str
    password: str

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    req.username = req.username.strip().lower()
    req.email = req.email.strip().lower()
    if "@" not in req.email or "." not in req.email:
        raise HTTPException(status_code=400, detail="Invalid email address format")
    if len(req.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing_user = db.query(User).filter(
        (User.username == req.username) | (User.email == req.email.lower())
    ).first()
    if existing_user:
        if existing_user.username == req.username:
            raise HTTPException(status_code=400, detail="Username already registered")
        else:
            raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=req.username,
        email=req.email.lower(),
        hashed_password=get_password_hash(req.password),
        display_name=req.display_name or req.username.capitalize(),
        avatar_url=req.avatar_url or f"https://api.dicebear.com/7.x/bottts/svg?seed={req.username}",
        bio=req.bio or "Hey there! I am using NetConnect."
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "username": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    identifier = req.username_or_email.strip().lower()
    user = db.query(User).filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(data={"sub": str(user.id), "username": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user.to_dict()

@router.put("/profile")
def update_profile(req: UpdateProfileRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.display_name is not None and req.display_name.strip():
        current_user.display_name = req.display_name.strip()
    if req.avatar_url is not None:
        current_user.avatar_url = req.avatar_url.strip()
    if req.bio is not None:
        current_user.bio = req.bio.strip()

    db.commit()
    db.refresh(current_user)
    return current_user.to_dict()
