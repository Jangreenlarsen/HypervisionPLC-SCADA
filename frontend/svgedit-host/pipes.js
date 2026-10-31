// Rør-værktøjet i Tegn (PLAN.md trin 4): rene beregninger (testes i src/lib/pipes.test.ts).
// Et rør er en <path> med kun vandrette og lodrette stykker. Punkter er [x, y] i tegningens koordinater.
// Enderne kan sidde fast i et symbols tilslutningspunkt (data-hv-from / data-hv-to = "<symbol-id>@<fx>,<fy>": punktet
// som brøkdel af symbolets egen boks (0,0.5 = venstre kants midte), så det følger med, uanset om symbolet flyttes via
// transform eller via sine egne mål (x, width …), skaleres eller drejes).

export const PIPE_STYLE = { stroke: '#555', 'stroke-width': '10', fill: 'none', 'stroke-linejoin': 'miter' };
const EPS = 1e-6;
const same = (a, b) => Math.abs(a[0] - b[0]) < EPS && Math.abs(a[1] - b[1]) < EPS;
const r2 = (v) => Math.round(v * 100) / 100;

/** Fjern dubletter og punkter midt på et lige stykke. */
export function simplify(points) {
  const out = [];
  for (const p of points) {
    if (out.length && same(out[out.length - 1], p)) continue;
    if (out.length >= 2) {
      const a = out[out.length - 2];
      const b = out[out.length - 1];
      const straight = (Math.abs(a[0] - b[0]) < EPS && Math.abs(b[0] - p[0]) < EPS) || (Math.abs(a[1] - b[1]) < EPS && Math.abs(b[1] - p[1]) < EPS);
      // kun hvis røret fortsætter samme vej — vender det om (U på samme linje), er punktet et rigtigt knæk
      const forward = (b[0] - a[0]) * (p[0] - b[0]) + (b[1] - a[1]) * (p[1] - b[1]) >= 0;
      if (straight && forward) { out[out.length - 1] = p; continue; }
    }
    out.push(p);
  }
  return out;
}

/**
 * Vinkelret forbindelse fra a til b: lige hvis de flugter, ellers et knæk. `firstAxis` = 'h' (vandret først) eller 'v';
 * uden angivelse går den længste retning først.
 */
export function orthoLeg(a, b, firstAxis) {
  if (Math.abs(a[0] - b[0]) < EPS || Math.abs(a[1] - b[1]) < EPS) return [a, b];
  const axis = firstAxis ?? (Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 'h' : 'v');
  return axis === 'h' ? [a, [b[0], a[1]], b] : [a, [a[0], b[1]], b];
}

/** Retningen af stykket a→b: 'h', 'v' eller null (skrå/ens). */
export function axisOf(a, b) {
  if (Math.abs(a[1] - b[1]) < EPS && Math.abs(a[0] - b[0]) >= EPS) return 'h';
  if (Math.abs(a[0] - b[0]) < EPS && Math.abs(a[1] - b[1]) >= EPS) return 'v';
  return null;
}

export const pathD = (points) => points.map((p, i) => `${i ? 'L' : 'M'}${r2(p[0])} ${r2(p[1])}`).join(' ');

/**
 * Flyt en ende ('start' eller 'end') til p og hold røret vinkelret: nabopunktet følger med på tværs af stykkets retning.
 * Et rør med kun ét stykke, der ikke længere flugter, får to knæk midtvejs (S-form).
 */
export function moveEnd(points, which, p) {
  const pts = which === 'start' ? [...points].reverse() : [...points];
  const n = pts.length;
  if (n < 2) return points;
  const last = pts[n - 1];
  const prev = pts[n - 2];
  const axis = axisOf(prev, last);
  let out;
  if (n === 2) {
    const a = pts[0];
    if (Math.abs(a[0] - p[0]) < EPS || Math.abs(a[1] - p[1]) < EPS) out = [a, p];
    else if (axis === 'v') { const my = (a[1] + p[1]) / 2; out = [a, [a[0], my], [p[0], my], p]; }
    else { const mx = (a[0] + p[0]) / 2; out = [a, [mx, a[1]], [mx, p[1]], p]; }
  } else if (axis === 'h') {
    out = [...pts.slice(0, n - 2), [prev[0], p[1]], p];
  } else if (axis === 'v') {
    out = [...pts.slice(0, n - 2), [p[0], prev[1]], p];
  } else {
    out = [...pts.slice(0, n - 1), ...orthoLeg(prev, p).slice(1)];
  }
  // nabopunktets flytning kan gøre stykket før det skråt — giv det et knæk
  const fixed = [out[0]];
  for (let i = 1; i < out.length; i++) {
    const a = fixed[fixed.length - 1];
    fixed.push(...orthoLeg(a, out[i], axisOf(out[i - 1], out[i]) ?? undefined).slice(1));
  }
  const res = simplify(fixed);
  return which === 'start' ? res.reverse() : res;
}

/**
 * Tilslutningspunkter for en form: hjørnepunkter af dens streger, der ligger på boksens kant (rørender), plus midten
 * af hver kant. `vertices` og `box` i samme koordinater.
 */
export function portsFrom(vertices, box, tol = 1.5) {
  const ports = [];
  const add = (p) => { if (!ports.some((q) => Math.hypot(q[0] - p[0], q[1] - p[1]) < tol * 2)) ports.push(p); };
  const x2 = box.x + box.w;
  const y2 = box.y + box.h;
  for (const v of vertices) {
    const onEdge = Math.abs(v[0] - box.x) < tol || Math.abs(v[0] - x2) < tol || Math.abs(v[1] - box.y) < tol || Math.abs(v[1] - y2) < tol;
    if (onEdge) add(v);
  }
  for (const p of [[box.x, box.y + box.h / 2], [x2, box.y + box.h / 2], [box.x + box.w / 2, box.y], [box.x + box.w / 2, y2]]) add(p);
  return ports;
}

/** Nærmeste punkt inden for `tol`, ellers null. */
export function nearest(points, p, tol) {
  let best = null;
  let bd = tol;
  for (const q of points) {
    const d = Math.hypot(q[0] - p[0], q[1] - p[1]);
    if (d <= bd) { best = q; bd = d; }
  }
  return best;
}

/**
 * "<id>@<fx>,<fy>[,<side>]" ↔ { id, local: [fx, fy], side } — side (l/r/t/b) er den kant, røret går ud fra (v3.1.0;
 * ældre referencer uden side: null). Null hvis teksten ikke er en gyldig reference.
 */
export function parseRef(text) {
  const m = /^(.+)@(-?[\d.]+(?:e[-+]?\d+)?),(-?[\d.]+(?:e[-+]?\d+)?)(?:,([lrtb]))?$/i.exec(String(text ?? ''));
  if (!m) return null;
  const x = Number(m[2]);
  const y = Number(m[3]);
  return Number.isFinite(x) && Number.isFinite(y) ? { id: m[1], local: [x, y], side: m[4]?.toLowerCase() ?? null } : null;
}
const r4 = (v) => Math.round(v * 1e4) / 1e4;
export const formatRef = (id, frac, side = null) => `${id}@${r4(frac[0])},${r4(frac[1])}${side ? `,${side}` : ''}`;

/** Punkt i boksen → brøkdel (en boks uden bredde/højde giver midten). */
export const toFrac = (p, box) => [box.w > 0 ? (p[0] - box.x) / box.w : 0.5, box.h > 0 ? (p[1] - box.y) / box.h : 0.5];
export const fromFrac = (f, box) => [box.x + f[0] * box.w, box.y + f[1] * box.h];

/**
 * Stykket fra a til b, når retningen ud af a (`axA`) og/eller ind i b (`axB`) er givet ('h'/'v'): ud og ind langs samme
 * akse giver to knæk midtvejs (S/Z-form), forskellige akser ét knæk, ingen krav som orthoLeg.
 */
export function connect(a, b, axA, axB) {
  if (Math.abs(a[0] - b[0]) < EPS || Math.abs(a[1] - b[1]) < EPS) {
    const ax = axisOf(a, b);
    if (!ax || ((!axA || axA === ax) && (!axB || axB === ax))) return [a, b];
  }
  if (axA && axB && axA === axB) {
    if (axA === 'h') { const mx = (a[0] + b[0]) / 2; return simplify([a, [mx, a[1]], [mx, b[1]], b]); }
    const my = (a[1] + b[1]) / 2;
    return simplify([a, [a[0], my], [b[0], my], b]);
  }
  if (axA) return orthoLeg(a, b, axA);
  if (axB) return orthoLeg(a, b, axB === 'h' ? 'v' : 'h');
  return orthoLeg(a, b);
}

// ---------------------------------------------------------------- v3.1.0: retning, stub, radius og alle stikommandoer
export const STUB = 20;   // røret går så langt lige ud fra et tilslutningspunkt, før det knækker

/**
 * Stiens segmenter: [{ type: 'L' | 'A' | 'C' | 'Q', from: [x, y], to: [x, y] }] — alle kommandoer (også buer og kurver),
 * kun endepunkterne. Ugyldig sti → [].
 */
export function pathSegments(d) {
  const tokens = String(d || '').match(/[a-zA-Z]|-?\d*\.?\d+(?:e[-+]?\d+)?/g);
  if (!tokens) return [];
  const segs = [];
  let i = 0, cmd = '', x = 0, y = 0, sx = 0, sy = 0;
  const n = () => Number(tokens[i++]);
  const counts = { M: 2, L: 2, H: 1, V: 1, Z: 0, A: 7, C: 6, S: 4, Q: 4, T: 2 };
  while (i < tokens.length) {
    if (/[a-zA-Z]/.test(tokens[i])) cmd = tokens[i++];
    else if (cmd === 'm') cmd = 'l';
    else if (cmd === 'M') cmd = 'L';
    const U = cmd.toUpperCase();
    if (!(U in counts)) return [];
    const rel = cmd !== U;
    const args = [];
    for (let k = 0; k < counts[U]; k++) args.push(n());
    if (args.some((v) => !Number.isFinite(v))) return [];
    const from = [x, y];
    let to;
    if (U === 'M') {
      to = rel ? [x + args[0], y + args[1]] : [args[0], args[1]];
      [x, y] = to;
      [sx, sy] = to;
      continue;
    }
    if (U === 'H') to = [rel ? x + args[0] : args[0], y];
    else if (U === 'V') to = [x, rel ? y + args[0] : args[0]];
    else if (U === 'Z') to = [sx, sy];
    else {
      const ex = args[args.length - 2];
      const ey = args[args.length - 1];
      to = rel ? [x + ex, y + ey] : [ex, ey];
    }
    const type = U === 'H' || U === 'V' || U === 'L' || U === 'Z' ? 'L' : U === 'A' ? 'A' : U === 'S' ? 'C' : U === 'T' ? 'Q' : U;
    segs.push({ type, from, to });
    [x, y] = to;
  }
  return segs;
}

/** Alle endepunkter i en sti (også efter buer/kurver). */
export function pathPoints(d) {
  const segs = pathSegments(d);
  if (!segs.length) return [];
  return [segs[0].from, ...segs.map((s) => s.to)];
}

/**
 * Tilslutningspunkter ud fra stregernes hjørnepunkter (ikke den samlede boks — tekster som "M" og "AB" må ikke flytte
 * punkterne): for hver side af stregernes boks midten af de punkter, der ligger på kanten. → [{ p, side }].
 */
export function portsFromVertices(vertices, tol = 1.5) {
  if (!vertices.length) return [];
  const xs = vertices.map((v) => v[0]);
  const ys = vertices.map((v) => v[1]);
  const x1 = Math.min(...xs), x2 = Math.max(...xs), y1 = Math.min(...ys), y2 = Math.max(...ys);
  const out = [];
  const side = (name, onEdge, along, fixed) => {
    const on = vertices.filter(onEdge);
    if (!on.length) return;
    const vals = on.map(along);
    const mid = (Math.min(...vals) + Math.max(...vals)) / 2;
    out.push({ p: fixed(mid), side: name });
  };
  if (x2 - x1 > tol) {
    side('l', (v) => Math.abs(v[0] - x1) < tol, (v) => v[1], (m) => [x1, m]);
    side('r', (v) => Math.abs(v[0] - x2) < tol, (v) => v[1], (m) => [x2, m]);
  }
  if (y2 - y1 > tol) {
    side('t', (v) => Math.abs(v[1] - y1) < tol, (v) => v[0], (m) => [m, y1]);
    side('b', (v) => Math.abs(v[1] - y2) < tol, (v) => v[0], (m) => [m, y2]);
  }
  return out;
}

const SIDE_DIR = { l: [-1, 0], r: [1, 0], t: [0, -1], b: [0, 1] };
export const sideDir = (side) => SIDE_DIR[side] ?? [1, 0];

/** Udadgående side for et punkt givet som brøkdel af boksen: nærmeste kant. */
export function fracSide(frac) {
  const [fx, fy] = frac;
  const d = { l: fx, r: 1 - fx, t: fy, b: 1 - fy };
  return Object.entries(d).sort((a, b) => a[1] - b[1])[0][0];
}

/** Retningsvektor efter symbolets matrix (drejning/spejling/skalering), afrundet til nærmeste akse. */
export function turnDir(dir, m) {
  const dx = m.a * dir[0] + m.c * dir[1];
  const dy = m.b * dir[0] + m.d * dir[1];
  return Math.abs(dx) >= Math.abs(dy) ? [Math.sign(dx) || 1, 0] : [0, Math.sign(dy) || 1];
}

export const axisOfDir = (dir) => (dir[0] ? 'h' : 'v');
const plus = (p, dir, len) => [p[0] + dir[0] * len, p[1] + dir[1] * len];

const DETOUR = 40;   // så langt ud til siden en U-omvej går
const unit = (a, b) => {
  const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  return [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
};
const dot = (u, v) => u[0] * v[0] + u[1] * v[1];

/**
 * Bedste vinkelrette vej fra S til E: første stykke må ikke gå imod `dirS` (ud af et punkt / videre fra forrige stykke),
 * sidste stykke må ikke gå i `dirE`s retning (det ville komme ind gennem symbolet), og røret må aldrig vende oven i sig
 * selv. Kandidater: lige, L (begge veje), Z (midtvejs) og U-omveje; kortest med færrest knæk vinder.
 */
export function bestRoute(S, dirS, E, dirE) {
  const [sx, sy] = S;
  const [ex, ey] = E;
  const mx = (sx + ex) / 2, my = (sy + ey) / 2;
  const lo = (u, v) => Math.min(u, v) - DETOUR, hi = (u, v) => Math.max(u, v) + DETOUR;
  const cands = [
    [S, E],
    [S, [ex, sy], E], [S, [sx, ey], E],
    [S, [mx, sy], [mx, ey], E], [S, [sx, my], [ex, my], E],
    ...[lo(sy, ey), hi(sy, ey)].map((y) => [S, [sx, y], [ex, y], E]),
    ...[lo(sx, ex), hi(sx, ex)].map((x) => [S, [x, sy], [x, ey], E]),
    // ud langs dirS først, så rundt (når målet ligger bag punktet)
    ...(dirS ? [lo(sy, ey), hi(sy, ey), lo(sx, ex), hi(sx, ex)].flatMap((v) => {
      const o = [sx + dirS[0] * DETOUR, sy + dirS[1] * DETOUR];
      return dirS[0] ? [[S, o, [o[0], v], [ex, v], E], [S, o, [o[0], ey], E]] : [[S, o, [v, o[1]], [v, ey], E], [S, o, [ex, o[1]], E]];
    }) : []),
  ];
  let best = null;
  let bestScore = Infinity;
  for (const raw of cands) {
    const pts = simplify(raw);
    if (pts.length < 2 && !(Math.abs(sx - ex) < EPS && Math.abs(sy - ey) < EPS)) continue;
    let ok = true;
    let len = 0;
    for (let i = 1; i < pts.length && ok; i++) {
      if (!axisOf(pts[i - 1], pts[i])) { ok = false; break; }
      const u = unit(pts[i - 1], pts[i]);
      len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      if (i === 1 && dirS && dot(u, dirS) < -EPS) ok = false;
      if (i === pts.length - 1 && dirE && dot(u, dirE) > EPS) ok = false;
      if (i >= 2 && dot(u, unit(pts[i - 2], pts[i - 1])) < -EPS) ok = false;   // vender oven i sig selv
    }
    if (!ok) continue;
    const score = len + 30 * (pts.length - 1);
    if (score < bestScore) { best = pts; bestScore = score; }
  }
  return best ?? connect(S, E);
}

/**
 * Rute fra a til b. `dirA`/`dirB` = udadgående retning ved et tilslutningspunkt (eller null): røret går STUB lige ud,
 * før det knækker, så det aldrig går ind i symbolet fra siden eller bagfra.
 */
export function routeBetween(a, b, dirA = null, dirB = null) {
  const sa = dirA ? plus(a, dirA, STUB) : a;
  const sb = dirB ? plus(b, dirB, STUB) : b;
  return simplify([a, ...bestRoute(sa, dirA, sb, dirB), b]);
}

/**
 * Flyt en ende ('start'/'end') til p med udadgående retning `dir` (eller null): stykket hen til enden lægges om fra
 * nærmeste knæk, så røret går lige ud af punktet. Resten af røret bevares.
 */
export function reroute(points, which, p, dir = null) {
  const pts = which === 'start' ? [...points].reverse() : [...points];
  const keep = pts.slice(0, -1);
  const sp = dir ? plus(p, dir, STUB) : p;
  const length = (list) => list.reduce((n, q, i) => (i ? n + Math.hypot(q[0] - list[i - 1][0], q[1] - list[i - 1][1]) : 0), 0);
  const routeFrom = (j) => {
    const kept = keep.slice(0, j + 1);
    const anchor = kept[kept.length - 1];
    const before = kept.length >= 2 ? kept[kept.length - 2] : null;
    const startDir = before ? unit(before, anchor) : keep.length >= 2 ? unit(keep[0], keep[1]) : null;
    const leg = bestRoute(anchor, startDir, sp, dir);
    return simplify([...kept, ...leg.slice(1), ...(dir ? [p] : [])]);
  };
  // Behold så meget af den eksisterende rute som muligt (brugeren kan have flyttet stykker): læg om fra det nærmeste
  // knæk, der ikke ligger BAG punktet (set i punktets retning) — et knæk bag punktet ville give en sløjfe (v3.6.0).
  for (let j = keep.length - 1; j >= 0; j--) {
    const a = keep[j];
    const behind = dir && (a[0] - p[0]) * dir[0] + (a[1] - p[1]) * dir[1] < -EPS;
    if (behind) continue;
    const res = routeFrom(j);
    return which === 'start' ? res.reverse() : res;
  }
  // alle knæk ligger bag punktet: den korteste rute med færrest knæk
  let best = null;
  let bestScore = Infinity;
  for (let j = keep.length - 1; j >= 0; j--) {
    const res = routeFrom(j);
    const score = length(res) + 30 * (res.length - 1);
    if (score < bestScore) { best = res; bestScore = score; }
  }
  return which === 'start' ? best.reverse() : best;
}

/**
 * Knækpunkterne i et rør tegnet med bløde bøjninger (eller uden): de lige stykker forlænges til de mødes. Buer og kurver
 * mellem lige stykker ignoreres.
 */
export function pipeCorners(d) {
  const lines = pathSegments(d).filter((s) => s.type === 'L' && Math.hypot(s.to[0] - s.from[0], s.to[1] - s.from[1]) > 1e-6);
  if (!lines.length) return pathPoints(d);
  const pts = [lines[0].from];
  for (let i = 1; i < lines.length; i++) {
    const a = lines[i - 1];
    const b = lines[i];
    const ha = Math.abs(a.from[1] - a.to[1]) < 1e-6;   // vandret
    const hb = Math.abs(b.from[1] - b.to[1]) < 1e-6;
    if (ha && !hb) pts.push([b.from[0], a.from[1]]);
    else if (!ha && hb) pts.push([a.from[0], b.from[1]]);
    else pts.push(a.to);   // samme retning (eller skråt): stykkerne mødes i a's ende
  }
  pts.push(lines[lines.length - 1].to);
  return simplify(pts);
}

/** Sti for røret med bløde bøjninger med radius r (0 = skarpe knæk). Radius begrænses af stykkernes længde. */
export function pipePath(points, r = 0) {
  const pts = simplify(points);
  if (!(r > 0) || pts.length < 3) return pathD(pts);
  let d = `M${r2(pts[0][0])} ${r2(pts[0][1])}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const a = pts[i - 1], c = pts[i], b = pts[i + 1];
    const lin = Math.hypot(c[0] - a[0], c[1] - a[1]);
    const lout = Math.hypot(b[0] - c[0], b[1] - c[1]);
    // de mellemste stykker deles med naboknækket; ved enderne bevares mindst 20 % lige rør, så knækkene altid kan
    // genfindes (pipeCorners) og røret går lige ind i tilslutningspunktet
    const rr = Math.min(r, i === 1 ? lin * 0.8 : lin / 2, i === pts.length - 2 ? lout * 0.8 : lout / 2);
    const u1 = [(c[0] - a[0]) / lin, (c[1] - a[1]) / lin];
    const u2 = [(b[0] - c[0]) / lout, (b[1] - c[1]) / lout];
    const p1 = [c[0] - u1[0] * rr, c[1] - u1[1] * rr];
    const p2 = [c[0] + u2[0] * rr, c[1] + u2[1] * rr];
    const sweep = u1[0] * u2[1] - u1[1] * u2[0] > 0 ? 1 : 0;
    d += ` L${r2(p1[0])} ${r2(p1[1])} A${r2(rr)} ${r2(rr)} 0 0 ${sweep} ${r2(p2[0])} ${r2(p2[1])}`;
  }
  const z = pts[pts.length - 1];
  return `${d} L${r2(z[0])} ${r2(z[1])}`;
}

/**
 * Forlæng et rør under tegning hen til `target`. Første stykke går ud af startpunktets retning (`startDir`); slutter
 * røret i et tilslutningspunkt, går det ind langs punktets retning (`endDir`). Senere stykker fortsætter videre fra det
 * forrige uden at vende. → hele rørets punkter.
 */
export function extendRoute(points, target, startDir = null, endDir = null) {
  if (points.length === 1) return routeBetween(points[0], target, startDir, endDir);
  const last = points[points.length - 1];
  const before = points[points.length - 2];
  const sp = endDir ? plus(target, endDir, STUB) : target;
  const leg = bestRoute(last, unit(before, last), sp, endDir);
  return simplify([...points, ...leg.slice(1), ...(endDir ? [target] : [])]);
}

// ---------------------------------------------------------------- v3.2.0: T-stykker (rør på rør)
/**
 * Nærmeste punkt på et rør (dets knækpunkter) — projiceret ind på det nærmeste stykke. → { q, k, dist }, hvor stykket
 * er points[k] → points[k + 1]. Rørets egne ender tæller ikke (der kobles man på enden, ikke et T).
 */
export function nearestOnRoute(points, p) {
  let best = null;
  for (let k = 0; k + 1 < points.length; k++) {
    const a = points[k];
    const b = points[k + 1];
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const len2 = dx * dx + dy * dy;
    if (!len2) continue;
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
    const q = [a[0] + t * dx, a[1] + t * dy];
    const dist = Math.hypot(p[0] - q[0], p[1] - q[1]);
    if (!best || dist < best.dist) best = { q, k, dist };
  }
  if (!best) return null;
  const first = points[0], last = points[points.length - 1];
  if (same(best.q, first) || same(best.q, last)) return null;
  return best;
}

/** Del rørets punkter i q (på stykket k) → [til q, fra q]. */
export function splitRoute(points, k, q) {
  return [simplify([...points.slice(0, k + 1), q]), simplify([q, ...points.slice(k + 1)])];
}

/** Siden (l/r/t/b) af et T-stykke i q, der vender mod punktet p (langs den dominerende akse). */
export function sideToward(q, p) {
  const dx = p[0] - q[0], dy = p[1] - q[1];
  if (Math.abs(dx) >= Math.abs(dy)) return dx < 0 ? 'l' : 'r';
  return dy < 0 ? 't' : 'b';
}

/**
 * Siden en gren skal have på et T-stykke, hvor hovedrøret bruger to sider: på tværs af hovedrøret, mod grenen
 * (`toward`). Er begge tværsider optaget, eller ligger grenen præcis på linje, bruges en ledig side.
 */
export function branchSide(used, q, toward) {
  const horizontal = used.includes('l') || used.includes('r');
  const across = horizontal ? (toward[1] < q[1] ? 't' : 'b') : (toward[0] < q[0] ? 'l' : 'r');
  if (!used.includes(across)) return across;
  return ['t', 'b', 'l', 'r'].find((s) => !used.includes(s)) ?? null;
}

// ---------------------------------------------------------------- v3.4.0: rør-ende på rør-ende
/**
 * Læg to rør sammen, hvor a's ende `aEnd` møder b's ende `bEnd` ('start' | 'end'). → punkterne fra a's anden ende
 * til b's anden ende. Enderne der mødes, skal ligge i samme punkt.
 */
export function mergeRoutes(a, aEnd, b, bEnd) {
  const A = aEnd === 'end' ? [...a] : [...a].reverse();
  const B = bEnd === 'start' ? [...b] : [...b].reverse();
  return simplify([...A, ...B.slice(1)]);
}

/** Retningen ud af rørets ende ('start'/'end') — langs dets sidste stykke, væk fra røret. */
export function endDir(points, which) {
  const n = points.length;
  const [a, b] = which === 'end' ? [points[n - 2], points[n - 1]] : [points[1], points[0]];
  const d = unit(a, b);
  return Math.abs(d[0]) >= Math.abs(d[1]) ? [Math.sign(d[0]) || 1, 0] : [0, Math.sign(d[1]) || 1];
}

// ---------------------------------------------------------------- v3.6.0: flyt et stykke af røret
/**
 * Flyt stykket k (points[k] → points[k + 1]) `delta` på tværs (et vandret stykke op/ned, et lodret til siden).
 * Nabostykkerne strækkes; rørets ender bliver, hvor de er — er stykket det første/sidste, beholdes et lige stykke på
 * STUB ud af enden (eller halvdelen af stykket, hvis det er kortere), og der indsættes et knæk.
 */
export function moveSegment(points, k, delta) {
  const n = points.length;
  if (k < 0 || k + 1 >= n || !delta) return points;
  const a = points[k];
  const b = points[k + 1];
  const axis = axisOf(a, b);
  if (!axis) return points;
  const shift = (p) => (axis === 'h' ? [p[0], p[1] + delta] : [p[0] + delta, p[1]]);
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const stub = Math.min(STUB, len / 3);
  const u = unit(a, b);
  const out = points.slice(0, k);
  if (k === 0) {
    // starten ligger fast: lige stykke ud af den, så knæk over til det flyttede stykke
    const s = [a[0] + u[0] * stub, a[1] + u[1] * stub];
    out.push(a, s, shift(s));
  } else out.push(shift(a));
  if (k + 1 === n - 1) {
    const e = [b[0] - u[0] * stub, b[1] - u[1] * stub];
    out.push(shift(e), e, b);
  } else out.push(shift(b));
  out.push(...points.slice(k + 2));
  return simplify(out);
}

/** Midten af hvert stykke, der er langt nok til et håndtag: [{ k, mid, axis }]. */
export function segmentHandles(points, minLen = 0) {
  const out = [];
  for (let k = 0; k + 1 < points.length; k++) {
    const a = points[k], b = points[k + 1];
    const axis = axisOf(a, b);
    if (!axis || Math.hypot(b[0] - a[0], b[1] - a[1]) < minLen) continue;
    out.push({ k, mid: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], axis });
  }
  return out;
}

// ---------------------------------------------------------------- v3.8.0: læg stykker sammen / ret røret ud
/**
 * Flytningen af stykke k, fanget så stykket kommer på linje med et andet parallelt stykke af røret eller en af enderne,
 * hvis det er inden for `tol` — så forsvinder hakket, og stykkerne bliver ét.
 */
export function alignDelta(points, k, delta, tol, extra = []) {
  const a = points[k], b = points[k + 1];
  const axis = axisOf(a, b);
  if (!axis) return delta;
  const at = (p) => (axis === 'h' ? p[1] : p[0]);
  const target = at(a) + delta;
  const lines = [];
  for (let i = 0; i + 1 < points.length; i++) {
    if (i === k || axisOf(points[i], points[i + 1]) !== axis) continue;
    lines.push(at(points[i]));
  }
  lines.push(at(points[0]), at(points[points.length - 1]), ...extra);   // extra: hjælpelinjer på samme akse
  let best = null;
  for (const c of lines) if (Math.abs(c - target) <= tol && (best === null || Math.abs(c - target) < Math.abs(best - target))) best = c;
  return best === null ? delta : best - at(a);
}

/** Ret røret ud: læg det helt om mellem enderne med så få knæk som muligt (retningen ind i punkterne bevares). */
export function straighten(points, dirStart = null, dirEnd = null) {
  if (points.length < 2) return points;
  return routeBetween(points[0], points[points.length - 1], dirStart, dirEnd);
}
