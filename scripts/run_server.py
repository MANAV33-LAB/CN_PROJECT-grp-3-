import sys
import os
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings

def main():
    print("=" * 70)
    print("  NETCONNECT - MULTI-CLIENT TCP/UDP REAL-TIME CHAT APPLICATION")
    print("=" * 70)
    print(f"[*] REST API & WebSocket Gateway: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"[*] Low-level TCP Server:        tcp://{settings.TCP_HOST}:{settings.TCP_PORT}")
    print(f"[*] Low-level UDP Server:        udp://{settings.UDP_HOST}:{settings.UDP_PORT}")
    print(f"[*] Interactive API Docs:        http://localhost:{settings.API_PORT}/docs")
    print("=" * 70)
    print("Starting server... Press Ctrl+C to terminate.")

    uvicorn.run(
        "backend.app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
        reload=False
    )

if __name__ == "__main__":
    main()
