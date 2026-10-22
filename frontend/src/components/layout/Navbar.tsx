import { Link, useLocation } from 'react-router-dom';
import { Terminal, Shield, Activity, Settings, User, LogOut } from 'lucide-react';
import { authService } from '../../services/auth';

export default function Navbar() {
  const location = useLocation();
  const user = authService.getUser();
  const isAuthenticated = authService.isAuthenticated();

  const handleLogout = () => {
    authService.clearTokens();
    window.location.href = '/';
  };

  const navLinks = [
    { name: 'Studio', href: '/workspace', icon: Terminal },
    { name: 'Repo Health', href: '/repo-health', icon: Activity },
    { name: 'Settings', href: '/settings', icon: Settings },
    { name: 'About', href: '/about' },
    { name: 'Contact', href: '/contact' },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[#050507]/80 backdrop-blur-xl border-b border-white/[0.06]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        
        {/* Brand Logo */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-950 border border-white/10 flex items-center justify-center group-hover:border-white/25 transition-all shadow-inner">
            <span className="font-mono text-xs font-bold text-white tracking-tight">CM</span>
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold tracking-tight text-white flex items-center gap-1.5">
              CodeMind <span className="text-zinc-500 font-normal">AI</span>
            </span>
            <span className="text-[10px] text-zinc-500 font-mono -mt-0.5 tracking-wider">
              AGENTIC RAG
            </span>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            const isActive = location.pathname === link.href;
            const Icon = link.icon;
            return (
              <Link
                key={link.name}
                to={link.href}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 ${
                  isActive
                    ? 'text-white bg-white/[0.06] border border-white/10 shadow-sm'
                    : 'text-zinc-400 hover:text-white hover:bg-white/[0.03]'
                }`}
              >
                {Icon && <Icon size={14} className={isActive ? 'text-white' : 'text-zinc-500'} />}
                {link.name}
              </Link>
            );
          })}
        </nav>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <div className="flex items-center gap-2">
              <Link
                to="/settings"
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all text-xs text-zinc-300"
              >
                <User size={13} className="text-zinc-400" />
                <span className="max-w-[120px] truncate">{user?.email || 'User'}</span>
              </Link>
              <button
                onClick={handleLogout}
                title="Log out"
                className="p-1.5 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-rose-400 transition-colors"
              >
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/auth"
                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link
                to="/workspace"
                className="px-3.5 py-1.5 rounded-lg bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all shadow-[0_0_20px_rgba(255,255,255,0.15)] flex items-center gap-1.5"
              >
                <Terminal size={13} />
                Open Studio
              </Link>
            </div>
          )}
        </div>

      </div>
    </header>
  );
}
