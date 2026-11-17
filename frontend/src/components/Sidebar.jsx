import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  Users,
  Activity,
  Layers,
  Settings,
  LogOut,
  Search,
  Plus,
  Radio,
  CheckCheck,
  Circle
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useSocket } from '../context/SocketContext';
import { api } from '../services/api';

export default function Sidebar({
  activeTab,
  setActiveTab,
  activeChat,
  setActiveChat,
  onOpenSettings,
  onOpenCreateGroup
}) {
  const { user, logout } = useAuth();
  const { isConnected, onlineUsers, typingUsers } = useSocket();

  const [conversations, setConversations] = useState([]);
  const [groups, setGroups] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);

  // Load conversations & groups
  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [convs, grps, usersList] = await Promise.all([
        api.getConversations(),
        api.getGroups(),
        api.getUsers()
      ]);
      setConversations(convs || []);
      setGroups(grps || []);
      setAllUsers(usersList || []);
    } catch (err) {
      console.error('Failed loading sidebar data:', err);
    }
  };

  // Filtered lists
  const filteredUsers = allUsers.filter(u =>
    u.display_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.username.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredGroups = groups.filter(g =>
    g.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside className="w-80 h-full bg-dark-900 border-r border-dark-800 flex flex-col select-none shrink-0">
      {/* Brand Header */}
      <div className="p-4 border-b border-dark-800 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Radio className="w-5 h-5 text-white animate-pulse-slow" />
          </div>
          <div>
            <h1 className="font-bold text-lg text-white tracking-tight flex items-center gap-1.5">
              NetConnect
              <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-400 border border-brand-500/30">
                TCP/UDP
              </span>
            </h1>
            <p className="text-xs text-slate-400">Course Project v1.0</p>
          </div>
        </div>

        {/* Network Connection Pill */}
        <div
          title={isConnected ? 'Connected to TCP & UDP servers' : 'Connecting to network sockets...'}
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors ${
            isConnected
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
              : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
          <span>{isConnected ? 'ONLINE' : 'CONNECTING'}</span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="px-3 pt-3 flex space-x-1 border-b border-dark-800/60 pb-2">
        <button
          onClick={() => setActiveTab('chats')}
          className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center space-x-1.5 transition-all ${
            activeTab === 'chats'
              ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800/40'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>Chats</span>
        </button>

        <button
          onClick={() => setActiveTab('groups')}
          className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center space-x-1.5 transition-all ${
            activeTab === 'groups'
              ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800/40'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>Groups</span>
        </button>

        <button
          onClick={() => setActiveTab('monitor')}
          className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center space-x-1.5 transition-all ${
            activeTab === 'monitor'
              ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800/40'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>Monitor</span>
        </button>

        <button
          onClick={() => setActiveTab('protocol')}
          className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center space-x-1.5 transition-all ${
            activeTab === 'protocol'
              ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800/40'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Demo</span>
        </button>
      </div>

      {/* Search Bar */}
      {(activeTab === 'chats' || activeTab === 'groups') && (
        <div className="p-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder={activeTab === 'chats' ? 'Search contacts...' : 'Search rooms...'}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-dark-800/70 border border-dark-700/60 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
            />
          </div>
        </div>
      )}

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {activeTab === 'chats' && (
          <div>
            <div className="px-2 py-1 flex items-center justify-between text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <span>Direct Messages</span>
              <span className="bg-dark-800 px-1.5 py-0.5 rounded text-[10px] text-slate-400">
                {allUsers.length}
              </span>
            </div>

            {filteredUsers.length === 0 ? (
              <p className="text-xs text-slate-500 px-3 py-4 text-center">No contacts found</p>
            ) : (
              filteredUsers.map((u) => {
                const isOnline = onlineUsers.has(u.id) || u.is_online;
                const isSelected = activeChat?.type === 'user' && activeChat?.target?.id === u.id;
                const isTyping = typingUsers[`user_${user?.id}`] === u.username;

                return (
                  <button
                    key={u.id}
                    onClick={() => setActiveChat({ type: 'user', target: u })}
                    className={`w-full p-2.5 rounded-xl flex items-center space-x-3 transition-all text-left ${
                      isSelected
                        ? 'bg-brand-600/15 border border-brand-500/30'
                        : 'hover:bg-dark-800/60 border border-transparent'
                    }`}
                  >
                    <div className="relative">
                      <img
                        src={u.avatar_url || `https://api.dicebear.com/7.x/bottts/svg?seed=${u.username}`}
                        alt={u.username}
                        className="w-10 h-10 rounded-full bg-dark-800 border border-dark-700 object-cover"
                      />
                      <span
                        className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-dark-900 ${
                          isOnline ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-slate-600'
                        }`}
                      />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm text-slate-200 truncate">{u.display_name}</span>
                        <span className="text-[10px] text-slate-500 font-mono">@{u.username}</span>
                      </div>
                      <div className="text-xs text-slate-400 truncate flex items-center gap-1">
                        {isTyping ? (
                          <span className="text-brand-400 italic flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-ping" />
                            typing...
                          </span>
                        ) : (
                          <span>{isOnline ? 'Online via UDP' : 'Offline'}</span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        )}

        {activeTab === 'groups' && (
          <div>
            <div className="px-2 py-1 flex items-center justify-between text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <span>Rooms & Groups</span>
              <button
                onClick={onOpenCreateGroup}
                className="p-1 hover:bg-dark-800 rounded text-brand-400 hover:text-brand-300 transition-colors"
                title="Create Group Room"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>

            {filteredGroups.length === 0 ? (
              <p className="text-xs text-slate-500 px-3 py-4 text-center">No groups joined yet</p>
            ) : (
              filteredGroups.map((g) => {
                const isSelected = activeChat?.type === 'group' && activeChat?.target?.id === g.id;
                return (
                  <button
                    key={g.id}
                    onClick={() => setActiveChat({ type: 'group', target: g })}
                    className={`w-full p-2.5 rounded-xl flex items-center space-x-3 transition-all text-left ${
                      isSelected
                        ? 'bg-brand-600/15 border border-brand-500/30'
                        : 'hover:bg-dark-800/60 border border-transparent'
                    }`}
                  >
                    <img
                      src={g.avatar_url || `https://api.dicebear.com/7.x/identicon/svg?seed=${g.name}`}
                      alt={g.name}
                      className="w-10 h-10 rounded-xl bg-dark-800 border border-dark-700 object-cover"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm text-slate-200 truncate">{g.name}</span>
                        <span className="text-[10px] bg-dark-800 text-slate-400 px-1.5 py-0.5 rounded">
                          {g.member_count || 1} members
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 truncate">
                        {g.description || 'TCP Group Channel'}
                      </p>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        )}

        {activeTab === 'monitor' && (
          <div className="p-3 text-xs text-slate-400 space-y-2">
            <p className="font-semibold text-slate-200">Network Telemetry Engine</p>
            <p>
              Switch between tabs to inspect live socket connections, packet metrics, and low-level protocol statistics.
            </p>
          </div>
        )}

        {activeTab === 'protocol' && (
          <div className="p-3 text-xs text-slate-400 space-y-2">
            <p className="font-semibold text-slate-200">TCP vs UDP Demonstration</p>
            <p>
              Run live interactive packet benchmark simulations comparing reliable TCP byte-streams against lossy UDP datagrams.
            </p>
          </div>
        )}
      </div>

      {/* User Profile Footer */}
      <div className="p-3 border-t border-dark-800 bg-dark-950/60 flex items-center justify-between">
        <div className="flex items-center space-x-2.5 min-w-0">
          <div className="relative">
            <img
              src={user?.avatar_url || `https://api.dicebear.com/7.x/bottts/svg?seed=${user?.username}`}
              alt={user?.username}
              className="w-9 h-9 rounded-full bg-dark-800 border border-dark-700"
            />
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-dark-900" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-200 truncate">{user?.display_name}</p>
            <p className="text-[10px] text-slate-400 truncate font-mono">@{user?.username}</p>
          </div>
        </div>

        <div className="flex items-center space-x-1">
          <button
            onClick={onOpenSettings}
            title="Settings"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition-colors"
          >
            <Settings className="w-4 h-4" />
          </button>
          <button
            onClick={logout}
            title="Log out"
            className="p-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
