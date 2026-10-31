// Hjælpelinjer i Tegn (v3.10.0): rene beregninger (testes i src/lib/guides.test.ts).
// Gemmes i tegningen som data-hv-guides på rod-elementet: {"every":100,"v":[120,480],"h":[300]} — every = fast inddeling
// (0 = fra), v = frie lodrette linjer (x), h = frie vandrette linjer (y). Overview viser dem ikke.

export const EVERY_CHOICES = [0, 50, 100, 200, 250];
export const EMPTY_GUIDES = { every: 0, v: [], h: [] };
const r2 = (v) => Math.round(v * 100) / 100;
const nums = (xs) => (Array.isArray(xs) ? [...new Set(xs.map(Number).filter(Number.isFinite).map(r2))].sort((a, b) => a - b) : []);

/** Læs attributten; ødelagt eller manglende → ingen hjælpelinjer. */
export function parseGuides(text) {
  try {
    const g = JSON.parse(text ?? '');
    if (!g || typeof g !== 'object') return { ...EMPTY_GUIDES };
    const every = Number(g.every);
    return { every: Number.isFinite(every) && every >= 10 ? every : 0, v: nums(g.v).slice(0, 100), h: nums(g.h).slice(0, 100) };
  } catch {
    return { ...EMPTY_GUIDES };
  }
}

/** Til attributten; ingen linjer → null (attributten fjernes). */
export function formatGuides(g) {
  const v = nums(g.v), h = nums(g.h);
  if (!(g.every > 0) && !v.length && !h.length) return null;
  return JSON.stringify({ every: g.every > 0 ? g.every : 0, v, h });
}

/** Alle linjer (fast inddeling + frie) inden for tegningen w × h. → { x: [...], y: [...] } */
export function guideLines(g, w, h) {
  const x = [...g.v], y = [...g.h];
  if (g.every > 0) {
    for (let v = g.every; v < w; v += g.every) x.push(v);
    for (let v = g.every; v < h; v += g.every) y.push(v);
  }
  return { x: [...new Set(x.map(r2))].sort((a, b) => a - b), y: [...new Set(y.map(r2))].sort((a, b) => a - b) };
}

/** Nærmeste linje inden for tol for et af tallene (fx venstre kant, midte, højre kant). → { d, at, from } eller null. */
function nearestHit(values, lines, tol) {
  let best = null;
  for (const v of values) for (const l of lines) {
    const d = l - v;
    if (Math.abs(d) <= tol && (best === null || Math.abs(d) < Math.abs(best.d))) best = { d, at: l, from: v };
  }
  return best;
}
const nearestShift = (values, lines, tol) => nearestHit(values, lines, tol)?.d ?? null;

/** Fang en boks: kanter eller midte til nærmeste linje på hver akse. → { dx, dy } (null = ingen linje tæt på). */
export function snapBoxToGuides(box, lines, tol) {
  const hx = nearestHit([box.x, box.x + box.w / 2, box.x + box.w], lines.x, tol);
  const hy = nearestHit([box.y, box.y + box.h / 2, box.y + box.h], lines.y, tol);
  return { dx: hx?.d ?? null, dy: hy?.d ?? null, atX: hx?.at ?? null, atY: hy?.at ?? null };
}

/**
 * Til visning mens der trækkes: hvilke linjer boksen fanges til, og hvor på boksen (prik midt på den kant/midte, der
 * rammer linjen). → { x: { at, mark } | null, y: { at, mark } | null }
 */
export function snapHint(box, lines, tol) {
  const hx = nearestHit([box.x, box.x + box.w / 2, box.x + box.w], lines.x, tol);
  const hy = nearestHit([box.y, box.y + box.h / 2, box.y + box.h], lines.y, tol);
  return {
    x: hx ? { at: hx.at, mark: [hx.at, box.y + box.h / 2 + (hy?.d ?? 0)] } : null,
    y: hy ? { at: hy.at, mark: [box.x + box.w / 2 + (hx?.d ?? 0), hy.at] } : null,
  };
}

/** Fang et punkt til linjerne (hver akse for sig). */
export function snapPointToGuides(p, lines, tol) {
  const dx = nearestShift([p[0]], lines.x, tol);
  const dy = nearestShift([p[1]], lines.y, tol);
  return [p[0] + (dx ?? 0), p[1] + (dy ?? 0)];
}

/**
 * Justér en boks til en hjælpelinje: lodret linje ved x (type l/c/r) eller vandret ved y (t/m/b). → flytning { dx, dy },
 * eller null hvis typen ikke passer til linjens retning.
 */
export function alignToGuide(box, type, axis, at) {
  if (axis === 'v') {
    const from = { l: box.x, c: box.x + box.w / 2, r: box.x + box.w }[type];
    return from === undefined ? null : { dx: at - from, dy: 0 };
  }
  const from = { t: box.y, m: box.y + box.h / 2, b: box.y + box.h }[type];
  return from === undefined ? null : { dx: 0, dy: at - from };
}
