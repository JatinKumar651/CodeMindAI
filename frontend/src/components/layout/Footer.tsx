import { Link } from 'react-router-dom';
import { Terminal, Shield, Sparkles } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.06] bg-[#050507] mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
          
          {/* Col 1: Brand & Philosophy */}
          <div className="space-y-3 md:col-span-1">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-zinc-900 border border-white/10 flex items-center justify-center font-mono text-[10px] font-bold text-white">
                CM
              </div>
              <span className="text-xs font-semibold tracking-tight text-white">CodeMind AI</span>
            </div>
            <p className="text-xs text-zinc-500 leading-relaxed">
              Deterministic Agentic RAG engine with AST semantic parsing, multi-hop self-healing loops, and zero hallucinations.
            </p>
            <div className="flex items-center gap-2 text-[11px] text-emerald-400 font-mono pt-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LangGraph Multi-Agent Pipeline Active
            </div>
          </div>

          {/* Col 2: Studio & Product */}
          <div>
            <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">Product</h4>
            <ul className="space-y-2 text-xs text-zinc-500">
              <li>
                <Link to="/workspace" className="hover:text-zinc-300 transition-colors flex items-center gap-1.5">
                  <Terminal size={12} />
                  Developer Studio
                </Link>
              </li>
              <li>
                <Link to="/repo-health" className="hover:text-zinc-300 transition-colors">
                  Repository Health & Scans
                </Link>
              </li>
              <li>
                <Link to="/settings" className="hover:text-zinc-300 transition-colors">
                  Engine Tuning & Rules
                </Link>
              </li>
              <li>
                <Link to="/workspace" className="hover:text-zinc-300 transition-colors">
                  Code Inspector & Diff
                </Link>
              </li>
            </ul>
          </div>

          {/* Col 3: Architecture & Security */}
          <div>
            <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">Architecture</h4>
            <ul className="space-y-2 text-xs text-zinc-500">
              <li><span className="text-zinc-400">Tree-sitter AST</span> Code Chunking</li>
              <li><span className="text-zinc-400">pgvector</span> High-Density Embeddings</li>
              <li><span className="text-zinc-400">Tavily Search</span> Grounded Fallbacks</li>
              <li><span className="text-zinc-400">HITL Gateway</span> Enterprise Guardrails</li>
            </ul>
          </div>

          {/* Col 4: Community & Docs */}
          <div>
            <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">Resources</h4>
            <ul className="space-y-2 text-xs text-zinc-500">
              <li>
                <Link to="/about" className="hover:text-zinc-300 transition-colors">
                  About the Engine
                </Link>
              </li>
              <li>
                <Link to="/contact" className="hover:text-zinc-300 transition-colors">
                  Enterprise Support
                </Link>
              </li>
              <li>
                <Link to="/settings" className="hover:text-zinc-300 transition-colors">
                  Workspace Settings
                </Link>
              </li>
            </ul>
          </div>

        </div>

        {/* Bottom bar */}
        <div className="pt-6 border-t border-white/[0.04] flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-zinc-600">
          <p>© 2026 CodeMind AI. Designed with precision for software engineers.</p>
          <div className="flex items-center gap-4">
            <span className="text-zinc-500 font-mono text-[11px]">v0.1.0-beta</span>
            <span className="text-zinc-700">•</span>
            <span className="text-zinc-500 font-mono text-[11px]">PostgreSQL 16 + pgvector</span>
          </div>
        </div>

      </div>
    </footer>
  );
}
