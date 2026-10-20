// Navne på kurverne i Trends-graferne: hver kurve får sit navn ved højre kant, ud for kurvens sidste synlige punkt.
// Ligger kurverne tæt, spredes navnene, så de kan læses, og et navn der er flyttet væk fra sin kurve får en pil til punktet.
// Rene funktioner (ingen canvas) — testet i lineLabels.test.ts.

/** Mindste lodrette afstand (px) mellem to navne, så teksten ikke overlapper. */
export const LABEL_GAP = 14;
/** Et navn flyttet mere end dette (px) fra sin kurve får en pil. */
export const ARROW_MIN = 3;

/** Indeks på det sidste punkt med en værdi inden for x-vinduet, eller -1. */
export function lastVisible(xs: number[], ys: (number | null | undefined)[], min: number, max: number): number {
  for (let i = Math.min(xs.length, ys.length) - 1; i >= 0; i--) {
    const v = ys[i];
    if (v !== null && v !== undefined && Number.isFinite(v) && xs[i] >= min && xs[i] <= max) return i;
  }
  return -1;
}

/**
 * Lodrette positioner til navnene (samme rækkefølge som `anchors`): så tæt på kurvens højde som muligt, men mindst
 * `gap` fra hinanden og inden for [top, bottom]. Er der ikke plads til alle, pakkes de så tæt som muligt fra toppen.
 */
export function spreadLabels(anchors: number[], top: number, bottom: number, gap = LABEL_GAP): number[] {
  const order = anchors.map((_, i) => i).sort((a, b) => anchors[a] - anchors[b] || a - b);
  const pos = order.map((i) => Math.min(bottom, Math.max(top, anchors[i])));
  for (let k = 1; k < pos.length; k++) pos[k] = Math.max(pos[k], pos[k - 1] + gap);          // skub nedad
  if (pos.length && pos[pos.length - 1] > bottom) {
    pos[pos.length - 1] = bottom;
    for (let k = pos.length - 2; k >= 0; k--) pos[k] = Math.min(pos[k], pos[k + 1] - gap);   // skub opad fra bunden
  }
  for (let k = 0; k < pos.length; k++) pos[k] = Math.max(pos[k], top + k * gap);              // aldrig over toppen
  const out = new Array<number>(anchors.length);
  order.forEach((i, k) => (out[i] = pos[k]));
  return out;
}

/** Skal navnet have en pil til kurven (er det flyttet væk fra kurvens højde)? */
export const needsArrow = (anchorY: number, labelY: number): boolean => Math.abs(anchorY - labelY) > ARROW_MIN;
