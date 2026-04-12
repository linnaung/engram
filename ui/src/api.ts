const BASE = '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface Status {
  episodes: number;
  concepts: number;
  facts: number;
  beliefs: number;
  edges: number;
  sessions: number;
  context_loaded: boolean;
  data_dir: string;
}

export interface RecallItem {
  content: string;
  layer: string;
  score: number;
  confidence: number;
  source_id: string;
}

export interface FactItem {
  subject: string;
  predicate: string;
  object: string;
  subject_type: string;
  object_type: string;
  confidence: number;
  id: string;
}

export interface BeliefItem {
  id: string;
  principle: string;
  confidence: number;
}

export interface EdgeItem {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface EpisodeItem {
  id: string;
  content: string;
  source: string;
  timestamp: string;
  confidence: number;
}

export interface ConceptItem {
  id: string;
  summary: string;
  confidence: number;
  reinforcement_count: number;
}

export interface ChatMemory {
  content: string;
  layer: string;
  score: number;
  confidence: number;
}

export interface ChatResponse {
  response: string;
  memories_used: ChatMemory[];
}

export interface SessionItem {
  id: string;
  title: string;
  created_at: string;
  ontology_path: string | null;
  last_message: string | null;
  message_count: number;
}

export interface MessageItem {
  id: string;
  role: string;
  content: string;
  created_at: string;
  memories_used: ChatMemory[];
}

export interface SynthesizeResult {
  episodes_processed: number;
  concepts_created: number;
  facts_created: number;
  fact_contradictions: number;
  concepts_merged: number;
  beliefs_created: number;
  edges_created: number;
  contradictions_resolved: number;
  episodes_garbage_collected: number;
}

export interface SimulateStep {
  day: number;
  episodes: number;
  concepts: number;
  facts: number;
  beliefs: number;
}

export interface ContextInfo {
  loaded: boolean;
  types: string[];
  predicates: string[];
  type_count: number;
  predicate_count: number;
}

export const api = {
  status: () => request<Status>('/status'),

  // Session management
  listSessions: () =>
    request<{ sessions: SessionItem[] }>('/sessions'),

  createSession: (title = 'New Chat') =>
    request<SessionItem>('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }),

  getSession: (id: string) =>
    request<{ session: SessionItem; messages: MessageItem[] }>(`/sessions/${id}`),

  deleteSession: (id: string) =>
    request<{ deleted: boolean }>(`/sessions/${id}`, { method: 'DELETE' }),

  sessionChat: (sessionId: string, message: string) =>
    request<ChatResponse>(`/sessions/${sessionId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    }),

  uploadSessionOntology: (sessionId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<{ loaded: boolean; types: string[]; predicates: string[] }>(
      `/sessions/${sessionId}/ontology`,
      { method: 'POST', body: form }
    );
  },

  // Legacy chat (no session)
  chat: (message: string, history: { role: string; content: string }[] = []) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
    }),

  ingest: (text: string, source = 'conversation') =>
    request<{ id: string; content: string }>('/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source }),
    }),

  recall: (query: string, top_k = 10) =>
    request<{ results: RecallItem[]; count: number }>('/recall', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k }),
    }),

  synthesize: () =>
    request<SynthesizeResult>('/synthesize', { method: 'POST' }),

  episodes: (limit = 50) =>
    request<{ episodes: EpisodeItem[]; count: number }>(`/episodes?limit=${limit}`),

  concepts: (limit = 50) =>
    request<{ concepts: ConceptItem[]; count: number }>(`/concepts?limit=${limit}`),

  facts: (subject?: string) =>
    request<{ facts: FactItem[]; count: number }>(
      `/facts${subject ? `?subject=${encodeURIComponent(subject)}` : ''}`
    ),

  beliefs: () =>
    request<{ beliefs: BeliefItem[]; edges: EdgeItem[] }>('/beliefs'),

  context: () => request<ContextInfo>('/context'),

  uploadContext: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<{ loaded: boolean; types: string[]; predicates: string[]; filename: string }>(
      '/context/upload',
      { method: 'POST', body: form }
    );
  },

  simulate: (days = 365, step = 30) =>
    request<{ steps: SimulateStep[]; total_episodes: number; total_concepts: number; total_facts: number; total_beliefs: number }>(
      `/simulate?days=${days}&step=${step}`
    ),

  forget: (id: string) =>
    request<{ forgotten: boolean }>(`/forget/${id}`, { method: 'DELETE' }),
};
