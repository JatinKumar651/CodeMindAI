import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import Navbar from '../components/layout/Navbar';
import RepoSelector from '../components/workspace/RepoSelector';
import ChatConsole from '../components/workspace/ChatConsole';
import PromptInput from '../components/workspace/PromptInput';
import SessionHistory from '../components/workspace/SessionHistory';
import { api } from '../services/api';
import { authService } from '../services/auth';
import type { Message, Repository, Session } from '../types';

// Module-level cache to make page transitions instantaneous
let cachedRepos: Repository[] = [];
let cachedSelectedRepo: Repository | null = null;
let cachedSessions: Session[] = [];

export default function WorkspacePage() {
  const [searchParams] = useSearchParams();
  const initialPrompt = searchParams.get('prompt') || '';

  const [repositories, setRepositories] = useState<Repository[]>(cachedRepos);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(cachedSelectedRepo);
  const [sessions, setSessions] = useState<Session[]>(cachedSessions);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync to cache on updates
  useEffect(() => {
    cachedRepos = repositories;
    cachedSelectedRepo = selectedRepo;
    cachedSessions = sessions;
  }, [repositories, selectedRepo, sessions]);

  // Load repositories on mount (stale-while-revalidate)
  useEffect(() => {
    async function loadRepos() {
      try {
        const repos = await api.listRepos();
        const repoList = Array.isArray(repos) ? repos : [];
        setRepositories(repoList);
        cachedRepos = repoList;
        if (repoList.length > 0 && !selectedRepo) {
          const defaultRepo = cachedSelectedRepo || repoList[0];
          setSelectedRepo(defaultRepo);
          cachedSelectedRepo = defaultRepo;
        }
      } catch (err: any) {
        console.warn('Failed to load repositories:', err.message);
        if (!authService.isAuthenticated()) {
          setError('You are viewing the workspace as a guest. Please sign in to save repositories and chat history.');
        }
      }
    }
    loadRepos();
  }, []);

  // Initialize fresh empty session on visit while preserving all past repository chats
  useEffect(() => {
    if (!selectedRepo) {
      setActiveSession(null);
      setSessions([]);
      setMessages([]);
      return;
    }

    const repoId = selectedRepo.id;

    async function initRepoSessions(targetRepoId: string) {
      try {
        const repoSessions = await api.listSessions(targetRepoId);
        const sessionList = Array.isArray(repoSessions) ? repoSessions : [];
        setSessions(sessionList);

        // Every time user logs in / opens the studio: start with a fresh EMPTY chat
        // Check if an existing session is empty (message_count === 0); if so, reuse it
        const emptySession = sessionList.find((s) => (s.message_count ?? 0) === 0);
        if (emptySession) {
          setActiveSession(emptySession);
          setMessages([]);
        } else {
          // All existing chats have messages; create a new empty chat session
          const freshSession = await api.createSession(targetRepoId, 'New Chat');
          setSessions([freshSession, ...sessionList]);
          setActiveSession(freshSession);
          setMessages([]);
        }
      } catch (err: any) {
        console.warn('Failed to load session for repo:', err.message);
        setMessages([]);
      }
    }

    initRepoSessions(repoId);
  }, [selectedRepo?.id]);

  // Live poll repository status whenever any repo is 'pending' or 'processing'
  useEffect(() => {
    const isPending =
      repositories.some((r) => r.status === 'pending' || r.status === 'processing') ||
      selectedRepo?.status === 'pending' ||
      selectedRepo?.status === 'processing';

    if (!isPending) return;

    const interval = setInterval(async () => {
      try {
        const freshRepos = await api.listRepos();
        const repoList = Array.isArray(freshRepos) ? freshRepos : [];
        if (repoList.length > 0) {
          setRepositories(repoList);
          if (selectedRepo) {
            const updated = repoList.find((r) => r.id === selectedRepo.id);
            if (
              updated &&
              (updated.status !== selectedRepo.status ||
                updated.total_chunks !== selectedRepo.total_chunks)
            ) {
              setSelectedRepo(updated);
            }
          }
        }
      } catch (err) {
        // Silent catch for background poll
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [repositories, selectedRepo?.status, selectedRepo?.total_chunks, selectedRepo?.id]);

  // Handle selecting a past chat session from history
  const handleSelectSession = async (session: Session) => {
    setActiveSession(session);
    setLoading(true);
    try {
      const msgs = await api.getMessages(session.id);
      setMessages(Array.isArray(msgs) ? msgs : []);
    } catch (err: any) {
      console.warn('Failed to fetch session messages:', err.message);
      setMessages([]);
    } finally {
      setLoading(false);
    }
  };

  // Start a fresh, empty chat
  const handleNewChat = async () => {
    if (!selectedRepo) return;
    if (activeSession && messages.length === 0) return;

    try {
      const freshSession = await api.createSession(selectedRepo.id, 'New Chat');
      setSessions((prev) => [freshSession, ...prev]);
      setActiveSession(freshSession);
      setMessages([]);
    } catch (err: any) {
      setError('Failed to start new chat: ' + err.message);
    }
  };

  // Delete a chat session
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId);
      const remaining = sessions.filter((s) => s.id !== sessionId);
      setSessions(remaining);

      // If active session was deleted, switch to a new clean chat
      if (activeSession?.id === sessionId) {
        if (selectedRepo) {
          const freshSession = await api.createSession(selectedRepo.id, 'New Chat');
          setSessions([freshSession, ...remaining]);
          setActiveSession(freshSession);
          setMessages([]);
        } else {
          setActiveSession(null);
          setMessages([]);
        }
      }
    } catch (err: any) {
      setError('Failed to delete chat: ' + err.message);
    }
  };

  // Handle auto-send if prompt param provided
  useEffect(() => {
    if (initialPrompt && activeSession && messages.length === 0) {
      handleSendMessage(initialPrompt);
    }
  }, [initialPrompt, activeSession]);

  const handleSendMessage = async (content: string) => {
    if (!selectedRepo) {
      setError('Please select or add a repository before sending messages.');
      return;
    }

    let session = activeSession;
    if (!session) {
      try {
        session = await api.createSession(selectedRepo.id, 'New Chat');
        setActiveSession(session);
        setSessions((prev) => [session!, ...prev]);
      } catch (err: any) {
        setError(err.message || 'Failed to initialize session.');
        return;
      }
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      session_id: session.id,
      role: 'user',
      content,
      citations: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);

    try {
      const aiMsg = await api.sendMessage(session.id, content);
      setMessages((prev) => [...prev, aiMsg]);

      // Refresh sessions list to display updated message count and auto-generated title
      try {
        const updatedSessions = await api.listSessions(selectedRepo.id);
        if (Array.isArray(updatedSessions)) {
          setSessions(updatedSessions);
          const current = updatedSessions.find((s) => s.id === session!.id);
          if (current) setActiveSession(current);
        }
      } catch {}
    } catch (err: any) {
      setError(err.message || 'Failed to send message to backend.');
    } finally {
      setLoading(false);
    }
  };

  const handleIngest = async (repoId: string) => {
    setIngesting(true);
    try {
      await api.ingestRepo(repoId);
      const repos = await api.listRepos();
      setRepositories(repos);
    } catch (err: any) {
      setError('Failed to trigger ingestion: ' + err.message);
    } finally {
      setIngesting(false);
    }
  };

  const handleAddRepo = async (name: string, githubUrl: string) => {
    setError(null);
    setIngesting(true);
    try {
      const newRepo = await api.createRepo({ name, github_url: githubUrl });
      setRepositories((prev) => [newRepo, ...(Array.isArray(prev) ? prev : [])]);
      setSelectedRepo(newRepo);
    } catch (err: any) {
      setError('Failed to create repository: ' + err.message);
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div className="h-screen bg-[#050507] text-[#eaeaf0] flex flex-col overflow-hidden">
      <Navbar />

      <div className="flex-1 flex flex-col pt-16 overflow-hidden">
        
        {/* Workspace Top Toolbar */}
        <div className="px-4 sm:px-6 py-2.5 border-b border-white/[0.06] bg-[#07070a] flex items-center justify-between">
          <RepoSelector
            repositories={repositories}
            selectedRepo={selectedRepo}
            onSelectRepo={setSelectedRepo}
            onIngestRepo={handleIngest}
            onAddRepo={handleAddRepo}
            loading={ingesting}
          />

          <div className="flex items-center gap-3">
            {selectedRepo && (
              <SessionHistory
                sessions={sessions}
                activeSession={activeSession}
                onSelectSession={handleSelectSession}
                onNewChat={handleNewChat}
                onDeleteSession={handleDeleteSession}
                disabled={!selectedRepo}
              />
            )}
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="px-4 py-2 bg-rose-950/40 border-b border-rose-800/40 text-xs text-rose-300 font-mono text-center flex items-center justify-center gap-2">
            <span>{error}</span>
            <button 
              onClick={() => setError(null)}
              className="text-rose-400 hover:text-white underline ml-2"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Chat Message Console */}
        <ChatConsole
          messages={messages}
          loading={loading}
          selectedRepo={selectedRepo}
          repositories={repositories}
          onSelectRepo={setSelectedRepo}
          onSelectPrompt={handleSendMessage}
          onConnectRepo={handleAddRepo}
        />

        {/* Prompt Input Box */}
        <PromptInput
          onSend={handleSendMessage}
          loading={loading}
          disabled={!selectedRepo && repositories.length === 0}
        />

      </div>
    </div>
  );
}
