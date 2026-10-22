import { useState } from 'react';
import { FileCode, Globe, ExternalLink, X } from 'lucide-react';
import type { Citation } from '../../types';

interface CitationPreviewProps {
  citations: Citation[];
}

export default function CitationPreview({ citations }: CitationPreviewProps) {
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-3 pt-2.5 border-t border-white/[0.06]">
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider">
          Grounded Sources ({citations.length})
        </span>
      </div>

      {/* Citation Pills */}
      <div className="flex flex-wrap gap-2">
        {(citations || []).filter(Boolean).map((cite, index) => {
          const pathStr = cite.file_path || (cite as any).url || (cite as any).title || 'source';
          const isWeb = Boolean(pathStr.startsWith('http') || (cite as any).type === 'web');
          const fileName = pathStr.split('/').pop() || pathStr;
          const lineRef = cite.start_line ? `:L${cite.start_line}${cite.end_line ? `-L${cite.end_line}` : ''}` : '';
          const scorePercent = typeof cite.similarity_score === 'number' ? Math.round(cite.similarity_score * 100) : null;

          return (
            <button
              key={index}
              onClick={() => setSelectedCitation(cite)}
              className="group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] hover:border-white/20 hover:bg-white/[0.08] transition-all text-xs text-zinc-300 font-mono"
            >
              {isWeb ? (
                <Globe size={12} className="text-cyan-400 group-hover:scale-110 transition-transform" />
              ) : (
                <FileCode size={12} className="text-zinc-400 group-hover:scale-110 transition-transform" />
              )}
              <span className="truncate max-w-[200px]">{fileName}{lineRef}</span>
              {scorePercent && (
                <span className="text-[10px] text-zinc-500 group-hover:text-zinc-400 font-normal">
                  {scorePercent}%
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Interactive Code Preview Modal/Popup */}
      {selectedCitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="relative w-full max-w-2xl rounded-xl border border-white/15 bg-[#0d0d14] p-5 shadow-2xl text-xs space-y-4">
            
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <FileCode size={14} className="text-zinc-300" />
                  <span className="font-mono font-semibold text-white text-sm">
                    {selectedCitation.file_path}
                  </span>
                </div>
                {selectedCitation.chunk_name && (
                  <p className="text-zinc-400 font-mono text-xs">
                    Symbol: <span className="text-white font-medium">{selectedCitation.chunk_name}</span>
                  </p>
                )}
                {selectedCitation.start_line && (
                  <p className="text-zinc-500 font-mono text-[11px]">
                    Lines {selectedCitation.start_line} to {selectedCitation.end_line}
                  </p>
                )}
              </div>

              <button
                onClick={() => setSelectedCitation(null)}
                className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Code Snippet */}
            <div className="rounded-lg bg-[#050507] border border-white/10 p-3 overflow-x-auto font-mono text-xs text-zinc-300 max-h-80">
              <pre>
                <code>{selectedCitation.snippet || '// AST Code excerpt retrieved from vector store'}</code>
              </pre>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/10 text-[11px] text-zinc-500">
              <span>Similarity Match: {selectedCitation.similarity_score ? `${Math.round(selectedCitation.similarity_score * 100)}%` : 'Direct AST'}</span>
              <button
                onClick={() => setSelectedCitation(null)}
                className="px-3 py-1 rounded bg-white/10 hover:bg-white/15 text-white font-medium transition-colors"
              >
                Close Preview
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
