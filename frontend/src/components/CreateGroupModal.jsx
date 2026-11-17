import React, { useState, useEffect } from 'react';
import { X, Users, Check, Plus } from 'lucide-react';
import { api } from '../services/api';

export default function CreateGroupModal({ onClose, onGroupCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [users, setUsers] = useState([]);
  const [selectedUserIds, setSelectedUserIds] = useState(new Set());
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.getUsers()
      .then((data) => setUsers(data || []))
      .catch(console.error);
  }, []);

  const toggleUser = (id) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    setCreating(true);
    try {
      const newGroup = await api.createGroup({
        name: name.trim(),
        description: description.trim(),
        initial_member_ids: Array.from(selectedUserIds)
      });
      onGroupCreated?.(newGroup);
      onClose();
    } catch (err) {
      alert(`Failed to create group: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-dark-900 border border-dark-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl animate-fadeIn">
        <div className="p-5 border-b border-dark-800 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-brand-500/10 text-brand-400">
              <Users className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-white text-base">Create Group Channel</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleCreate} className="p-6 space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Group Room Name
            </label>
            <input
              type="text"
              placeholder="e.g. Networks-Study-Group"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-dark-850 border border-dark-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500"
              required
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Description (Optional)
            </label>
            <input
              type="text"
              placeholder="Topic or lab details..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-dark-850 border border-dark-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Member Selection */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2">
              Add Members ({selectedUserIds.size} selected)
            </label>
            <div className="max-h-48 overflow-y-auto space-y-1.5 border border-dark-800 rounded-xl p-2 bg-dark-950/60">
              {users.map((u) => {
                const isSelected = selectedUserIds.has(u.id);
                return (
                  <button
                    type="button"
                    key={u.id}
                    onClick={() => toggleUser(u.id)}
                    className={`w-full p-2 rounded-lg flex items-center justify-between text-left transition-colors ${
                      isSelected
                        ? 'bg-brand-600/20 border border-brand-500/30'
                        : 'hover:bg-dark-800 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5 min-w-0">
                      <img
                        src={u.avatar_url || `https://api.dicebear.com/7.x/bottts/svg?seed=${u.username}`}
                        alt=""
                        className="w-7 h-7 rounded-full bg-dark-800"
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-slate-200 truncate">{u.display_name}</p>
                        <p className="text-[10px] text-slate-500 font-mono">@{u.username}</p>
                      </div>
                    </div>

                    <div
                      className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors ${
                        isSelected
                          ? 'bg-brand-600 border-brand-500 text-white'
                          : 'border-dark-700 bg-dark-900 text-transparent'
                      }`}
                    >
                      <Check className="w-3 h-3" />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-end space-x-3 pt-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating || !name.trim()}
              className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold transition-colors disabled:opacity-50 shadow-lg shadow-brand-600/20"
            >
              {creating ? 'Creating...' : 'Create Group'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
