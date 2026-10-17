// Farver på valgte symboler i Tegn (v0.61.0): rene funktioner — testes i src/lib/colors.test.ts.

const NAMED = {
  black: '#000000', white: '#ffffff', gray: '#808080', grey: '#808080', silver: '#c0c0c0', lightgray: '#d3d3d3', lightgrey: '#d3d3d3',
  darkgray: '#a9a9a9', darkgrey: '#a9a9a9', red: '#ff0000', green: '#008000', lime: '#00ff00', blue: '#0000ff', yellow: '#ffff00',
  orange: '#ffa500', navy: '#000080', teal: '#008080', purple: '#800080', maroon: '#800000', olive: '#808000', aqua: '#00ffff', fuchsia: '#ff00ff',
};
const PROPS = ['fill', 'stroke'];

/** Farve → '#rrggbb' (små bogstaver), eller null for "ingen farve" (none, transparent, url(...), currentColor, inherit, ukendt). */
export function normColor(v) {
  if (v == null) return null;
  const s = String(v).trim().toLowerCase();
  if (!s) return null;
  let m = /^#([0-9a-f]{3})$/.exec(s);
  if (m) return '#' + [...m[1]].map((c) => c + c).join('');
  if (/^#[0-9a-f]{6}$/.test(s)) return s;
  m = /^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/.exec(s);
  if (m) return '#' + m.slice(1, 4).map((x) => Math.min(255, Number(x)).toString(16).padStart(2, '0')).join('');
  return NAMED[s] ?? null;
}

/** 'fill:#555; stroke:red' → [['fill', '#555'], ['stroke', 'red']] (andre egenskaber bevares af recolorAttrs). */
function styleDecls(style) {
  return String(style || '').split(';').map((d) => d.trim()).filter(Boolean).map((d) => {
    const i = d.indexOf(':');
    return i < 0 ? [d, ''] : [d.slice(0, i).trim().toLowerCase(), d.slice(i + 1).trim()];
  });
}

/** Farverne i et elements fill/stroke (attributter og style). → ['#rrggbb', …] (med gentagelser). */
export function colorsOf(attrs) {
  const out = [];
  for (const p of PROPS) { const c = normColor(attrs[p]); if (c) out.push(c); }
  for (const [k, v] of styleDecls(attrs.style)) if (PROPS.includes(k)) { const c = normColor(v); if (c) out.push(c); }
  return out;
}

/** Saml farver fra mange elementer. → [{ color, uses }], mest brugte først. */
export function collectColors(list) {
  const n = new Map();
  for (const a of list) for (const c of colorsOf(a)) n.set(c, (n.get(c) ?? 0) + 1);
  return [...n].map(([color, uses]) => ({ color, uses })).sort((a, b) => b.uses - a.uses || a.color.localeCompare(b.color));
}

/**
 * Skift farven `from` til `to` i et elements fill/stroke. → de attributter der ændres ({ fill?, stroke?, style? } med NYE
 * værdier), eller null hvis elementet ikke bruger farven. Andre style-egenskaber bevares.
 */
export function recolorAttrs(attrs, from, to) {
  const f = normColor(from), t = normColor(to);
  if (!f || !t) return null;
  const out = {};
  for (const p of PROPS) if (normColor(attrs[p]) === f) out[p] = t;
  if (attrs.style) {
    let hit = false;
    const decls = styleDecls(attrs.style).map(([k, v]) => {
      if (PROPS.includes(k) && normColor(v) === f) { hit = true; return [k, t]; }
      return [k, v];
    });
    if (hit) out.style = decls.map(([k, v]) => (v === '' ? k : `${k}:${v}`)).join(';');
  }
  return Object.keys(out).length ? out : null;
}
