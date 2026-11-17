import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.database import engine, Base
from backend.app.models import * # Ensure all models are imported before creating tables
from backend.app.networking.connection_manager import network_manager
from backend.app.networking.websocket_gateway import websocket_gateway
from backend.app.utils.auth import decode_token
from backend.app.database import SessionLocal
from backend.app.models.user import User

from backend.app.routes import (
    auth,
    users,
    conversations,
    groups,
    files,
    network
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("NetConnect.Main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables and boot socket servers
    logger.info("Initializing NetConnect database tables...")
    Base.metadata.create_all(bind=engine)

    logger.info("Starting TCP and UDP Socket engines...")
    network_manager.start_servers()

    yield

    # Shutdown: Stop socket servers cleanly
    logger.info("Stopping NetConnect servers...")
    network_manager.stop_servers()

app = FastAPI(
    title="NetConnect - Multi-Client TCP/UDP Chat System",
    description="Real-Time Computer Networks Course Project demonstrating raw TCP and UDP socket programming.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(conversations.router)
app.include_router(groups.router)
app.include_router(files.router)
app.include_router(network.router)

# Mount Static Uploads
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

@app.get("/")
def root():
    return {
        "app": "NetConnect Real-Time TCP/UDP Chat Server",
        "version": "1.0.0",
        "status": "online",
        "tcp_port": settings.TCP_PORT,
        "udp_port": settings.UDP_PORT,
        "docs_url": "/docs"
    }

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    WebSocket endpoint bridging web browsers to the custom TCP and UDP servers.
    """
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    user_id_str = payload.get("sub")
    if not user_id_str:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing user ID")
        return

    user_id = int(user_id_str)
    username = payload.get("username", "")

    # If username missing from token, fetch from DB
    if not username:
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == user_id).first()
            if u:
                username = u.username
        finally:
            db.close()

    session = await websocket_gateway.connect_client(websocket, user_id, username)
    if not session:
        return

    try:
        while True:
            text_data = await websocket.receive_text()
            await websocket_gateway.handle_ws_message(session, text_data)
    except WebSocketDisconnect:
        await websocket_gateway.disconnect_client(websocket)
    except Exception as e:
        logger.debug(f"WebSocket exception for user {user_id}: {e}")
        await websocket_gateway.disconnect_client(websocket)
