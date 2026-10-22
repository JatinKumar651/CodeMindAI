import { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, Search, Cpu, Globe, ShieldCheck, Sparkles, AlertCircle } from 'lucide-react';
import type { AgentTrace } from '../../types';

interface ThoughtStreamProps {
  trace?: AgentTrace | null;
  latencyMs?: number | null;
  tokensUsed?: number;
}

export default function ThoughtStream({ trace, latencyMs, tokensUsed }: ThoughtStreamProps) {
  const [expanded, setExpanded] = useState(false);

  if (!trace) return null;

  const steps = [
    {
      id: 'router',
      label: 'Router',
      icon: Cpu,
      active: Boolean(trace.router),
      summary: trace.router ? `Classified intent: ${trace.router.intent}${trace.router.is_error_query ? ' (Error Debugging Detected)' : ''}` : 'Classifying request...',
      details: trace.router ? [
        trace.router.error_type ? `Error Type: ${trace.router.error_type}` : null,
        trace.router.file_hint ? `File Target: ${trace.router.file_hint}` : null,
      ].filter(Boolean) : [],
    },
    {
      id: 'retriever',
      label: 'Retriever',
      icon: Search,
      active: Boolean(trace.retriever),
      summary: trace.retriever ? `Retrieved ${trace.retriever.total_retrieved} AST chunks from vector store` : 'Searching codebase AST...',
      details: trace.retriever?.file_count ? [`Across ${trace.retriever.file_count} unique files`] : [],
    },
    {
      id: 'grader',
      label: 'Grader',
      icon: CheckCircle2,
      active: Boolean(trace.grader),
      summary: trace.grader ? `${trace.grader.passed_count}/${trace.grader.total_graded} chunks passed relevance threshold` : 'Evaluating chunk relevance...',
      details: trace.grader?.rewritten_query ? [`Rewritten Query: "${trace.grader.rewritten_query}"`] : [],
    },
    trace.web_searcher?.invoked ? {
      id: 'web_searcher',
      label: 'Tavily Search',
      icon: Globe,
      active: true,
      summary: `Fallback web search invoked — retrieved ${trace.web_searcher.sources_count || 0} external docs`,
      details: trace.web_searcher.query_used ? [`Query: ${trace.web_searcher.query_used}`] : [],
    } : null,
    {
      id: 'validator',
      label: 'Validator',
      icon: ShieldCheck,
      active: Boolean(trace.validator),
      summary: trace.validator ? `Grounding confidence: ${Math.round((trace.validator.confidence_score || 0.9) * 100)}% (${trace.validator.passed ? 'Verified Grounded' : 'Needs Review'})` : 'Validating hallucinations...',
      details: trace.validator?.reason ? [trace.validator.reason] : [],
    },
  ].filter(Boolean);

  return (
    <div className="mb-4 rounded-lg border border-white/[0.08] bg-[#09090e]/70 backdrop-blur-md overflow-hidden transition-all text-xs">
      
      {/* Header bar */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3.5 py-2 flex items-center justify-between hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-white/10 flex items-center justify-center text-zinc-300">
            <Sparkles size={10} />
          </div>
          <span className="font-mono font-medium text-zinc-300">Agent Thought Stream</span>
          <span className="text-[11px] text-zinc-500 font-mono">({steps.length} stages)</span>
        </div>

        <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-500">
          {latencyMs ? <span>{latencyMs}ms</span> : null}
          {tokensUsed ? <span>{tokensUsed} tokens</span> : null}
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </button>

      {/* Expanded Step-by-Step Flow */}
      {expanded && (
        <div className="px-3.5 pb-3 pt-1 border-t border-white/[0.05] space-y-2">
          {steps.map((step) => {
            if (!step) return null;
            const Icon = step.icon;
            return (
              <div key={step.id} className="flex items-start gap-2.5 py-1">
                <div className="mt-0.5 p-1 rounded bg-white/[0.04] border border-white/[0.06] text-zinc-400">
                  <Icon size={12} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-zinc-300 font-medium text-[11px]">{step.label}</span>
                    <span className="text-zinc-500 text-[11px]">• {step.summary}</span>
                  </div>
                  {step.details && step.details.length > 0 && (
                    <div className="mt-1 space-y-0.5">
                      {step.details.map((detail, idx) => (
                        <p key={idx} className="text-[10px] text-zinc-400 font-mono bg-black/40 px-2 py-0.5 rounded border border-white/[0.03]">
                          {detail}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
