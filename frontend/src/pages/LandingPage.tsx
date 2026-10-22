import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Terminal, Cpu, ShieldCheck, Search, Sparkles } from 'lucide-react';
import Navbar from '../components/layout/Navbar';
import Footer from '../components/layout/Footer';
import ThreeScene from '../components/3d/ThreeScene';

export default function LandingPage() {
  const [quickPrompt, setQuickPrompt] = useState('');
  const navigate = useNavigate();

  const handleLaunchStudio = (e: React.FormEvent) => {
    e.preventDefault();
    if (quickPrompt.trim()) {
      navigate(`/workspace?prompt=${encodeURIComponent(quickPrompt.trim())}`);
    } else {
      navigate('/workspace');
    }
  };

  const featurePillars = [
    {
      icon: Cpu,
      title: 'Deterministic AST Parsing',
      description: 'Parses code with Tree-sitter into syntax-aware AST chunks preserving class hierarchies, function signatures, and imports.',
    },
    {
      icon: Search,
      title: 'Cyclic Agentic RAG',
      description: 'LangGraph multi-step cycles: routing, vector retrieval, parallel chunk grading, query rewrite, and web fallback.',
    },
    {
      icon: ShieldCheck,
      title: 'Hallucination Validation',
      description: 'Validates claims against retrieved code AST and web citations before output generation, enforcing zero guesswork.',
    },
  ];

  return (
    <div className="min-h-screen bg-[#050507] text-[#eaeaf0] flex flex-col relative selection:bg-white/10 selection:text-white">
      <Navbar />

      <main className="flex-1 pt-16">
        
        {/* Hero Section with Three.js 3D Canvas */}
        <section className="relative overflow-hidden pt-1 sm:pt-3 pb-12 md:pb-16 flex flex-col items-center justify-center text-center px-4">
          
          {/* Subtle Ambient Radial Glow */}
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-white/[0.02] rounded-full blur-3xl pointer-events-none" />

          {/* Interactive 3D Canvas (Three.js) */}
          <div className="w-full max-w-3xl mx-auto -mb-10 sm:-mb-14 md:-mb-16 z-0">
            <ThreeScene />
          </div>

          {/* Hero Typography & CTA */}
          <div className="relative z-10 max-w-3xl mx-auto space-y-6">
            
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono text-zinc-400">
              <Sparkles size={11} className="text-white" />
              <span>Next-Generation Deterministic Code Agent</span>
            </div>

            <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white leading-tight sm:leading-none">
              Code intelligence <br className="hidden sm:inline" />
              with <span className="text-zinc-500">zero hallucination.</span>
            </h1>

            <p className="text-sm sm:text-base text-zinc-400 max-w-xl mx-auto leading-relaxed font-normal">
              CodeMind AI navigates your repository AST with surgical precision. 
              Step-by-step reasoning, real-time citation previews, and grounded debugging.
            </p>

            {/* Quick Interactive Prompt Capsule */}
            <form onSubmit={handleLaunchStudio} className="max-w-xl mx-auto pt-2">
              <div className="relative flex items-center rounded-2xl glass-input p-1.5 focus-within:border-white/25 transition-all shadow-2xl">
                <input
                  type="text"
                  placeholder="Ask a question about your code or paste an error to debug..."
                  value={quickPrompt}
                  onChange={(e) => setQuickPrompt(e.target.value)}
                  className="w-full bg-transparent px-3 py-2 text-xs sm:text-sm text-white placeholder-zinc-500 outline-none"
                />
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all flex items-center gap-1.5 shrink-0 shadow"
                >
                  <Terminal size={13} />
                  <span>Launch</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </form>

            <div className="flex items-center justify-center gap-6 pt-2 text-xs text-zinc-500 font-mono">
              <span>• LangGraph Cycles</span>
              <span>• Tree-sitter AST</span>
              <span>• Tavily Fallback</span>
            </div>

          </div>

        </section>

        {/* Feature Grid (Clean, Simple, High-Impact) */}
        <section className="py-16 border-t border-white/[0.06] bg-[#07070a]/60 relative z-10">
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            
            <div className="text-center max-w-lg mx-auto mb-12 space-y-2">
              <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                Architected for precision
              </h2>
              <p className="text-xs text-zinc-400">
                Borrowing the best developer workflows from Cursor, Windsurf, Sourcegraph, and Perplexity.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {featurePillars.map((pillar, idx) => {
                const Icon = pillar.icon;
                return (
                  <div key={idx} className="p-6 rounded-2xl glass-card space-y-3">
                    <div className="w-9 h-9 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center text-white">
                      <Icon size={18} />
                    </div>
                    <h3 className="text-sm font-semibold text-white tracking-tight">{pillar.title}</h3>
                    <p className="text-xs text-zinc-400 leading-relaxed font-normal">
                      {pillar.description}
                    </p>
                  </div>
                );
              })}
            </div>

          </div>
        </section>

        {/* Action Banner */}
        <section className="py-16 border-t border-white/[0.06] text-center px-4 relative z-10">
          <div className="max-w-2xl mx-auto space-y-6">
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Ready to explore your codebase?
            </h2>
            <p className="text-xs sm:text-sm text-zinc-400">
              Connect your repositories and let CodeMind AI analyze dependencies and debug errors.
            </p>
            <div className="flex items-center justify-center gap-3">
              <Link
                to="/workspace"
                className="px-6 py-2.5 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all shadow-[0_0_30px_rgba(255,255,255,0.1)] flex items-center gap-2"
              >
                <Terminal size={14} />
                Open Developer Studio
              </Link>
              <Link
                to="/repo-health"
                className="px-5 py-2.5 rounded-xl bg-white/[0.04] border border-white/10 text-white text-xs hover:bg-white/[0.08] transition-all"
              >
                Run Quality Scan
              </Link>
            </div>
          </div>
        </section>

      </main>

      <Footer />
    </div>
  );
}
