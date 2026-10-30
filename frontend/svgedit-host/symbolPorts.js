// Tilslutningspunkter på symboler — fælles for Tegn (scada-core.js) og symbol-editoren (pages/SymbolEditor.svelte).
// Et punkt er en brøkdel [fx, fy] af symbolets EGEN boks (getBBox på symbolets rod), så det følger symbolet, når det
// flyttes, skaleres eller drejes. Rettede punkter bygges ind i symbolet ved indsættelse: data-hv-ports="fx,fy;fx,fy".
import { pathVertices } from './snap.js';
import { portsFrom, toFrac } from './pipes.js';

const r4 = (v) => Math.round(v * 1e4) / 1e4;

/** "0,0.5;1,0.5" → [[0,0.5],[1,0.5]]; ugyldige punkter springes over, intet gyldigt → null. */
export function parsePorts(text) {
  if (typeof text !== 'string' || !text.trim()) return null;
  const out = [];
  for (const part of text.split(';')) {
    const [x, y] = part.split(',').map((v) => Number(v.trim()));
    if (Number.isFinite(x) && Number.isFinite(y) && x >= 0 && x <= 1 && y >= 0 && y <= 1) out.push([x, y]);
  }
  return out.length ? out : null;
}

export const formatPorts = (ports) => ports.map((p) => `${r4(p[0])},${r4(p[1])}`).join(';');

/** Rørets retning ud af punktet: fra en sidekant vandret, fra top/bund lodret, ellers ud mod nærmeste kant. */
export function portAxis(frac) {
  const [fx, fy] = frac;
  const dx = Math.min(fx, 1 - fx);
  const dy = Math.min(fy, 1 - fy);
  return dx <= dy ? 'h' : 'v';
}

const M = (m) => ({ a: m.a, b: m.b, c: m.c, d: m.d, e: m.e, f: m.f });
const apply = (m, v) => [m.a * v[0] + m.c * v[1] + m.e, m.b * v[0] + m.d * v[1] + m.f];
function inverse(m) {
  const det = m.a * m.d - m.b * m.c;
  if (!det) return null;
  return { a: m.d / det, b: -m.b / det, c: -m.c / det, d: m.a / det, e: (m.c * m.f - m.d * m.e) / det, f: (m.b * m.e - m.a * m.f) / det };
}
const mul = (m, n) => ({
  a: m.a * n.a + m.c * n.b, b: m.b * n.a + m.d * n.b, c: m.a * n.c + m.c * n.d, d: m.b * n.c + m.d * n.d,
  e: m.a * n.e + m.c * n.f + m.e, f: m.b * n.e + m.d * n.f + m.f,
});

/** Hjørnepunkter af symbolets streger, i rodens egne koordinater (samme som rodens getBBox). Elementet skal vises. */
export function localVertices(root) {
  const base = root.getCTM?.();
  const inv = base ? inverse(M(base)) : null;
  if (!inv) return [];
  const out = [];
  for (const e of [root, ...root.querySelectorAll('path, line, polyline, polygon, rect')]) {
    const tag = e.tagName.toLowerCase();
    const n = (a) => Number(e.getAttribute(a)) || 0;
    let vs;
    if (tag === 'path') vs = pathVertices(e.getAttribute('d')) || [];
    else if (tag === 'line') vs = [[n('x1'), n('y1')], [n('x2'), n('y2')]];
    else if (tag === 'polyline' || tag === 'polygon') {
      const nums = (e.getAttribute('points') || '').trim().split(/[\s,]+/).map(Number);
      vs = [];
      for (let i = 0; i + 1 < nums.length; i += 2) vs.push([nums[i], nums[i + 1]]);
    } else if (tag === 'rect') {
      const x = n('x'), y = n('y'), w = n('width'), h = n('height');
      vs = [[x, y + h / 2], [x + w, y + h / 2], [x + w / 2, y], [x + w / 2, y + h]];
    } else continue;
    const own = e.getCTM?.();
    if (!own) continue;
    const m = e === root ? { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 } : mul(inv, M(own));
    for (const v of vs) if (Number.isFinite(v[0]) && Number.isFinite(v[1])) out.push(apply(m, v));
  }
  return out;
}

/** Rodens boks som { x, y, w, h } — eller null, hvis den ikke kan måles. */
export function boxOfRoot(root) {
  try {
    const bb = root.getBBox();
    return bb.width > 0 || bb.height > 0 ? { x: bb.x, y: bb.y, w: bb.width, h: bb.height } : null;
  } catch {
    return null;
  }
}

/** De automatisk fundne punkter som brøkdele (rørender på kanten + kantmidter). */
export function autoPorts(root) {
  const box = boxOfRoot(root);
  if (!box) return [];
  return portsFrom(localVertices(root), box).map((p) => toFrac(p, box).map(r4));
}

/** Kandidater at fange til i symbol-editoren: alle hjørnepunkter + kantmidter, som brøkdele inden for boksen. */
export function snapCandidates(root) {
  const box = boxOfRoot(root);
  if (!box) return [];
  const inside = (f) => f[0] >= -1e-6 && f[0] <= 1 + 1e-6 && f[1] >= -1e-6 && f[1] <= 1 + 1e-6;
  const all = [...localVertices(root).map((v) => toFrac(v, box)), [0, 0.5], [1, 0.5], [0.5, 0], [0.5, 1]];
  const out = [];
  for (const f of all.filter(inside).map((f) => f.map(r4))) if (!out.some((q) => q[0] === f[0] && q[1] === f[1])) out.push(f);
  return out;
}

/** Symbolets type som i tegningen (data-hv-type) og i /api/symbol-ports — samme regel som ved indsættelse. */
export const symbolType = (id) => String(id).toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 40);
