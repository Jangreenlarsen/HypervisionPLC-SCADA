// Overview-navigation: hvilken tegning der vises først, og zoom/panorering via SVG'ens viewBox.
// Rene funktioner — testet i viewport.test.ts.

export interface View { x: number; y: number; w: number; h: number }

/** Største indzoomning (gange den fulde tegning). */
export const MAX_ZOOM = 20;

/**
 * Tegningen Overview åbner med: den i adressen → den man sidst så i denne fane → start-tegningen
 * (valgt under Tegninger) → den første. Kun tegninger brugeren har adgang til (listen er filtreret).
 */
export function pickDrawing(drawings: { id: string; start?: boolean }[], route: string | undefined, last: string | null): string {
  const has = (id: string | null | undefined) => !!id && drawings.some((d) => d.id === id);
  if (has(route)) return route!;
  if (has(last)) return last!;
  return drawings.find((d) => d.start)?.id ?? drawings[0]?.id ?? '';
}

/** Hold udsnittet inden for tegningen: aldrig mindre zoom end hele tegningen, aldrig mere end MAX_ZOOM. */
export function clampView(v: View, full: View): View {
  const w = Math.min(full.w, Math.max(full.w / MAX_ZOOM, v.w));
  const h = w * (full.h / full.w);
  const x = Math.min(full.x + full.w - w, Math.max(full.x, v.x));
  const y = Math.min(full.y + full.h - h, Math.max(full.y, v.y));
  return { x, y, w, h };
}

/** Zoom med faktor `k` (>1 = ind) om punktet (px, py) i tegningens koordinater — punktet bliver stående. */
export function zoomAt(v: View, full: View, k: number, px: number, py: number): View {
  return clampView({ x: px - (px - v.x) / k, y: py - (py - v.y) / k, w: v.w / k, h: v.h / k }, full);
}

/** Panorér med (dx, dy) i tegningens koordinater. */
export function panBy(v: View, full: View, dx: number, dy: number): View {
  return clampView({ ...v, x: v.x + dx, y: v.y + dy }, full);
}

export const zoomLevel = (v: View, full: View) => full.w / v.w;
