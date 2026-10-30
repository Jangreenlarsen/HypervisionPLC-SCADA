// Redigering fra panelet i den nye tegne-editor: rene beregninger (testes i src/lib/editMath.test.ts).
// Bokse er { x, y, w, h } i tegningens koordinater; matricer er { a, b, c, d, e, f } som i SVG.

/** Matricen der afbilder boksen `from` over i `to` (flyt + skalér om øverste venstre hjørne). */
export function boxMapping(from, to) {
  const sx = from.w > 0 ? to.w / from.w : 1;
  const sy = from.h > 0 ? to.h / from.h : 1;
  return { a: sx, b: 0, c: 0, d: sy, e: to.x - from.x * sx, f: to.y - from.y * sy };
}

/**
 * Den nye boks, når ét felt i panelet ændres. Med `keepRatio` følger den anden side med (som "Skalér symmetrisk").
 * Bredde/højde under 1 afvises (null) — et element på 0 kan ikke gøres større igen.
 */
export function editBox(box, field, value, keepRatio = false) {
  const v = Number(value);
  if (!Number.isFinite(v)) return null;
  const next = { ...box };
  if (field === 'x' || field === 'y') {
    next[field] = v;
    return next;
  }
  if (field !== 'w' && field !== 'h') return null;
  if (v < 1) return null;
  next[field] = v;
  if (keepRatio && box.w > 0 && box.h > 0) {
    if (field === 'w') next.h = box.h * (v / box.w);
    else next.w = box.w * (v / box.h);
  }
  return next;
}

/**
 * Fordel boksene med lige store mellemrum langs aksen ('x' vandret, 'y' lodret). De to yderste bliver stående.
 * Giver flytningen (dx eller dy) pr. boks i samme rækkefølge som input. Under 3 bokse: ingen flytning.
 */
export function distribute(boxes, axis) {
  const n = boxes.length;
  const zero = boxes.map(() => 0);
  if (n < 3) return zero;
  const pos = axis === 'x' ? 'x' : 'y';
  const size = axis === 'x' ? 'w' : 'h';
  const order = boxes.map((b, i) => i).sort((i, j) => boxes[i][pos] - boxes[j][pos]);
  const first = boxes[order[0]];
  const last = boxes[order[n - 1]];
  const total = last[pos] + last[size] - first[pos];
  const used = boxes.reduce((s, b) => s + b[size], 0);
  const gap = (total - used) / (n - 1);
  const out = [...zero];
  let at = first[pos];
  for (const i of order) {
    out[i] = at - boxes[i][pos];
    at += boxes[i][size] + gap;
  }
  return out;
}

/** Afrund til 2 decimaler (felterne i panelet). */
export const round2 = (v) => Math.round(v * 100) / 100;
