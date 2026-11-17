import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, getToken, setToken } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setTokenState] = useState(getToken());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadUser() {
      const storedToken = getToken();
      if (!storedToken) {
        setLoading(false);
        return;
      }
      try {
        const userData = await api.getMe();
        setUser(userData);
      } catch (err) {
        console.error('Failed to restore session:', err);
        setToken(null);
        setTokenState(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, []);

  const login = async (usernameOrEmail, password) => {
    const res = await api.login({ username_or_email: usernameOrEmail, password });
    setToken(res.access_token);
    setTokenState(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const register = async (username, email, password, displayName) => {
    const res = await api.register({
      username,
      email,
      password,
      display_name: displayName
    });
    setToken(res.access_token);
    setTokenState(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const logout = () => {
    setToken(null);
    setTokenState(null);
    setUser(null);
  };

  const updateProfile = async (updates) => {
    const updated = await api.updateProfile(updates);
    setUser(updated);
    return updated;
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
