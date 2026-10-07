// REST-klient mod SCADA-serveren. Viser ALTID serverens specifikke fejltekst (CLAUDE.md regel 12).

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Udtræk den mest specifikke fejltekst fra et svar — `{"error": "..."}` er normalformen. */
export function errorText(status: number, body: unknown, fallback: string): string {
  if (body && typeof body === 'object') {
    const err = (body as Record<string, unknown>).error ?? (body as Record<string, unknown>).detail;
    if (typeof err === 'string' && err.trim()) return err.trim();
    if (Array.isArray(err) && err.length) {
      return err.map((e) => (e && typeof e === 'object' && 'msg' in e ? String(e.msg) : String(e))).join('; ');
    }
  }
  if (typeof body === 'string' && body.trim()) return body.trim().slice(0, 300);
  return fallback || `HTTP ${status}`;
}

export async function api<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(path, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, `Ingen forbindelse til SCADA-serveren (${(e as Error).message})`);
  }
  if (resp.status === 204) return undefined as T;
  const text = await resp.text();
  let data: unknown = text;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    // Ikke-JSON (fx en proxy-fejlside) — teksten bruges som fejlbesked nedenfor.
  }
  if (!resp.ok) throw new ApiError(resp.status, errorText(resp.status, data, resp.statusText));
  return data as T;
}

export const get = <T>(path: string) => api<T>('GET', path);
export const post = <T>(path: string, body: unknown) => api<T>('POST', path, body);
export const patch = <T>(path: string, body: unknown) => api<T>('PATCH', path, body);
export const put = <T>(path: string, body: unknown) => api<T>('PUT', path, body);
export const del = (path: string) => api<void>('DELETE', path);

// --- typer der matcher backend

export interface LiveValue {
  value: unknown;
  quality: 'good' | 'comm_error' | 'bad' | 'unknown';
  ts: number;
  error: string | null;
}

export interface TagMeta {
  unit: string;
  decimals: number | null;
  description: string;
  plc: string;
}

export interface Binding {
  element: string;
  tag: string;
  anim: 'text' | 'fill' | 'stroke' | 'visible' | 'blink' | 'level' | 'rotate' | 'opacity';
  params: Record<string, any>;
  source?: 'explicit' | 'auto';
}

export interface DrawingView {
  id: string;
  name: string;
  version: number;
  svg: string;
  bindings: Binding[];
  orphaned_bindings: string[];
  tags: Record<string, TagMeta>;
}

export interface PlcSummary {
  name: string;
  state: string;
  message: string;
  sse: string | null;
}
