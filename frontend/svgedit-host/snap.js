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

/**
 * Hjørnerne i en sti (d-attributten) som [[x, y], …]: M/L/H/V/Z, store og små bogstaver (relativ/absolut).
 * Kurver (C/S/Q/A) tolkes ikke — så giver den null, og delen regnes ikke for en retningsgivende trekant.
 */
export function pathVertices(d) {
  const tokens = String(d || '').match(/[a-zA-Z]|-?\d*\.?\d+(?:e[-+]?\d+)?/g);
  if (!tokens) return null;
  const pts = [];
  let i = 0;
  let cmd = '';
  let x = 0;
  let y = 0;
  let startX = 0;
  let startY = 0;
  const num = () => Number(tokens[i++]);
  const push = (px, py) => {
    x = px;
    y = py;
    const last = pts[pts.length - 1];
    if (!last || Math.abs(last[0] - px) > 1e-6 || Math.abs(last[1] - py) > 1e-6) pts.push([px, py]);
  };
  while (i < tokens.length) {
    if (/[a-zA-Z]/.test(tokens[i])) cmd = tokens[i++];
    else if (cmd === 'm') cmd = 'l';
    else if (cmd === 'M') cmd = 'L';
    const rel = cmd === cmd.toLowerCase();
    switch (cmd.toUpperCase()) {
      case 'M': { const px = num(), py = num(); push(rel ? x + px : px, rel ? y + py : py); startX = x; startY = y; break; }
      case 'L': { const px = num(), py = num(); push(rel ? x + px : px, rel ? y + py : py); break; }
      case 'H': { const px = num(); push(rel ? x + px : px, y); break; }
      case 'V': { const py = num(); push(x, rel ? y + py : py); break; }
      case 'Z': push(startX, startY); break;
      default: return null;
    }
    if (tokens.slice(0, i).some((t) => Number.isNaN(Number(t)) && !/[a-zA-Z]/.test(t))) return null;
  }
  // en lukket sti slutter i startpunktet: fjern den dobbelte
  if (pts.length > 1 && Math.abs(pts[0][0] - pts[pts.length - 1][0]) < 1e-6 && Math.abs(pts[0][1] - pts[pts.length - 1][1]) < 1e-6) pts.pop();
  return pts;
}

/**
 * Er hjørnerne en ligebenet trekant? → { apex: [x, y], vector: [dx, dy] } hvor vector går fra grundlinjens midte til toppen
 * (retningen trekanten "peger"). Ellers null. En ligesidet trekant har ingen entydig retning og giver null.
 */
export function triangleApex(vertices) {
  if (!vertices || vertices.length !== 3) return null;
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  let best = null;
  for (let k = 0; k < 3; k++) {
    const a = vertices[k];
    const b = vertices[(k + 1) % 3];
    const c = vertices[(k + 2) % 3];
    const e1 = dist(a, b);
    const e2 = dist(a, c);
    const base = dist(b, c);
    if (e1 < 1e-6 || e2 < 1e-6 || base < 1e-6) return null;
    const similar = Math.min(e1, e2) / Math.max(e1, e2);
    if (similar >= 0.97 && Math.abs(e1 - base) / base > 0.05 && (!best || similar > best.similar)) {
      best = { similar, apex: a, vector: [a[0] - (b[0] + c[0]) / 2, a[1] - (b[1] + c[1]) / 2] };
    }
  }
  return best ? { apex: best.apex, vector: best.vector } : null;
}

/** Vinklen (grader, 0 = mod højre, 90 = nedad som på skærmen) for en vektor efter en matrix; afrundet til 0,1°. */
export function directionAngle(vector, m) {
  const dx = m.a * vector[0] + m.c * vector[1];
  const dy = m.b * vector[0] + m.d * vector[1];
  return Math.round((Math.atan2(dy, dx) * 1800) / Math.PI) / 10;
}

/** Drejning der får et symbol med retningen `native` til at pege som `target` — i området −180…180. */
export function turnTo(target, native = 0) {
  const d = (((target - native + 180) % 360) + 360) % 360 - 180;
  return d === -180 ? 180 : d;
}
