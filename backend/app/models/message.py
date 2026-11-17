from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    client_msg_id = Column(String(100), nullable=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True) # null if group message
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)     # null if direct message
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text") # 'text', 'file', 'system'
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    status = Column(String(20), default="sent") # 'sent', 'delivered', 'read'
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    sender = relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])
    recipient = relationship("User", back_populates="received_messages", foreign_keys=[recipient_id])
    group = relationship("Group", back_populates="messages")
    file = relationship("FileRecord", back_populates="message", uselist=False)
    receipts = relationship("MessageReceipt", back_populates="message", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "client_msg_id": self.client_msg_id,
            "sender_id": self.sender_id,
            "sender_username": self.sender.username if self.sender else None,
            "sender_name": self.sender.display_name if self.sender else None,
            "recipient_id": self.recipient_id,
            "group_id": self.group_id,
            "content": self.content,
            "message_type": self.message_type,
            "file": self.file.to_dict() if self.file else None,
            "status": self.status,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class MessageReceipt(Base):
    __tablename__ = "message_receipts"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="delivered") # 'delivered', 'read'
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    message = relationship("Message", back_populates="receipts")
