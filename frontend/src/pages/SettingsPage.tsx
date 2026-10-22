import { useState } from 'react';
import { User, Sliders, Shield, Save, Key } from 'lucide-react';
import Navbar from '../components/layout/Navbar';
import Footer from '../components/layout/Footer';
import { authService } from '../services/auth';

export default function SettingsPage() {
  const user = authService.getUser();

  const [maxIterations, setMaxIterations] = useState(3);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.75);
  const [tavilyFallback, setTavilyFallback] = useState(true);
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#050507] text-[#eaeaf0] flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 pt-24 pb-16 space-y-8">
        
        {/* Header */}
        <div className="border-b border-white/[0.06] pb-6">
          <h1 className="text-2xl font-bold text-white tracking-tight">Engine Settings</h1>
          <p className="text-xs text-zinc-400 mt-1">
            Configure agent reflection loops, vector retrieval thresholds, and authentication parameters.
          </p>
        </div>

        <form onSubmit={handleSave} className="space-y-6">
          
          {/* Section 1: User & Auth */}
          <div className="p-5 rounded-xl glass-card space-y-4">
            <div className="flex items-center gap-2 text-white text-sm font-semibold">
              <User size={16} />
              <span>Authentication Profile</span>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block text-zinc-500 font-mono text-[11px] mb-1">Email Account</label>
                <div className="px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-white font-mono">
                  {user?.email || 'guest@codemind.ai'}
                </div>
              </div>

              <div>
                <label className="block text-zinc-500 font-mono text-[11px] mb-1">Role / Permissions</label>
                <div className="px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-emerald-400 font-mono">
                  {user?.role || 'Developer (Standard)'}
                </div>
              </div>
            </div>
          </div>

          {/* Section 2: Agentic RAG Tuning */}
          <div className="p-5 rounded-xl glass-card space-y-4">
            <div className="flex items-center gap-2 text-white text-sm font-semibold">
              <Sliders size={16} />
              <span>Agent Reflection & Search Tuning</span>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-zinc-300 font-medium">Max Query Rewrite Cycles</label>
                  <span className="font-mono text-white">{maxIterations} loops</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={5}
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(Number(e.target.value))}
                  className="w-full accent-white bg-zinc-800"
                />
                <p className="text-[11px] text-zinc-500 mt-1">
                  How many self-correcting query rewrites the Grader will execute before falling back.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-zinc-300 font-medium">Cosine Similarity Threshold</label>
                  <span className="font-mono text-white">{similarityThreshold}</span>
                </div>
                <input
                  type="range"
                  min={0.5}
                  max={0.95}
                  step={0.05}
                  value={similarityThreshold}
                  onChange={(e) => setSimilarityThreshold(Number(e.target.value))}
                  className="w-full accent-white bg-zinc-800"
                />
                <p className="text-[11px] text-zinc-500 mt-1">
                  Minimum semantic score for AST chunks to pass the relevance filter.
                </p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-white/5">
                <div>
                  <span className="text-zinc-300 font-medium block">Tavily Web Fallback</span>
                  <span className="text-[11px] text-zinc-500">
                    Search online technical documentation if repository retrieval yields 0 chunks.
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={tavilyFallback}
                  onChange={(e) => setTavilyFallback(e.target.checked)}
                  className="w-4 h-4 rounded accent-white bg-zinc-800"
                />
              </div>
            </div>
          </div>

          {/* Section 3: Indexing Excludes */}
          <div className="p-5 rounded-xl glass-card space-y-3">
            <div className="flex items-center gap-2 text-white text-sm font-semibold">
              <Shield size={16} />
              <span>AST Parsing Exclusions</span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Default patterns ignored during Tree-sitter AST parsing:
            </p>
            <div className="flex flex-wrap gap-2 text-xs font-mono text-zinc-400">
              {['node_modules/**', '.git/**', 'dist/**', 'build/**', '__pycache__/**', '*.pyc', 'vendor/**'].map((pat) => (
                <span key={pat} className="px-2.5 py-1 rounded bg-black/40 border border-white/10 text-zinc-300">
                  {pat}
                </span>
              ))}
            </div>
          </div>

          {/* Submit */}
          <div className="flex items-center justify-end gap-3 pt-2">
            {saved && (
              <span className="text-xs font-mono text-emerald-400">
                Preferences saved successfully!
              </span>
            )}
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all flex items-center gap-1.5 shadow"
            >
              <Save size={13} />
              Save Settings
            </button>
          </div>

        </form>

      </main>

      <Footer />
    </div>
  );
}
