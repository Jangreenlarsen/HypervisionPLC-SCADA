// Omskiftere (v0.91.1): tegningens positioner (navnene rundt om grebet) skal følge opsætningens positioner.
// Ren logik — testet i selectorRedraw.test.ts.
import { selectorAngles } from './symbols';
import { POS, type SymbolConfig } from './symbolConfig';

/** Bibliotekets omskiftere — deres tegning bygges ud fra positionernes navne. */
export const SELECTOR_TYPES: ReadonlySet<string> = new Set(['omskifter', 'omskifter3', 'drejeomskifter']);

const norm = (l: string[]) => l.map((x) => x.trim());

/** Viser tegningen andre positioner (antal eller navne) end opsætningen? Kun når opsætningen har mindst 2. */
export function selectorMismatch(drawn: string[], positions: string[]): boolean {
  if (positions.length < 2) return false;
  const a = norm(drawn), b = norm(positions);
  return a.length !== b.length || a.some((x, i) => x !== b[i]);
}

/**
 * Opsætningen efter en ny tegning: grebets drej pr. position (Drej på positionen) peger på navnene i den nye tegning
 * (`selectorAngles`), og animationen sidder på det nye greb (`grebId`, hvis det har fået et andet id).
 */
export function withSelectorAngles(cfg: SymbolConfig, grebId: string | null, oldGreb: string | null): SymbolConfig {
  const n = cfg.positions.length;
  const angles = selectorAngles(n);
  return {
    ...cfg,
    anims: cfg.anims.map((a) => {
      if (a.type !== 'rotate' || a.src !== POS) return a;
      const part = grebId && (a.part === oldGreb || a.part === grebId) ? grebId : a.part;
      return { ...a, part, params: { ...a.params, angles: [...angles] } };
    }),
  };
}
