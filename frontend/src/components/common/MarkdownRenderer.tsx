import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Copy, Terminal } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
}

interface CodeBlockProps {
  language?: string;
  value: string;
}

function CodeBlock({ language, value }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  const displayLanguage = (language || 'code').toUpperCase();

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-white/10 bg-[#09090f] shadow-lg">
      {/* Code Header Bar */}
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-white/[0.03] border-b border-white/[0.06] text-[11px] font-mono text-zinc-400">
        <div className="flex items-center gap-1.5">
          <Terminal size={12} className="text-cyan-400" />
          <span className="text-zinc-300 font-semibold tracking-wider text-[10px]">
            {displayLanguage}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded-md hover:bg-white/10 text-zinc-400 hover:text-white transition-colors text-[10px]"
          title="Copy code"
          type="button"
        >
          {copied ? (
            <>
              <Check size={11} className="text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy size={11} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code Content */}
      <div className="p-3.5 overflow-x-auto text-[11.5px] font-mono leading-relaxed text-zinc-200 selection:bg-cyan-500/30">
        <pre className="!bg-transparent !p-0 !m-0 font-mono">
          <code>{value}</code>
        </pre>
      </div>
    </div>
  );
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="markdown-body text-xs text-zinc-200 leading-relaxed font-sans space-y-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Custom Code Blocks and Inline Code
          code({ node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const rawCode = String(children).replace(/\n$/, '');
            const isMultiLine = rawCode.includes('\n');

            // If it has a language or is multi-line, render as code block card
            if (match || isMultiLine) {
              return <CodeBlock language={match ? match[1] : undefined} value={rawCode} />;
            }

            // Inline code snippet
            return (
              <code
                className="bg-white/[0.08] text-cyan-300 px-1.5 py-0.5 rounded font-mono text-[11px] border border-white/10"
                {...props}
              >
                {children}
              </code>
            );
          },

          // Clean up <pre> container so CodeBlock handles its own styling
          pre({ children }) {
            return <div className="not-prose">{children}</div>;
          },

          // Headings
          h1({ children }) {
            return (
              <h1 className="text-base font-bold text-white mt-4 mb-2 pb-1 border-b border-white/10 flex items-center gap-2">
                {children}
              </h1>
            );
          },
          h2({ children }) {
            return (
              <h2 className="text-sm font-semibold text-white mt-3.5 mb-1.5 flex items-center gap-1.5">
                {children}
              </h2>
            );
          },
          h3({ children }) {
            return (
              <h3 className="text-xs font-semibold text-zinc-100 mt-3 mb-1 text-cyan-300">
                {children}
              </h3>
            );
          },

          // Paragraphs
          p({ children }) {
            return <p className="leading-relaxed text-zinc-300 my-1.5">{children}</p>;
          },

          // Unordered Lists
          ul({ children }) {
            return <ul className="list-disc pl-5 my-2 space-y-1 text-zinc-300">{children}</ul>;
          },

          // Ordered Lists
          ol({ children }) {
            return <ol className="list-decimal pl-5 my-2 space-y-1 text-zinc-300">{children}</ol>;
          },

          // List item
          li({ children }) {
            return <li className="leading-relaxed">{children}</li>;
          },

          // Blockquotes
          blockquote({ children }) {
            return (
              <blockquote className="border-l-2 border-cyan-500/70 bg-cyan-950/20 pl-3 py-1.5 my-2.5 text-zinc-300 italic rounded-r-lg">
                {children}
              </blockquote>
            );
          },

          // Strong / Bold
          strong({ children }) {
            return <strong className="font-semibold text-white">{children}</strong>;
          },

          // Tables
          table({ children }) {
            return (
              <div className="overflow-x-auto my-3 rounded-xl border border-white/10 bg-[#09090f]">
                <table className="min-w-full divide-y divide-white/10 text-left text-xs">
                  {children}
                </table>
              </div>
            );
          },
          thead({ children }) {
            return <thead className="bg-white/[0.04] text-zinc-200 font-semibold">{children}</thead>;
          },
          th({ children }) {
            return <th className="px-3.5 py-2 font-mono text-[11px] text-zinc-300">{children}</th>;
          },
          td({ children }) {
            return <td className="px-3.5 py-2 border-t border-white/5 text-zinc-300">{children}</td>;
          },

          // Links
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="text-cyan-400 hover:text-cyan-300 underline underline-offset-2 transition-colors font-medium"
              >
                {children}
              </a>
            );
          },

          // Horizontal rule
          hr() {
            return <hr className="border-white/10 my-3" />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
