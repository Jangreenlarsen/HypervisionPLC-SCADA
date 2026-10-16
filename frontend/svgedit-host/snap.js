// Rene hjælpefunktioner til at fange (snappe) til andre objekter i Tegn. Ingen DOM — testet i src/lib/snap.test.ts.
// Alle bokse er i tegningens egne koordinater: { x, y, w, h }.

/** Venstre/midt/højre (eller top/midt/bund) for en boks. */
const edgesX = (b) => [b.x, b.x + b.w / 2, b.x + b.w];
const edgesY = (b) => [b.y, b.y + b.h / 2, b.y + b.h];

/** Den mindste boks der rummer dem alle (null hvis ingen). */
export function unionBox(boxes) {
  const list = boxes.filter(Boolean);
  if (!list.length) return null;
  const x1 = Math.min(...list.map((b) => b.x));
  const y1 = Math.min(...list.map((b) => b.y));
  const x2 = Math.max(...list.map((b) => b.x + b.w));
  const y2 = Math.max(...list.map((b) => b.y + b.h));
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

/** Den korteste forskydning fra en kant/midte i `mine` til en kant/midte i `theirs` — kun hvis den er højst `threshold`. */
function nearest(mine, theirs, threshold) {
  let best = null;
  for (const m of mine) {
    for (const t of theirs) {
      const d = t - m;
      if (Math.abs(d) <= threshold && (best === null || Math.abs(d) < Math.abs(best.d))) best = { d, at: t };
    }
  }
  return best;
}

/**
 * Hvor langt skal `moving` flyttes for at ligge kant i kant (eller midte mod midte) med nærmeste objekt i `others`?
 * threshold er i tegningens enheder. → { dx, dy, guideX, guideY } (guide = koordinaten der fanges til, ellers null).
 * X og Y afgøres hver for sig, så en boks kan fanges i begge retninger på én gang.
 */
export function snapToObjects(moving, others, threshold) {
  const mx = edgesX(moving);
  const my = edgesY(moving);
  let bx = null;
  let by = null;
  for (const o of others) {
    const cx = nearest(mx, edgesX(o), threshold);
    if (cx && (bx === null || Math.abs(cx.d) < Math.abs(bx.d))) bx = cx;
    const cy = nearest(my, edgesY(o), threshold);
    if (cy && (by === null || Math.abs(cy.d) < Math.abs(by.d))) by = cy;
  }
  return { dx: bx ? bx.d : 0, dy: by ? by.d : 0, guideX: bx ? bx.at : null, guideY: by ? by.at : null };
}

/** Er det en flytning (samme størrelse, ny placering) — og stor nok til at være et træk, ikke en piletast-justering? */
export function isDrag(before, after, minMove = 3, sizeTolerance = 0.5) {
  if (!before || !after) return false;
  const sameSize = Math.abs(before.w - after.w) <= sizeTolerance && Math.abs(before.h - after.h) <= sizeTolerance;
  const moved = Math.max(Math.abs(after.x - before.x), Math.abs(after.y - before.y));
  return sameSize && moved > minMove;
}

/** Hvor langt skal en boks flyttes for at dens øverste venstre hjørne ligger på et gitterpunkt (multipla af `step`)? */
export function gridCorrection(box, step) {
  if (!(step > 0)) return { dx: 0, dy: 0 };
  const fix = (v) => (Math.abs(v) < 1e-9 ? 0 : v);   // undgå -0 og afrundingsstøj
  return { dx: fix(Math.round(box.x / step) * step - box.x), dy: fix(Math.round(box.y / step) * step - box.y) };
}

// 2D-matricer som i SVG: { a, b, c, d, e, f } — x' = a·x + c·y + e, y' = b·x + d·y + f
export const identityMatrix = () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 });

/** m · n (n anvendes først). */
export function multiplyMatrix(m, n) {
  return {
    a: m.a * n.a + m.c * n.b, b: m.b * n.a + m.d * n.b, c: m.a * n.c + m.c * n.d, d: m.b * n.c + m.d * n.d,
    e: m.a * n.e + m.c * n.f + m.e, f: m.b * n.e + m.d * n.f + m.f,
  };
}

/** Den omvendte matrix; null hvis den ikke kan vendes (nul-skalering). */
export function invertMatrix(m) {
  const det = m.a * m.d - m.b * m.c;
  if (!det || !Number.isFinite(det)) return null;
  return {
    a: m.d / det, b: -m.b / det, c: -m.c / det, d: m.a / det,
    e: (m.c * m.f - m.d * m.e) / det, f: (m.b * m.e - m.a * m.f) / det,
  };
}

/** Boksen (x, y, w, h) efter en matrix — den mindste boks om de fire transformerede hjørner. */
export function transformBox(box, m) {
  const pts = [[box.x, box.y], [box.x + box.w, box.y], [box.x, box.y + box.h], [box.x + box.w, box.y + box.h]]
    .map(([x, y]) => [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f]);
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
}
