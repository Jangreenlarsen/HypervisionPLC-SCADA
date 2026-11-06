// Tilstanden for symbolbiblioteket (egne symboler + opdeling), hentet fra /api/library. Delt af Tegn, Erstat med symbol,
// symbolguiden og Opsætning › Symboler. Logikken ligger i library.ts.
import { api, get, patch, post, put } from './api';
import { allDefs, emptyLayout, type Layout, type OwnSymbol } from './library';
import { setOwnPresets } from './symbolConfig';
import type { SymbolDef } from './symbols';

export const library = $state<{ own: OwnSymbol[]; layout: Layout; loaded: boolean; error: string }>({
  own: [], layout: emptyLayout(), loaded: false, error: '',
});

function apply(own: OwnSymbol[], layout: Layout): void {
  library.own = own;
  library.layout = layout;
  library.loaded = true;
  library.error = '';
  setOwnPresets(Object.fromEntries(own.map((s) => [s.type, s.preset])));
}

/** Hent biblioteket. Fejler det, virker de indbyggede symboler stadig — fejlen står i `library.error`. */
export async function loadLibrary(): Promise<void> {
  try {
    const r = await get<{ symbols: OwnSymbol[]; layout: Layout }>('/api/library');
    apply(r.symbols, r.layout);
  } catch (e) {
    library.error = `Egne symboler kunne ikke hentes: ${(e as Error).message}`;
  }
}

/** Gem opdelingen (med revisionen den bygger på — serveren afviser, hvis en anden har gemt imens). */
export async function saveLayout(layout: Layout): Promise<void> {
  const saved = await put<Layout>('/api/library/layout', { layout, rev: library.layout.rev });
  library.layout = saved;
}

export const defs = (): SymbolDef[] => allDefs(library.own);

export type Conflict = 'rename' | 'version' | 'skip';
export interface ImportResult {
  file: string; status: 'created' | 'version' | 'renamed' | 'skipped' | 'error';
  type?: string; label?: string; version?: number; parts?: string[]; warnings?: string[]; error?: string;
}
export interface ImportSummary { results: ImportResult[]; count: Record<ImportResult['status'], number> }

/** Importér SVG-filer (én fil = ét symbol) og hent biblioteket igen. */
export async function importSvgFiles(files: { name: string; svg: string }[], section: string, onConflict: Conflict): Promise<ImportSummary> {
  const r = await post<ImportSummary>('/api/library/import', { files, section, on_conflict: onConflict });
  await loadLibrary();
  return r;
}

/** Bibliotekspakke med egne symboler (alle, eller de valgte typer). */
export const exportPackage = (types: string[] = []): Promise<unknown> =>
  get(`/api/library/package${types.length ? `?types=${encodeURIComponent(types.join(','))}` : ''}`);

export async function importPackage(pkg: unknown, onConflict: Conflict): Promise<ImportSummary> {
  const r = await post<ImportSummary>('/api/library/package', { package: pkg, on_conflict: onConflict });
  await loadLibrary();
  return r;
}

/** Omdøb/ret forklaring på et eget symbol. */
export async function updateOwn(type: string, label: string, hint: string): Promise<void> {
  await patch(`/api/library/symbols/${encodeURIComponent(type)}`, { label, hint });
  await loadLibrary();
}

/** Slet flere egne symboler i én handling (alt eller intet). Svarer med hvilke tegninger der stadig har en kopi. */
export async function deleteOwnMany(types: string[]): Promise<{ deleted: number; used_in: Record<string, string[]> }> {
  try {
    return await api<{ deleted: number; used_in: Record<string, string[]> }>('POST', '/api/library/symbols/delete', { types });
  } finally {
    await loadLibrary();   // også ved fejl: vis bibliotekets faktiske tilstand
  }
}

/** Slet et eget symbol → de tegninger, der stadig har en kopi. */
export async function deleteOwn(type: string): Promise<string[]> {
  const r = await api<{ used_in: string[] }>('DELETE', `/api/library/symbols/${encodeURIComponent(type)}`);
  await loadLibrary();
  return r.used_in;
}
