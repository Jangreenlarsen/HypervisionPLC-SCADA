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
      if (straight) { out[out.length - 1] = p; continue; }
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

/** "<id>@<x>,<y>" ↔ { id, local: [x, y] } — null hvis teksten ikke er en gyldig reference. */
export function parseRef(text) {
  const m = /^(.+)@(-?[\d.]+(?:e[-+]?\d+)?),(-?[\d.]+(?:e[-+]?\d+)?)$/i.exec(String(text ?? ''));
  if (!m) return null;
  const x = Number(m[2]);
  const y = Number(m[3]);
  return Number.isFinite(x) && Number.isFinite(y) ? { id: m[1], local: [x, y] } : null;
}
const r4 = (v) => Math.round(v * 1e4) / 1e4;
export const formatRef = (id, frac) => `${id}@${r4(frac[0])},${r4(frac[1])}`;

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
