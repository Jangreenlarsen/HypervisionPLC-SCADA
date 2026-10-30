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

let unauthorizedHandler: (() => void) | null = null;

/** App'en registrerer her hvad der skal ske når sessionen er udløbet (vis login). */
export function onUnauthorized(handler: () => void): void {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized(): void {
  unauthorizedHandler?.();
}

export async function api<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
  let resp: Response;
  const file = body instanceof Blob; // filer sendes uændret (fx trend-historik), alt andet som JSON
  try {
    resp = await fetch(path, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': file ? 'application/octet-stream' : 'application/json' },
      body: body === undefined ? undefined : file ? (body as Blob) : JSON.stringify(body),
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
  if (resp.status === 401 && !path.startsWith('/api/auth/')) notifyUnauthorized();
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
  writable?: boolean;
  min?: number | null;
  max?: number | null;
  confirm_write?: boolean;
  kind?: string;
  datatype?: string;
  is_bool?: boolean;
}

export interface Binding {
  element: string;
  tag: string;
  anim: 'text' | 'fill' | 'stroke' | 'visible' | 'blink' | 'level' | 'rotate' | 'opacity' | 'move' | 'flow' | 'spin' | 'flicker' | 'scale' | 'segments'
    | 'click:write' | 'click:toggle' | 'click:pulse' | 'click:select' | 'click:goto';
  params: Record<string, any>;
  source?: 'explicit' | 'auto' | 'symbol' | 'group';
  /** Bindinger dannet af en symbol-konfiguration: symbolets element-id */
  symbol?: string;
  /** Rækkefølgen (symbolets animationer: 1000 + nummer) — bruges til prioriteringen af aktiv/passiv-animationer */
  position?: number;
}

export interface DrawingView {
  id: string;
  name: string;
  version: number;
  /** Deaktiveret tegning (v1.6.0): offline — ingen live-data eller betjening */
  disabled?: boolean;
  svg: string;
  bindings: Binding[];
  orphaned_bindings: string[];
  tags: Record<string, TagMeta>;
  /** Symbolers forklaring (element → tekst), sat under Bindinger. */
  symbols: Record<string, string>;
  /** Symboler med en symbol-konfiguration (symbolstandarden): element → det Overview behøver. */
  symbol_config?: Record<string, import('./symbolUi').SymbolView>;
}

export type Role = 'viewer' | 'operator' | 'panel' | 'engineer' | 'admin';
export const ROLES: Role[] = ['viewer', 'operator', 'panel', 'engineer', 'admin'];
/** Rettighedsniveau (som backendens ROLE_LEVEL): driftpanel = operatør; forskellen er kun visningen (ingen menu). */
const ROLE_LEVEL: Record<Role, number> = { viewer: 0, operator: 1, panel: 1, engineer: 2, admin: 3 };

export function roleAtLeast(role: Role | undefined, required: Role): boolean {
  return !!role && role in ROLE_LEVEL && ROLE_LEVEL[role] >= ROLE_LEVEL[required];
}

export interface Me {
  username: string;
  role: Role;
  must_change_password: boolean;
  drawings: string[] | null; // null = alle tegninger
}

export interface Alarm {
  key: string;
  tag: string;
  plc: string;
  kind: 'high' | 'low' | 'state' | 'comm' | 'symbol';
  level: 'HH' | 'H' | 'L' | 'LL' | 'ON' | 'COMM';
  priority: 'high' | 'medium' | 'low';
  state: 'active_unack' | 'active_ack' | 'rtn_unack';
  raised_at: number;
  value: unknown;
  message: string;
  acked_by: string | null;
  acked_at: number | null;
}

export interface AlarmSummary {
  active: number;
  unacked: number;
  high: number;
}

export interface PlcSummary {
  name: string;
  state: string;
  message: string;
  sse: string | null;
}
