import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "NetConnect"
    ENV: str = os.getenv("ENV", "development")
    
    # Server ports
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("PORT", "5001"))
    
    # TCP Server (Dedicated socket for reliable messaging and file transfers)
    TCP_HOST: str = os.getenv("TCP_HOST", "127.0.0.1")
    TCP_PORT: int = int(os.getenv("TCP_PORT", "8888"))
    
    # UDP Server (Dedicated socket for presence, heartbeats, typing indicators)
    UDP_HOST: str = os.getenv("UDP_HOST", "127.0.0.1")
    UDP_PORT: int = int(os.getenv("UDP_PORT", "8889"))
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "netconnect_super_secret_network_project_key_2026")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./netconnect.db")
    
    # Networking parameters
    HEARTBEAT_INTERVAL: int = 3  # seconds
    HEARTBEAT_TIMEOUT: int = 9   # seconds (3 missed heartbeats marks client offline)
    TYPING_TIMEOUT: int = 4      # seconds
    TCP_CHUNK_SIZE: int = 16384  # 16KB per chunk for TCP file transfers
    MAX_FILE_SIZE_MB: int = 50   # 50MB
    
    # Storage
    UPLOAD_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))

    class Config:
        case_sensitive = True

settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
