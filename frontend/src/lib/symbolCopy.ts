// "Kopiér opsætning til flere" (v0.59.0): udvælgelse af målsymboler og opsummering af serverens svar.
import { PIPE_IDS, SYMBOLS } from './symbols';

/** Et symbol på tegningen, som serveren lister det (GET /api/drawings/{id}/symbols). */
export interface SymbolRow { element: string; name: string | null; type: string; configured: boolean }
export interface CopyResult { element: string; status: 'ok' | 'skipped' | 'error'; message: string; notes: string[] }
export interface CopyResponse { source: string; results: CopyResult[]; ok: number; skipped: number; error: number }

const LABEL = new Map(SYMBOLS.map((s) => [s.id, s.label]));
/** Bibliotekstypens læsbare navn (fx "Rør vandret"), ellers selve typen. */
export const typeLabel = (type: string): string => LABEL.get(type) ?? (type === 'custom' ? 'Eget symbol' : type);
export const rowLabel = (r: SymbolRow): string => r.name?.trim() || r.element;

/** Mulige mål: alle symboler undtagen kilden, filtreret på navn, id eller type (uden forskel på store/små bogstaver). */
export function candidates(rows: SymbolRow[], source: string, query: string): SymbolRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter((r) => r.element !== source && (!q || [rowLabel(r), r.element, r.type, typeLabel(r.type)].some((s) => s.toLowerCase().includes(q))));
}

/** Symboler af samme bibliotekstype som kilden ("custom" matcher intet — egne symboler kan være hvad som helst). */
export function sameType(rows: SymbolRow[], source: string, type: string): string[] {
  if (!type || type === 'custom') return [];
  return rows.filter((r) => r.element !== source && r.type === type).map((r) => r.element);
}

/** Alle rør og fittings (rør, bøjninger, T-stykker, kryds …). */
export function pipes(rows: SymbolRow[], source: string): string[] {
  return rows.filter((r) => r.element !== source && PIPE_IDS.has(r.type)).map((r) => r.element);
}

/** Kort opsummering til brugeren efter en kopiering. */
export function summary(r: CopyResponse): string {
  const parts = [`${r.ok} kopieret`];
  if (r.skipped) parts.push(`${r.skipped} sprunget over (havde allerede en opsætning)`);
  if (r.error) parts.push(`${r.error} med fejl`);
  return parts.join(', ') + '.';
}

// ---- Kopiér/indsæt opsætning i Tegn (v0.60.0)

/** Det kopierede symbol. Selve opsætningen ligger på serveren — indsæt bruger den GEMTE opsætning på indsætningstidspunktet. */
export interface ConfigClip { drawingId: string; element: string; name: string }

/** Mål for "Indsæt opsætning": de valgte elementer med navn (symboler), uden kilden selv. */
export function pasteTargets(sel: { id: string; name?: string }[], clip: ConfigClip): { targets: string[]; unnamed: number; self: boolean } {
  const named = sel.filter((s) => !!s.name?.trim());
  return {
    targets: named.filter((s) => s.id !== clip.element).map((s) => s.id),
    unnamed: sel.length - named.length,
    self: named.some((s) => s.id === clip.element),
  };
}

/** Oversæt serverens svar til en besked (info) og en liste over problemer pr. symbol (vises som fejl). */
export function pasteReport(r: CopyResponse, from: string, nameOf: (id: string) => string): { info: string; problems: string[] } {
  const okNames = r.results.filter((x) => x.status === 'ok').map((x) => nameOf(x.element));
  const info = r.ok ? `Opsætningen fra "${from}" er indsat i ${okNames.length === 1 ? `"${okNames[0]}"` : `${r.ok} symboler`}.` : '';
  const problems = r.results.flatMap((x) => [
    ...(x.status !== 'ok' ? [`${nameOf(x.element)}: ${x.message}`] : []),
    ...x.notes.map((n) => `${nameOf(x.element)}: ${n}`),
  ]);
  return { info, problems };
}
