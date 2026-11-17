from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger
from backend.app.database import Base

class NetworkLog(Base):
    __tablename__ = "network_logs"

    id = Column(Integer, primary_key=True, index=True)
    protocol = Column(String(10), nullable=False) # 'TCP' or 'UDP'
    event_type = Column(String(50), nullable=False) # 'CONNECT', 'DISCONNECT', 'MSG_RELAY', 'HEARTBEAT', 'TYPING', 'FILE_CHUNK', 'TIMEOUT'
    client_ip = Column(String(50), nullable=True)
    client_port = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True)
    bytes_transferred = Column(BigInteger, default=0)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "protocol": self.protocol,
            "event_type": self.event_type,
            "client_ip": self.client_ip,
            "client_port": self.client_port,
            "user_id": self.user_id,
            "bytes_transferred": self.bytes_transferred,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
