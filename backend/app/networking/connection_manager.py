import logging
from typing import Optional
from backend.app.networking.tcp_server import TCPServer
from backend.app.networking.udp_server import UDPServer

logger = logging.getLogger("NetConnect.ConnectionManager")

class NetworkManager:
    """
    Central orchestration manager for the NetConnect TCP and UDP servers.
    Provides singleton instances and lifecycle hooks for the application.
    """

    _instance: Optional["NetworkManager"] = None

    def __init__(self):
        self.tcp_server = TCPServer()
        self.udp_server = UDPServer()
        self._wire_subscribers()

    @classmethod
    def get_instance(cls) -> "NetworkManager":
        if cls._instance is None:
            cls._instance = NetworkManager()
        return cls._instance

    def _wire_subscribers(self):
        # Wire UDP presence notifications so TCP server logs and pushes updates if needed
        def on_presence_event(event_type: str, data: dict):
            if event_type == "PRESENCE_CHANGE":
                uid = data.get("user_id")
                is_online = data.get("is_online")
                logger.debug(f"[NetworkManager] User {uid} presence changed to online={is_online}")

        self.udp_server.add_presence_subscriber(on_presence_event)

    def start_servers(self):
        """Starts both TCP and UDP servers."""
        logger.info("Starting TCP and UDP network servers...")
        self.tcp_server.start()
        self.udp_server.start()

    def stop_servers(self):
        """Stops both TCP and UDP servers."""
        logger.info("Stopping TCP and UDP network servers...")
        self.tcp_server.stop()
        self.udp_server.stop()

    def get_aggregate_stats(self) -> dict:
        """Returns consolidated networking metrics from both TCP and UDP layers."""
        tcp_stats = self.tcp_server.get_stats()
        udp_stats = self.udp_server.get_stats()

        total_bytes = tcp_stats["total_bytes_transferred"] + udp_stats["total_bytes_transferred"]
        total_packets = tcp_stats["total_messages_relayed"] + udp_stats["total_datagrams_received"] + udp_stats["total_datagrams_sent"]

        # Combined recent events sorted by timestamp
        combined_events = sorted(
            tcp_stats["recent_events"] + udp_stats["recent_events"],
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )[:50]

        return {
            "tcp": tcp_stats,
            "udp": udp_stats,
            "aggregate": {
                "total_bytes_transferred": total_bytes,
                "total_network_packets": total_packets,
                "active_tcp_connections": tcp_stats["active_connections"],
                "active_udp_online_users": udp_stats["online_users_count"],
                "server_uptime_seconds": max(tcp_stats["uptime_seconds"], udp_stats["uptime_seconds"])
            },
            "recent_events": combined_events
        }

network_manager = NetworkManager.get_instance()
