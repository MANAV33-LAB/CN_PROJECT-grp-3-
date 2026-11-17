import React, { useState, useEffect } from 'react';
import {
  Activity,
  Layers,
  ArrowUpRight,
  ArrowDownLeft,
  Server,
  Radio,
  Clock,
  HardDrive,
  RefreshCw,
  Cpu,
  Database,
  ShieldCheck,
  Zap
} from 'lucide-react';
import { api } from '../services/api';

export default function NetworkDashboard() {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [filterProtocol, setFilterProtocol] = useState('ALL');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 2500);
    return () => clearInterval(interval);
  }, [filterProtocol]);

  const fetchData = async () => {
    try {
      const [statsData, logsData] = await Promise.all([
        api.getNetworkStats(),
        api.getNetworkLogs(50, filterProtocol === 'ALL' ? null : filterProtocol)
      ]);
      setStats(statsData);
      setLogs(logsData || []);
    } catch (err) {
      console.error('Failed fetching network stats:', err);
    }
  };

  const handleManualRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setTimeout(() => setRefreshing(false), 400);
  };

  const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  const formatUptime = (seconds) => {
    if (!seconds) return '0s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  const aggregate = stats?.aggregate || {};
  const tcp = stats?.tcp || {};
  const udp = stats?.udp || {};

  return (
    <div className="flex-1 h-full overflow-y-auto bg-dark-950 p-8 space-y-6 select-none">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Activity className="w-6 h-6 text-brand-400" />
            Network Monitoring Dashboard
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Real-time telemetry from low-level Python TCP & UDP socket servers.
          </p>
        </div>

        <button
          onClick={handleManualRefresh}
          className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-800 hover:bg-dark-850 text-slate-300 text-xs font-medium transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-brand-400' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Metrics Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* TCP Connections */}
        <div className="bg-dark-900 border border-dark-800 rounded-2xl p-5 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider">Active TCP Sockets</span>
            <div className="p-2 rounded-xl bg-brand-500/10 text-brand-400">
              <Server className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-white">
            {tcp.active_connections ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-2 flex items-center gap-1.5 font-mono">
            <span>Port {tcp.port || 8888}</span>
            <span>•</span>
            <span className="text-emerald-400">Reliable Stream</span>
          </p>
        </div>

        {/* UDP Online Presence */}
        <div className="bg-dark-900 border border-dark-800 rounded-2xl p-5 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider">UDP Online Registry</span>
            <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
              <Radio className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-white">
            {udp.online_users_count ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-2 flex items-center gap-1.5 font-mono">
            <span>Port {udp.port || 8889}</span>
            <span>•</span>
            <span className="text-emerald-400">{udp.total_heartbeats ?? 0} Heartbeats</span>
          </p>
        </div>

        {/* Total Packets / Messages */}
        <div className="bg-dark-900 border border-dark-800 rounded-2xl p-5 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider">Packets Exchanged</span>
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <Zap className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-white">
            {aggregate.total_network_packets ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-2 flex items-center gap-1.5">
            <span className="font-mono text-slate-300">{tcp.total_messages_relayed || 0} TCP</span>
            <span>+</span>
            <span className="font-mono text-slate-300">{(udp.total_datagrams_received || 0) + (udp.total_datagrams_sent || 0)} UDP</span>
          </p>
        </div>

        {/* Total Data Transferred */}
        <div className="bg-dark-900 border border-dark-800 rounded-2xl p-5 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Throughput</span>
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400">
              <HardDrive className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-white">
            {formatBytes(aggregate.total_bytes_transferred)}
          </div>
          <p className="text-[11px] text-slate-400 mt-2 flex items-center gap-1 font-mono">
            <Clock className="w-3 h-3 text-slate-500" />
            <span>Uptime: {formatUptime(aggregate.server_uptime_seconds)}</span>
          </p>
        </div>
      </div>

      {/* Layer Statistics Comparison */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* TCP Engine Status */}
        <div className="bg-dark-900 border border-dark-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-dark-800 pb-3">
            <div className="flex items-center space-x-2.5">
              <div className="w-3 h-3 rounded-full bg-brand-500" />
              <h3 className="font-bold text-white text-base">TCP Socket Engine</h3>
            </div>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
              SOCK_STREAM
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs font-mono">
            <div className="bg-dark-950/60 p-3 rounded-xl border border-dark-800/80">
              <span className="text-slate-400 block mb-1">Messages Relayed</span>
              <span className="text-white text-base font-bold">{tcp.total_messages_relayed ?? 0}</span>
            </div>
            <div className="bg-dark-950/60 p-3 rounded-xl border border-dark-800/80">
              <span className="text-slate-400 block mb-1">Total Connections Served</span>
              <span className="text-white text-base font-bold">{tcp.total_connections_served ?? 0}</span>
            </div>
            <div className="bg-dark-950/60 p-3 rounded-xl border border-dark-800/80">
              <span className="text-slate-400 block mb-1">Bytes Received</span>
              <span className="text-emerald-400 text-sm font-semibold">{formatBytes(tcp.total_bytes_received)}</span>
            </div>
            <div className="bg-dark-950/60 p-3 rounded-xl border border-dark-800/80">
              <span className="text-slate-400 block mb-1">Bytes Sent</span>
              <span className="text-indigo-400 text-sm font-semibold">{formatBytes(tcp.total_bytes_sent)}</span>
            </div>
          </div>
        </div>

        {/* UDP Engine Status */}
        <div className="bg-dark-900 border border-dark-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-dark-800 pb-3">
            <div className="flex items-center space-x-2.5">
              <div className="w-3 h-3 rounded-full bg-emerald-500" />
              <h3 className="font-bold text-white text-base">UDP Datagram Engine</h3>
            </div>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
              SOCK_DGRAM
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs font-mono">
            <div className="bg-dark-950/60 p-3 rounded-xl border border-dark-800/80">
              <span className="text-slate-400 block mb-1">Heartbeats Received</span>
              <span className="text-white text-base font-bold">{udp.total_heartbeats ?? 0}</span>
            </div>
            <div className="bg-dark-950/60 p-3 rounded-xl border border-dark-800/80">
              <span className="text-slate-400 block mb-1">Typing Notifications</span>
              <span className="text-white text-base font-bold">{udp.total_typing_events ?? 0}</span>
            </div>
            <div className="bg-dark-950/60 p-3 rounded-xl border border-dark-800/80">
              <span className="text-slate-400 block mb-1">Datagrams Sent/Recv</span>
              <span className="text-slate-200 text-sm font-semibold">
                {udp.total_datagrams_received || 0} / {udp.total_datagrams_sent || 0}
              </span>
            </div>
            <div className="bg-dark-950/60 p-3 rounded-xl border border-dark-800/80">
              <span className="text-slate-400 block mb-1">Malformed Packets Dropped</span>
              <span className="text-rose-400 text-sm font-semibold">{udp.dropped_malformed_packets ?? 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Real-Time Network Packet Event Log */}
      <div className="bg-dark-900 border border-dark-800 rounded-2xl p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-dark-800 pb-4">
          <div>
            <h3 className="font-bold text-white text-base">Live Packet Event Stream</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Auditing socket calls, handshakes, message relays, and UDP heartbeats.
            </p>
          </div>

          {/* Protocol Filter Pills */}
          <div className="flex space-x-1.5">
            {['ALL', 'TCP', 'UDP'].map((proto) => (
              <button
                key={proto}
                onClick={() => setFilterProtocol(proto)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  filterProtocol === proto
                    ? 'bg-brand-600 text-white'
                    : 'bg-dark-800 text-slate-400 hover:text-slate-200 hover:bg-dark-700'
                }`}
              >
                {proto}
              </button>
            ))}
          </div>
        </div>

        {/* Logs Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-dark-800 text-slate-400">
                <th className="py-2.5 px-3">Time</th>
                <th className="py-2.5 px-3">Protocol</th>
                <th className="py-2.5 px-3">Event</th>
                <th className="py-2.5 px-3">Client Endpoint</th>
                <th className="py-2.5 px-3">Bytes</th>
                <th className="py-2.5 px-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-800/40 text-slate-300">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-500">
                    No network events recorded yet.
                  </td>
                </tr>
              ) : (
                logs.map((log) => {
                  const isTcp = log.protocol === 'TCP';
                  return (
                    <tr key={log.id} className="hover:bg-dark-850/50 transition-colors">
                      <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                        {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            isTcp
                              ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30'
                              : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          }`}
                        >
                          {log.protocol}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-slate-200">
                        {log.event_type}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {log.client_ip}:{log.client_port || 0}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">
                        {log.bytes_transferred ? formatBytes(log.bytes_transferred) : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 max-w-xs truncate">
                        {log.details || '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
