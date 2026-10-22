import { Mail, MessageSquare, Shield, Send } from 'lucide-react';
import { useState } from 'react';
import Navbar from '../components/layout/Navbar';
import Footer from '../components/layout/Footer';

export default function ContactPage() {
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-[#050507] text-[#eaeaf0] flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 pt-24 pb-16 space-y-12">
        
        <div className="space-y-3 border-b border-white/[0.06] pb-8">
          <span className="text-xs font-mono text-zinc-500 uppercase tracking-wider">
            Contact & Support
          </span>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Enterprise VPC & Developer Community
          </h1>
          <p className="text-sm text-zinc-400 leading-relaxed max-w-xl font-normal">
            Need on-premise deployment, custom AST parsers for proprietary languages, or dedicated support? Reach out to our engineering team.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          
          {/* Contact Form */}
          <div className="p-6 rounded-2xl glass-card space-y-4">
            <h3 className="text-sm font-semibold text-white">Send an Enterprise Inquiry</h3>

            {submitted ? (
              <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-800/40 text-xs text-emerald-300 font-mono space-y-1">
                <p className="font-semibold">Thank you for contacting us.</p>
                <p className="text-zinc-400">Our engineering leads will respond within 24 hours.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-3 text-xs">
                <div>
                  <label className="block text-zinc-400 font-mono text-[11px] mb-1">Your Name</label>
                  <input
                    type="text"
                    required
                    placeholder="Jane Doe"
                    className="w-full px-3 py-2 rounded-xl glass-input text-white"
                  />
                </div>

                <div>
                  <label className="block text-zinc-400 font-mono text-[11px] mb-1">Work Email</label>
                  <input
                    type="email"
                    required
                    placeholder="jane@enterprise.com"
                    className="w-full px-3 py-2 rounded-xl glass-input text-white"
                  />
                </div>

                <div>
                  <label className="block text-zinc-400 font-mono text-[11px] mb-1">Message</label>
                  <textarea
                    rows={4}
                    required
                    placeholder="Tell us about your team size, repository volume, and deployment requirements..."
                    className="w-full px-3 py-2 rounded-xl glass-input text-white resize-none"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all flex items-center justify-center gap-1.5 shadow"
                >
                  <Send size={13} />
                  Submit Inquiry
                </button>
              </form>
            )}
          </div>

          {/* Direct channels */}
          <div className="space-y-4">
            <div className="p-5 rounded-2xl glass-card space-y-2">
              <div className="flex items-center gap-2 text-white text-xs font-semibold">
                <Mail size={15} />
                <span>Direct Engineering Email</span>
              </div>
              <p className="text-xs text-zinc-400 font-mono">
                team@codemind.ai
              </p>
            </div>

            <div className="p-5 rounded-2xl glass-card space-y-2">
              <div className="flex items-center gap-2 text-white text-xs font-semibold">
                <Shield size={15} />
                <span>Security & Zero-Retention Audits</span>
              </div>
              <p className="text-xs text-zinc-400">
                CodeMind AI runs completely stateless. Your code chunks and AST trees never leave your private VPC.
              </p>
            </div>

            <div className="p-5 rounded-2xl glass-card space-y-2">
              <div className="flex items-center gap-2 text-white text-xs font-semibold">
                <MessageSquare size={15} />
                <span>Discord Developer Community</span>
              </div>
              <p className="text-xs text-zinc-400">
                Join our Discord to discuss Agentic RAG architectures, LangGraph custom nodes, and AST chunking.
              </p>
            </div>
          </div>

        </div>

      </main>

      <Footer />
    </div>
  );
}
