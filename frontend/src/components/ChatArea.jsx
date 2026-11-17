import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Paperclip,
  Check,
  CheckCheck,
  FileText,
  Download,
  Image as ImageIcon,
  Info,
  Clock,
  ShieldAlert,
  Radio
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useSocket } from '../context/SocketContext';
import { api } from '../services/api';

export default function ChatArea({ activeChat, onToggleRightPanel, isRightPanelOpen }) {
  const { user } = useAuth();
  const {
    addMessageListener,
    sendDirectMessage,
    sendGroupMessage,
    sendTyping,
    sendStatusUpdate,
    onlineUsers,
    typingUsers
  } = useSocket();

  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const typingTimeoutRef = useRef(null);

  // Load message history when activeChat changes
  useEffect(() => {
    if (!activeChat) return;

    async function loadHistory() {
      try {
        let history = [];
        if (activeChat.type === 'user') {
          history = await api.getDirectMessages(activeChat.target.id);
        } else if (activeChat.type === 'group') {
          history = await api.getGroupMessages(activeChat.target.id);
        }
        setMessages(history || []);
      } catch (err) {
        console.error('Failed to load message history:', err);
      }
    }

    loadHistory();
  }, [activeChat]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Listen for live incoming messages and status receipts from WebSocket/TCP gateway
  useEffect(() => {
    const unsubscribe = addMessageListener((payload) => {
      const type = payload.type;

      // New direct message
      if (type === 'CHAT_PRIVATE') {
        if (
          activeChat?.type === 'user' &&
          (payload.sender_id === activeChat.target.id || payload.recipient_id === activeChat.target.id)
        ) {
          setMessages((prev) => {
            // Deduplicate if already present by id or client_msg_id
            if (prev.some((m) => m.id === payload.id || (payload.client_msg_id && m.client_msg_id === payload.client_msg_id))) {
              return prev;
            }
            return [...prev, payload];
          });

          // If incoming to me in active conversation, notify read status
          if (payload.recipient_id === user?.id) {
            sendStatusUpdate(payload.id, 'read');
          }
        }
      }

      // New group message
      else if (type === 'CHAT_GROUP') {
        if (activeChat?.type === 'group' && payload.group_id === activeChat.target.id) {
          setMessages((prev) => {
            if (prev.some((m) => m.id === payload.id || (payload.client_msg_id && m.client_msg_id === payload.client_msg_id))) {
              return prev;
            }
            return [...prev, payload];
          });
        }
      }

      // Message status update (delivered / read)
      else if (type === 'MSG_STATUS') {
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id === payload.message_id || (payload.client_msg_id && m.client_msg_id === payload.client_msg_id)) {
              return {
                ...m,
                status: payload.status,
                delivered_at: payload.delivered_at || m.delivered_at
              };
            }
            return m;
          })
        );
      }
    });

    return unsubscribe;
  }, [activeChat, user, addMessageListener, sendStatusUpdate]);

  const handleInputChange = (e) => {
    setInputText(e.target.value);

    // Emit typing indicator over UDP (throttled)
    if (activeChat) {
      sendTyping(activeChat.type, activeChat.target.id, true);

      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      typingTimeoutRef.current = setTimeout(() => {
        sendTyping(activeChat.type, activeChat.target.id, false);
      }, 2000);
    }
  };

  const handleSendMessage = (e) => {
    e?.preventDefault();
    const content = inputText.trim();
    if (!content || !activeChat) return;

    const clientMsgId = `cli_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const optimisticMessage = {
      id: `temp_${Date.now()}`,
      client_msg_id: clientMsgId,
      sender_id: user.id,
      sender_username: user.username,
      sender_name: user.display_name,
      recipient_id: activeChat.type === 'user' ? activeChat.target.id : null,
      group_id: activeChat.type === 'group' ? activeChat.target.id : null,
      content,
      message_type: 'text',
      status: 'sent',
      created_at: new Date().toISOString()
    };

    // Optimistic UI update
    setMessages((prev) => [...prev, optimisticMessage]);
    setInputText('');

    // Clear typing notice
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    sendTyping(activeChat.type, activeChat.target.id, false);

    // Route over custom TCP socket
    if (activeChat.type === 'user') {
      sendDirectMessage(activeChat.target.id, content, clientMsgId);
    } else if (activeChat.type === 'group') {
      sendGroupMessage(activeChat.target.id, content, clientMsgId);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !activeChat) return;

    setUploading(true);
    setUploadProgress(20);

    const formData = new FormData();
    formData.append('file', file);
    if (activeChat.type === 'user') {
      formData.append('recipient_id', activeChat.target.id);
    } else {
      formData.append('group_id', activeChat.target.id);
    }

    try {
      setUploadProgress(60);
      const res = await api.uploadFile(formData);
      setUploadProgress(100);

      // Add to local message stream
      if (res.message) {
        setMessages((prev) => [...prev, res.message]);
      }
    } catch (err) {
      alert(`File upload failed: ${err.message}`);
    } finally {
      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }, 500);
    }
  };

  if (!activeChat) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-dark-950 p-6 text-center select-none">
        <div className="w-16 h-16 rounded-2xl bg-dark-900 border border-dark-800 flex items-center justify-center mb-4 text-brand-400 shadow-xl">
          <Radio className="w-8 h-8 animate-pulse-slow" />
        </div>
        <h3 className="text-xl font-bold text-white mb-2">Select a Conversation</h3>
        <p className="text-sm text-slate-400 max-w-sm mb-6">
          Choose a contact or group from the sidebar to start exchanging real-time messages and files over low-level TCP sockets.
        </p>
        <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full bg-dark-900 border border-dark-800 text-xs text-slate-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
          <span>TCP Socket 8888 • UDP Socket 8889 Active</span>
        </div>
      </div>
    );
  }

  const isUserOnline =
    activeChat.type === 'user' &&
    (onlineUsers.has(activeChat.target.id) || activeChat.target.is_online);

  const activeTypingUser =
    activeChat.type === 'user'
      ? typingUsers[`user_${user?.id}`]
      : typingUsers[`group_${activeChat.target.id}`];

  return (
    <div className="flex-1 h-full flex flex-col bg-dark-950 min-w-0">
      {/* Header */}
      <div className="h-16 px-6 border-b border-dark-800 flex items-center justify-between bg-dark-950/80 backdrop-blur shrink-0">
        <div className="flex items-center space-x-3.5 min-w-0">
          <div className="relative">
            <img
              src={
                activeChat.target.avatar_url ||
                (activeChat.type === 'user'
                  ? `https://api.dicebear.com/7.x/bottts/svg?seed=${activeChat.target.username}`
                  : `https://api.dicebear.com/7.x/identicon/svg?seed=${activeChat.target.name}`)
              }
              alt=""
              className={`w-10 h-10 ${activeChat.type === 'user' ? 'rounded-full' : 'rounded-xl'} bg-dark-800 border border-dark-700 object-cover`}
            />
            {activeChat.type === 'user' && (
              <span
                className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-dark-950 ${
                  isUserOnline ? 'bg-emerald-500' : 'bg-slate-600'
                }`}
              />
            )}
          </div>

          <div className="min-w-0">
            <div className="flex items-center space-x-2">
              <h2 className="font-semibold text-slate-100 truncate text-base">
                {activeChat.type === 'user' ? activeChat.target.display_name : activeChat.target.name}
              </h2>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-dark-800 text-slate-400 border border-dark-700">
                {activeChat.type === 'user' ? `TCP Direct` : `TCP Group`}
              </span>
            </div>
            <p className="text-xs text-slate-400 truncate">
              {activeChat.type === 'user'
                ? isUserOnline
                  ? 'Connected • UDP Heartbeat Active'
                  : 'Offline • Messages will be queued over TCP'
                : `${activeChat.target.member_count || 1} members connected`}
            </p>
          </div>
        </div>

        <button
          onClick={onToggleRightPanel}
          className={`p-2 rounded-lg transition-colors ${
            isRightPanelOpen
              ? 'bg-brand-600/20 text-brand-400'
              : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800'
          }`}
          title="Toggle Details Panel"
        >
          <Info className="w-5 h-5" />
        </button>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
            <p className="text-sm">No messages exchanged yet.</p>
            <p className="text-xs text-slate-600 mt-1">Send a message to initiate reliable TCP transmission.</p>
          </div>
        ) : (
          messages.map((m) => {
            const isMe = m.sender_id === user.id;

            return (
              <div key={m.id || m.client_msg_id} className={`flex flex-col ${isMe ? 'items-end' : 'items-start'}`}>
                {/* Sender name for groups */}
                {!isMe && activeChat.type === 'group' && (
                  <span className="text-[11px] text-slate-400 font-medium ml-1 mb-1">
                    {m.sender_name || m.sender_username}
                  </span>
                )}

                <div
                  className={`max-w-[70%] rounded-2xl px-4 py-2.5 shadow-sm text-sm break-words ${
                    isMe
                      ? 'bg-brand-600 text-white rounded-br-none'
                      : 'bg-dark-850 text-slate-200 border border-dark-800 rounded-bl-none'
                  }`}
                >
                  {/* File Attachment Rendering */}
                  {m.message_type === 'file' && m.file && (
                    <div className="mb-2 p-3 rounded-xl bg-dark-950/40 border border-white/10 flex items-center space-x-3">
                      {m.file.mime_type?.startsWith('image/') ? (
                        <div className="w-12 h-12 rounded-lg overflow-hidden bg-dark-900 shrink-0">
                          <img
                            src={m.file.download_url}
                            alt={m.file.original_name}
                            className="w-full h-full object-cover"
                          />
                        </div>
                      ) : (
                        <div className="w-10 h-10 rounded-lg bg-brand-500/20 text-brand-300 flex items-center justify-center shrink-0">
                          <FileText className="w-5 h-5" />
                        </div>
                      )}

                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-xs truncate">{m.file.original_name}</p>
                        <p className="text-[10px] text-slate-400">
                          {(m.file.file_size / 1024).toFixed(1)} KB • TCP Chunked
                        </p>
                      </div>

                      <a
                        href={m.file.download_url}
                        download={m.file.original_name}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 text-slate-200 transition-colors"
                        title="Download file"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    </div>
                  )}

                  {/* Text Content */}
                  <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>

                  {/* Timestamp & Status Icon */}
                  <div
                    className={`flex items-center space-x-1 text-[10px] mt-1 ${
                      isMe ? 'text-brand-200 justify-end' : 'text-slate-400'
                    }`}
                  >
                    <span>
                      {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>

                    {isMe && (
                      <span className="ml-0.5">
                        {m.status === 'read' ? (
                          <CheckCheck className="w-3.5 h-3.5 text-sky-300" title="Read" />
                        ) : m.status === 'delivered' ? (
                          <CheckCheck className="w-3.5 h-3.5 text-brand-200" title="Delivered" />
                        ) : (
                          <Check className="w-3.5 h-3.5 text-brand-300" title="Sent (TCP Relay)" />
                        )}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Typing Indicator Banner */}
      {activeTypingUser && (
        <div className="px-6 py-1.5 bg-dark-900/60 border-t border-dark-800/60 text-xs text-brand-400 italic flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-brand-400 animate-ping" />
          <span>{activeTypingUser} is typing via UDP...</span>
        </div>
      )}

      {/* Upload Progress Bar */}
      {uploading && (
        <div className="px-6 py-2 bg-dark-900 border-t border-dark-800">
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>Streaming chunked TCP file transfer...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-dark-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-brand-500 h-full transition-all duration-300 rounded-full"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Input Bar */}
      <form onSubmit={handleSendMessage} className="p-4 border-t border-dark-800 bg-dark-900/50 flex items-center space-x-3">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          className="hidden"
        />

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="p-2.5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-dark-800 transition-colors shrink-0"
          title="Attach file (TCP stream)"
        >
          <Paperclip className="w-5 h-5" />
        </button>

        <input
          type="text"
          placeholder={`Message ${activeChat.type === 'user' ? `@${activeChat.target.username}` : `#${activeChat.target.name}`}...`}
          value={inputText}
          onChange={handleInputChange}
          className="flex-1 bg-dark-850 border border-dark-800 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
        />

        <button
          type="submit"
          disabled={!inputText.trim()}
          className="p-3 rounded-xl bg-brand-600 hover:bg-brand-500 disabled:opacity-40 disabled:hover:bg-brand-600 text-white font-medium transition-colors shadow-lg shadow-brand-600/20 shrink-0"
          title="Send message (TCP)"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
