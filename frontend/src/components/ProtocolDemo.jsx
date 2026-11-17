import React, { useState } from 'react';
import {
  Layers,
  Zap,
  ShieldCheck,
  Flame,
  ArrowRight,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Info
} from 'lucide-react';
import { api } from '../services/api';

export default function ProtocolDemo() {
  const [packetCount, setPacketCount] = useState(20);
  const [lossRate, setLossRate] = useState(25);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);

  const runBenchmark = async () => {
    setRunning(true);
    setResults(null);
    try {
      const data = await api.simulateComparison({
        packet_count: packetCount,
        simulate_packet_loss: true,
        loss_rate_percent: lossRate
      });
      setResults(data);
    } catch (err) {
      alert(`Simulation failed: ${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex-1 h-full overflow-y-auto bg-dark-950 p-8 space-y-8 select-none">
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold text-white flex items-center gap-2.5">
          <Layers className="w-6 h-6 text-brand-400" />
          TCP vs UDP Protocol Demonstration
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Interactive practical demonstration of transport-layer protocols implemented in NetConnect.
        </p>
      </div>

      {/* Comparison Matrix Table */}
      <div className="bg-dark-900 border border-dark-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="p-5 border-b border-dark-800 bg-dark-950/40 flex items-center justify-between">
          <h3 className="font-bold text-slate-100 text-sm">Transport Layer Architectural Comparison</h3>
          <span className="text-xs text-slate-400 font-mono">RFC 793 (TCP) • RFC 768 (UDP)</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-dark-950/60 text-slate-400 border-b border-dark-800">
              <tr>
                <th className="py-3 px-5 font-semibold">Feature / Metric</th>
                <th className="py-3 px-5 font-semibold text-brand-400">Transmission Control Protocol (TCP)</th>
                <th className="py-3 px-5 font-semibold text-emerald-400">User Datagram Protocol (UDP)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-800/60 text-slate-300">
              <tr>
                <td className="py-3 px-5 font-medium text-slate-400">Connection Paradigm</td>
                <td className="py-3 px-5 font-semibold text-slate-100">Connection-Oriented (3-Way Handshake)</td>
                <td className="py-3 px-5 font-semibold text-slate-100">Connectionless (Fire-and-Forget)</td>
              </tr>
              <tr>
                <td className="py-3 px-5 font-medium text-slate-400">Delivery Reliability</td>
                <td className="py-3 px-5 text-emerald-400 font-semibold flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  Guaranteed (ACKs + Automatic Retransmission ARQ)
                </td>
                <td className="py-3 px-5 text-amber-400 font-semibold">
                  Unreliable (Best-effort datagram, no resend)
                </td>
              </tr>
              <tr>
                <td className="py-3 px-5 font-medium text-slate-400">Packet Sequencing & Ordering</td>
                <td className="py-3 px-5 text-emerald-400 font-semibold">
                  Guaranteed in-order delivery (Seq & Ack numbers)
                </td>
                <td className="py-3 px-5 text-slate-400">
                  No ordering guarantee (Packets may arrive out-of-order)
                </td>
              </tr>
              <tr>
                <td className="py-3 px-5 font-medium text-slate-400">Flow & Congestion Control</td>
                <td className="py-3 px-5 text-slate-200">
                  Sliding window, slow-start, congestion avoidance
                </td>
                <td className="py-3 px-5 text-slate-400">
                  None (Sender transmits at arbitrary line speed)
                </td>
              </tr>
              <tr>
                <td className="py-3 px-5 font-medium text-slate-400">Header Overhead</td>
                <td className="py-3 px-5 text-slate-200 font-mono">
                  20 to 60 bytes (flags, checksum, window, options)
                </td>
                <td className="py-3 px-5 text-emerald-400 font-mono font-semibold">
                  8 bytes fixed (Source, Dest, Length, Checksum)
                </td>
              </tr>
              <tr>
                <td className="py-3 px-5 font-medium text-slate-400">Application Usage in NetConnect</td>
                <td className="py-3 px-5 font-medium text-brand-300">
                  Reliable chat messages, offline queues, chunked file transfer
                </td>
                <td className="py-3 px-5 font-medium text-emerald-300">
                  Periodic presence heartbeats, typing indicator pings
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Interactive Benchmark Simulation */}
      <div className="bg-dark-900 border border-dark-800 rounded-2xl p-6 space-y-6">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Zap className="w-5 h-5 text-brand-400" />
            Live Transmission Benchmark
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Trigger simultaneous transmissions of raw packets against the running local TCP and UDP sockets
            to observe real-time latency, delivery guarantees, and packet drop behavior.
          </p>
        </div>

        {/* Configuration Controls */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-dark-950/60 p-5 rounded-xl border border-dark-800/80">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2">
              Number of Packets: <span className="text-brand-400 font-mono">{packetCount}</span>
            </label>
            <input
              type="range"
              min="10"
              max="50"
              step="5"
              value={packetCount}
              onChange={(e) => setPacketCount(parseInt(e.target.value))}
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
              <span>10 pkts</span>
              <span>50 pkts</span>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2">
              UDP Simulated Packet Loss: <span className="text-rose-400 font-mono">{lossRate}%</span>
            </label>
            <input
              type="range"
              min="0"
              max="50"
              step="5"
              value={lossRate}
              onChange={(e) => setLossRate(parseInt(e.target.value))}
              className="w-full accent-rose-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
              <span>0% (Ideal)</span>
              <span>50% (Lossy link)</span>
            </div>
          </div>

          <div className="flex items-end">
            <button
              onClick={runBenchmark}
              disabled={running}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-semibold text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-brand-500/20 disabled:opacity-50"
            >
              <Play className={`w-4 h-4 fill-current ${running ? 'animate-spin' : ''}`} />
              <span>{running ? 'Benchmarking Sockets...' : 'Run Socket Benchmark'}</span>
            </button>
          </div>
        </div>

        {/* Benchmark Results */}
        {results && (
          <div className="space-y-6 animate-fadeIn">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* TCP Card */}
              <div className="bg-dark-950 rounded-xl p-5 border border-brand-500/30 space-y-4">
                <div className="flex items-center justify-between border-b border-dark-800 pb-3">
                  <div className="flex items-center space-x-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-brand-500" />
                    <h4 className="font-bold text-white text-sm">TCP Transmission Results</h4>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    {results.tcp.delivery_rate_percent}% Delivery
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="bg-dark-900 p-2.5 rounded-lg border border-dark-800">
                    <span className="text-slate-400 block text-[10px]">Packets Received</span>
                    <span className="text-white font-bold text-base">
                      {results.tcp.packets_received} / {results.packet_count}
                    </span>
                  </div>
                  <div className="bg-dark-900 p-2.5 rounded-lg border border-dark-800">
                    <span className="text-slate-400 block text-[10px]">Average Round-Trip</span>
                    <span className="text-brand-400 font-bold text-base">
                      {results.tcp.average_rtt_ms} ms
                    </span>
                  </div>
                  <div className="bg-dark-900 p-2.5 rounded-lg border border-dark-800">
                    <span className="text-slate-400 block text-[10px]">3-Way Handshake</span>
                    <span className="text-slate-200 font-bold">
                      {results.tcp.connection_handshake_ms} ms
                    </span>
                  </div>
                  <div className="bg-dark-900 p-2.5 rounded-lg border border-dark-800">
                    <span className="text-slate-400 block text-[10px]">Packets Dropped</span>
                    <span className="text-emerald-400 font-bold">0 (Guaranteed)</span>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 bg-dark-900/60 p-3 rounded-lg border border-dark-800">
                  <p className="font-semibold text-slate-300 mb-1">TCP Reliability Verification:</p>
                  Every payload was safely framed with 4-byte length prefix, verified by sequence numbers,
                  and fully acknowledged without missing a single byte.
                </div>
              </div>

              {/* UDP Card */}
              <div className="bg-dark-950 rounded-xl p-5 border border-emerald-500/30 space-y-4">
                <div className="flex items-center justify-between border-b border-dark-800 pb-3">
                  <div className="flex items-center space-x-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                    <h4 className="font-bold text-white text-sm">UDP Datagram Results</h4>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                    results.udp.delivery_rate_percent >= 90
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                  }`}>
                    {results.udp.delivery_rate_percent}% Delivery
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="bg-dark-900 p-2.5 rounded-lg border border-dark-800">
                    <span className="text-slate-400 block text-[10px]">Packets Received</span>
                    <span className="text-white font-bold text-base">
                      {results.udp.packets_received} / {results.packet_count}
                    </span>
                  </div>
                  <div className="bg-dark-900 p-2.5 rounded-lg border border-dark-800">
                    <span className="text-slate-400 block text-[10px]">Average Round-Trip</span>
                    <span className="text-emerald-400 font-bold text-base">
                      {results.udp.average_rtt_ms} ms
                    </span>
                  </div>
                  <div className="bg-dark-900 p-2.5 rounded-lg border border-dark-800">
                    <span className="text-slate-400 block text-[10px]">Setup Handshake</span>
                    <span className="text-emerald-400 font-bold">0.0 ms (None)</span>
                  </div>
                  <div className="bg-dark-900 p-2.5 rounded-lg border border-dark-800">
                    <span className="text-slate-400 block text-[10px]">Packets Dropped</span>
                    <span className="text-rose-400 font-bold">
                      {results.udp.packets_lost} packets
                    </span>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 bg-dark-900/60 p-3 rounded-lg border border-dark-800">
                  <p className="font-semibold text-slate-300 mb-1">UDP Characteristic Verification:</p>
                  Zero connection establishment latency and minimal header overhead. Any packet lost
                  due to buffer overflow or route issues is dropped permanently without retransmission.
                </div>
              </div>
            </div>

            {/* Academic Conclusion */}
            <div className="bg-dark-950 p-4 rounded-xl border border-dark-800 text-xs text-slate-300 leading-relaxed">
              <span className="font-bold text-white block mb-1">Empirical Conclusion:</span>
              {results.conclusion}
            </div>
          </div>
        )}
      </div>

      {/* Protocol Visual Diagrams */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-dark-900 border border-dark-800 rounded-2xl p-5 space-y-3">
          <h4 className="font-bold text-white text-sm">TCP 3-Way Handshake & Connection</h4>
          <div className="bg-dark-950 rounded-xl p-4 font-mono text-xs text-slate-300 space-y-2 border border-dark-800">
            <div className="flex items-center justify-between text-brand-400">
              <span>Client</span>
              <span>SYN (Seq = x) ───────────────&gt;</span>
              <span>Server</span>
            </div>
            <div className="flex items-center justify-between text-emerald-400">
              <span>Client</span>
              <span>&lt;─────────────── SYN-ACK (Seq=y, Ack=x+1)</span>
              <span>Server</span>
            </div>
            <div className="flex items-center justify-between text-indigo-400">
              <span>Client</span>
              <span>ACK (Ack = y+1) ───────────&gt;</span>
              <span>Server</span>
            </div>
          </div>
          <p className="text-xs text-slate-400">
            Guarantees synchronized sequence numbers and socket allocation before transmitting chat data.
          </p>
        </div>

        <div className="bg-dark-900 border border-dark-800 rounded-2xl p-5 space-y-3">
          <h4 className="font-bold text-white text-sm">UDP Datagram Structure</h4>
          <div className="bg-dark-950 rounded-xl p-4 font-mono text-xs text-slate-300 space-y-1.5 border border-dark-800">
            <div className="grid grid-cols-2 gap-1 text-center font-bold text-[10px]">
              <div className="bg-dark-900 p-1.5 rounded border border-dark-800 text-emerald-400">
                Source Port (16 bits)
              </div>
              <div className="bg-dark-900 p-1.5 rounded border border-dark-800 text-emerald-400">
                Destination Port (16 bits)
              </div>
              <div className="bg-dark-900 p-1.5 rounded border border-dark-800 text-slate-300">
                Length (16 bits)
              </div>
              <div className="bg-dark-900 p-1.5 rounded border border-dark-800 text-slate-300">
                Checksum (16 bits)
              </div>
            </div>
            <div className="bg-emerald-500/10 text-emerald-400 text-center py-2 rounded border border-emerald-500/20 text-xs">
              Application Payload (JSON: type, user_id, seq, timestamp)
            </div>
          </div>
          <p className="text-xs text-slate-400">
            Streamlined 8-byte header provides maximum throughput and minimum latency for presence heartbeats.
          </p>
        </div>
      </div>
    </div>
  );
}
