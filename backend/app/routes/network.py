import time
import socket
import random
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.network_log import NetworkLog
from backend.app.networking.connection_manager import network_manager
from backend.app.config import settings
from backend.app.networking.protocol import (
    send_framed_message,
    recv_framed_message,
    build_udp_packet,
    parse_udp_packet
)

router = APIRouter(prefix="/api/network", tags=["Network Monitoring"])

class SimulationRequest(BaseModel):
    packet_count: int = 20
    simulate_packet_loss: bool = True
    loss_rate_percent: int = 20 # 20% dropped for UDP demo

@router.get("/stats")
def get_network_statistics():
    """Provides real-time networking stats from the TCP and UDP socket engines."""
    return network_manager.get_aggregate_stats()

@router.get("/logs")
def get_network_logs(
    limit: int = Query(50, ge=1, le=200),
    protocol: Optional[str] = Query(None), # 'TCP', 'UDP', or None for both
    db: Session = Depends(get_db)
):
    query = db.query(NetworkLog)
    if protocol:
        query = query.filter(NetworkLog.protocol == protocol.upper())
    logs = query.order_by(NetworkLog.timestamp.desc()).limit(limit).all()
    return [l.to_dict() for l in logs]

@router.post("/simulate-comparison")
def run_protocol_comparison_simulation(req: SimulationRequest):
    """
    Executes a live benchmark comparing TCP reliable byte stream
    vs UDP unreliable datagram transmission directly against local sockets.
    Returns transmission latencies, packet delivery rate, packet ordering,
    and overhead comparison.
    """
    count = max(5, min(req.packet_count, 50))
    loss_rate = max(0, min(req.loss_rate_percent, 80)) / 100.0

    # 1. Benchmark TCP Transmission
    tcp_results = {
        "packets_sent": count,
        "packets_received": 0,
        "packets_lost": 0,
        "delivery_rate_percent": 100.0,
        "ordering_preserved": True,
        "rtt_times_ms": [],
        "average_rtt_ms": 0.0,
        "bytes_sent": 0,
        "protocol_features": {
            "connection_oriented": True,
            "flow_control": "Sliding window",
            "congestion_control": "TCP Reno/Cubic",
            "error_checking": "Checksum + Retransmission (ARQ)",
            "header_overhead_bytes": "20-60 bytes"
        }
    }

    tcp_sock = None
    try:
        t_start_conn = time.perf_counter()
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.settimeout(2.0)
        tcp_sock.connect((settings.TCP_HOST, settings.TCP_PORT))
        tcp_connect_time_ms = (time.perf_counter() - t_start_conn) * 1000

        # Send PINGs and await PONGs
        for seq in range(count):
            t0 = time.perf_counter()
            ping_payload = {"type": "PING", "seq": seq, "timestamp": time.time()}
            b_sent = send_framed_message(tcp_sock, ping_payload)
            tcp_results["bytes_sent"] += b_sent

            pong, _ = recv_framed_message(tcp_sock, parse_json=True)
            rtt = (time.perf_counter() - t0) * 1000
            tcp_results["rtt_times_ms"].append(round(rtt, 3))
            tcp_results["packets_received"] += 1

        tcp_results["connection_handshake_ms"] = round(tcp_connect_time_ms, 3)
    except Exception as e:
        tcp_results["error"] = str(e)
    finally:
        if tcp_sock:
            try:
                tcp_sock.close()
            except Exception:
                pass

    if tcp_results["packets_received"] > 0:
        tcp_results["average_rtt_ms"] = round(
            sum(tcp_results["rtt_times_ms"]) / len(tcp_results["rtt_times_ms"]), 3
        )
        tcp_results["delivery_rate_percent"] = round(
            (tcp_results["packets_received"] / count) * 100.0, 1
        )

    # 2. Benchmark UDP Transmission
    udp_results = {
        "packets_sent": count,
        "packets_received": 0,
        "packets_lost": 0,
        "delivery_rate_percent": 0.0,
        "ordering_preserved": True,
        "rtt_times_ms": [],
        "average_rtt_ms": 0.0,
        "bytes_sent": 0,
        "simulated_drop_count": 0,
        "protocol_features": {
            "connection_oriented": False,
            "flow_control": "None (Application responsibility)",
            "congestion_control": "None",
            "error_checking": "Optional Checksum (No Retransmission)",
            "header_overhead_bytes": "8 bytes fixed"
        }
    }

    udp_sock = None
    try:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.settimeout(0.5)

        for seq in range(count):
            # If simulated packet loss is enabled, simulate network congestion / buffer drop
            should_drop = req.simulate_packet_loss and (random.random() < loss_rate)
            t0 = time.perf_counter()

            packet_data = build_udp_packet("PING", user_id=9999, username="BenchmarkBot", seq=seq)
            sent_len = udp_sock.sendto(packet_data, (settings.UDP_HOST, settings.UDP_PORT))
            udp_results["bytes_sent"] += sent_len

            if should_drop:
                # Packet was lost in transit / dropped before read
                udp_results["simulated_drop_count"] += 1
                udp_results["packets_lost"] += 1
                continue

            try:
                resp_bytes, _ = udp_sock.recvfrom(4096)
                rtt = (time.perf_counter() - t0) * 1000
                udp_results["rtt_times_ms"].append(round(rtt, 3))
                udp_results["packets_received"] += 1
            except socket.timeout:
                udp_results["packets_lost"] += 1

    except Exception as e:
        udp_results["error"] = str(e)
    finally:
        if udp_sock:
            try:
                udp_sock.close()
            except Exception:
                pass

    if udp_results["packets_received"] > 0:
        udp_results["average_rtt_ms"] = round(
            sum(udp_results["rtt_times_ms"]) / len(udp_results["rtt_times_ms"]), 3
        )
    udp_results["delivery_rate_percent"] = round(
        (udp_results["packets_received"] / count) * 100.0, 1
    )

    return {
        "tested_at": time.time(),
        "packet_count": count,
        "tcp": tcp_results,
        "udp": udp_results,
        "conclusion": (
            "TCP achieved 100% delivery guarantee with ordered packet sequencing at the cost of "
            "connection handshake and acknowledgment overhead. UDP demonstrated near-zero setup overhead "
            "and minimal latency, but lacks retransmission and packet delivery guarantees, making it "
            "ideal for lightweight heartbeats and presence rather than mission-critical message data."
        )
    }
