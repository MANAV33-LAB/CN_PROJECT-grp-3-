import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { useAuth } from './AuthContext';

const SocketContext = createContext(null);

export function SocketProvider({ children }) {
  const { user, token } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [onlineUsers, setOnlineUsers] = useState(new Set());
  const [typingUsers, setTypingUsers] = useState({}); // { "user_12": "Alice", "group_5": "Bob" }
  const [soundEnabled, setSoundEnabled] = useState(true);

  const wsRef = useRef(null);
  const eventListenersRef = useRef(new Set());
  const typingTimersRef = useRef({});

  // Web Audio Chime generator
  const playNotificationSound = () => {
    if (!soundEnabled) return;
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880.00, ctx.currentTime + 0.15); // A5

      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
      // Audio autoplay policy
    }
  };

  useEffect(() => {
    if (!token || !user) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
      return;
    }

    let reconnectTimer;
    let isMounted = true;

    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/${token}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted) return;
        setIsConnected(true);
        console.log('[Socket] Connected & bridged to TCP/UDP socket servers');
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          handleIncomingMessage(payload);
        } catch (err) {
          console.error('[Socket] Failed to parse message:', err);
        }
      };

      ws.onclose = () => {
        if (!isMounted) return;
        setIsConnected(false);
        console.log('[Socket] Connection closed. Reconnecting in 3s...');
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.warn('[Socket] WebSocket error:', err);
        ws.close();
      };
    }

    connect();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [token, user]);

  const handleIncomingMessage = (payload) => {
    const type = payload.type;

    // UDP Presence update
    if (type === 'PRESENCE_CHANGE') {
      const data = payload.data;
      setOnlineUsers((prev) => {
        const next = new Set(prev);
        if (data.is_online) {
          next.add(data.user_id);
        } else {
          next.delete(data.user_id);
        }
        return next;
      });
    }

    // UDP Typing notification
    else if (type === 'TYPING') {
      const data = payload.data;
      const key = `${data.target_type}_${data.target_id}`;

      if (data.is_typing) {
        setTypingUsers((prev) => ({ ...prev, [key]: data.username }));

        // Clear existing timer for this key
        if (typingTimersRef.current[key]) {
          clearTimeout(typingTimersRef.current[key]);
        }
        // Auto-remove typing indicator after 3.5s
        typingTimersRef.current[key] = setTimeout(() => {
          setTypingUsers((prev) => {
            const next = { ...prev };
            delete next[key];
            return next;
          });
        }, 3500);
      } else {
        setTypingUsers((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }
    }

    // TCP Chat message arrival (Private or Group)
    else if (type === 'CHAT_PRIVATE' || type === 'CHAT_GROUP') {
      playNotificationSound();
    }

    // Dispatch to registered UI listeners
    eventListenersRef.current.forEach((listener) => {
      try {
        listener(payload);
      } catch (err) {
        console.error('Listener callback error:', err);
      }
    });
  };

  const addMessageListener = (listener) => {
    eventListenersRef.current.add(listener);
    return () => eventListenersRef.current.delete(listener);
  };

  const sendDirectMessage = (recipientId, content, clientMsgId) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        action: 'chat_private',
        recipient_id: recipientId,
        content,
        client_msg_id: clientMsgId || `msg_${Date.now()}`
      })
    );
  };

  const sendGroupMessage = (groupId, content, clientMsgId) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        action: 'chat_group',
        group_id: groupId,
        content,
        client_msg_id: clientMsgId || `grp_${Date.now()}`
      })
    );
  };

  const sendTyping = (targetType, targetId, isTyping) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        action: 'typing',
        target_type: targetType,
        target_id: targetId,
        is_typing: isTyping
      })
    );
  };

  const sendStatusUpdate = (messageId, status) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        action: 'msg_status',
        message_id: messageId,
        status: status
      })
    );
  };

  return (
    <SocketContext.Provider
      value={{
        isConnected,
        onlineUsers,
        typingUsers,
        soundEnabled,
        setSoundEnabled,
        addMessageListener,
        sendDirectMessage,
        sendGroupMessage,
        sendTyping,
        sendStatusUpdate
      }}
    >
      {children}
    </SocketContext.Provider>
  );
}

export function useSocket() {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error('useSocket must be used within a SocketProvider');
  }
  return context;
}
