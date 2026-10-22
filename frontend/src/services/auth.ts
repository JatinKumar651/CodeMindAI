import type { AuthTokens, User } from '../types';

const TOKEN_KEY = 'codemind_auth_tokens';
const USER_KEY = 'codemind_user';

export const authService = {
  getTokens(): AuthTokens | null {
    try {
      const item = localStorage.getItem(TOKEN_KEY);
      return item ? JSON.parse(item) : null;
    } catch {
      return null;
    }
  },

  setTokens(tokens: AuthTokens): void {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  },

  clearTokens(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  getUser(): User | null {
    try {
      const item = localStorage.getItem(USER_KEY);
      return item ? JSON.parse(item) : null;
    } catch {
      return null;
    }
  },

  setUser(user: User): void {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  getAuthHeader(): Record<string, string> {
    const tokens = this.getTokens();
    if (tokens?.access_token) {
      return { Authorization: `Bearer ${tokens.access_token}` };
    }
    return {};
  },

  isAuthenticated(): boolean {
    return Boolean(this.getTokens()?.access_token);
  },
};
