import { useState, useEffect } from 'react';
import { useNavigate, Link, useSearchParams } from 'react-router-dom';
import { Terminal, Lock, Mail, ArrowRight, ShieldCheck } from 'lucide-react';
import Navbar from '../components/layout/Navbar';
import Footer from '../components/layout/Footer';
import { api } from '../services/api';

export default function AuthPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const err = searchParams.get('error');
    if (err) {
      setError(decodeURIComponent(err));
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;

    setLoading(true);
    setError(null);

    try {
      if (isSignUp) {
        await api.signup(email, password);
      } else {
        await api.login(email, password);
      }
      navigate('/workspace');
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      const res = await api.getGoogleOAuthUrl();
      if (res?.url) {
        window.location.href = res.url;
      }
    } catch (err: any) {
      setError('Google OAuth initialization failed: ' + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-[#050507] text-[#eaeaf0] flex flex-col">
      <Navbar />

      <main className="flex-1 flex items-center justify-center p-4 pt-20 pb-16">
        <div className="w-full max-w-md rounded-2xl glass-card p-6 sm:p-8 space-y-6 shadow-2xl border border-white/10">
          
          <div className="text-center space-y-2">
            <div className="w-10 h-10 rounded-xl bg-white/[0.05] border border-white/10 mx-auto flex items-center justify-center text-white">
              <Terminal size={18} />
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              {isSignUp ? 'Create your account' : 'Welcome back to CodeMind AI'}
            </h2>
            <p className="text-xs text-zinc-400">
              Deterministic code intelligence and AST error debugging.
            </p>
          </div>

          {/* Google SSO Button */}
          <button
            onClick={handleGoogleLogin}
            type="button"
            className="w-full py-2.5 px-4 rounded-xl bg-white/[0.04] border border-white/10 hover:bg-white/[0.08] hover:border-white/20 transition-all flex items-center justify-center gap-3 text-xs font-medium text-white shadow-sm"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="#EA4335"
                d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z"
              />
              <path
                fill="#4285F4"
                d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z"
              />
              <path
                fill="#FBBC05"
                d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12 0 14.5s.7 4.8 1.9 7.2l3.7-2.9z"
              />
              <path
                fill="#34A853"
                d="M12 23.5c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16.5C3.7 20.4 7.5 23.5 12 23.5z"
              />
            </svg>
            Continue with Google
          </button>

          <div className="relative flex items-center justify-center">
            <div className="border-t border-white/[0.06] w-full" />
            <span className="bg-[#0e0e14] px-2.5 text-[11px] font-mono text-zinc-500 uppercase tracking-wider">
              Or with email
            </span>
            <div className="border-t border-white/[0.06] w-full" />
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/40 text-xs text-rose-300 font-mono">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1">Email</label>
              <div className="relative flex items-center">
                <Mail size={14} className="absolute left-3 text-zinc-500" />
                <input
                  type="email"
                  required
                  placeholder="engineer@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl glass-input text-xs text-white"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1">Password</label>
              <div className="relative flex items-center">
                <Lock size={14} className="absolute left-3 text-zinc-500" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl glass-input text-xs text-white"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all flex items-center justify-center gap-2 shadow disabled:opacity-50"
            >
              <span>{isSignUp ? 'Create Account' : 'Sign In'}</span>
              <ArrowRight size={13} />
            </button>
          </form>

          {/* Switch tab */}
          <div className="text-center text-xs text-zinc-500">
            {isSignUp ? 'Already have an account?' : "Don't have an account yet?"}{' '}
            <button
              onClick={() => setIsSignUp(!isSignUp)}
              className="text-white hover:underline font-medium"
            >
              {isSignUp ? 'Sign In' : 'Sign Up'}
            </button>
          </div>

        </div>
      </main>

      <Footer />
    </div>
  );
}
