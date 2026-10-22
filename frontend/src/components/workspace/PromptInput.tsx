import { useState, useRef, useEffect } from 'react';
import { ArrowUp, CornerDownLeft } from 'lucide-react';

interface PromptInputProps {
  onSend: (message: string) => void;
  loading?: boolean;
  disabled?: boolean;
}

export default function PromptInput({ onSend, loading = false, disabled = false }: PromptInputProps) {
  const [content, setContent] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [content]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!content.trim() || loading || disabled) return;
    onSend(content.trim());
    setContent('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  return (
    <div className="p-4 border-t border-white/[0.06] bg-[#07070a]/90 backdrop-blur-xl">
      <div className="max-w-4xl mx-auto">
        <div className="relative rounded-2xl glass-input p-2 flex items-end gap-2 focus-within:border-white/20 transition-all">
          
          <textarea
            ref={textareaRef}
            rows={1}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading || disabled}
            placeholder="Ask about your code, debug stack traces, or search AST symbols..."
            className="flex-1 bg-transparent resize-none outline-none text-xs sm:text-sm text-white placeholder-zinc-500 py-1.5 px-2 max-h-44 overflow-y-auto leading-relaxed"
          />

          <div className="flex items-center gap-2 shrink-0 pb-0.5">
            <span className="hidden sm:inline-flex items-center gap-1 text-[10px] font-mono text-zinc-500 pr-1">
              <span>Return</span>
              <CornerDownLeft size={10} />
            </span>

            <button
              onClick={handleSubmit}
              disabled={!content.trim() || loading || disabled}
              className="w-8 h-8 rounded-xl bg-white text-black disabled:bg-zinc-800 disabled:text-zinc-600 flex items-center justify-center transition-all hover:scale-105 active:scale-95 shadow"
            >
              <ArrowUp size={15} />
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
