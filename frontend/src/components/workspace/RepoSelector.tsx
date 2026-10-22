import { useState, useEffect } from 'react';
import { GitBranch, RefreshCw, Plus, Database, ChevronDown } from 'lucide-react';
import type { Repository } from '../../types';
import StatusBadge from '../common/StatusBadge';

interface RepoSelectorProps {
  repositories: Repository[];
  selectedRepo: Repository | null;
  onSelectRepo: (repo: Repository) => void;
  onIngestRepo: (repoId: string) => void;
  onAddRepo: (name: string, githubUrl: string) => void;
  loading?: boolean;
}

export default function RepoSelector({
  repositories,
  selectedRepo,
  onSelectRepo,
  onIngestRepo,
  onAddRepo,
  loading = false,
}: RepoSelectorProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [newRepoName, setNewRepoName] = useState('');
  const [newRepoUrl, setNewRepoUrl] = useState('');

  const repoList = Array.isArray(repositories) ? repositories : [];

  const handleUrlChange = (url: string) => {
    setNewRepoUrl(url);
    if (!newRepoName.trim() && url.trim()) {
      try {
        const cleaned = url.trim().replace(/\.git$/, '');
        const parts = cleaned.split('/');
        const extracted = parts[parts.length - 1];
        if (extracted) setNewRepoName(extracted);
      } catch {}
    }
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRepoName.trim()) return;
    onAddRepo(newRepoName.trim(), newRepoUrl.trim());
    setNewRepoName('');
    setNewRepoUrl('');
    setModalOpen(false);
  };

  return (
    <div className="relative flex items-center gap-2 sm:gap-3">
      
      {/* Active Repo Dropdown Trigger */}
      <div className="relative">
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/10 hover:border-white/20 transition-all text-xs text-white"
        >
          <Database size={13} className="text-zinc-400" />
          <span className="font-medium truncate max-w-[140px]">
            {selectedRepo ? selectedRepo.name : 'Select Repository'}
          </span>
          <ChevronDown size={13} className="text-zinc-500" />
        </button>

        {dropdownOpen && (
          <div className="absolute left-0 mt-1.5 w-64 rounded-xl border border-white/10 bg-[#0d0d14] p-1.5 shadow-xl z-40 text-xs space-y-1">
            <div className="px-2 py-1 text-[11px] font-mono text-zinc-500 uppercase tracking-wider">
              Repositories ({repoList.length})
            </div>
            
            <div className="max-h-52 overflow-y-auto space-y-0.5">
              {repoList.length === 0 ? (
                <div className="px-2 py-3 text-center text-zinc-500 text-xs">
                  No repositories yet
                </div>
              ) : (
                repoList.map((repo) => (
                  <button
                    key={repo.id}
                    onClick={() => {
                      onSelectRepo(repo);
                      setDropdownOpen(false);
                    }}
                    className={`w-full px-2.5 py-1.5 rounded-lg text-left flex items-center justify-between transition-colors ${
                      selectedRepo?.id === repo.id
                        ? 'bg-white/10 text-white font-medium'
                        : 'text-zinc-400 hover:text-white hover:bg-white/[0.04]'
                    }`}
                  >
                    <span className="truncate">{repo.name}</span>
                    <StatusBadge status={repo.status} size="sm" />
                  </button>
                ))
              )}
            </div>

            <button
              onClick={() => {
                setDropdownOpen(false);
                setModalOpen(true);
              }}
              className="w-full mt-1 pt-1 border-t border-white/5 px-2.5 py-1.5 rounded-lg text-left text-zinc-300 hover:text-white hover:bg-white/[0.04] flex items-center gap-1.5 text-xs"
            >
              <Plus size={13} />
              Connect New Repository
            </button>
          </div>
        )}
      </div>

      {/* Prominent Quick-Connect Button in Toolbar */}
      <button
        onClick={() => setModalOpen(true)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/10 border border-white/10 text-xs text-zinc-300 hover:text-white transition-all font-mono"
        title="Connect a GitHub repository"
      >
        <Plus size={12} className="text-zinc-400" />
        <span className="hidden sm:inline">Connect Repo</span>
      </button>

      {/* Active Branch and Ingest Status */}
      {selectedRepo && (
        <div className="flex items-center gap-2 text-xs">
          <div className="hidden sm:flex items-center gap-1 text-zinc-400 font-mono px-2 py-1 rounded bg-white/[0.02] border border-white/[0.06]">
            <GitBranch size={12} className="text-zinc-500" />
            <span>{selectedRepo.default_branch || 'main'}</span>
          </div>

          <StatusBadge status={selectedRepo.status} />

          <button
            onClick={() => onIngestRepo(selectedRepo.id)}
            disabled={loading || selectedRepo.status === 'processing'}
            title="Re-index AST chunks"
            className="p-1.5 rounded-lg border border-white/10 hover:border-white/20 bg-white/[0.03] text-zinc-400 hover:text-white transition-all disabled:opacity-50"
          >
            <RefreshCw size={13} className={selectedRepo.status === 'processing' ? 'animate-spin' : ''} />
          </button>
        </div>
      )}

      {/* Add Repo Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-white/15 bg-[#0d0d14] p-6 shadow-2xl space-y-4">
            <h3 className="text-sm font-semibold text-white">Connect Repository</h3>
            <p className="text-xs text-zinc-400">
              CodeMind AI parses the AST, extracts symbols, and generates high-density embeddings.
            </p>

            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-[11px] font-mono text-zinc-400 mb-1">
                  GitHub Repository URL <span className="text-cyan-400">*</span>
                </label>
                <input
                  type="url"
                  required
                  placeholder="https://github.com/username/repository"
                  value={newRepoUrl}
                  onChange={(e) => handleUrlChange(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg glass-input text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono text-zinc-400 mb-1">Repository Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. FireReach"
                  value={newRepoName}
                  onChange={(e) => setNewRepoName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg glass-input text-xs text-white"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all shadow"
                >
                  Connect & Ingest
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
