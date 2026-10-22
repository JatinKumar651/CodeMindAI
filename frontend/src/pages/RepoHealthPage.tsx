import { useState, useEffect } from 'react';
import { Shield, Code, ChevronDown, RefreshCw, AlertCircle } from 'lucide-react';
import Navbar from '../components/layout/Navbar';
import Footer from '../components/layout/Footer';
import StatusBadge from '../components/common/StatusBadge';
import { api } from '../services/api';
import type { Repository, Scan } from '../types';

// Module-level cache for instant page switching
let cachedHealthRepos: Repository[] = [];
let cachedHealthSelectedRepo: Repository | null = null;
let cachedScans: Scan[] = [];

export default function RepoHealthPage() {
  const [repositories, setRepositories] = useState<Repository[]>(cachedHealthRepos);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(cachedHealthSelectedRepo);
  const [scans, setScans] = useState<Scan[]>(cachedScans);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync to cache on updates
  useEffect(() => {
    cachedHealthRepos = repositories;
    cachedHealthSelectedRepo = selectedRepo;
    cachedScans = scans;
  }, [repositories, selectedRepo, scans]);

  useEffect(() => {
    async function loadRepos() {
      try {
        const repos = await api.listRepos();
        const repoList = Array.isArray(repos) ? repos : [];
        setRepositories(repoList);
        cachedHealthRepos = repoList;
        if (repoList.length > 0 && !selectedRepo) {
          const defaultRepo = cachedHealthSelectedRepo || repoList[0];
          setSelectedRepo(defaultRepo);
          cachedHealthSelectedRepo = defaultRepo;
        }
      } catch (err: any) {
        console.warn('Failed to load repositories for scans:', err.message);
      }
    }
    loadRepos();
  }, []);

  useEffect(() => {
    if (!selectedRepo) {
      setScans([]);
      return;
    }

    async function loadScans(repoId: string) {
      try {
        const scanList = await api.listScans(repoId);
        setScans(Array.isArray(scanList) ? scanList : []);
      } catch (err: any) {
        console.warn('No scans or error fetching scans:', err.message);
        setScans([]);
      }
    }

    loadScans(selectedRepo.id);
  }, [selectedRepo?.id]);

  const handleTriggerScan = async (type: string) => {
    if (!selectedRepo) {
      setError('Please select a repository to scan.');
      return;
    }
    setScanning(true);
    setError(null);
    try {
      const newScan = await api.triggerScan(selectedRepo.id, type);
      setScans((prev) => [newScan, ...prev]);
    } catch (err: any) {
      setError('Scan failed: ' + (err.message || 'Could not execute scan on backend.'));
    } finally {
      setScanning(false);
    }
  };

  const highCount = scans.reduce((acc, s) => acc + (s.severity_counts?.high || 0), 0);
  const medCount = scans.reduce((acc, s) => acc + (s.severity_counts?.medium || 0), 0);
  const lowCount = scans.reduce((acc, s) => acc + (s.severity_counts?.low || 0), 0);

  return (
    <div className="min-h-screen bg-[#050507] text-[#eaeaf0] flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-6xl mx-auto w-full px-4 sm:px-6 pt-24 pb-16 space-y-8">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.06] pb-6">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Repository Health & Scans
            </h1>
            <p className="text-xs text-zinc-400 mt-1">
              Static code analysis, vulnerability scanning, and AST complexity telemetry.
            </p>
          </div>

          {/* Repository Picker & Actions */}
          <div className="flex items-center gap-3">
            {repositories.length > 0 && (
              <select
                value={selectedRepo?.id || ''}
                onChange={(e) => {
                  const repo = repositories.find((r) => r.id === e.target.value);
                  if (repo) setSelectedRepo(repo);
                }}
                className="px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/10 text-xs text-white outline-none cursor-pointer"
              >
                {repositories.map((repo) => (
                  <option key={repo.id} value={repo.id} className="bg-[#0e0e14] text-white">
                    {repo.name} ({repo.default_branch})
                  </option>
                ))}
              </select>
            )}

            <button
              onClick={() => handleTriggerScan('security')}
              disabled={scanning || !selectedRepo}
              className="px-3.5 py-1.5 rounded-lg bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              <Shield size={13} />
              Run Security Scan
            </button>
            <button
              onClick={() => handleTriggerScan('complexity')}
              disabled={scanning || !selectedRepo}
              className="px-3.5 py-1.5 rounded-lg bg-white/[0.04] border border-white/10 text-white text-xs hover:bg-white/[0.08] transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              <Code size={13} />
              Run Complexity Scan
            </button>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/40 text-xs text-rose-300 font-mono flex items-center gap-2">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Real Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl glass-card space-y-1">
            <span className="text-[11px] font-mono text-zinc-500 uppercase">Indexed AST Chunks</span>
            <div className="text-2xl font-bold text-white font-mono">
              {selectedRepo ? (selectedRepo.total_chunks || 0) : 0}
            </div>
            <span className="text-[11px] text-zinc-400 font-mono">
              {selectedRepo ? `Status: ${selectedRepo.status}` : 'No repo selected'}
            </span>
          </div>

          <div className="p-4 rounded-xl glass-card space-y-1">
            <span className="text-[11px] font-mono text-zinc-500 uppercase">High Severity Findings</span>
            <div className="text-2xl font-bold text-white font-mono">
              {highCount}
            </div>
            <span className="text-[11px] text-zinc-400 font-mono">
              {highCount === 0 ? 'No critical vulnerabilities' : 'Requires review'}
            </span>
          </div>

          <div className="p-4 rounded-xl glass-card space-y-1">
            <span className="text-[11px] font-mono text-zinc-500 uppercase">Medium / Low Issues</span>
            <div className="text-2xl font-bold text-white font-mono">
              {medCount + lowCount}
            </div>
            <span className="text-[11px] text-zinc-400 font-mono">
              {medCount} med, {lowCount} low
            </span>
          </div>

          <div className="p-4 rounded-xl glass-card space-y-1">
            <span className="text-[11px] font-mono text-zinc-500 uppercase">Total Scans Executed</span>
            <div className="text-2xl font-bold text-white font-mono">{scans.length}</div>
            <span className="text-[11px] text-zinc-400 font-mono">Recorded in database</span>
          </div>
        </div>

        {/* Scan History Table */}
        <div className="rounded-xl border border-white/[0.08] bg-[#09090e]/80 backdrop-blur-md overflow-hidden">
          <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
            <span className="text-xs font-semibold text-white">Scan Audit Log</span>
            <span className="text-[11px] font-mono text-zinc-500">{scans.length} scans</span>
          </div>

          {scans.length === 0 ? (
            <div className="p-12 text-center space-y-2">
              <p className="text-xs text-zinc-400">
                No scans recorded yet for {selectedRepo ? selectedRepo.name : 'this repository'}.
              </p>
              <p className="text-[11px] text-zinc-500">
                Click "Run Security Scan" or "Run Complexity Scan" above to analyze the codebase.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {scans.map((scan) => (
                <div key={scan.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs hover:bg-white/[0.02] transition-colors">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-medium text-white uppercase text-[11px]">
                        {scan.scan_type}
                      </span>
                      <StatusBadge status={scan.status} size="sm" />
                    </div>
                    <p className="text-zinc-400 text-xs leading-relaxed">
                      {scan.summary || 'Scan completed.'}
                    </p>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 font-mono text-[11px] text-zinc-500">
                    <span className="text-rose-400">High: {scan.severity_counts?.high || 0}</span>
                    <span className="text-amber-400">Med: {scan.severity_counts?.medium || 0}</span>
                    <span className="text-zinc-400">Low: {scan.severity_counts?.low || 0}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </main>

      <Footer />
    </div>
  );
}
