import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.file import FileRecord
from backend.app.models.message import Message
from backend.app.models.user import User
from backend.app.models.group import GroupMember
from backend.app.utils.auth import get_current_user
from backend.app.networking.connection_manager import network_manager

router = APIRouter(prefix="/api/files", tags=["Files"])

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    recipient_id: Optional[int] = Form(None),
    group_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accepts an uploaded file from HTTP/browser, stores safely in uploads/,
    creates FileRecord, and dispatches message via TCP networking layer.
    """
    if not recipient_id and not group_id:
        raise HTTPException(status_code=400, detail="Must specify either recipient_id or group_id")

    safe_name = os.path.basename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{safe_name}"
    target_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    total_bytes = 0
    with open(target_path, "wb") as f_out:
        while True:
            chunk = await file.read(settings.TCP_CHUNK_SIZE)
            if not chunk:
                break
            f_out.write(chunk)
            total_bytes += len(chunk)

    if total_bytes > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        os.remove(target_path)
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB")

    # Save metadata to DB
    file_record = FileRecord(
        original_name=safe_name,
        stored_filename=unique_filename,
        file_size=total_bytes,
        mime_type=file.content_type or "application/octet-stream",
        file_path=target_path,
        uploaded_by=current_user.id
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    now = datetime.now(timezone.utc)
    # Create Message entry
    msg = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        group_id=group_id,
        content=f"Shared file: {safe_name}",
        message_type="file",
        file_id=file_record.id,
        status="sent",
        created_at=now
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Route message via TCP server to recipient or group
    payload = {
        "type": "CHAT_PRIVATE" if recipient_id else "CHAT_GROUP",
        "id": msg.id,
        "sender_id": current_user.id,
        "sender_username": current_user.username,
        "sender_name": current_user.display_name,
        "recipient_id": recipient_id,
        "group_id": group_id,
        "content": msg.content,
        "message_type": "file",
        "file": file_record.to_dict(),
        "status": "delivered" if recipient_id and network_manager.tcp_server.send_to_user(recipient_id, {}) else "sent",
        "created_at": now.isoformat()
    }

    if recipient_id:
        delivered = network_manager.tcp_server.send_to_user(recipient_id, payload)
        if delivered:
            msg.status = "delivered"
            msg.delivered_at = now
            db.commit()
    elif group_id:
        members = db.query(GroupMember.user_id).filter(GroupMember.group_id == group_id).all()
        for (mid,) in members:
            if mid != current_user.id:
                network_manager.tcp_server.send_to_user(mid, payload)

    network_manager.tcp_server.log_network_event(
        "FILE_UPLOAD",
        f"File '{safe_name}' ({total_bytes} bytes) uploaded and routed by user {current_user.username}",
        user_id=current_user.id,
        bytes_count=total_bytes
    )

    return {
        "file": file_record.to_dict(),
        "message": msg.to_dict()
    }

@router.get("/download/{file_id}")
def download_file(file_id: int, db: Session = Depends(get_db)):
    """Streams file download to client."""
    file_record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not file_record or not os.path.exists(file_record.file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_record.file_path,
        filename=file_record.original_name,
        media_type=file_record.mime_type
    )
