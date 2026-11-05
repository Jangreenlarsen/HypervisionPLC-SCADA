// Tilstanden for symbolbiblioteket (egne symboler + opdeling), hentet fra /api/library. Delt af Tegn, Erstat med symbol,
// symbolguiden og Opsætning › Symboler. Logikken ligger i library.ts.
import { get, put } from './api';
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
