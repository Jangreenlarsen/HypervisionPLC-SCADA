// "Kopiér opsætning til flere" (v0.59.0): udvælgelse af målsymboler og opsummering af serverens svar.
import { ANIM_TXT, OP_TXT, type Op, type SymbolConfig, type SymbolInfo } from './symbolConfig';
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

/**
 * Mål for "Indsæt opsætning": de valgte elementer med navn (symboler), uden kilden selv, og de valgte UDEN navn
 * (de navngives efter kilden før indsætning). Elementer uden id kan ikke få en opsætning og tælles i `noId`.
 */
export function pasteTargets(sel: { id: string; name?: string }[], clip: ConfigClip): { targets: string[]; unnamed: string[]; noId: number; self: boolean } {
  const withId = sel.filter((s) => !!s.id);
  const named = withId.filter((s) => !!s.name?.trim());
  return {
    targets: named.filter((s) => s.id !== clip.element).map((s) => s.id),
    unnamed: withId.filter((s) => !s.name?.trim()).map((s) => s.id),
    noId: sel.length - withId.length,
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

// ---- Opsæt flere symboler samlet (v0.63.0)

/** Et valgt symbol med sin gemte opsætning (null = ingen) og symbolets dele (fra GET …/config). */
export interface Member { element: string; name: string; config: SymbolConfig | null; symbol: SymbolInfo | null }
/** Valgte symboler med SAMME opsætning (dele sammenlignet efter biblioteksnavn). */
export interface ConfigGroup { key: string; members: Member[]; summary: string }

/**
 * Opsætningens "fingeraftryk" uafhængigt af symbolets egne id'er: en animation på en del sammenlignes efter delens
 * biblioteksnavn (pid), så to rør med hver sin del-id men samme opsætning tæller som ens. Nøglelåsen tæller ikke med
 * (den kopieres ikke).
 */
export function configSignature(cfg: SymbolConfig, symbol: SymbolInfo | null): string {
  const part = (id: string) => (id === 'all' ? 'all' : symbol?.parts[id]?.pid ? `pid:${symbol.parts[id].pid}` : `id:${id}`);
  const { lock: _lock, type: _type, ...rest } = cfg;   // typen er symbolets, ikke opsætningens
  return JSON.stringify({ ...rest, anims: (cfg.anims ?? []).map((a) => ({ ...a, part: part(a.part) })) });
}

/** Kort beskrivelse af en opsætning, fx "Kun visning · Løbelys (Lys), Farve (Fejl)". */
export function describeConfig(cfg: SymbolConfig): string {
  const anims = (cfg.anims ?? []).map((a) => `${ANIM_TXT[a.type] ?? a.type}${a.src ? ` (${a.src})` : ''}`);
  const tags = (cfg.signals ?? []).map((s) => s.tag).filter(Boolean);
  return [OP_TXT[cfg.op as Op] ?? cfg.op, tags.length ? `tag ${tags.join(', ')}` : '', anims.join(', ')].filter(Boolean).join(' · ');
}

/** De forskellige opsætninger blandt de valgte (dem uden opsætning udeladt), flest medlemmer først. */
export function configGroups(members: Member[]): ConfigGroup[] {
  const groups = new Map<string, ConfigGroup>();
  for (const m of members) {
    if (!m.config) continue;
    const key = configSignature(m.config, m.symbol);
    const g = groups.get(key) ?? { key, members: [], summary: describeConfig(m.config) };
    g.members.push(m);
    groups.set(key, g);
  }
  return [...groups.values()].sort((a, b) => b.members.length - a.members.length);
}

/** "Rør 1, Rør 2 og 3 andre" — navnene i en gruppe, forkortet. */
export function memberNames(ms: { name: string }[], max = 3): string {
  const names = ms.map((m) => m.name);
  if (names.length <= max) return names.length > 1 ? `${names.slice(0, -1).join(', ')} og ${names[names.length - 1]}` : names.join('');
  return `${names.slice(0, max).join(', ')} og ${names.length - max} andre`;
}
