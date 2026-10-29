// Tilstandsmærke, skygge af PLC'ens position og hængelås oven på et symbol på Overview (symbolstandarden afsnit 5).
// Tegnes i et lag øverst i tegningen (samme koordinater), så det følger zoom/panorering og aldrig fanger klik.
import { GLYPH, STATE_TXT, type SymbolState } from './symbolUi';

const NS = 'http://www.w3.org/2000/svg';

export interface OverlayInput {
  state: SymbolState | null;   // null = intet mærke (fx trykknap)
  remoteLabel: string | null;  // PLC'ens position — vises som skygge ved afvigelse
  locked: boolean;
  /** Navnene på de låste positioner (nøglelås) — får en lille hængelås ud for positionens tekst i symbolet */
  lockedLabels?: string[];
}

/** Tekster i symbolet, der viser en låst position (teksten er præcis positionens navn). */
export function lockedTexts(el: Element, labels: string[]): SVGTextElement[] {
  const want = new Set(labels.map((l) => l.trim()).filter(Boolean));
  if (!want.size) return [];
  return [...el.querySelectorAll<SVGTextElement>('text')].filter((t) => want.has((t.textContent ?? '').trim()));
}

function lockGlyph(x: number, y: number, s: number, title: string): SVGElement {
  const lock = make('g', { class: 'hv-lock', transform: `translate(${x} ${y}) scale(${s})` });
  lock.appendChild(make('title', {}, title));
  lock.appendChild(make('path', { d: 'M5 10 V6 a5 5 0 0 1 10 0 V10' }));
  lock.appendChild(make('rect', { x: 2, y: 10, width: 16, height: 12, rx: 2 }));
  return lock;
}

/** Symbolets kasse i tegningens koordinater (rodens brugerkoordinater), uanset symbolets egne transforms. */
export function boxInRoot(root: SVGSVGElement, el: SVGGraphicsElement): { x: number; y: number; w: number; h: number } | null {
  try {
    const bb = el.getBBox();
    const rootM = root.getScreenCTM();
    const elM = el.getScreenCTM();
    if (!rootM || !elM) return null;
    const m = rootM.inverse().multiply(elM);
    const pts = [[bb.x, bb.y], [bb.x + bb.width, bb.y], [bb.x, bb.y + bb.height], [bb.x + bb.width, bb.y + bb.height]]
      .map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
  } catch {
    return null; // getBBox/getScreenCTM findes ikke i alle miljøer (fx jsdom) — så intet mærke
  }
}

function make(tag: string, attrs: Record<string, string | number>, text?: string): SVGElement {
  const e = document.createElementNS(NS, tag) as SVGElement;
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  if (text !== undefined) e.textContent = text;
  return e;
}

function layer(root: SVGSVGElement): SVGGElement {
  let g = root.querySelector<SVGGElement>(':scope > g.hv-symlayer');
  if (!g) {
    g = make('g', { class: 'hv-symlayer', 'pointer-events': 'none' }) as SVGGElement;
    root.appendChild(g);
  } else if (g !== root.lastElementChild) {
    root.appendChild(g); // altid øverst
  }
  return g;
}

/** Tegn (eller opdatér) mærket for ét symbol. */
export function drawOverlay(root: SVGSVGElement, element: string, input: OverlayInput): void {
  const el = root.querySelector<SVGGraphicsElement>(`#${CSS.escape(element)}`);
  const lay = layer(root);
  lay.querySelector(`:scope > g[data-for="${CSS.escape(element)}"]`)?.remove();
  const texts = el ? lockedTexts(el, input.lockedLabels ?? []) : [];
  if (!el || (!input.state && !input.locked && !texts.length)) return;
  const box = boxInRoot(root, el);
  if (!box) return;
  const g = make('g', { 'data-for': element, class: 'hv-symstate' }) as SVGGElement;
  const r = Math.max(6, Math.min(14, Math.min(box.w, box.h) * 0.14));
  if (input.state === 'mismatch' && input.remoteLabel !== null) {
    // Skygge af PLC'ens position: stiplet ramme og teksten under symbolet
    g.appendChild(make('rect', { class: 'hv-ghost', x: box.x - 3, y: box.y - 3, width: box.w + 6, height: box.h + 6, rx: 4 }));
    g.appendChild(make('text', { class: 'hv-ghosttext', x: box.x + box.w / 2, y: box.y + box.h + r * 1.6, 'text-anchor': 'middle',
      'font-size': r * 1.2 }, `PLC: ${input.remoteLabel}`));
  }
  if (input.state) {
    const cx = box.x + box.w, cy = box.y;
    const badge = make('g', { class: `hv-badge ${input.state}` });
    badge.appendChild(make('title', {}, STATE_TXT[input.state]));
    badge.appendChild(make('circle', { cx, cy, r }));
    badge.appendChild(make('text', { x: cx, y: cy + r * 0.38, 'text-anchor': 'middle', 'font-size': r * 1.15 }, GLYPH[input.state]));
    g.appendChild(badge);
  }
  if (input.locked) {
    g.appendChild(lockGlyph(box.x - r * 0.4, box.y - r * 1.2, r / 10, 'Låst position'));
  }
  // Ud for hver låst positions tekst: en lille hængelås lige til højre for teksten, i tekstens højde
  for (const t of texts) {
    const tb = boxInRoot(root, t);
    if (!tb || !tb.h) continue;
    const h = tb.h * 0.8, s = h / 22;
    g.appendChild(lockGlyph(tb.x + tb.w + h * 0.15, tb.y + (tb.h - h) / 2, s, `${(t.textContent ?? '').trim()} er låst (kode kræves)`));
  }
  lay.appendChild(g);
}

/** Fjern alle mærker (fx når en ny tegning vises). */
export function clearOverlays(root: SVGSVGElement | null): void {
  root?.querySelector(':scope > g.hv-symlayer')?.remove();
}
