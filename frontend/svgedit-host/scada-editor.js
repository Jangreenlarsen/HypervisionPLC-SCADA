// Værtsside for SVG-Edit inde i SCADA'en (indlæses i en iframe fra samme origin).
// Forældresiden (DrawEditor.svelte) bruger `window.scada` nedenfor.
import Editor from './Editor.js';

const editor = new Editor(document.getElementById('container'));
editor.setConfig({
  lang: 'da',
  imgPath: './images',
  extPath: './extensions',
  noDefaultExtensions: true,
  // Kun udvidelser der arbejder lokalt — ingen browser-lagring eller filåbning udenom SCADA'en
  extensions: ['ext-connector', 'ext-eyedropper', 'ext-grid', 'ext-markers', 'ext-panning', 'ext-polystar', 'ext-shapes'],
  noStorageOnLoad: true,
  forceStorage: false,
  emptyStorageOnDecline: true,
  showRulers: true,
  dimensions: [1200, 700],
  allowInitialUserOverride: false,
});
editor.init();

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
    if (selectionListener) selectionListener(currentSelection());
  });
  const prevChanged = c.bind('changed', (win, elems) => {
    if (prevChanged) prevChanged(win, elems);
    if (changeListener) changeListener();
    if (selectionListener) selectionListener(currentSelection());
  });
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
    return ok;
  },

  newDrawing(width, height) {
    editor.loadFromString(
      `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
        `<g class="layer"><title>Lag 1</title><rect id="baggrund" x="0" y="0" width="${width}" height="${height}" fill="#d9d9d9"/></g></svg>`,
      { noAlert: true },
    );
    canvas().undoMgr.resetUndoStack();
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
    // Børn får unikke id'er så flere kopier af samme symbol ikke kolliderer
    node.querySelectorAll('[id]').forEach((el) => el.setAttribute('id', uniqueId(`${node.id}_${el.id}`)));
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
