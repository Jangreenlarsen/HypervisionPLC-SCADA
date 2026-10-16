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
