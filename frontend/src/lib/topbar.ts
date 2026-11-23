// Rene hjælpefunktioner til topbaren (ur, brugernavn, PLC-/forbindelseschip). Ingen DOM, ingen netværk.
import type { PlcSummary } from './api';

export type ChipLevel = 'ok' | 'warn' | 'error' | 'pending';
export interface PlcChip { label: string; level: ChipLevel; title: string }

const p2 = (n: number) => String(n).padStart(2, '0');

/** HH:MM:SS i browserens lokale tid. */
export function formatClock(d: Date): string {
  return `${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}`;
}

/** Dato og tidszone til tooltip, fx "2026-11-23 · Europe/Copenhagen". */
export function clockTitle(d: Date): string {
  let tz = '';
  try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch { /* ukendt tidszone */ }
  const off = -d.getTimezoneOffset();
  const sign = off < 0 ? '-' : '+';
  const utc = `UTC${sign}${p2(Math.floor(Math.abs(off) / 60))}:${p2(Math.abs(off) % 60)}`;
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())} · ${tz ? `${tz} (${utc})` : utc}`;
}

/** Afkort et navn med ellipsis (standard 10 tegn). */
export function shortName(name: string | null | undefined, max = 10): string {
  const n = (name ?? '').trim();
  if (!n) return '';
  const chars = [...n];
  return chars.length <= max ? n : chars.slice(0, Math.max(1, max - 1)).join('') + '…';
}

const OK_STATES = new Set(['ok', 'connected']);
const PENDING_STATES = new Set(['connecting']);
const STATE_TXT: Record<string, string> = {
  ok: 'ok', connected: 'ok', connecting: 'henter', stopped: 'stoppet', error: 'fejl',
};

/** Samlet status for PLC'erne fra live-strømmen + forbindelsen til SCADA-serveren. */
export function plcChip(plcs: Record<string, PlcSummary> | null | undefined, connected: boolean): PlcChip {
  const entries = Object.entries(plcs ?? {});
  const lines = entries.map(([key, p]) => {
    const name = (p?.name || '').trim() || key;
    const state = p?.state || 'ukendt';
    const msg = (p?.message || '').trim();
    return `${name}: ${STATE_TXT[state] ?? state}${msg && msg !== state ? ` — ${msg}` : ''}`;
  });
  if (!connected) {
    return { label: 'Ingen forbindelse', level: 'error',
      title: ['Forbindelsen til SCADA-serveren er afbrudt — værdierne er ikke opdaterede.', ...lines].join('\n') };
  }
  if (!entries.length) return { label: 'PLC …', level: 'pending', title: 'Henter PLC-status …' };
  let ok = 0, error = 0, warn = 0, pending = 0;
  for (const [, p] of entries) {
    const s = p?.state ?? '';
    if (OK_STATES.has(s)) ok++;
    else if (PENDING_STATES.has(s)) pending++;
    else if (s === 'error') error++;
    else warn++;   // stopped og ukendte tilstande
  }
  const level: ChipLevel = error ? 'error' : warn ? 'warn' : pending ? 'pending' : 'ok';
  return { label: `PLC ${ok}/${entries.length}`, level, title: lines.join('\n') };
}
