import Navbar from '../components/layout/Navbar';
import Footer from '../components/layout/Footer';
import { Cpu, Shield, Search, Zap } from 'lucide-react';

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-[#050507] text-[#eaeaf0] flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 pt-24 pb-16 space-y-12">
        
        {/* Header */}
        <div className="space-y-3 border-b border-white/[0.06] pb-8">
          <span className="text-xs font-mono text-zinc-500 uppercase tracking-wider">
            About CodeMind AI
          </span>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Deterministic AST intelligence over stochastic guessing.
          </h1>
          <p className="text-sm text-zinc-400 leading-relaxed max-w-2xl font-normal">
            Most LLM coding tools generate plausible-looking code based on loose text matches. 
            CodeMind AI parses your entire repository into syntax-aware Abstract Syntax Trees (AST), 
            grounding every response in real code definitions.
          </p>
        </div>

        {/* Philosophy Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div className="p-5 rounded-xl glass-card space-y-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white">
              <Cpu size={16} />
            </div>
            <h3 className="text-sm font-semibold text-white">Grammar-Aware AST Chunking</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              We decompose code along syntactic boundaries (functions, classes, docstrings) using Tree-sitter, avoiding arbitrary line splits that destroy meaning.
            </p>
          </div>

          <div className="p-5 rounded-xl glass-card space-y-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white">
              <Search size={16} />
            </div>
            <h3 className="text-sm font-semibold text-white">Parallel Relevance Grading</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Every retrieved chunk is evaluated concurrently for strict query relevance. Non-relevant chunks are discarded before answer synthesis.
            </p>
          </div>

          <div className="p-5 rounded-xl glass-card space-y-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white">
              <Zap size={16} />
            </div>
            <h3 className="text-sm font-semibold text-white">Self-Correcting Query Rewriting</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              When retrieval yields weak matches, the agent automatically rewrites its search query to isolate root symbols and exception keywords.
            </p>
          </div>

          <div className="p-5 rounded-xl glass-card space-y-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white">
              <Shield size={16} />
            </div>
            <h3 className="text-sm font-semibold text-white">Human-in-the-Loop Safeguards</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Low-confidence answers or hallucination-prone generations are intercepted by an integrated review gateway before reaching developers.
            </p>
          </div>
        </div>

      </main>

      <Footer />
    </div>
  );
}
