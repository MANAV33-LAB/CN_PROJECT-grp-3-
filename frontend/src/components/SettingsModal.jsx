import React, { useState } from 'react';
import { X, Volume2, VolumeX, Shield, Radio, Server, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useSocket } from '../context/SocketContext';

export default function SettingsModal({ onClose }) {
  const { user, updateProfile } = useAuth();
  const { soundEnabled, setSoundEnabled } = useSocket();

  const [displayName, setDisplayName] = useState(user?.display_name || '');
  const [bio, setBio] = useState(user?.bio || '');
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url || '');
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateProfile({
        display_name: displayName,
        bio: bio,
        avatar_url: avatarUrl
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2000);
    } catch (err) {
      alert(`Update failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-dark-900 border border-dark-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl animate-fadeIn">
        {/* Header */}
        <div className="p-5 border-b border-dark-800 flex items-center justify-between">
          <h3 className="font-bold text-white text-base">User & Network Settings</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSave} className="p-6 space-y-5">
          {/* Display Name */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Display Name
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full bg-dark-850 border border-dark-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-brand-500"
              required
            />
          </div>

          {/* Bio */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Bio / Status Message
            </label>
            <input
              type="text"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              className="w-full bg-dark-850 border border-dark-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Avatar URL */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Avatar URL
            </label>
            <input
              type="text"
              value={avatarUrl}
              onChange={(e) => setAvatarUrl(e.target.value)}
              className="w-full bg-dark-850 border border-dark-800 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Audio Chime Notification Toggle */}
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-dark-950/60 border border-dark-800">
            <div className="flex items-center space-x-3">
              {soundEnabled ? (
                <Volume2 className="w-5 h-5 text-brand-400" />
              ) : (
                <VolumeX className="w-5 h-5 text-slate-500" />
              )}
              <div>
                <p className="text-xs font-semibold text-slate-200">Message Notification Sound</p>
                <p className="text-[10px] text-slate-400">Play chime on incoming TCP messages</p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setSoundEnabled(!soundEnabled)}
              className={`w-11 h-6 rounded-full transition-colors relative ${
                soundEnabled ? 'bg-brand-600' : 'bg-dark-800'
              }`}
            >
              <span
                className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform ${
                  soundEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Network Configuration Summary */}
          <div className="p-3.5 rounded-xl bg-dark-950/60 border border-dark-800 space-y-1.5 text-xs font-mono">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              Low-Level Socket Architecture
            </p>
            <div className="flex justify-between text-slate-300">
              <span>TCP Server Port:</span>
              <span className="text-brand-400 font-bold">8888 (SOCK_STREAM)</span>
            </div>
            <div className="flex justify-between text-slate-300">
              <span>UDP Server Port:</span>
              <span className="text-emerald-400 font-bold">8889 (SOCK_DGRAM)</span>
            </div>
            <div className="flex justify-between text-slate-300">
              <span>UDP Heartbeat Interval:</span>
              <span className="text-slate-400">3 seconds</span>
            </div>
            <div className="flex justify-between text-slate-300">
              <span>UDP Inactivity Timeout:</span>
              <span className="text-slate-400">9 seconds</span>
            </div>
            <div className="flex justify-between text-slate-300">
              <span>TCP Chunk Buffer:</span>
              <span className="text-slate-400">16,384 bytes (16 KB)</span>
            </div>
          </div>

          {/* Footer buttons */}
          <div className="flex items-center justify-end space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition-colors"
            >
              Close
            </button>

            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold flex items-center space-x-1.5 transition-colors shadow-lg shadow-brand-600/20 disabled:opacity-50"
            >
              {savedSuccess ? (
                <>
                  <Check className="w-4 h-4" />
                  <span>Saved!</span>
                </>
              ) : (
                <span>{saving ? 'Saving...' : 'Save Profile'}</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
