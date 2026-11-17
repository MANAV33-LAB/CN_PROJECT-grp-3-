const API_BASE = '/api';

export function getToken() {
  return localStorage.getItem('netconnect_token');
}

export function setToken(token) {
  if (token) {
    localStorage.setItem('netconnect_token', token);
  } else {
    localStorage.removeItem('netconnect_token');
  }
}

async function request(endpoint, options = {}) {
  const token = getToken();
  const headers = {
    ...options.headers,
  };

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // Unauthorized
    setToken(null);
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg = data?.detail || data?.error || 'Request failed';
    throw new Error(errorMsg);
  }

  return data;
}

export const api = {
  // Auth
  register: (payload) => request('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload) => request('/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  getMe: () => request('/auth/me'),
  updateProfile: (payload) => request('/auth/profile', { method: 'PUT', body: JSON.stringify(payload) }),

  // Users
  getUsers: (search) => request(`/users${search ? `?search=${encodeURIComponent(search)}` : ''}`),
  getUserDetail: (userId) => request(`/users/${userId}`),

  // Conversations
  getConversations: () => request('/conversations'),
  getDirectMessages: (otherUserId) => request(`/conversations/direct/${otherUserId}/messages`),

  // Groups
  getGroups: () => request('/groups'),
  getDiscoverGroups: () => request('/groups/discover'),
  createGroup: (payload) => request('/groups', { method: 'POST', body: JSON.stringify(payload) }),
  getGroupDetails: (groupId) => request(`/groups/${groupId}`),
  getGroupMessages: (groupId) => request(`/groups/${groupId}/messages`),
  joinGroup: (groupId) => request(`/groups/${groupId}/join`, { method: 'POST' }),
  leaveGroup: (groupId) => request(`/groups/${groupId}/leave`, { method: 'POST' }),

  // Files
  uploadFile: (formData) => request('/files/upload', { method: 'POST', body: formData }),

  // Network Monitoring
  getNetworkStats: () => request('/network/stats'),
  getNetworkLogs: (limit = 50, protocol = null) =>
    request(`/network/logs?limit=${limit}${protocol ? `&protocol=${protocol}` : ''}`),
  simulateComparison: (payload) =>
    request('/network/simulate-comparison', { method: 'POST', body: JSON.stringify(payload) }),
};
