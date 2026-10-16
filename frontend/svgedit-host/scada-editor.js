// Værtsside for SVG-Edit inde i SCADA'en (indlæses i en iframe fra samme origin).
// Forældresiden (DrawEditor.svelte) bruger `window.scada` nedenfor.
import Editor from './Editor.js';
import {
  directionAngle, gridCorrection, identityMatrix, invertMatrix, isDrag, multiplyMatrix, pathVertices, snapToObjects, transformBox, triangleApex, turnTo, unionBox,
} from './snap.js';

const editor = new Editor(document.getElementById('container'));
editor.setConfig({
  lang: 'da',
  imgPath: './images',
  extPath: './extensions',
  noDefaultExtensions: true,
  // Kun udvidelser der arbejder lokalt — ingen browser-lagring eller filåbning udenom SCADA'en
  extensions: ['ext-connector', 'ext-eyedropper', 'ext-markers', 'ext-panning', 'ext-polystar', 'ext-shapes'],
  noStorageOnLoad: true,
  forceStorage: false,
  emptyStorageOnDecline: true,
  showRulers: true,
  dimensions: [1200, 700],
  allowInitialUserOverride: false,
});
editor.init();

// ---------------------------------------------------------------- hjælpelinjer: gitter, fang til gitter, fang til objekter
// Gitteret tegnes af os selv (SVG-Edits eget gitter kan kun 10/100/…-inddelinger og matcher ikke fangtrinnet).
const guides = { grid: false, snapGrid: false, step: 10, snapObjects: false };
const SNAP_PX = 8;                       // fang inden for så mange skærm-pixel
let lastBoxes = new Map();               // valgte elementer → deres boks ved forrige 'selected'/'changed' (til at se en flytning)
let snapping = false;

/**
 * Elementets matrix til tegningens koordinater: dets egen og forfædres transform, uden zoom (rodens viewBox/størrelse
 * fjernes ved at dividere med en probe lagt direkte under roden).
 */
function toDocMatrix(el) {
  const root = canvas().getSvgContent();
  const own = el.getCTM?.();
  if (!own) return null;
  const probe = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  root.appendChild(probe);
  let base = null;
  try {
    base = probe.getCTM?.() ?? null;
  } finally {
    root.removeChild(probe);
  }
  const inv = invertMatrix(base ?? identityMatrix());
  return inv ? multiplyMatrix(inv, own) : own;
}

/** Elementets boks i tegningens koordinater (geometrien inkl. transform, uden streg), uafhængig af zoom. */
function boxOf(el) {
  try {
    const m = toDocMatrix(el);
    const bb = el.getBBox();
    if (m && Number.isFinite(bb.x)) return transformBox({ x: bb.x, y: bb.y, w: bb.width, h: bb.height }, m);
  } catch {
    // getBBox/getCTM kaster for elementer der ikke vises — fald tilbage til skærmplaceringen
  }
  const r = el.getBoundingClientRect();
  const o = canvas().getSvgContent().getBoundingClientRect();
  const z = canvas().getZoom() || 1;
  return { x: (r.left - o.left) / z, y: (r.top - o.top) / z, w: r.width / z, h: r.height / z };
}

const selectedEls = () => (canvas().getSelectedElements() || []).filter(Boolean);

function rememberBoxes() {
  lastBoxes = new Map(selectedEls().map((el) => [el, boxOf(el)]));
}

function drawGrid() {
  // Gitteret ligger OVENPÅ tegningen som et gennemsigtigt lag: en tegning har ofte et uigennemsigtigt baggrundsrektangel
  // (nye tegninger har), og et lag under tegningen — som SVG-Edits eget gitter — ville aldrig kunne ses.
  const host = document.getElementById('svgcanvas');
  const content = canvas()?.getSvgContent?.();
  if (!host || !content) return;
  let layer = host.querySelector('#hvGrid');
  if (!layer) {
    const NS = 'http://www.w3.org/2000/svg';
    layer = document.createElementNS(NS, 'svg');
    layer.setAttribute('id', 'hvGrid');
    layer.style.cssText = 'position:absolute; pointer-events:none; z-index:50; overflow:hidden;';
    layer.innerHTML = '<defs><pattern id="hvGridMinor" patternUnits="userSpaceOnUse"><path fill="none" stroke="#000" stroke-opacity=".2" stroke-width="1"/></pattern>' +
      '<pattern id="hvGridMajor" patternUnits="userSpaceOnUse"><path fill="none" stroke="#000" stroke-opacity=".4" stroke-width="1"/></pattern></defs>' +
      '<rect width="100%" height="100%" fill="url(#hvGridMinor)"/><rect width="100%" height="100%" fill="url(#hvGridMajor)"/>';
    host.appendChild(layer);
  }
  layer.style.display = guides.grid ? 'block' : 'none';
  if (!guides.grid) return;
  const z = canvas().getZoom() || 1;
  // For tæt et net er ubrugeligt at se på: spring over til hver 2./4./8. linje ved lav zoom
  let minor = guides.step;
  while (minor * z < 6) minor *= 2;
  // laget dækker præcis tegningen (skærmplacering og -størrelse, så det følger zoom og rulning)
  const hr = host.getBoundingClientRect();
  const cr = content.getBoundingClientRect();
  layer.style.left = `${cr.left - hr.left + host.scrollLeft}px`;
  layer.style.top = `${cr.top - hr.top + host.scrollTop}px`;
  layer.setAttribute('width', cr.width);
  layer.setAttribute('height', cr.height);
  const set = (id, size) => {
    const p = layer.querySelector(`#${id}`);
    p.setAttribute('width', size);
    p.setAttribute('height', size);
    p.firstElementChild.setAttribute('d', `M ${size} 0 L 0 0 0 ${size}`);
  };
  set('hvGridMinor', minor * z);
  set('hvGridMajor', minor * z * 5);
}

function applyGuides() {
  const c = canvas();
  const cfg = editor.configObj?.curConfig;
  if (cfg) {
    cfg.gridSnapping = guides.snapGrid;
    cfg.snappingStep = guides.step;
  }
  try {
    c.setConfig({ gridSnapping: guides.snapGrid, snappingStep: guides.step });
  } catch {
    // ældre SVG-Edit uden setConfig på lærredet: curConfig ovenfor er det samme objekt
  }
  drawGrid();
}

/**
 * Fang de valgte elementer: med "fang til gitter" lægges deres øverste venstre hjørne på nærmeste gitterpunkt
 * (ABSOLUT: SVG-Edits egen fang afrunder kun selve flytningen, så et objekt uden for gitteret ender uden for gitteret,
 * og en indsat kopi lander et tilfældigt sted). Med "fang til objekter" og et træk lægges det kant mod kant eller midte
 * mod midte med nærmeste objekt, hvis det er tæt på — det vinder over gitteret i den retning.
 */
function settleSelection(dragged) {
  const sel = selectedEls();
  if (!sel.length || snapping) return;
  const now = unionBox(sel.map(boxOf));
  if (!now) return;
  let dx = 0;
  let dy = 0;
  if (guides.snapGrid) ({ dx, dy } = gridCorrection(now, guides.step));
  if (guides.snapObjects && dragged) {
    const content = canvas().getSvgContent();
    const others = [...content.querySelectorAll('g.layer > *')]
      .filter((el) => el.tagName !== 'title' && !sel.includes(el) && !sel.some((s) => s.contains(el) || el.contains(s)))
      .map(boxOf)
      .filter((b) => b.w > 0 || b.h > 0);
    const hit = snapToObjects(now, others, SNAP_PX / (canvas().getZoom() || 1));
    if (hit.guideX !== null) dx = hit.dx;
    if (hit.guideY !== null) dy = hit.dy;
  }
  if (dx || dy) {
    snapping = true;
    try {
      canvas().moveSelectedElements(dx, dy, true);
    } finally {
      snapping = false;
    }
  }
  rememberBoxes();
}

/** Efter et museslip: var det et træk (samme størrelse, ny placering), så fang. */
function settleAfterMouseUp() {
  const sel = selectedEls();
  const now = unionBox(sel.map(boxOf));
  const before = unionBox(sel.map((el) => lastBoxes.get(el)));
  if (sel.length && sel.every((el) => lastBoxes.has(el)) && isDrag(before, now)) settleSelection(true);
  else rememberBoxes();
}

let selectionListener = null;
let insertCount = 0;
let changeListener = null;

function canvas() {
  return editor.svgCanvas;
}

/** Vent til SVG-Edit er helt klar (init er asynkron). */
function whenReady() {
  return new Promise((resolve) => {
    const check = () => (editor.svgCanvas && editor.svgCanvas.getSvgString ? resolve() : setTimeout(check, 50));
    check();
  });
}

function hookEvents() {
  const c = canvas();
  // bind() returnerer editorens egen handler — kald den først, så editoren virker uændret.
  const prevSelected = c.bind('selected', (win, elems) => {
    if (prevSelected) prevSelected(win, elems);
    rememberBoxes();
    if (selectionListener) selectionListener(currentSelection());
  });
  const prevChanged = c.bind('changed', (win, elems) => {
    if (prevChanged) prevChanged(win, elems);
    if (changeListener) changeListener();
    if (selectionListener) selectionListener(currentSelection());
  });
  // SVG-Edit sender ikke 'changed' efter en flytning med musen, så vi lytter selv på museknappen (efter editorens egen
  // håndtering): ved nedtryk huskes de valgte elementers placering, ved slip fanges der — hvis det var et træk.
  document.addEventListener('mousedown', () => setTimeout(rememberBoxes, 0), true);
  document.addEventListener('mouseup', () => setTimeout(() => { if (!snapping) settleAfterMouseUp(); }, 0), true);
  // Indsæt og dupliker (Ctrl+V, Ctrl+D): kopien lægges på gitteret, så den passer sammen med originalen
  for (const name of ['pasteElements', 'cloneSelectedElements']) {
    const original = c[name];
    if (typeof original !== 'function') continue;
    c[name] = function wrapped(...args) {
      const result = original.apply(this, args);
      const small = name === 'cloneSelectedElements' && Math.max(Math.abs(args[0] ?? 0), Math.abs(args[1] ?? 0)) < 5;   // finjustering med tasterne
      if (!small) setTimeout(() => settleSelection(false), 0);
      return result;
    };
  }
  const prevZoomed = c.bind('zoomed', (...args) => {
    if (prevZoomed) prevZoomed(...args);
    drawGrid();
  });
  drawGrid();
}

function currentSelection() {
  const elems = (canvas().getSelectedElements() || []).filter(Boolean);
  return elems.map((el) => ({
    id: el.id || '', tag: el.tagName.toLowerCase(), interactive: el.hasAttribute('data-hv-auto'),
    name: el.getAttribute('data-hv-name') || '', desc: el.getAttribute('data-hv-desc') || '',
    children: [...el.children].filter((c) => !RESERVED.has(c.tagName.toLowerCase())).length,
  }));
}

function idExists(id) {
  return !!canvas().getSvgContent().querySelector(`#${CSS.escape(id)}`);
}

function uniqueId(base) {
  const clean = base.replace(/[^A-Za-z0-9_-]/g, '_') || 'symbol';
  if (!idExists(clean)) return clean;
  for (let i = 2; ; i++) if (!idExists(`${clean}_${i}`)) return `${clean}_${i}`;
}

/** Et navn der ikke er i brug: "Pumpe", "Pumpe 2", … */
function uniqueNameIn(base) {
  const used = new Set(Array.from(canvas().getSvgContent().querySelectorAll('[data-hv-name]')).map((el) => el.getAttribute('data-hv-name')));
  if (!used.has(base)) return base;
  for (let i = 2; ; i++) if (!used.has(`${base} ${i}`)) return `${base} ${i}`;
}

/** Et bibliotekssymbol (SVG-fragment med ét rodelement) som et element med unikke id'er — endnu ikke sat ind. */
function buildSymbolNode(fragment, baseId, wantedId) {
  const parsed = new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${fragment}</svg>`, 'image/svg+xml');
  const src = parsed.documentElement.firstElementChild;
  if (!src) return null;
  const node = document.importNode(src, true);
  node.setAttribute('id', uniqueId(wantedId || baseId));
  // Bibliotekstypen og delenes egne navne gemmes, så symbol-guiden kender symbolet og dets dele
  // (id'erne nedenfor kan få et løbenummer, så delens navn kan ikke udledes sikkert af id'et)
  node.setAttribute('data-hv-type', String(baseId).toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 40));
  // Børn får unikke id'er så flere kopier af samme symbol ikke kolliderer
  node.querySelectorAll('[id]').forEach((el) => {
    el.setAttribute('data-hv-pid', el.id);
    el.setAttribute('id', uniqueId(`${node.id}_${el.id}`));
  });
  return node;
}

const TAGS_OF_INTEREST = ['rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path', 'text', 'g', 'image'];
const RESERVED = new Set(['title', 'defs', 'desc', 'metadata']);

/** Tegningens koordinater for elementet: geometriens boks og matrix (uden zoom) — størrelse langs egne akser, drejning og midte. */
function geometryOf(el) {
  const M = toDocMatrix(el);
  const bb = el.getBBox();
  if (!M || !Number.isFinite(bb.x)) return null;
  const cxl = bb.x + bb.width / 2;
  const cyl = bb.y + bb.height / 2;
  return {
    w: bb.width * Math.hypot(M.a, M.b),
    h: bb.height * Math.hypot(M.c, M.d),
    angle: (Math.atan2(M.b, M.a) * 180) / Math.PI,
    cx: M.a * cxl + M.c * cyl + M.e,
    cy: M.b * cxl + M.d * cyl + M.f,
    box: boxOf(el),
  };
}

/** Tæl figurerne i et element (inkl. det selv): { rect: 1, path: 2, … }. */
function countShapes(el) {
  const counts = {};
  for (const e of [el, ...el.querySelectorAll('*')]) {
    const t = e.tagName.toLowerCase();
    if (TAGS_OF_INTEREST.includes(t)) counts[t] = (counts[t] || 0) + 1;
  }
  return counts;
}

/** Det øverste element under laget som indeholder `el` (så et nyt symbol kan lægges lige efter). */
function topLevelOf(el) {
  let cur = el;
  while (cur.parentNode && !(cur.parentNode.tagName === 'g' && cur.parentNode.classList.contains('layer'))) cur = cur.parentNode;
  return cur;
}

/** Tekster der ligger inde i elementets boks (midten), både inde i og ved siden af det. */
function textsWithin(el, geom) {
  const parent = el.parentNode;
  if (!parent || !geom) return [];
  const inside = (b) => b && b.x + b.w / 2 >= geom.box.x && b.x + b.w / 2 <= geom.box.x + geom.box.w && b.y + b.h / 2 >= geom.box.y && b.y + b.h / 2 <= geom.box.y + geom.box.h;
  const candidates = [...el.querySelectorAll('text'), ...[...parent.children].filter((c) => c !== el && c.tagName.toLowerCase() === 'text')];
  return candidates.map((t) => ({ el: t, text: (t.textContent || '').replace(/\s+/g, ' ').trim() })).filter((t) => t.text && inside(boxOf(t.el)));
}

/** Retningen (grader i tegningen) som delens ENE trekant peger: ligebenet trekant i en sti/polygon. Null hvis der ikke er præcis én. */
function apexAngleOf(el) {
  const found = [];
  for (const e of [el, ...el.querySelectorAll('path, polygon')]) {
    const tag = e.tagName.toLowerCase();
    let verts = null;
    if (tag === 'path') verts = pathVertices(e.getAttribute('d'));
    else if (tag === 'polygon') verts = (e.getAttribute('points') || '').trim().split(/[\s,]+/).map(Number).reduce((acc, v, i, all) => (i % 2 ? acc : [...acc, [v, all[i + 1]]]), []);
    const tri = verts && verts.length === 3 ? triangleApex(verts) : null;
    if (tri) found.push({ e, tri });
  }
  if (found.length !== 1) return null;
  const M = toDocMatrix(found[0].e);
  return M ? directionAngle(found[0].tri.vector, M) : null;
}

/** Alle id'er der forsvinder, når elementet erstattes: det selv, dets underelementer og tekster der ligger inde i det. */
function affectedIds(el, geom) {
  const own = [el.id, ...[...el.querySelectorAll('[id]')].map((e) => e.id)];
  const texts = textsWithin(el, geom).map((t) => t.el.id);
  return [...new Set([...own, ...texts])].filter(Boolean);
}

/** Andre elementer under samme forælder med samme opbygning og omtrent samme størrelse (til "erstat alle lignende"). */
function similarTo(el, any = false) {
  const parent = el.parentNode;
  const g0 = geometryOf(el);
  if (!parent || !g0) return [];
  const key = (c) => JSON.stringify(Object.entries(c).sort());
  const k0 = key(countShapes(el));
  const near = (a, b) => Math.abs(a - b) <= Math.max(2, 0.12 * Math.max(a, b));
  return [...parent.children].filter((o) => {
    if (o === el || RESERVED.has(o.tagName.toLowerCase()) || o.tagName.toLowerCase() !== el.tagName.toLowerCase()) return false;
    if (o.hasAttribute('data-hv-type') || key(countShapes(o)) !== k0) return false;
    const g = geometryOf(o);
    if (!g || (o.getAttribute('rx') ?? '') !== (el.getAttribute('rx') ?? '') || (o.getAttribute('fill') ?? '') !== (el.getAttribute('fill') ?? '')) return false;
    if ((o.getAttribute('stroke') ?? '') !== (el.getAttribute('stroke') ?? '') || (o.getAttribute('stroke-width') ?? '') !== (el.getAttribute('stroke-width') ?? '')) return false;
    if (!any) return near(Math.abs(g.angle), Math.abs(g0.angle)) && near(g.w, g0.w) && near(g.h, g0.h);
    // "Alle af samme slags": drejning er ligegyldig (hver beholder sin egen), og størrelsen må afvige — men formen skal ligne:
    // omtrent samme højde og samme proportioner (en etiket med lang tekst er bredere, men en tynd linje er ikke en etiket)
    const ratio = (a, b) => (Math.max(a, b) > 0 ? Math.min(a, b) / Math.max(a, b) : 1);
    const lo = Math.min(g.w, g.h), hi = Math.max(g.w, g.h), lo0 = Math.min(g0.w, g0.h), hi0 = Math.max(g0.w, g0.h);
    return ratio(lo, lo0) >= 0.65 && ratio(hi / (lo || 1), hi0 / (lo0 || 1)) >= 0.38;
  });
}

window.scada = {
  ready: whenReady().then(hookEvents),

  load(svg) {
    const ok = editor.loadFromString(svg, { noAlert: true });
    canvas().undoMgr.resetUndoStack();
    drawGrid();
    return ok;
  },

  newDrawing(width, height) {
    editor.loadFromString(
      `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
        `<g class="layer"><title>Lag 1</title><rect id="baggrund" x="0" y="0" width="${width}" height="${height}" fill="#d9d9d9"/></g></svg>`,
      { noAlert: true },
    );
    canvas().undoMgr.resetUndoStack();
    drawGrid();
  },

  getSvg() {
    canvas().clearSelection();
    // Tomme navne/forklaringer (felterne tømt i Tegn) gemmes ikke
    canvas().getSvgContent().querySelectorAll('[data-hv-name=""],[data-hv-desc=""]').forEach((el) => {
      if (el.getAttribute('data-hv-name') === '') el.removeAttribute('data-hv-name');
      if (el.getAttribute('data-hv-desc') === '') el.removeAttribute('data-hv-desc');
    });
    return canvas().getSvgString();
  },

  /** Gitter, fang til gitter (trin i tegningens enheder) og fang til objekter — sættes fra Tegn-siden. */
  setGuides(opts) {
    guides.grid = !!opts.grid;
    guides.snapGrid = !!opts.snapGrid;
    guides.snapObjects = !!opts.snapObjects;
    const step = Number(opts.step);
    guides.step = Number.isFinite(step) && step >= 1 ? step : 10;
    applyGuides();
  },

  hasUndo() {
    return canvas().undoMgr.getUndoStackSize() > 0;
  },

  onSelection(fn) {
    selectionListener = fn;
  },

  onChange(fn) {
    changeListener = fn;
  },

  /** Sæt id på det valgte element (med fortryd). Returnerer fejltekst eller ''. */
  setSelectedId(id) {
    const elems = canvas().getSelectedElements().filter(Boolean);
    if (elems.length !== 1) return 'Vælg præcis ét element';
    if (!/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(id)) return 'Ugyldigt id';
    if (elems[0].id !== id && idExists(id)) return `Id'et "${id}" bruges allerede af et andet element`;
    canvas().changeSelectedAttribute('id', id);
    if (selectionListener) selectionListener(currentSelection());
    return '';
  },

  /** Sæt symbolets navn eller forklaring på det valgte element (med fortryd). Returnerer fejltekst eller ''. */
  setSelectedText(attr, value) {
    const limit = { 'data-hv-name': 60, 'data-hv-desc': 500 }[attr];
    if (!limit) return 'Ukendt felt';
    const elems = canvas().getSelectedElements().filter(Boolean);
    if (elems.length !== 1) return 'Vælg præcis ét element';
    const text = String(value ?? '').replace(/\s+/g, ' ').trim();
    if (text.length > limit) return `Højst ${limit} tegn`;
    // Navnet er symbolets identitet i konfigurationen under Bindinger — det skal være unikt
    if (attr === 'data-hv-name' && text && Array.from(canvas().getSvgContent().querySelectorAll('[data-hv-name]'))
      .some((el) => el !== elems[0] && el.getAttribute('data-hv-name') === text)) {
      return `Navnet "${text}" bruges allerede af et andet symbol — vælg et andet`;
    }
    if ((elems[0].getAttribute(attr) || '') === text) return '';
    canvas().changeSelectedAttribute(attr, text);
    if (selectionListener) selectionListener(currentSelection());
    return '';
  },

  /**
   * Beskrivelse af det valgte element til "Erstat med symbol": opbygning, størrelse, drejning, farver, tekster inde i
   * det, andre lignende elementer og alle id'er (til at finde bindinger der ville gå tabt).
   */
  describeSelection() {
    const sel = selectedEls();
    if (sel.length !== 1) return null;
    const el = sel[0];
    const g = geometryOf(el);
    if (!g) return null;
    const children = [...el.children].filter((c) => !RESERVED.has(c.tagName.toLowerCase())).length;
    return {
      id: el.id || '',
      tag: el.tagName.toLowerCase(),
      counts: countShapes(el),
      children,
      w: Math.round(g.w * 10) / 10,
      h: Math.round(g.h * 10) / 10,
      angle: Math.round(g.angle * 10) / 10,
      fill: el.getAttribute('fill') || '',
      stroke: el.getAttribute('stroke') || '',
      strokeWidth: parseFloat(el.getAttribute('stroke-width') || '0') || 0,
      rx: parseFloat(el.getAttribute('rx') || '0') || 0,
      name: el.getAttribute('data-hv-name') || '',
      symbolType: el.getAttribute('data-hv-type') || '',
      // id'er der forsvinder ved en erstatning: delen, dens underelementer og de tekster der ligger inde i den
      apexAngle: apexAngleOf(el),
      ids: affectedIds(el, g),
      texts: textsWithin(el, g).map((t) => t.text),
      similar: similarTo(el).length,
      similarAny: similarTo(el, true).length,
      similarGroups: similarTo(el, true).map((o) => affectedIds(o, geometryOf(o))),   // pr. lignende del: de id'er der forsvinder
    };
  },

  /**
   * Erstat det valgte element (og evt. alle lignende) med et bibliotekssymbol: samme midte, størrelse og drejning, i ét
   * fortryd-trin. opts: { name, keepId, stretch, useText, similar }. → { ok, replaced, ids } eller { error }.
   */
  replaceSelected(fragment, baseId, opts = {}) {
    const c = canvas();
    const sel = selectedEls();
    if (sel.length !== 1) return { error: 'Vælg præcis ét element' };
    const targets = [sel[0], ...(opts.similar ? similarTo(sel[0], opts.similar === 'any') : [])];
    const batch = new c.history.BatchCommand(`Erstat med symbol (${targets.length})`);
    c.clearSelection();
    const created = [];
    const protect = new Set(opts.protectIds || []);
    let skipped = 0;
    for (const [index, old] of targets.entries()) {
      const g = geometryOf(old);
      if (!g) continue;
      // Lignende dele med bindinger (på dem selv, deres dele eller deres tekster) røres ikke — de erstattes enkeltvis
      if (index > 0 && affectedIds(old, g).some((id) => protect.has(id))) {
        skipped++;
        continue;
      }
      const parent = old.parentNode;
      const anchor = topLevelOf(old);
      const layer = anchor.parentNode;
      const texts = opts.useText ? textsWithin(old, g) : [];
      const oldId = old.id;
      // Retningen måles FØR delen fjernes (en frakoblet del har ingen matrix i tegningen)
      const apex = opts.apexNative !== undefined ? apexAngleOf(old) : null;
      // 1) fjern det gamle (og de tekster det overtager) — i samme fortryd-trin
      const removeTracked = (node) => {
        const next = node.nextSibling;
        const par = node.parentNode;
        batch.addSubCommand(new c.history.RemoveElementCommand(node, next, par));
        par.removeChild(node);
      };
      const anchorNext = anchor.nextSibling;
      for (const t of texts) if (t.el.parentNode === parent && !old.contains(t.el)) removeTracked(t.el);
      const insertBeforeNode = anchor === old ? old.nextSibling : anchorNext;
      removeTracked(old);
      // 2) nyt symbol (bevarer id'et hvis ønsket, så bindinger på elementet følger med)
      const node = buildSymbolNode(fragment, baseId, opts.keepId && oldId ? oldId : undefined);
      if (!node) continue;
      layer.insertBefore(node, insertBeforeNode && insertBeforeNode.parentNode === layer ? insertBeforeNode : null);
      const nb = node.getBBox();
      const sx0 = nb.width > 0 ? g.w / nb.width : 1;
      const sy0 = nb.height > 0 ? g.h / nb.height : 1;
      const sx = opts.stretch ? sx0 : Math.min(sx0, sy0);
      const sy = opts.stretch ? sy0 : Math.min(sx0, sy0);
      const tx = g.cx - sx * (nb.x + nb.width / 2);
      const ty = g.cy - sy * (nb.y + nb.height / 2);
      // Retningsgivende symboler (pumpe): drej, så symbolets trekant peger samme vej som den tegnede; ellers delens egen drejning
      const angle = apex !== null ? turnTo(apex, opts.apexNative) : g.angle;
      const rot = Math.abs(angle) > 0.01 ? `rotate(${angle.toFixed(3)} ${g.cx.toFixed(3)} ${g.cy.toFixed(3)}) ` : '';
      node.setAttribute('transform', `${rot}translate(${tx.toFixed(3)} ${ty.toFixed(3)}) scale(${sx.toFixed(5)} ${sy.toFixed(5)})`);
      if (texts.length) {
        const slot = node.querySelector('[data-hv-pid="tekst"]');
        if (slot) slot.textContent = texts[0].text;
      }
      // Det valgte element får det indtastede navn; de øvrige "<symbol> <deres egen tekst>" (ellers løbenumre)
      if (opts.name) {
        const own = index === 0 ? opts.name : `${opts.namePrefix || opts.name}${texts[0] ? ` ${texts[0].text}` : ''}`;
        node.setAttribute('data-hv-name', uniqueNameIn(own));
      }
      batch.addSubCommand(new c.history.InsertElementCommand(node));
      created.push(node);
    }
    c.undoMgr.addCommandToHistory(batch);
    c.clearSelection();
    if (created.length) c.addToSelection([created[0]]);
    lastBoxes = new Map(selectedEls().map((el) => [el, boxOf(el)]));
    if (changeListener) changeListener();
    if (selectionListener) selectionListener(currentSelection());
    return created.length ? { ok: true, replaced: created.length, skipped, ids: created.map((n) => n.id) } : { error: 'Intet blev erstattet' };
  },

  /** Vælg elementet med dette id (til test og til at hoppe til et element). Returnerer false hvis det ikke findes. */
  selectById(id) {
    const el = canvas().getSvgContent().querySelector(`#${CSS.escape(id)}`);
    if (!el) return false;
    canvas().clearSelection();
    canvas().addToSelection([el]);
    return true;
  },

  /** Opløs den valgte gruppe, så dens dele kan vælges enkeltvis. Returnerer fejltekst eller ''. */
  ungroupSelected() {
    const sel = selectedEls();
    if (sel.length !== 1 || sel[0].tagName.toLowerCase() !== 'g') return 'Vælg en gruppe';
    if (sel[0].hasAttribute('data-hv-type')) return 'Et symbol kan ikke opløses — det mister sin opsætning';
    canvas().ungroupSelectedElement();
    if (changeListener) changeListener();
    if (selectionListener) selectionListener(currentSelection());
    return '';
  },

  /** Et navn der ikke er i brug: "Vippekontakt", "Vippekontakt 2", … */
  uniqueName(base) {
    return uniqueNameIn(base);
  },

  /** Indsæt et symbol (SVG-fragment med ét rodelement) midt i den synlige del, valgt og med fortryd. */
  insertSymbol(fragment, baseId) {
    const c = canvas();
    const node = buildSymbolNode(fragment, baseId);
    if (!node) return '';
    const res = c.getResolution();
    const step = (insertCount++ % 6) * 30; // forskyd hvert nyt symbol, så de ikke ligger oven i hinanden
    node.setAttribute('transform', `translate(${Math.round(res.w / 2 - 40 + step)} ${Math.round(res.h / 2 - 40 + step)})`);
    c.getCurrentDrawing().getCurrentLayer().appendChild(node);
    c.undoMgr.addCommandToHistory(new c.history.InsertElementCommand(node));
    c.clearSelection();
    c.addToSelection([node]);
    settleSelection(false);   // et nyt symbol lægges på gitteret
    if (changeListener) changeListener();
    return node.id;
  },
};
