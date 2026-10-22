import { Copy, Check, Terminal, User, Sparkles, Plus, ArrowRight, GitBranch, Code2, Layers } from 'lucide-react';
import { useState } from 'react';
import type { Message, Repository } from '../../types';
import ThoughtStream from './ThoughtStream';
import CitationPreview from './CitationPreview';
import StatusBadge from '../common/StatusBadge';
import { MarkdownRenderer } from '../common/MarkdownRenderer';

interface ChatConsoleProps {
  messages: Message[];
  loading?: boolean;
  selectedRepo?: Repository | null;
  repositories?: Repository[];
  onSelectRepo?: (repo: Repository) => void;
  onSelectPrompt?: (prompt: string) => void;
  onConnectRepo?: (name: string, url: string) => void;
}

export default function ChatConsole({
  messages,
  loading = false,
  selectedRepo,
  repositories = [],
  onSelectRepo,
  onSelectPrompt,
  onConnectRepo,
}: ChatConsoleProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [repoUrlInput, setRepoUrlInput] = useState('');
  const [repoNameInput, setRepoNameInput] = useState('');

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleUrlChange = (val: string) => {
    setRepoUrlInput(val);
    if (!repoNameInput.trim() && val.trim()) {
      try {
        const cleaned = val.trim().replace(/\.git$/, '');
        const parts = cleaned.split('/');
        const extracted = parts[parts.length - 1];
        if (extracted) setRepoNameInput(extracted);
      } catch {}
    }
  };

  const handleConnectSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoNameInput.trim() && !repoUrlInput.trim()) return;
    const finalName = repoNameInput.trim() || 'my-repository';
    if (onConnectRepo) {
      onConnectRepo(finalName, repoUrlInput.trim());
    }
    setRepoUrlInput('');
    setRepoNameInput('');
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
      
      {/* Empty State */}
      {messages.length === 0 && !loading && (
        <div className="max-w-2xl mx-auto py-12 space-y-6">
          
          {/* If No Repo Connected / Selected */}
          {!selectedRepo ? (
            <div className="rounded-2xl border border-white/10 bg-[#0d0d14]/80 backdrop-blur-md p-6 sm:p-8 shadow-2xl space-y-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-white/[0.06] border border-white/10 flex items-center justify-center text-white">
                  <GitBranch size={20} />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white tracking-tight">
                    Connect Your Codebase
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Paste your GitHub repository URL to trigger AST parsing, symbol indexing, and vector embedding.
                  </p>
                </div>
              </div>

              <form onSubmit={handleConnectSubmit} className="space-y-3.5 pt-2">
                <div>
                  <label className="block text-[11px] font-mono text-zinc-400 mb-1.5 flex items-center justify-between">
                    <span>GitHub Repository URL</span>
                    <span className="text-zinc-600">Public or Private</span>
                  </label>
                  <div className="relative">
                    <input
                      type="url"
                      required
                      placeholder="https://github.com/username/repository"
                      value={repoUrlInput}
                      onChange={(e) => handleUrlChange(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.04] border border-white/10 focus:border-white/30 text-xs text-white placeholder-zinc-600 outline-none transition-all font-mono"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-mono text-zinc-400 mb-1.5">
                      Repository Name
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. backend-api"
                      value={repoNameInput}
                      onChange={(e) => setRepoNameInput(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.04] border border-white/10 focus:border-white/30 text-xs text-white placeholder-zinc-600 outline-none transition-all"
                    />
                  </div>
                  <div className="flex items-end">
                    <button
                      type="submit"
                      className="w-full py-2.5 px-4 rounded-xl bg-white hover:bg-zinc-200 text-black font-semibold text-xs transition-all shadow flex items-center justify-center gap-2"
                    >
                      <Plus size={14} />
                      Connect & Ingest Codebase
                    </button>
                  </div>
                </div>
              </form>

              {/* Existing Repos List if Available */}
              {repositories.length > 0 && onSelectRepo && (
                <div className="pt-4 border-t border-white/[0.06] space-y-2">
                  <span className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider block">
                    Or select an existing repository:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {repositories.map((repo) => (
                      <button
                        key={repo.id}
                        onClick={() => onSelectRepo(repo)}
                        className="px-3 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 text-xs text-zinc-300 hover:text-white flex items-center gap-2 transition-all font-mono"
                      >
                        <Code2 size={12} className="text-zinc-500" />
                        <span>{repo.name}</span>
                        <StatusBadge status={repo.status} size="sm" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Selected Repo Hero Card */
            <div className="space-y-6">
              <div className="rounded-2xl border border-white/10 bg-[#0d0d14]/70 backdrop-blur-md p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white">
                      <Code2 size={16} />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
                        {selectedRepo.name}
                        <StatusBadge status={selectedRepo.status} size="sm" />
                      </h3>
                      <p className="text-[11px] text-zinc-500 font-mono">
                        Branch: {selectedRepo.default_branch || 'main'} • Total AST Chunks: {selectedRepo.total_chunks ?? 0}
                      </p>
                    </div>
                  </div>
                </div>

                {selectedRepo.github_url && (
                  <p className="text-xs text-zinc-400 font-mono truncate">
                    Source: <a href={selectedRepo.github_url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">{selectedRepo.github_url}</a>
                  </p>
                )}
              </div>

              {/* Starter Investigation Prompts */}
              {onSelectPrompt && (
                <div className="space-y-2">
                  <span className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider block">
                    Suggested Code Investigations
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                    {[
                      {
                        title: 'Architecture Overview',
                        desc: 'Explain the high-level design and core services',
                        prompt: 'Explain the high-level architecture, module breakdown, and primary entrypoints of this codebase.',
                      },
                      {
                        title: 'API & Data Flow',
                        desc: 'Trace routing, controllers, and persistence',
                        prompt: 'Trace how an API request flows through routing, authentication, middleware, and database operations.',
                      },
                      {
                        title: 'Dependencies & Security',
                        desc: 'Examine external libraries and potential risks',
                        prompt: 'Analyze key third-party packages, configuration requirements, and potential security boundary risks in this repository.',
                      },
                    ].map((item, i) => (
                      <button
                        key={i}
                        onClick={() => onSelectPrompt(item.prompt)}
                        className="p-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] hover:border-white/15 text-left transition-all group flex flex-col justify-between space-y-2"
                      >
                        <div>
                          <h4 className="text-xs font-semibold text-zinc-200 group-hover:text-white transition-colors">
                            {item.title}
                          </h4>
                          <p className="text-[11px] text-zinc-500 group-hover:text-zinc-400 transition-colors mt-0.5 leading-snug">
                            {item.desc}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 text-[10px] font-mono text-cyan-400 group-hover:translate-x-0.5 transition-transform pt-1">
                          <span>Investigate</span>
                          <ArrowRight size={10} />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      )}

      {/* Messages Stream */}
      {messages.map((msg) => {
        const isUser = msg.role === 'user';

        return (
          <div
            key={msg.id}
            className={`flex gap-3 max-w-4xl mx-auto ${isUser ? 'justify-end' : 'justify-start'}`}
          >
            {!isUser && (
              <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-white/10 flex items-center justify-center text-white shrink-0 mt-1">
                <Sparkles size={13} />
              </div>
            )}

            <div className={`space-y-2 max-w-[85%] sm:max-w-[78%] ${isUser ? 'items-end' : 'items-start'}`}>
              
              {/* User or Assistant Bubble */}
              <div
                className={`rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                  isUser
                    ? 'bg-zinc-800 text-white rounded-tr-sm border border-white/10'
                    : 'bg-[#0d0d14] text-zinc-200 rounded-tl-sm border border-white/[0.08] shadow-sm'
                }`}
              >
                {/* Agent Thought Stream (Cursor/Windsurf Inspiration) */}
                {!isUser && msg.agent_trace && (
                  <ThoughtStream
                    trace={msg.agent_trace}
                    latencyMs={msg.latency_ms}
                    tokensUsed={msg.tokens_used}
                  />
                )}

                {/* Message Body Content */}
                {isUser ? (
                  <div className="whitespace-pre-wrap font-sans text-xs space-y-2">
                    {msg.content}
                  </div>
                ) : (
                  <MarkdownRenderer content={msg.content} />
                )}

                {/* Grounded Citation Pills (Perplexity Inspiration) */}
                {!isUser && msg.citations && msg.citations.length > 0 && (
                  <CitationPreview citations={msg.citations} />
                )}

                {/* Message Footer Meta */}
                {!isUser && (
                  <div className="mt-3 pt-2 flex items-center justify-between border-t border-white/[0.04] text-[10px] text-zinc-500 font-mono">
                    <div className="flex items-center gap-2">
                      {msg.model_used && <span>{msg.model_used}</span>}
                      {msg.needs_review && (
                        <span className="text-amber-400 bg-amber-950/30 px-1.5 py-0.5 rounded border border-amber-800/40">
                          Human Review Flagged
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => handleCopy(msg.id, msg.content)}
                      className="hover:text-zinc-300 transition-colors p-1"
                      title="Copy response"
                    >
                      {copiedId === msg.id ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                    </button>
                  </div>
                )}
              </div>

            </div>

            {isUser && (
              <div className="w-7 h-7 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center text-zinc-300 shrink-0 mt-1">
                <User size={13} />
              </div>
            )}
          </div>
        );
      })}

      {/* Loading Skeleton Indicator */}
      {loading && (
        <div className="flex gap-3 max-w-4xl mx-auto justify-start animate-pulse">
          <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-white/10 flex items-center justify-center text-zinc-500 shrink-0 mt-1">
            <Sparkles size={13} />
          </div>
          <div className="rounded-2xl px-4 py-3 bg-[#0d0d14] border border-white/[0.08] text-xs text-zinc-400 space-y-2 w-72">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              <span className="font-mono text-zinc-300 text-[11px]">Executing LangGraph pipeline...</span>
            </div>
            <div className="h-2 bg-white/5 rounded w-3/4" />
            <div className="h-2 bg-white/5 rounded w-1/2" />
          </div>
        </div>
      )}

    </div>
  );
}
