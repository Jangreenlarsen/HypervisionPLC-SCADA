// Hjælperen (LLM, v4.1.0): spørgsmål strømmes som server-sent events fra POST /api/assist/ask.
// Ren logik her (SSE-tolkning, kontekst ud fra adressen, samtalen i sessionStorage) — testet i assist.test.ts.
import DOMPurify from 'dompurify';
import { Marked } from 'marked';
import { errorText, notifyUnauthorized } from './api';

const md = new Marked({ gfm: true, breaks: true });
/** Modellens svar (markdown) → ren HTML: kun tekstformatering — ingen links, billeder eller HTML fra modellen. */
export function answerHtml(text: string): string {
  const html = md.parse(text.replace(/</g, '&lt;'), { async: false }) as string;
  return DOMPurify.sanitize(html, { ALLOWED_TAGS: ['p', 'ul', 'ol', 'li', 'strong', 'em', 'code', 'br', 'h3', 'h4'], ALLOWED_ATTR: [] });
}

export interface Source { label: string; href: string }
export type AssistEvent =
  | { type: 'sources'; sources: Source[]; tools: string[] }
  | { type: 'queued'; waiting: number }
  | { type: 'delta'; text: string }
  | { type: 'done'; ms: number; prompt_ms: number; tokens_in: number; tokens_out: number; tokens_per_s: number }
  | { type: 'error'; message: string };

export interface AskContext { page: string; drawing?: string | null; alarm?: string | null; tags?: string[] }
export interface Turn { role: 'user' | 'assistant'; content: string; sources?: Source[]; error?: boolean; ms?: number; label?: string }

/** Del en SSE-buffer i hændelser. Returnerer hændelserne og resten (en ufærdig hændelse venter på mere). */
export function parseSse(buffer: string): { events: AssistEvent[]; rest: string } {
  const events: AssistEvent[] = [];
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const rest = blocks.pop() ?? '';
  for (const block of blocks) {
    const data = block.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trimStart()).join('\n');
    if (!data) continue;   // kommentarlinje (": venter") holder blot forbindelsen åben
    try {
      const ev = JSON.parse(data) as AssistEvent;
      if (ev && typeof ev === 'object' && 'type' in ev) events.push(ev);
    } catch {
      // ufuldstændig/ugyldig hændelse springes over
    }
  }
  return { events, rest };
}

/** Sidens kontekst ud fra adressen (#overview/<tegning>, #draw/<tegning>, #editor/<tegning> …). */
export function contextFromRoute(route: string, page: string): AskContext {
  const [, arg] = route.split('/');
  const drawing = (page === 'overview' || page === 'draw' || page === 'editor') && arg ? decodeURIComponent(arg) : null;
  return { page, drawing };
}

/** Kun spørgsmål og svar (ikke fejl, ikke kilder) sendes med som samtale — de seneste fire. */
export function historyFor(turns: Turn[]): { role: 'user' | 'assistant'; content: string }[] {
  return turns.filter((t) => !t.error && t.content.trim()).slice(-4).map((t) => ({ role: t.role, content: t.content.slice(0, 1000) }));
}

/** Kort tekst om svartid til visning under svaret. */
export function timingText(ev: { ms: number; tokens_per_s: number }): string {
  return `${(ev.ms / 1000).toFixed(1).replace('.', ',')} s${ev.tokens_per_s ? ` · ${String(ev.tokens_per_s).replace('.', ',')} tokens/s` : ''}`;
}

const STORE = 'hv-assist-turns';
export function loadTurns(): Turn[] {
  try {
    const raw = JSON.parse(sessionStorage.getItem(STORE) ?? '[]');
    return Array.isArray(raw) ? (raw as Turn[]).slice(-40) : [];
  } catch {
    return [];
  }
}
export function saveTurns(turns: Turn[]): void {
  try {
    sessionStorage.setItem(STORE, JSON.stringify(turns.slice(-40)));
  } catch {
    // fuld/afvist sessionStorage: samtalen gemmes bare ikke
  }
}

/** Stil et spørgsmål; `onEvent` kaldes for hver hændelse. Kaster ved HTTP-fejl (serverens tekst). */
export function ask(body: { question: string; context: AskContext; history: { role: string; content: string }[] },
  onEvent: (ev: AssistEvent) => void, signal?: AbortSignal): Promise<void> {
  return postStream('/api/assist/ask', body, onEvent, signal);
}

/** POST, hvis svar strømmes som server-sent events (hjælperens lange svar). Kaster ved HTTP-fejl (serverens tekst). */
export async function postStream<E extends { type: string }>(url: string, body: unknown, onEvent: (ev: E) => void,
  signal?: AbortSignal): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new Error(`Ingen forbindelse til SCADA-serveren (${(e as Error).message})`);
  }
  if (!resp.ok || !resp.body) {
    const text = await resp.text();
    let data: unknown = text;
    try { data = JSON.parse(text); } catch { /* tekst */ }
    if (resp.status === 401) notifyUnauthorized();
    throw new Error(errorText(resp.status, data, resp.statusText));
  }
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const { events, rest } = parseSse(buf);
    buf = rest;
    (events as unknown as E[]).forEach(onEvent);
  }
  const { events } = parseSse(buf + '\n\n');
  (events as unknown as E[]).forEach(onEvent);
}
