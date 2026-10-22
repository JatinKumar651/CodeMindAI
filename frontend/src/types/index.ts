/* ================================================================
   CodeMind AI — Type Definitions
   Directly mapped to FastAPI backend models and schemas
   ================================================================ */

export type Role = 'user' | 'assistant' | 'system';

/** Citation schema returned by Agentic RAG pipeline */
export interface Citation {
  file_path: string;
  chunk_name?: string | null;
  start_line?: number | null;
  end_line?: number | null;
  similarity_score?: number | null;
  snippet?: string;
}

/** Node execution in LangGraph Agent Trace */
export interface AgentTraceStep {
  name: string;
  label: string;
  status: 'completed' | 'running' | 'skipped' | 'failed';
  duration_ms?: number;
  summary?: string;
  data?: Record<string, any>;
}

/** Full agent trace matching LangGraph backend */
export interface AgentTrace {
  router?: {
    intent: string;
    is_error_query?: boolean;
    error_type?: string;
    file_hint?: string;
  };
  retriever?: {
    total_retrieved: number;
    file_count?: number;
  };
  grader?: {
    total_graded: number;
    passed_count: number;
    avg_score?: number;
    rewritten_query?: string;
  };
  web_searcher?: {
    invoked: boolean;
    sources_count?: number;
    query_used?: string;
  };
  validator?: {
    confidence_score: number;
    passed: boolean;
    reason?: string;
  };
  generator?: {
    model_used?: string;
    tokens_used?: number;
  };
}

/** Chat message matching MessageResponse schema */
export interface Message {
  id: string;
  session_id: string;
  role: Role;
  content: string;
  citations: Citation[];
  agent_trace?: AgentTrace | null;
  tokens_used?: number;
  latency_ms?: number | null;
  model_used?: string | null;
  needs_review?: boolean;
  created_at: string;
}

/** Chat session matching SessionResponse */
export interface Session {
  id: string;
  repository_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

/** Repository matching RepoResponse */
export interface Repository {
  id: string;
  name: string;
  github_url?: string | null;
  default_branch: string;
  language?: string | null;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  total_chunks?: number;
  created_at: string;
  updated_at: string;
}

/** Security & quality scan matching ScanResponse */
export interface Scan {
  id: string;
  repository_id: string;
  scan_type: 'security' | 'dead_code' | 'complexity' | 'tests' | 'deps' | 'documentation';
  status: 'pending' | 'running' | 'completed' | 'failed';
  results: Record<string, any>;
  summary?: string | null;
  severity_counts: {
    high: number;
    medium: number;
    low: number;
  };
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

/** Authenticated user matching UserResponse */
export interface User {
  id: string;
  email: string;
  role: string;
}

/** Auth token response matching TokenResponse */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
}
