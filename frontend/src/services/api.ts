import { authService } from './auth';
import type { 
  AuthTokens, 
  Message, 
  Repository, 
  Scan, 
  Session, 
  User 
} from '../types';

const API_BASE = '';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = {
    'Content-Type': 'application/json',
    ...authService.getAuthHeader(),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    credentials: 'include',
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = 'An error occurred';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.error || JSON.stringify(errJson);
    } catch {
      errorDetail = response.statusText;
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // ── Authentication ──
  async login(email: string, password: string): Promise<AuthTokens> {
    const tokens = await request<AuthTokens>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    authService.setTokens(tokens);
    return tokens;
  },

  async signup(email: string, password: string): Promise<AuthTokens> {
    const tokens = await request<AuthTokens>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    authService.setTokens(tokens);
    return tokens;
  },

  async getGoogleOAuthUrl(): Promise<{ provider: string; url: string }> {
    return request<{ provider: string; url: string }>('/auth/google');
  },

  async getMe(): Promise<User> {
    const user = await request<User>('/auth/me');
    authService.setUser(user);
    return user;
  },

  // ── Repositories (Sourcegraph/Cody Style) ──
  async listRepos(): Promise<Repository[]> {
    const res = await request<any>('/repos');
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.repositories)) return res.repositories;
    return [];
  },

  async createRepo(data: {
    name: string;
    github_url?: string;
    default_branch?: string;
    language?: string;
  }): Promise<Repository> {
    return request<Repository>('/repos', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async ingestRepo(repoId: string): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/repos/${repoId}/ingest`, {
      method: 'POST',
    });
  },

  // ── Sessions & Chat (Cursor/Windsurf Agentic RAG) ──
  async listSessions(repoId: string): Promise<Session[]> {
    const res = await request<any>(`/repos/${repoId}/sessions`);
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.sessions)) return res.sessions;
    return [];
  },

  async createSession(repoId: string, title?: string): Promise<Session> {
    return request<Session>(`/repos/${repoId}/sessions`, {
      method: 'POST',
      body: JSON.stringify({ title: title || 'Main' }),
    });
  },

  async deleteSession(sessionId: string): Promise<void> {
    return request<void>(`/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  },

  async getMessages(sessionId: string): Promise<Message[]> {
    const res = await request<any>(`/sessions/${sessionId}/messages`);
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.messages)) return res.messages;
    return [];
  },

  async sendMessage(sessionId: string, content: string): Promise<Message> {
    return request<Message>(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },

  // ── Quality & Security Scans ──
  async listScans(repoId: string): Promise<Scan[]> {
    const res = await request<any>(`/repos/${repoId}/scans`);
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.scans)) return res.scans;
    return [];
  },

  async triggerScan(repoId: string, scanType: string): Promise<Scan> {
    return request<Scan>(`/repos/${repoId}/scans`, {
      method: 'POST',
      body: JSON.stringify({ scan_type: scanType }),
    });
  },

  // ── System Health ──
  async getHealth(): Promise<{ status: string; [key: string]: any }> {
    return request<{ status: string }>('/health');
  },
};
