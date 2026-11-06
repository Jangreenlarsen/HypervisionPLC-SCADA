// SPDX-License-Identifier: AGPL-3.0-or-later
// Nye tegneredskaber i Tegn (v3.33.0): polygon, stjerne og regulær polygon, billede, stiplet streg, pile, gradient,
// skygge og lag. Ren logik + små DOM-hjælpere på tegningens <svg> — testet i shapes.test.ts. Selve værktøjerne
// (mus) ligger i engine.ts, API'et i scada-core.js.

export const NS = 'http://www.w3.org/2000/svg';
export const XLINK = 'http://www.w3.org/1999/xlink';
/** Id-præfikser for de defs, Tegn selv laver — kun de ryddes op, når de ikke bruges mere. */
export const OWN_DEFS = ['hv_pil_', 'hv_grad_', 'hv_skygge_'];

const r2 = (v) => Math.round(v * 100) / 100;

/** Punkterne i en regulær polygon med n hjørner (første hjørne i retningen `angle`, grader, 0 = op). */
export function regularPoints(cx, cy, r, n, angle = 0) {
  const k = Math.max(3, Math.min(64, Math.round(n)));
  return Array.from({ length: k }, (_, i) => {
    const a = ((angle + (360 * i) / k) * Math.PI) / 180;
    return [r2(cx + r * Math.sin(a)), r2(cy - r * Math.cos(a))];
  });
}

/** Punkterne i en stjerne med n spidser; `inner` = indre radius som brøkdel af den ydre (0,1–0,95). */
export function starPoints(cx, cy, r, n, inner = 0.5, angle = 0) {
  const k = Math.max(3, Math.min(64, Math.round(n)));
  const ri = r * Math.max(0.1, Math.min(0.95, inner));
  return Array.from({ length: 2 * k }, (_, i) => {
    const a = ((angle + (180 * i) / k) * Math.PI) / 180;
    const rr = i % 2 ? ri : r;
    return [r2(cx + rr * Math.sin(a)), r2(cy - rr * Math.cos(a))];
  });
}

/** Vinkel (grader, 0 = op, med uret) fra midten til et punkt — Shift-fang i 15°-trin med `snap`. */
export function angleTo(cx, cy, x, y, snap = 0) {
  let a = (Math.atan2(x - cx, cy - y) * 180) / Math.PI;
  if (snap) a = Math.round(a / snap) * snap;
  return ((a % 360) + 360) % 360;
}

/** En cirkelbue med uret fra vinkel a0 til a1 (grader, 0 = op) som path-data. */
export function arcPath(cx, cy, r, a0, a1) {
  const pt = (a) => [r2(cx + r * Math.sin((a * Math.PI) / 180)), r2(cy - r * Math.cos((a * Math.PI) / 180))];
  let d = (((a1 - a0) % 360) + 360) % 360;
  if (d < 0.5) d = 359.9;   // samme vinkel: næsten hel cirkel (en bue med samme start og slut tegnes ikke)
  const [sx, sy] = pt(a0), [ex, ey] = pt(a0 + d);
  return `M${sx},${sy} A${r2(r)},${r2(r)} 0 ${d > 180 ? 1 : 0} 1 ${ex},${ey}`;
}

export const pointsAttr = (pts) => pts.map((p) => `${p[0]},${p[1]}`).join(' ');

export function parsePoints(s) {
  const nums = String(s || '').trim().split(/[\s,]+/).map(Number).filter(Number.isFinite);
  const out = [];
  for (let i = 0; i + 1 < nums.length; i += 2) out.push([nums[i], nums[i + 1]]);
  return out;
}

/** Formens parametre (data-hv-shape) → { k: 'star'|'regpoly', n, ri } eller null. */
export function shapeParams(el) {
  try {
    const p = JSON.parse(el?.getAttribute?.('data-hv-shape') || 'null');
    if (p && (p.k === 'star' || p.k === 'regpoly') && Number.isFinite(p.n)) return { k: p.k, n: p.n, ri: Number.isFinite(p.ri) ? p.ri : 0.5 };
  } catch { /* ugyldig — behandles som en almindelig polygon */ }
  return null;
}

/** Tegn en stjerne/regulær polygon (tegnet med `params`) om igen med parametrene `next`: midte, radius og drejning læses fra de nuværende punkter
 *  (så en form, der er flyttet eller skaleret med musen, bliver stående). → points-streng eller null. */
export function regenerate(points, params, next = params) {
  const pts = parsePoints(points);
  const outer = params.k === 'star' ? pts.filter((_, i) => i % 2 === 0) : pts;
  if (outer.length < 3) return null;
  const cx = outer.reduce((s, p) => s + p[0], 0) / outer.length;
  const cy = outer.reduce((s, p) => s + p[1], 0) / outer.length;
  const r = Math.hypot(outer[0][0] - cx, outer[0][1] - cy);
  const angle = (Math.atan2(outer[0][0] - cx, cy - outer[0][1]) * 180) / Math.PI;
  return pointsAttr(next.k === 'star' ? starPoints(cx, cy, r, next.n, next.ri, angle) : regularPoints(cx, cy, r, next.n, angle));
}

// ---------------------------------------------------------------- streg

export const DASHES = [
  { v: 'solid', label: 'Fuld' }, { v: 'dash', label: 'Stiplet' }, { v: 'dot', label: 'Prikket' }, { v: 'dashdot', label: 'Stiplet-prikket' },
];

/** stroke-dasharray for en stregtype — skaleret med stregens tykkelse, så mønstret passer til både tynde og tykke. */
export function dashArray(kind, width) {
  const w = Math.max(1, Number(width) || 1);
  const f = (...m) => m.map((x) => r2(x * w)).join(' ');
  if (kind === 'dash') return f(4, 2);
  if (kind === 'dot') return f(1, 2);
  if (kind === 'dashdot') return f(4, 2, 1, 2);
  return null;
}

/** Stregtypen ud fra et dasharray (det modsatte af dashArray; ukendte mønstre → 'custom'). */
export function dashKind(dash, width) {
  if (!dash || dash === 'none') return 'solid';
  for (const k of ['dash', 'dot', 'dashdot']) if (dashArray(k, width) === dash.trim().replace(/,/g, ' ').replace(/\s+/g, ' ')) return k;
  return 'custom';
}

// ---------------------------------------------------------------- defs (pile, gradienter, skygge)

/** Tegningens <defs> (oprettes forrest, hvis den mangler). */
export function defsOf(svg) {
  let d = [...svg.children].find((c) => c.localName === 'defs');
  if (!d) { d = document.createElementNS(NS, 'defs'); svg.insertBefore(d, svg.firstChild); }
  return d;
}

const hex = (c) => String(c || '#000000').replace(/[^0-9a-zA-Z]/g, '').slice(0, 12) || 'sort';

/** En pilespids i stregens farve (én pr. farve, genbruges). → id */
export function ensureArrow(svg, color) {
  const id = `hv_pil_${hex(color)}`;
  if (svg.querySelector(`#${id}`)) return id;
  const m = document.createElementNS(NS, 'marker');
  for (const [k, v] of Object.entries({ id, viewBox: '0 0 10 10', refX: '8', refY: '5', markerWidth: '5', markerHeight: '5',
    orient: 'auto-start-reverse', markerUnits: 'strokeWidth' })) m.setAttribute(k, v);
  const p = document.createElementNS(NS, 'path');
  p.setAttribute('d', 'M0,0 L10,5 L0,10 Z');
  p.setAttribute('fill', color && color !== 'none' ? color : '#000000');
  m.appendChild(p);
  defsOf(svg).appendChild(m);
  return id;
}

const urlId = (v) => /url\(\s*['"]?#([^'")\s]+)['"]?\s*\)/.exec(v || '')?.[1] ?? null;

/** Gradienten et fyld peger på → { kind: 'linear'|'radial', c1, c2, angle } eller null. */
export function gradientOf(svg, fill) {
  const id = urlId(fill);
  const g = id ? svg.querySelector(`#${CSS.escape(id)}`) : null;
  if (!g || !/^(linear|radial)Gradient$/.test(g.localName)) return null;
  const stops = [...g.querySelectorAll('stop')];
  const col = (s) => s?.getAttribute('stop-color') || /stop-color:\s*([^;]+)/.exec(s?.getAttribute('style') || '')?.[1]?.trim() || '#ffffff';
  let angle = 90;
  if (g.localName === 'linearGradient') {
    const n = (a, d) => { const v = parseFloat(g.getAttribute(a) ?? ''); return Number.isFinite(v) ? v : d; };
    const dx = n('x2', 1) - n('x1', 0), dy = n('y2', 0) - n('y1', 0);
    angle = Math.round((Math.atan2(dx, -dy) * 180) / Math.PI);
  }
  return { kind: g.localName === 'linearGradient' ? 'linear' : 'radial', c1: col(stops[0]), c2: col(stops[stops.length - 1]), angle, id };
}

/** Lav/ret elementets egen gradient (`hv_grad_<id>`). angle i grader (0 = nedefra og op, 90 = venstre mod højre). → id */
export function ensureGradient(svg, elId, kind, c1, c2, angle = 90) {
  const id = `hv_grad_${elId}`;
  let g = svg.querySelector(`#${CSS.escape(id)}`);
  const tag = kind === 'radial' ? 'radialGradient' : 'linearGradient';
  if (g && g.localName !== tag) { g.remove(); g = null; }
  if (!g) {
    g = document.createElementNS(NS, tag);
    g.setAttribute('id', id);
    defsOf(svg).appendChild(g);
  }
  if (kind === 'radial') {
    for (const [k, v] of Object.entries({ cx: '0.5', cy: '0.5', r: '0.5' })) g.setAttribute(k, v);
  } else {
    const a = (Number(angle) * Math.PI) / 180;
    const dx = Math.sin(a) / 2, dy = -Math.cos(a) / 2;
    for (const [k, v] of Object.entries({ x1: r2(0.5 - dx), y1: r2(0.5 - dy), x2: r2(0.5 + dx), y2: r2(0.5 + dy) })) g.setAttribute(k, String(v));
  }
  g.replaceChildren(...[[0, c1], [1, c2]].map(([o, c]) => {
    const s = document.createElementNS(NS, 'stop');
    s.setAttribute('offset', String(o));
    s.setAttribute('stop-color', c);
    return s;
  }));
  return id;
}

/** Elementets skygge (`hv_skygge_<id>`, feDropShadow) → { dx, dy, blur, color } eller null. */
export function shadowOf(svg, filter) {
  const id = urlId(filter);
  const f = id ? svg.querySelector(`#${CSS.escape(id)}`) : null;
  const d = f?.querySelector('feDropShadow');
  if (!d) return null;
  const n = (a, def) => { const v = parseFloat(d.getAttribute(a) ?? ''); return Number.isFinite(v) ? v : def; };
  return { dx: n('dx', 3), dy: n('dy', 3), blur: n('stdDeviation', 2), color: d.getAttribute('flood-color') || '#000000' };
}

export function ensureShadow(svg, elId, { dx = 3, dy = 3, blur = 2, color = '#000000' } = {}) {
  const id = `hv_skygge_${elId}`;
  let f = svg.querySelector(`#${CSS.escape(id)}`);
  if (!f) {
    f = document.createElementNS(NS, 'filter');
    for (const [k, v] of Object.entries({ id, x: '-50%', y: '-50%', width: '200%', height: '200%' })) f.setAttribute(k, v);
    f.appendChild(document.createElementNS(NS, 'feDropShadow'));
    defsOf(svg).appendChild(f);
  }
  const d = f.querySelector('feDropShadow');
  const c = (v, lo, hi) => String(Math.max(lo, Math.min(hi, Number(v) || 0)));
  for (const [k, v] of Object.entries({ dx: c(dx, -50, 50), dy: c(dy, -50, 50), stdDeviation: c(blur, 0, 30), 'flood-color': color, 'flood-opacity': '0.5' })) d.setAttribute(k, v);
  return id;
}

/** Fjern Tegns egne defs (pile, gradienter, skygger), som intet element længere henviser til. → antal fjernet */
export function cleanupDefs(svg) {
  const used = new Set();
  for (const el of svg.querySelectorAll('*')) {
    for (const a of el.attributes) {
      const re = /url\(\s*['"]?#([^'")\s]+)['"]?\s*\)/g;
      let m;
      while ((m = re.exec(a.value))) used.add(m[1]);
      if (a.localName === 'href' && a.value.startsWith('#')) used.add(a.value.slice(1));
    }
  }
  let n = 0;
  for (const d of [...svg.querySelectorAll('defs > [id]')]) {
    if (OWN_DEFS.some((p) => d.id.startsWith(p)) && !used.has(d.id)) { d.remove(); n++; }
  }
  return n;
}

// ---------------------------------------------------------------- billede

export const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];
export const MAX_IMAGE_BYTES = 2 * 1024 * 1024;

/** Billedets størrelse i tegningen: naturlig størrelse, skaleret ned til højst `maxFrac` af tegningen. */
export function fitImage(w, h, canvasW, canvasH, maxFrac = 0.6) {
  const k = Math.min(1, (canvasW * maxFrac) / Math.max(w, 1), (canvasH * maxFrac) / Math.max(h, 1));
  return { w: Math.max(1, Math.round(w * k)), h: Math.max(1, Math.round(h * k)) };
}

/** Kontrol af en billedfil før den læses: type og størrelse. → fejltekst eller '' */
export function imageProblem(file) {
  if (!IMAGE_TYPES.includes(file.type)) return `${file.name}: kun PNG, JPG, WebP og GIF kan sættes ind`;
  if (file.size > MAX_IMAGE_BYTES) return `${file.name}: billedet er større end 2 MB — gør det mindre først`;
  return '';
}
