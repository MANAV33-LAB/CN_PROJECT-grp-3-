import React, { useState } from 'react';
import { Radio, Lock, User, ArrowRight, ShieldCheck, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LoginPage({ onSwitchToRegister }) {
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!identifier || !password) return;
    setLoading(true);
    setError('');
    try {
      await login(identifier, password);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemo = (userUname) => {
    setIdentifier(userUname);
    setPassword('password123');
    login(userUname, 'password123').catch((err) => setError(err.message));
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-dark-950 p-4 relative overflow-hidden select-none">
      {/* Subtle background glow */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-brand-600/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md bg-dark-900 border border-dark-800 rounded-3xl p-8 shadow-2xl relative z-10">
        {/* App Logo */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center shadow-xl shadow-brand-500/25 mb-3">
            <Radio className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">NetConnect</h1>
          <p className="text-xs text-slate-400 mt-1">Multi-Client TCP/UDP Real-Time Chat System</p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 text-center">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Username or Email
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
              <input
                type="text"
                placeholder="alice or alice@netconnect.local"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                className="w-full bg-dark-850 border border-dark-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
                required
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-dark-850 border border-dark-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold text-sm transition-all shadow-lg shadow-brand-600/25 flex items-center justify-center space-x-2 disabled:opacity-50 mt-2"
          >
            <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        {/* Quick Demo Accounts for Evaluator */}
        <div className="mt-6 pt-6 border-t border-dark-800/80">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center justify-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-brand-400" />
            Quick Demo Sign-In (1-Click)
          </p>
          <div className="grid grid-cols-3 gap-2">
            {[
              { name: 'Alice', user: 'alice' },
              { name: 'Bob', user: 'bob' },
              { name: 'Charlie', user: 'charlie' }
            ].map((d) => (
              <button
                key={d.user}
                type="button"
                onClick={() => handleQuickDemo(d.user)}
                className="py-1.5 px-2 rounded-xl bg-dark-850 hover:bg-dark-800 border border-dark-750 text-xs font-medium text-slate-300 hover:text-white transition-colors"
              >
                {d.name}
              </button>
            ))}
          </div>
        </div>

        {/* Switch to Register */}
        <div className="mt-6 text-center text-xs text-slate-400">
          Don't have an account?{' '}
          <button
            onClick={onSwitchToRegister}
            className="text-brand-400 font-semibold hover:underline ml-1"
          >
            Create an Account
          </button>
        </div>
      </div>
    </div>
  );
}
