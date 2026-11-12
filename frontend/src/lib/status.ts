// System › Status: typer og formatering til /api/health/details (v3.15.0). Vurderingen (gul/rød) laves af serveren.
export type Level = 'ok' | 'warn' | 'error';

export interface Problem { level: Level; area: string; message: string }
export interface PlcHealth {
  key: string; name: string; enabled: boolean; state: string; message: string; attention: boolean;
  last_ok_age_s: number | null; request_rate: number | null; requests_per_cycle: number | null;
  throttled: number; last_throttled: number | null;
  partial: { what: string; message: string; tags: number }[]; cycles: number | null; errors: number | null; sse: string | null;
}
export interface Health {
  now: number; started: number; uptime_s: number; version: { version: string; build: string };
  level: Level; problems: Problem[]; plcs: PlcHealth[];
  loop: { lag_last_s: number; lag_max_s: number | null };
  ws_clients: number; alarms: { active: number; unacked: number; high: number };
  db: { ok: boolean; latency_s: number | null; error?: string };
  disk: { total: number; used: number; free: number } | null;
  host: { mem_total: number | null; mem_available: number | null; load: number[] | null; cpu_temp_c: number | null;
          throttled: { now: string[]; past: string[] } | null; time_sync?: boolean | null };
  trends: { db_bytes: number | null; rows: number; flushes: number; rows_per_day: number | null };
  backup: { interval_h: number; count: number; last_age_s: number | null };
  tls: Tls | null;
  assist?: { asks?: number; requests: number; errors: number; busy: number; waiting: number; last_ms: number } | null;
}
export interface Tls { issuer: string; subject: string; self_signed: boolean; fingerprint: string; not_after_ts: number; days_left: number }

export const LEVEL_TEXT: Record<Level, string> = { ok: 'Alt i orden', warn: 'Opmærksomhed', error: 'Fejl' };
export const AREA_TEXT: Record<string, string> = {
  plc: "PLC'er", server: 'Server', database: 'Database', disk: 'Disk', host: 'Maskine', backup: 'Backup', tls: 'Certifikat', notify: 'Notifikation',
};

export function fmtBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
  return `${Math.max(0, Math.round(n / 1e3))} kB`;
}

/** 93784 s → "1 d 2 t 3 min"; under et minut: "12 s". */
export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return [d ? `${d} d` : '', d || h ? `${h} t` : '', `${m} min`].filter(Boolean).join(' ');
}

export function fmtMs(seconds: number | null | undefined): string {
  return seconds === null || seconds === undefined ? '—' : `${(seconds * 1000).toFixed(seconds < 0.01 ? 1 : 0)} ms`;
}

export function fmtPercent(part: number | null | undefined, total: number | null | undefined): string {
  return part === null || part === undefined || !total ? '—' : `${Math.round((part / total) * 100)} %`;
}

/** Badge-klasse (app.css) ud fra niveau. */
export const levelClass = (l: Level): string => (l === 'ok' ? 'ok' : l === 'error' ? 'error' : 'warn');

/** Udstederens organisation eller fælles navn ("C=US, O=Let's Encrypt, CN=R11" → "Let's Encrypt"). */
export function issuerName(issuer: string): string {
  const part = (k: string) => new RegExp(`(?:^|,\\s*)${k}=([^,]+)`).exec(issuer)?.[1]?.trim();
  return part('O') ?? part('CN') ?? issuer;
}

/** Kortets overskrift og forklaring: "42 dage" og hvem der har udstedt (selvsigneret fremhæves). */
export function certSummary(tls: Tls): { big: string; note: string } {
  const big = tls.days_left < 0 ? 'udløbet' : tls.days_left === 1 ? '1 dag' : `${tls.days_left} dage`;
  const note = tls.self_signed
    ? 'Selvsigneret — browsere advarer; se Let\'s Encrypt i manualen'
    : `${issuerName(tls.issuer)} · ${tls.subject.replace(/^CN=/, '')}`;
  return { big, note };
}
