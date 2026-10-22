import { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, 
  Plus, 
  Trash2, 
  Clock, 
  ChevronDown, 
  Search, 
  Sparkles,
  Check
} from 'lucide-react';
import type { Session } from '../../types';

interface SessionHistoryProps {
  sessions: Session[];
  activeSession: Session | null;
  onSelectSession: (session: Session) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  disabled?: boolean;
}

export default function SessionHistory({
  sessions,
  activeSession,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  disabled = false,
}: SessionHistoryProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const filteredSessions = sessions.filter((s) =>
    (s.title || 'New Chat').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffHours = diffMs / (1000 * 60 * 60);

      if (diffHours < 24 && now.getDate() === d.getDate()) {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } else if (diffHours < 48) {
        return 'Yesterday';
      } else {
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
      }
    } catch {
      return '';
    }
  };

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setDeletingId(sessionId);
    try {
      await onDeleteSession(sessionId);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="relative flex items-center gap-2" ref={menuRef}>
      {/* Session Switcher Trigger */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen(!isOpen)}
        className="h-8 px-3 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-xs text-zinc-300 hover:text-white flex items-center gap-2 transition-all disabled:opacity-40 font-mono shadow-sm group"
        title="View chat history for this repository"
      >
        <MessageSquare size={13} className="text-zinc-400 group-hover:text-cyan-400 transition-colors" />
        <span className="max-w-[140px] sm:max-w-[190px] truncate font-medium">
          {activeSession?.title || 'New Chat'}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-400 border border-white/5">
          {sessions.length} {sessions.length === 1 ? 'chat' : 'chats'}
        </span>
        <ChevronDown
          size={12}
          className={`text-zinc-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Quick "+ New Chat" Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          onNewChat();
          setIsOpen(false);
        }}
        className="h-8 px-2.5 sm:px-3 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] border border-white/15 text-xs text-white flex items-center gap-1.5 font-medium transition-all shadow-sm hover:border-white/30 active:scale-95 disabled:opacity-40"
        title="Start a fresh chat conversation"
      >
        <Plus size={13} />
        <span className="hidden sm:inline text-[11px] font-mono">New Chat</span>
      </button>

      {/* Popover Dropdown */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-xl bg-[#0c0c12]/95 border border-white/15 backdrop-blur-2xl shadow-2xl z-50 p-3 space-y-2.5 animate-in fade-in zoom-in-95 duration-150">
          
          {/* Header */}
          <div className="flex items-center justify-between px-1 pb-1 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Sparkles size={13} className="text-cyan-400" />
              <span className="text-xs font-semibold text-white tracking-tight">Repository Chats</span>
              <span className="text-[10px] font-mono text-zinc-500">({sessions.length})</span>
            </div>

            <button
              onClick={() => {
                onNewChat();
                setIsOpen(false);
              }}
              className="text-[11px] font-mono px-2 py-1 rounded-md bg-white/[0.08] hover:bg-white/[0.16] text-white flex items-center gap-1 transition-all border border-white/10"
            >
              <Plus size={11} />
              <span>New</span>
            </button>
          </div>

          {/* Search bar if > 3 sessions */}
          {sessions.length > 3 && (
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-2.5 text-zinc-500" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search chat history..."
                className="w-full pl-7 pr-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/10 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/25 font-mono"
              />
            </div>
          )}

          {/* Session List */}
          <div className="max-h-72 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
            {filteredSessions.length === 0 ? (
              <div className="text-center py-6 text-xs text-zinc-500 font-mono">
                {searchTerm ? 'No matching chats found.' : 'No saved chats yet. Start asking questions below!'}
              </div>
            ) : (
              filteredSessions.map((session) => {
                const isActive = activeSession?.id === session.id;
                return (
                  <div
                    key={session.id}
                    onClick={() => {
                      onSelectSession(session);
                      setIsOpen(false);
                    }}
                    className={`group relative flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-all border ${
                      isActive
                        ? 'bg-white/[0.09] border-white/20 text-white shadow-sm'
                        : 'bg-white/[0.02] hover:bg-white/[0.06] border-transparent hover:border-white/10 text-zinc-300 hover:text-white'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1 pr-2">
                      <div
                        className={`w-2 h-2 rounded-full shrink-0 ${
                          isActive ? 'bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.6)]' : 'bg-zinc-600'
                        }`}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium truncate font-sans">
                          {session.title || 'New Chat'}
                        </p>
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono mt-0.5">
                          <span className="flex items-center gap-1">
                            <Clock size={10} />
                            {formatDate(session.updated_at || session.created_at)}
                          </span>
                          <span>•</span>
                          <span>{session.message_count ?? 0} msgs</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      {isActive && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/40 mr-1">
                          Active
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={(e) => handleDelete(e, session.id)}
                        disabled={deletingId === session.id}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-zinc-500 hover:text-rose-400 hover:bg-rose-950/30 transition-all"
                        title="Delete this chat"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer note */}
          <div className="pt-2 border-t border-white/[0.05] text-[10px] text-zinc-500 font-mono text-center">
            All chats for this repository are automatically preserved.
          </div>

        </div>
      )}
    </div>
  );
}
