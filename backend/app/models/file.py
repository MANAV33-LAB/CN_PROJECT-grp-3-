from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class FileRecord(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    original_name = Column(String(255), nullable=False)
    stored_filename = Column(String(255), unique=True, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), default="application/octet-stream")
    file_path = Column(String(500), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = relationship("User", back_populates="uploaded_files")
    message = relationship("Message", back_populates="file", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "original_name": self.original_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "uploaded_by": self.uploaded_by,
            "download_url": f"/api/files/download/{self.id}",
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
