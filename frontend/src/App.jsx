import React, { useState } from 'react';
import { useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import RightPanel from './components/RightPanel';
import NetworkDashboard from './components/NetworkDashboard';
import ProtocolDemo from './components/ProtocolDemo';
import SettingsModal from './components/SettingsModal';
import CreateGroupModal from './components/CreateGroupModal';

export default function App() {
  const { user, loading } = useAuth();
  const [authView, setAuthView] = useState('login'); // 'login' or 'register'

  // Application State
  const [activeTab, setActiveTab] = useState('chats'); // 'chats', 'groups', 'monitor', 'protocol'
  const [activeChat, setActiveChat] = useState(null); // { type: 'user'|'group', target: obj }
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isCreateGroupOpen, setIsCreateGroupOpen] = useState(false);

  if (loading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-dark-950 text-slate-300">
        <div className="w-12 h-12 border-4 border-brand-500/20 border-t-brand-500 rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium">Booting NetConnect Network Layer...</p>
      </div>
    );
  }

  if (!user) {
    return authView === 'login' ? (
      <LoginPage onSwitchToRegister={() => setAuthView('register')} />
    ) : (
      <RegisterPage onSwitchToLogin={() => setAuthView('login')} />
    );
  }

  return (
    <div className="h-screen w-screen flex bg-dark-950 overflow-hidden font-sans">
      {/* Left Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeChat={activeChat}
        setActiveChat={(chat) => {
          setActiveChat(chat);
          if (activeTab === 'monitor' || activeTab === 'protocol') {
            setActiveTab(chat.type === 'user' ? 'chats' : 'groups');
          }
        }}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenCreateGroup={() => setIsCreateGroupOpen(true)}
      />

      {/* Middle Content View */}
      <main className="flex-1 h-full flex flex-col min-w-0 bg-dark-950">
        {(activeTab === 'chats' || activeTab === 'groups') && (
          <ChatArea
            activeChat={activeChat}
            onToggleRightPanel={() => setIsRightPanelOpen(!isRightPanelOpen)}
            isRightPanelOpen={isRightPanelOpen}
          />
        )}

        {activeTab === 'monitor' && <NetworkDashboard />}

        {activeTab === 'protocol' && <ProtocolDemo />}
      </main>

      {/* Right Details Panel */}
      {(activeTab === 'chats' || activeTab === 'groups') && activeChat && isRightPanelOpen && (
        <RightPanel
          activeChat={activeChat}
          onClose={() => setIsRightPanelOpen(false)}
        />
      )}

      {/* Modals */}
      {isSettingsOpen && <SettingsModal onClose={() => setIsSettingsOpen(false)} />}
      {isCreateGroupOpen && (
        <CreateGroupModal
          onClose={() => setIsCreateGroupOpen(false)}
          onGroupCreated={(newGroup) => {
            setActiveTab('groups');
            setActiveChat({ type: 'group', target: newGroup });
          }}
        />
      )}
    </div>
  );
}
