// Hurtigvalg af brugte farver ved farvefelterne i Opsæt symbol (v1.5.0): først de farver symbolets animationer allerede bruger,
// så symbolets egne tegnede farver (mest brugte først), så tegningens øvrige — så farver holdes ens uden at skulle gentages.
// @ts-expect-error — ren JS-fil i værtsmappen til SVG-Edit (ingen typer)
import { collectColors, normColor } from '../../svgedit-host/colors.js';

export const MAX_PALETTE = 10;

/** Farver (#rrggbb) i alle tekst-værdier i animationernes parametre (fx on/off, grænser, paletter, løbelysets rør/lys). */
export function paramColors(anims: { params?: Record<string, unknown> }[]): string[] {
  const out: string[] = [];
  const walk = (v: unknown): void => {
    if (typeof v === 'string') {
      const c = /^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(v.trim()) ? (normColor(v) as string | null) : null;
      if (c) out.push(c);
    } else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  for (const a of anims) walk(a.params ?? {});
  return out;
}

/** Fyld- og stregfarver i et elements billede (`elementId`) eller i hele tegningen (uden id), mest brugte først. */
export function svgColors(svgText: string, elementId?: string): string[] {
  if (!svgText) return [];
  const doc = new DOMParser().parseFromString(svgText, 'image/svg+xml');
  const root = elementId ? doc.getElementById(elementId) ?? doc.querySelector(`[id="${elementId.replace(/"/g, '')}"]`) : doc.documentElement;
  if (!root) return [];
  const nodes = [root, ...Array.from(root.querySelectorAll('*'))];
  const list = nodes.map((el) => ({ fill: el.getAttribute('fill'), stroke: el.getAttribute('stroke'), style: el.getAttribute('style') }));
  return (collectColors(list) as { color: string }[]).map((c) => c.color);
}

/** Saml flere farvelister til ét hurtigvalg: den første liste har forrang, dubletter fjernes, højst `max`. */
export function mergePalette(lists: string[][], max = MAX_PALETTE): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const list of lists) {
    for (const raw of list) {
      const c = (normColor(raw) as string | null) ?? null;
      if (c && !seen.has(c)) { seen.add(c); out.push(c); }
    }
  }
  return out.slice(0, max);
}
