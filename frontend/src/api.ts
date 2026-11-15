// Thin client for the Clarity API. Uses the browser's fetch; no extra dependencies.

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
const TOKEN_KEY = 'token';

// ---------------------------------------------------------------- types

export interface User {
  id: number;
  email: string;
  timezone: string;
  created_at: string;
  assessment_completed_at: string | null;
}

export type Mood = 'happy' | 'neutral' | 'sad' | 'energized' | 'tired';

export interface JournalEntry {
  id: number;
  content: string;
  mood: Mood | null;
  tags: string | null;
  entry_date: string;
  created_at: string;
  updated_at: string;
}

export interface JournalStats {
  total_entries: number;
  entries_this_week: number;
  dominant_mood: Mood | null;
  all_tags: string[];
}

export interface CalendarStats {
  has_data: boolean;
  uploaded_at: string | null;
  days_since_upload?: number;
  range_start?: string;
  range_end?: string;
  workdays?: number;
  total_events?: number;
  total_hours?: number;
  avg_events_per_workday?: number;
  avg_hours_per_workday?: number;
  avg_event_minutes?: number;
  busiest_weekday?: string | null;
  busiest_hour?: number | null;
  back_to_back_per_week?: number;
  focus_share?: number | null;
  days_without_focus_block?: number;
  working_hours?: string;
  observations?: string[];
}

export interface UploadResult {
  imported: number;
  skipped: Record<string, number>;
  source: string;
  range_start: string;
  range_end: string;
}

export type InsightStatus = 'pattern' | 'info' | 'no_pattern' | 'need_more_data';

export interface Insight {
  id: string;
  title: string;
  status: InsightStatus;
  strength: 'early' | 'consistent' | null;
  text: string;
  suggestion: string | null;
  evidence: { days?: number; entries?: number } & Record<string, unknown>;
  progress: { have: number; need: number } | null;
}

export interface InsightsResponse {
  insights: Insight[];
  patterns_found: number;
  entries: number;
  has_calendar: boolean;
  method_note: string;
  generated_at: string;
}

export interface QuizOption {
  id: string;
  text: string;
}

export interface QuizQuestion {
  id: number;
  text: string;
  options: QuizOption[];
}

export interface QuizProfile {
  profile_type: string;
  profile_name: string;
  profile_emoji: string;
  description: string;
  strengths: string[];
  optimal_schedule: string;
  meeting_preference: string;
  tips: string[];
  disclaimer: string;
}

// ---------------------------------------------------------------- plumbing

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** A message safe to show a person, whatever was thrown. */
export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.message) return error.message;
  return fallback;
}

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token: string): void => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage unavailable: the session lasts until the page reloads */
    }
  },
  clear: (): void => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* nothing to clear */
    }
  },
};

let unauthorizedHandler: (() => void) | null = null;

/** Called when the server rejects our token, so the app can send the person back to login. */
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

function describeError(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === 'string') return first.msg.replace(/^Value error, /, '');
  }
  if (status === 413) return 'That file is too large.';
  if (status >= 500) return 'Something went wrong on our side. Please try again.';
  return 'Request failed. Please try again.';
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | undefined>;
  /** Login and signup failures are not "session expired". */
  skipUnauthorizedHandler?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let url = API_BASE_URL + path;
  if (options.query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined && value !== '') params.set(key, String(value));
    }
    const queryString = params.toString();
    if (queryString) url += '?' + queryString;
  }

  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let payload: BodyInit | undefined;
  if (options.form) {
    payload = options.form; // the browser sets the multipart boundary itself
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(url, { method: options.method || 'GET', headers, body: payload });
  } catch {
    throw new ApiError(0, "Can't reach the server. It may be waking up; try again in a minute.");
  }

  if (response.status === 204) return undefined as T;

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    if (response.status === 401 && !options.skipUnauthorizedHandler) {
      tokenStore.clear();
      if (unauthorizedHandler) unauthorizedHandler();
    }
    throw new ApiError(response.status, describeError(body, response.status));
  }
  return body as T;
}

// ---------------------------------------------------------------- endpoints

export const auth = {
  config: () => request<{ invite_required: boolean }>('/auth/config'),

  signup: (email: string, password: string, inviteCode?: string) =>
    request<User>('/auth/signup', {
      method: 'POST',
      body: { email, password, timezone: browserTimezone(), invite_code: inviteCode || undefined },
      skipUnauthorizedHandler: true,
    }),

  login: async (email: string, password: string): Promise<void> => {
    const result = await request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: { email, password },
      skipUnauthorizedHandler: true,
    });
    tokenStore.set(result.access_token);
  },

  logout: (): void => tokenStore.clear(),

  getMe: () => request<User>('/auth/me'),
};

export const account = {
  setTimezone: (timezone: string) => request<User>('/account', { method: 'PATCH', body: { timezone } }),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<void>('/account/password', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword },
    }),

  exportData: () => request<Record<string, unknown>>('/account/export'),

  deleteAccount: (password: string) => request<void>('/account/delete', { method: 'POST', body: { password } }),
};

export const journal = {
  createEntry: (content: string, mood: Mood | null, tags: string | null) =>
    request<JournalEntry>('/journal/entries', {
      method: 'POST',
      body: { content, mood, tags, timezone: browserTimezone() },
    }),

  listEntries: (params: { search?: string; mood?: string; limit?: number } = {}) =>
    request<JournalEntry[]>('/journal/entries', { query: params }),

  updateEntry: (id: number, data: { content?: string; mood?: Mood | null; tags?: string | null }) =>
    request<JournalEntry>(`/journal/entries/${id}`, { method: 'PATCH', body: data }),

  deleteEntry: (id: number) => request<void>(`/journal/entries/${id}`, { method: 'DELETE' }),

  getStats: () => request<JournalStats>('/journal/stats'),
};

export const calendar = {
  upload: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    form.append('timezone', browserTimezone());
    return request<UploadResult>('/calendar/upload', { method: 'POST', form });
  },

  getStats: () => request<CalendarStats>('/calendar/stats'),

  deleteAll: () => request<void>('/calendar/events', { method: 'DELETE' }),
};

export const insights = {
  get: () => request<InsightsResponse>('/insights'),
};

export const assessment = {
  getQuestions: () =>
    request<{ questions: QuizQuestion[]; total_questions: number; disclaimer: string }>('/assessment/questions'),

  submit: (answers: Record<string, string>) =>
    request<{ profile: QuizProfile }>('/assessment/submit', { method: 'POST', body: { answers } }),

  getProfile: () =>
    request<{ has_profile: boolean; profile: QuizProfile | null; completed_at: string | null }>(
      '/assessment/profile',
    ),

  reset: () => request<void>('/assessment/profile', { method: 'DELETE' }),
};
