// Værtsside for SVG-Edit inde i SCADA'en (indlæses i en iframe fra samme origin).
// Forældresiden (DrawEditor.svelte) bruger `window.scada` nedenfor.
import Editor from './Editor.js';
import { isDrag, snapToObjects, unionBox } from './snap.js';

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

/** Elementets boks i tegningens koordinater (inkl. transform), ud fra skærmplaceringen og zoom. */
function boxOf(el) {
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

/** Efter en flytning: ligg kant mod kant (eller midte mod midte) med nærmeste objekt, hvis det er tæt på. */
function snapSelectionToObjects() {
  const sel = selectedEls();
  if (!sel.length) return;
  const now = unionBox(sel.map(boxOf));
  const before = unionBox(sel.map((el) => lastBoxes.get(el)));
  const known = sel.every((el) => lastBoxes.has(el));
  if (guides.snapObjects && known && isDrag(before, now)) {
    const content = canvas().getSvgContent();
    const others = [...content.querySelectorAll('g.layer > *')]
      .filter((el) => el.tagName !== 'title' && !sel.includes(el) && !sel.some((s) => s.contains(el) || el.contains(s)))
      .map(boxOf)
      .filter((b) => b.w > 0 || b.h > 0);
    const hit = snapToObjects(now, others, SNAP_PX / (canvas().getZoom() || 1));
    if ((hit.dx || hit.dy) && !snapping) {
      snapping = true;
      try {
        canvas().moveSelectedElements(hit.dx, hit.dy, true);
      } finally {
        snapping = false;
      }
    }
  }
  lastBoxes = new Map(selectedEls().map((el) => [el, boxOf(el)]));
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
  document.addEventListener('mouseup', () => setTimeout(() => { if (!snapping) snapSelectionToObjects(); }, 0), true);
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

  /** Et navn der ikke er i brug: "Vippekontakt", "Vippekontakt 2", … */
  uniqueName(base) {
    const used = new Set(Array.from(canvas().getSvgContent().querySelectorAll('[data-hv-name]')).map((el) => el.getAttribute('data-hv-name')));
    if (!used.has(base)) return base;
    for (let i = 2; ; i++) if (!used.has(`${base} ${i}`)) return `${base} ${i}`;
  },

  /** Indsæt et symbol (SVG-fragment med ét rodelement) midt i den synlige del, valgt og med fortryd. */
  insertSymbol(fragment, baseId) {
    const c = canvas();
    const parsed = new DOMParser().parseFromString(
      `<svg xmlns="http://www.w3.org/2000/svg">${fragment}</svg>`, 'image/svg+xml');
    const src = parsed.documentElement.firstElementChild;
    if (!src) return '';
    const node = document.importNode(src, true);
    node.setAttribute('id', uniqueId(baseId));
    // Bibliotekstypen og delenes egne navne gemmes, så symbol-guiden kender symbolet og dets dele
    // (id'erne nedenfor kan få et løbenummer, så delens navn kan ikke udledes sikkert af id'et)
    node.setAttribute('data-hv-type', String(baseId).toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 40));
    // Børn får unikke id'er så flere kopier af samme symbol ikke kolliderer
    node.querySelectorAll('[id]').forEach((el) => {
      el.setAttribute('data-hv-pid', el.id);
      el.setAttribute('id', uniqueId(`${node.id}_${el.id}`));
    });
    const res = c.getResolution();
    const step = (insertCount++ % 6) * 30; // forskyd hvert nyt symbol, så de ikke ligger oven i hinanden
    node.setAttribute('transform', `translate(${Math.round(res.w / 2 - 40 + step)} ${Math.round(res.h / 2 - 40 + step)})`);
    c.getCurrentDrawing().getCurrentLayer().appendChild(node);
    c.undoMgr.addCommandToHistory(new c.history.InsertElementCommand(node));
    c.clearSelection();
    c.addToSelection([node]);
    if (changeListener) changeListener();
    return node.id;
  },
};
