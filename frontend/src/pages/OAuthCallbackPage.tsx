import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sparkles, AlertCircle } from 'lucide-react';
import { authService } from '../services/auth';
import { api } from '../services/api';

export default function OAuthCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function handleAuth() {
      try {
        // Check query parameters
        let accessToken = searchParams.get('access_token');
        let refreshToken = searchParams.get('refresh_token');
        let userId = searchParams.get('user_id');

        // Check hash parameters (if tokens passed in #)
        if (!accessToken && window.location.hash) {
          const hashParams = new URLSearchParams(window.location.hash.substring(1));
          accessToken = hashParams.get('access_token');
          refreshToken = hashParams.get('refresh_token');
          userId = hashParams.get('user_id');
        }

        if (accessToken) {
          authService.setTokens({
            access_token: accessToken,
            refresh_token: refreshToken || '',
            token_type: 'bearer',
            expires_in: 3600,
            user_id: userId || '',
          });

          // Fetch user profile and cache it
          try {
            await api.getMe();
          } catch (profileErr) {
            console.warn('Profile fetch warning:', profileErr);
          }

          // Redirect to workspace
          navigate('/workspace', { replace: true });
        } else {
          setError('No authentication tokens found in callback.');
        }
      } catch (err: any) {
        setError(err.message || 'Failed to complete Google authentication.');
      }
    }

    handleAuth();
  }, [navigate, searchParams]);

  return (
    <div className="min-h-screen bg-[#050507] text-[#eaeaf0] flex items-center justify-center p-4">
      <div className="max-w-md w-full p-8 rounded-2xl glass-card text-center space-y-4 border border-white/10 shadow-2xl">
        {error ? (
          <>
            <div className="w-12 h-12 rounded-xl bg-rose-950/40 border border-rose-800/40 text-rose-400 mx-auto flex items-center justify-center">
              <AlertCircle size={22} />
            </div>
            <h2 className="text-base font-semibold text-white">Authentication Failed</h2>
            <p className="text-xs text-zinc-400 font-mono">{error}</p>
            <button
              onClick={() => navigate('/auth')}
              className="mt-4 px-4 py-2 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-all shadow"
            >
              Back to Sign In
            </button>
          </>
        ) : (
          <>
            <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 text-white mx-auto flex items-center justify-center animate-pulse">
              <Sparkles size={22} />
            </div>
            <h2 className="text-base font-semibold text-white tracking-tight">Authenticating with Google...</h2>
            <p className="text-xs text-zinc-400 font-mono">
              Establishing secure session. Redirecting to Developer Studio...
            </p>
          </>
        )}
      </div>
    </div>
  );
}
