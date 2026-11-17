import React, { useState, useEffect } from 'react';
import {
  X,
  FileText,
  Download,
  Shield,
  Activity,
  Calendar,
  Layers,
  Radio,
  Users
} from 'lucide-react';
import { useSocket } from '../context/SocketContext';
import { api } from '../services/api';

export default function RightPanel({ activeChat, onClose }) {
  const { onlineUsers } = useSocket();
  const [groupDetails, setGroupDetails] = useState(null);

  useEffect(() => {
    if (activeChat?.type === 'group') {
      api.getGroupDetails(activeChat.target.id)
        .then(setGroupDetails)
        .catch(console.error);
    }
  }, [activeChat]);

  if (!activeChat) return null;

  const isUser = activeChat.type === 'user';
  const target = activeChat.target;
  const isOnline = isUser && (onlineUsers.has(target.id) || target.is_online);

  return (
    <aside className="w-80 h-full bg-dark-900 border-l border-dark-800 flex flex-col select-none shrink-0 overflow-y-auto">
      {/* Header */}
      <div className="p-4 border-b border-dark-800 flex items-center justify-between">
        <h3 className="font-semibold text-sm text-slate-200">
          {isUser ? 'Contact Details' : 'Group Information'}
        </h3>
        <button
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Profile Overview */}
      <div className="p-6 flex flex-col items-center text-center border-b border-dark-800">
        <div className="relative mb-3">
          <img
            src={
              target.avatar_url ||
              (isUser
                ? `https://api.dicebear.com/7.x/bottts/svg?seed=${target.username}`
                : `https://api.dicebear.com/7.x/identicon/svg?seed=${target.name}`)
            }
            alt=""
            className={`w-20 h-20 ${isUser ? 'rounded-full' : 'rounded-2xl'} bg-dark-800 border-2 border-dark-700 object-cover`}
          />
          {isUser && (
            <span
              className={`absolute bottom-1 right-1 w-4 h-4 rounded-full border-2 border-dark-900 ${
                isOnline ? 'bg-emerald-500 shadow-md shadow-emerald-500/50' : 'bg-slate-600'
              }`}
            />
          )}
        </div>

        <h4 className="font-bold text-base text-slate-100">{isUser ? target.display_name : target.name}</h4>
        <p className="text-xs text-slate-400 font-mono mt-0.5">
          {isUser ? `@${target.username}` : `Room ID: ${target.id}`}
        </p>

        <p className="text-xs text-slate-300 mt-3 px-2">
          {isUser ? target.bio || 'Hey there! I am using NetConnect.' : target.description || 'TCP/UDP Broadcast Room'}
        </p>
      </div>

      {/* Network Socket Metadata */}
      <div className="p-4 border-b border-dark-800 space-y-3">
        <h5 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          Networking Layer
        </h5>

        <div className="bg-dark-950/60 rounded-xl p-3 border border-dark-800 space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Reliable Messaging:</span>
            <span className="text-brand-400 font-mono font-medium">TCP Port 8888</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Heartbeat / Presence:</span>
            <span className="text-emerald-400 font-mono font-medium">UDP Port 8889</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Framing Protocol:</span>
            <span className="text-slate-300 font-mono">4-Byte Prefix + JSON</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Connection State:</span>
            <span className={`font-medium ${isOnline ? 'text-emerald-400' : 'text-slate-400'}`}>
              {isUser ? (isOnline ? 'Connected' : 'Offline (Queued)') : 'Active Room'}
            </span>
          </div>
        </div>
      </div>

      {/* Group Members List (If Group Chat) */}
      {!isUser && groupDetails && (
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h5 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Room Members ({groupDetails.members?.length || 0})
            </h5>
          </div>

          <div className="space-y-1.5">
            {groupDetails.members?.map((m) => {
              const u = m.user;
              if (!u) return null;
              const uOnline = onlineUsers.has(u.id) || u.is_online;

              return (
                <div
                  key={m.id}
                  className="p-2 rounded-xl bg-dark-950/40 border border-dark-800/60 flex items-center justify-between"
                >
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <div className="relative">
                      <img
                        src={u.avatar_url || `https://api.dicebear.com/7.x/bottts/svg?seed=${u.username}`}
                        alt=""
                        className="w-7 h-7 rounded-full bg-dark-800 border border-dark-700"
                      />
                      <span
                        className={`absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full border border-dark-900 ${
                          uOnline ? 'bg-emerald-500' : 'bg-slate-600'
                        }`}
                      />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-slate-200 truncate">{u.display_name}</p>
                      <p className="text-[10px] text-slate-500 font-mono">@{u.username}</p>
                    </div>
                  </div>

                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-dark-800 text-slate-400 font-medium">
                    {m.role}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </aside>
  );
}
