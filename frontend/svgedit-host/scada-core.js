// Kernen i Tegn: alt vores eget oven på SVG-Edits tegnemotor (`@svgedit/svgcanvas`) — gitter, fang, id'er, navne,
// symboler og API'et som Tegn-siden bruger. Kender ikke SVG-Edits brugerflade: værten giver lærredet og de få ting,
// der afhænger af den omgivende side (genindlæsning, lærredets størrelse, laget til gitteret).
import {
  axisAngle, centroid, directionAngle, gridCorrection, identityMatrix, invertMatrix, isDrag, fieldResize, multiplyMatrix, pathVertices, recenterOffset, rotationCenter, snapToObjects, transformBox, triangleApex, turnAxis, turnTo, unionBox,
} from './snap.js';
import { collectColors, recolorAttrs } from './colors.js';
import { duplicateNames, nextFreeName, numberedNames, uniqueRenames } from './names.js';
import { boxMapping, distribute as distributeBoxes, editBox, round2 } from './edit.js';
import { PIPE_STYLE, connect, formatRef, fromFrac, moveEnd, nearest, orthoLeg, parseRef, pathD, portsFrom, simplify, toFrac } from './pipes.js';

/**
 * @param {{ canvas(): any, loadFromString(svg: string): unknown, updateCanvas(): void, gridHost(): HTMLElement | null,
 *   curConfig?(): any, decorate?(): void }} host
 */
export function createScada(host) {
  const life = new AbortController();   // lyttere på document fjernes igen med dispose()

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

  /**
   * Tegningens størrelse efter fortryd/gentag (v0.92.0): SVG-Edit opdaterer kun sin interne størrelse (contentW/H), når
   * trinnet er én ændring af rod-elementet — ikke i et samlet trin (fx "Tilpas til indholdet", eller SVG-Edits egen
   * størrelsesændring). Så sætter vi den ud fra viewBox, ellers springer tegningen tilbage til den nye størrelse.
   */
  function syncContentSize() {
    const c = canvas();
    const vb = (c?.getSvgContent?.()?.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || !(vb[2] > 0) || !(vb[3] > 0)) return;
    if (vb[2] === c.contentW && vb[3] === c.contentH) return;
    c.contentW = vb[2];
    c.contentH = vb[3];
    host.updateCanvas();
    drawGrid();
  }

  /**
   * Tegningens flade på skærmen. Ikke content.getBoundingClientRect(): for et indre <svg> er det indholdets yderkanter,
   * så gitteret blev for lille og forskudt i tegninger uden et baggrundsrektangel over det hele. Fladen er yderste
   * svg (lærredet) + tegningens x/y og bredde/højde (allerede ganget med zoom).
   */
  function contentRect(content) {
    const root = canvas().getSvgRoot?.() ?? content.ownerSVGElement;
    const rr = root.getBoundingClientRect();
    const num = (a) => Number(content.getAttribute(a)) || 0;
    return { left: rr.left + num('x'), top: rr.top + num('y'), width: num('width'), height: num('height') };
  }

  function drawGrid() {
    // Gitteret ligger OVENPÅ tegningen som et gennemsigtigt lag: en tegning har ofte et uigennemsigtigt baggrundsrektangel
    // (nye tegninger har), og et lag under tegningen — som SVG-Edits eget gitter — ville aldrig kunne ses.
    const gridHost = host.gridHost();
    const content = canvas()?.getSvgContent?.();
    if (!gridHost || !content) return;
    let layer = gridHost.querySelector('#hvGrid');
    if (!layer) {
      const NS = 'http://www.w3.org/2000/svg';
      layer = document.createElementNS(NS, 'svg');
      layer.setAttribute('id', 'hvGrid');
      layer.style.cssText = 'position:absolute; pointer-events:none; z-index:50; overflow:hidden;';
      layer.innerHTML = '<defs><pattern id="hvGridMinor" patternUnits="userSpaceOnUse"><path fill="none" stroke="#000" stroke-opacity=".2" stroke-width="1"/></pattern>' +
        '<pattern id="hvGridMajor" patternUnits="userSpaceOnUse"><path fill="none" stroke="#000" stroke-opacity=".4" stroke-width="1"/></pattern></defs>' +
        '<rect width="100%" height="100%" fill="url(#hvGridMinor)"/><rect width="100%" height="100%" fill="url(#hvGridMajor)"/>';
      gridHost.appendChild(layer);
    }
    layer.style.display = guides.grid ? 'block' : 'none';
    if (!guides.grid) return;
    const z = canvas().getZoom() || 1;
    // For tæt et net er ubrugeligt at se på: spring over til hver 2./4./8. linje ved lav zoom
    let minor = guides.step;
    while (minor * z < 6) minor *= 2;
    // laget dækker præcis tegningen (skærmplacering og -størrelse, så det følger zoom og rulning)
    const hr = gridHost.getBoundingClientRect();
    const cr = contentRect(content);
    layer.style.left = `${cr.left - hr.left + gridHost.scrollLeft}px`;
    layer.style.top = `${cr.top - hr.top + gridHost.scrollTop}px`;
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
    const cfg = host.curConfig?.();
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

  /** Efter et museslip: var det et træk (samme størrelse, ny placering), så fang; var det en strækning, så ryd op i drejede grupper. */
  function settleAfterMouseUp() {
    const sel = selectedEls();
    const now = unionBox(sel.map(boxOf));
    const before = unionBox(sel.map((el) => lastBoxes.get(el)));
    if (sel.length && sel.every((el) => lastBoxes.has(el)) && isDrag(before, now)) settleSelection(true);
    else {
      const resized = before && now && (Math.abs(before.w - now.w) > 0.5 || Math.abs(before.h - now.h) > 0.5);
      if (resized) {
        normalizeRotatedGroups(sel);
        normalizeFields(sel);
      }
      rememberBoxes();
    }
  }

  /**
   * En DREJET gruppe (fx et drejet biblioteksrør), der strækkes, får af SVG-Edit stablet "translate · scale · translate" efter
   * sin rotate — og næste strækning regnes så ud fra den ustrakte størrelse, så den vokser for meget (BUGS.md v0.65.1).
   * Ryd op: læg strækningen ned i gruppens dele, og lad gruppen kun dreje om sin (nye) midte. Tegningen ser ens ud;
   * oprydningen er sit eget fortryd-trin efter strækningen.
   */
  /** Felt-symboler (flade + tekst), hvor en strækning skal give mere plads til tekst — ikke strakt tekst (v0.77.0). */
  const FIELD_TYPES = new Set(['statusfelt', 'vaerdi', 'automanuel']);

  /**
   * Efter en strækning af et felt-symbol: læg strækningen ned i fladen (ny bredde/højde) og flyt teksten, men behold dens
   * skriftstørrelse (fieldResize). Kun for ikke-drejede felter, hvor delene ingen egen transform har. Ét fortryd-trin.
   */
  function normalizeFields(sel) {
    const c = canvas();
    const svg = c.getSvgRoot();
    const batch = new c.history.BatchCommand('Felt: plads til mere tekst');
    const r = (v) => +v.toFixed(3);
    for (const g of sel) {
      if (g.tagName !== 'g' || !FIELD_TYPES.has(g.getAttribute('data-hv-type') || '')) continue;
      const kids = [...g.children].filter((k) => !RESERVED.has(k.tagName.toLowerCase()));
      const rects = kids.filter((k) => k.tagName === 'rect');
      const texts = kids.filter((k) => k.tagName === 'text');
      if (!rects.length || rects.length + texts.length !== kids.length || kids.some((k) => k.getAttribute('transform'))) continue;
      // gruppens samlede matrix — uden at ændre dens transform (consolidate() ville skrive den om, også hvis vi springer over)
      const tl = g.transform.baseVal;
      let m = svg.createSVGMatrix();
      for (let i = 0; i < tl.numberOfItems; i++) m = m.multiply(tl.getItem(i).matrix);
      if (Math.abs(m.b) > 1e-9 || Math.abs(m.c) > 1e-9) continue;          // drejet/skævt: rør det ikke
      const sx = m.a, sy = m.d;
      if (Math.abs(sx - 1) < 1e-6 && Math.abs(sy - 1) < 1e-6) continue;
      const num = (el, a) => parseFloat(el.getAttribute(a) || '0') || 0;
      const res = fieldResize(
        rects.map((el) => ({ x: num(el, 'x'), y: num(el, 'y'), w: num(el, 'width'), h: num(el, 'height'), rx: num(el, 'rx') })),
        texts.map((el) => ({ x: num(el, 'x'), y: num(el, 'y'), anchor: el.getAttribute('text-anchor') || 'start' })),
        sx, sy);
      const oldG = g.getAttribute('transform');
      const change = (el, attrs) => {
        const old = {};
        for (const k of Object.keys(attrs)) { old[k] = el.getAttribute(k); el.setAttribute(k, String(attrs[k])); }
        batch.addSubCommand(new c.history.ChangeElementCommand(el, old));
      };
      rects.forEach((el, i) => {
        const n = res.rects[i];
        change(el, { x: r(n.x), y: r(n.y), width: r(n.w), height: r(n.h), ...(el.hasAttribute('rx') ? { rx: r(n.rx) } : {}) });
      });
      texts.forEach((el, i) => change(el, { x: r(res.texts[i].x), y: r(res.texts[i].y) }));
      g.setAttribute('transform', `translate(${r(m.e)} ${r(m.f)})`);
      batch.addSubCommand(new c.history.ChangeElementCommand(g, { transform: oldG }));
      c.selectorManager.requestSelector(g).resize();
    }
    if (!batch.isEmpty()) {
      c.undoMgr.addCommandToHistory(batch);
      if (changeListener) changeListener();
    }
  }

  function normalizeRotatedGroups(sel) {
    const c = canvas();
    const svg = c.getSvgRoot();
    const batch = new c.history.BatchCommand('Ryd op i drejet gruppe');
    const fmt = (m) => `matrix(${[m.a, m.b, m.c, m.d, m.e, m.f].map((v) => +v.toFixed(6)).join(' ')})`;
    for (const g of sel) {
      if (g.tagName !== 'g') continue;
      const tl = g.transform?.baseVal;
      if (!tl || tl.numberOfItems < 2) continue;
      const first = tl.getItem(0);
      if (first.type !== SVGTransform.SVG_TRANSFORM_ROTATE || !first.angle) continue;
      const c0 = rotationCenter(first.matrix);
      if (!c0) continue;
      const angle = first.angle;
      let M = svg.createSVGMatrix();
      for (let i = 1; i < tl.numberOfItems; i++) M = M.multiply(tl.getItem(i).matrix);
      const kids = [...g.children].filter((k) => !RESERVED.has(k.tagName.toLowerCase()) && k.transform);
      const oldKids = new Map(kids.map((k) => [k, k.getAttribute('transform')]));
      const oldG = g.getAttribute('transform');
      const own = (k) => k.transform.baseVal.consolidate()?.matrix ?? svg.createSVGMatrix();
      for (const k of kids) k.setAttribute('transform', fmt(M.multiply(own(k))));
      const bb = g.getBBox();   // i gruppens egne koordinater, med delenes nye transform
      const c1 = [bb.x + bb.width / 2, bb.y + bb.height / 2];
      const [dx, dy] = recenterOffset(angle, c0, c1);
      if (Math.abs(dx) > 1e-9 || Math.abs(dy) > 1e-9) {
        const T = svg.createSVGMatrix().translate(dx, dy);
        for (const k of kids) k.setAttribute('transform', fmt(T.multiply(own(k))));
      }
      const r = (v) => +v.toFixed(4);
      g.setAttribute('transform', `rotate(${r(angle)} ${r(c1[0])} ${r(c1[1])})`);
      batch.addSubCommand(new c.history.ChangeElementCommand(g, { transform: oldG }));
      for (const k of kids) batch.addSubCommand(new c.history.ChangeElementCommand(k, { transform: oldKids.get(k) }));
      c.selectorManager.requestSelector(g).resize();
    }
    if (!batch.isEmpty()) {
      c.undoMgr.addCommandToHistory(batch);
      if (changeListener) changeListener();
    }
  }

  let selectionListener = null;
  let insertCount = 0;
  let changeListener = null;

  function canvas() {
    return host.canvas();
  }

  /** Vent til SVG-Edit er helt klar (init er asynkron). */
  function whenReady() {
    return new Promise((resolve) => {
      const check = () => (host.canvas()?.getSvgString ? resolve() : setTimeout(check, 50));
      check();
    });
  }

  /** Det aktive værktøj (SVG-Edits "mode") til hjælpelinjen i Tegn (v0.92.0). */
  let modeListener = null;

  function hookEvents() {
    const c = canvas();
    host.decorate?.();
    hookPipeFollow();
    if (typeof c.setMode === 'function' && !c.__hvMode) {
      const setMode = c.setMode.bind(c);
      c.setMode = (mode) => { const r = setMode(mode); if (modeListener) modeListener(String(mode)); return r; };
      c.__hvMode = true;
    }
    // SVG-Edits egne id'er (svg_N — tegneværktøjer, indsæt, dupliker): spring reserverede over. Dupliker henter id'et
    // direkte fra tegningsobjektet (ikke lærredet), så det er tegningens getNextId — fælles for alle tegninger — der pakkes ind.
    const proto = Object.getPrototypeOf(c.getCurrentDrawing());
    if (proto && !proto.__hvReserved) {
      const nextId = proto.getNextId;
      proto.getNextId = function getNextIdSkippingReserved() {
        let id = nextId.call(this);
        for (let n = 0; reservedIds.has(id) && n < 100000; n++) id = nextId.call(this);
        return id;
      };
      proto.__hvReserved = true;
    }
    // bind() returnerer editorens egen handler — kald den først, så editoren virker uændret.
    const prevSelected = c.bind('selected', (win, elems) => {
      if (prevSelected) prevSelected(win, elems);
      rememberBoxes();
      if (selectionListener) selectionListener(currentSelection());
    });
    const prevChanged = c.bind('changed', (win, elems) => {
      // før editorens egen håndtering: den skriver contentW/H tilbage i viewBox (updateCanvas)
      syncContentSize();
      if (prevChanged) prevChanged(win, elems);
      if (changeListener) changeListener();
      if (selectionListener) selectionListener(currentSelection());
    });
    // SVG-Edit sender ikke 'changed' efter en flytning med musen, så vi lytter selv på museknappen (efter editorens egen
    // håndtering): ved nedtryk huskes de valgte elementers placering, ved slip fanges der — hvis det var et træk.
    document.addEventListener('mousedown', () => setTimeout(rememberBoxes, 0), { capture: true, signal: life.signal });
    document.addEventListener('mouseup', () => setTimeout(() => { if (!snapping) settleAfterMouseUp(); }, 0), { capture: true, signal: life.signal });
    // Indsæt og dupliker (Ctrl+V, Ctrl+D): kopien lægges på gitteret, så den passer sammen med originalen
    for (const name of ['pasteElements', 'cloneSelectedElements']) {
      const original = c[name];
      if (typeof original !== 'function') continue;
      c[name] = function wrapped(...args) {
        const result = original.apply(this, args);
        renameCopies();
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

  /**
   * Efter indsæt/dupliker: kopierne (den nye markering) har fået originalens navn med — giv dem et ledigt navn, så navnene
   * forbliver unikke (BUGS.md v0.63.0). Kopien hører til samme fortryd-trin som indsætningen, så navnet fortrydes med den.
   */
  function renameCopies() {
    for (const el of selectedEls()) for (const e of [el, ...el.querySelectorAll('[data-hv-pipe]')]) {
      e.removeAttribute('data-hv-from');
      e.removeAttribute('data-hv-to');
    }
    const root = canvas().getSvgContent();
    const copies = selectedEls().flatMap((el) => [el, ...el.querySelectorAll('[data-hv-name]')]).filter((el) => el.getAttribute('data-hv-name'));
    if (!copies.length) return;
    const copySet = new Set(copies);
    const used = Array.from(root.querySelectorAll('[data-hv-name]')).filter((el) => !copySet.has(el)).map((el) => el.getAttribute('data-hv-name'));
    for (const el of copies) {
      const name = nextFreeName(el.getAttribute('data-hv-name'), used);
      if (name) el.setAttribute('data-hv-name', name);
      used.push(name);
    }
  }

  function currentSelection() {
    const elems = (canvas().getSelectedElements() || []).filter(Boolean);
    return elems.map((el) => ({
      id: el.id || '', tag: el.tagName.toLowerCase(), interactive: el.hasAttribute('data-hv-auto'),
      type: el.getAttribute('data-hv-type') || '',
      // et T-stykke/kryds fra før v0.68.0: én sti, der kan deles i rør
      onePath: el.tagName === 'g' && [...el.children].filter((ch) => !RESERVED.has(ch.tagName.toLowerCase())).length === 1 && el.querySelector(':scope > path') !== null,
      name: el.getAttribute('data-hv-name') || '', desc: el.getAttribute('data-hv-desc') || '',
      children: [...el.children].filter((c) => !RESERVED.has(c.tagName.toLowerCase())).length,
    }));
  }

  /**
   * Id'er der har en symbolopsætning eller binding på tegningen (også forsvundne) — nye elementer må ikke få dem, ellers
   * "vågner" en gammel opsætning op på det nye element (BUGS.md v0.68.0). Sættes af Tegn, når en tegning åbnes.
   */
  let reservedIds = new Set();

  function idExists(id) {
    return reservedIds.has(id) || !!canvas().getSvgContent().querySelector(`#${CSS.escape(id)}`);
  }

  function uniqueId(base) {
    const clean = base.replace(/[^A-Za-z0-9_-]/g, '_') || 'symbol';
    if (!idExists(clean)) return clean;
    for (let i = 2; ; i++) if (!idExists(`${clean}_${i}`)) return `${clean}_${i}`;
  }

  /** Et navn der ikke er i brug: "Pumpe", "Pumpe 2", … */
  function uniqueNameIn(base, except = null) {
    const used = new Set(Array.from(canvas().getSvgContent().querySelectorAll('[data-hv-name]')).filter((el) => el !== except).map((el) => el.getAttribute('data-hv-name')));
    if (!used.has(base)) return base;
    for (let i = 2; ; i++) if (!used.has(`${base} ${i}`)) return `${base} ${i}`;
  }

  /** Et bibliotekssymbol (SVG-fragment med ét rodelement) som et element med unikke id'er — endnu ikke sat ind. */
  function buildSymbolNode(fragment, baseId, wantedId) {
    const parsed = new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${fragment}</svg>`, 'image/svg+xml');
    const src = parsed.documentElement.firstElementChild;
    if (!src) return null;
    const node = document.importNode(src, true);
    // "Behold id": det erstattede elements eget id må genbruges, selv om det er reserveret (det har jo en opsætning/binding,
    // som netop skal følge med) — reservationen gælder kun NYE elementer (BUGS.md v0.84.0)
    const free = (id) => !canvas().getSvgContent().querySelector(`#${CSS.escape(id)}`);
    node.setAttribute('id', wantedId && free(wantedId) ? wantedId : uniqueId(wantedId || baseId));
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

  /** De valgte elementer og alle deres efterkommere (uden title/desc/defs/metadata), hver kun én gang. */
  function paintedIn(roots) {
    const seen = new Set();
    const walk = (el) => {
      if (!el || seen.has(el) || RESERVED.has(el.tagName.toLowerCase())) return;
      seen.add(el);
      for (const ch of el.children) walk(ch);
    };
    roots.forEach(walk);
    return [...seen];
  }

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

  /** Samlet geometri for flere dele: boksen i tegningen, uden drejning. */
  function unionGeometry(els) {
    const u = unionBox(els.map(boxOf));
    return u ? { w: u.w, h: u.h, angle: 0, cx: u.x + u.w / 2, cy: u.y + u.h / 2, box: u } : null;
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

  /** Trekanterne (3 hjørner) i elementerne og deres underelementer, med hjørnerne i tegningens koordinater. */
  function trianglesIn(els) {
    const out = [];
    for (const root of els) {
      for (const e of [root, ...root.querySelectorAll('path, polygon')]) {
        const tag = e.tagName.toLowerCase();
        let verts = null;
        if (tag === 'path') verts = pathVertices(e.getAttribute('d'));
        else if (tag === 'polygon') verts = (e.getAttribute('points') || '').trim().split(/[\s,]+/).map(Number).reduce((acc, v, i, all) => (i % 2 ? acc : [...acc, [v, all[i + 1]]]), []);
        if (!verts || verts.length !== 3) continue;
        const M = toDocMatrix(e);
        if (!M) continue;
        out.push(verts.map(([x, y]) => [M.a * x + M.c * y + M.e, M.b * x + M.d * y + M.f]));
      }
    }
    return out;
  }

  /** Aksen (grader i [0, 180)) for en ventil tegnet som to trekanter med spidserne mod hinanden. Null hvis ikke præcis to trekanter. */
  function valveAxisOf(els) {
    const tris = trianglesIn(els);
    return tris.length === 2 ? axisAngle(centroid(tris[0]), centroid(tris[1])) : null;
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
      // Et symbol fra biblioteket ligner kun symboler af samme type (fx alle gamle pumper, der skal opdateres); en tegnet del kun tegnede
      if ((o.getAttribute('data-hv-type') ?? '') !== (el.getAttribute('data-hv-type') ?? '') || key(countShapes(o)) !== k0) return false;
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



  // ---------------------------------------------------------------- rør (PLAN.md trin 4)
  // Et rør er en <path data-hv-pipe> med vandrette/lodrette stykker. Enderne kan sidde fast i et symbols
  // tilslutningspunkt (data-hv-from/-to, se pipes.js); når symbolet flyttes, følger røret med i samme fortryd-trin.
  const NS = 'http://www.w3.org/2000/svg';
  const isPipe = (el) => el?.hasAttribute?.('data-hv-pipe');
  const toPoint = (m, v) => [m.a * v[0] + m.c * v[1] + m.e, m.b * v[0] + m.d * v[1] + m.f];

  /** Hjørnepunkter af formens streger, i `el`s egne koordinater. */
  function localVertices(el) {
    const base = toDocMatrix(el);
    const inv = invertMatrix(base);
    if (!inv) return [];
    const out = [];
    for (const e of [el, ...el.querySelectorAll('path, line, polyline, polygon, rect')]) {
      const tag = e.tagName.toLowerCase();
      let vs = [];
      const n = (a) => Number(e.getAttribute(a)) || 0;
      if (tag === 'path') vs = pathVertices(e.getAttribute('d')) || [];
      else if (tag === 'line') vs = [[n('x1'), n('y1')], [n('x2'), n('y2')]];
      else if (tag === 'polyline' || tag === 'polygon') vs = (e.getAttribute('points') || '').trim().split(/[\s,]+/).map(Number).reduce((a, v, i, all) => (i % 2 ? a : [...a, [v, all[i + 1]]]), []);
      else if (tag === 'rect') { const x = n('x'), y = n('y'), w = n('width'), h = n('height'); vs = [[x, y + h / 2], [x + w, y + h / 2], [x + w / 2, y], [x + w / 2, y + h]]; }
      else continue;
      const m = e === el ? identityMatrix() : multiplyMatrix(inv, toDocMatrix(e));
      for (const v of vs) if (Number.isFinite(v[0]) && Number.isFinite(v[1])) out.push(toPoint(m, v));
    }
    return out;
  }

  /** Symbolets tilslutningspunkter: [{ local, doc, axis }] — axis = retningen et rør bør starte i ('h' fra en sidekant). */
  function portsOf(el) {
    let bb;
    try { bb = el.getBBox(); } catch { return []; }
    if (!(bb.width > 0 || bb.height > 0)) return [];
    const box = { x: bb.x, y: bb.y, w: bb.width, h: bb.height };
    const m = toDocMatrix(el);
    return portsFrom(localVertices(el), box).map((local) => {
      const side = Math.abs(local[0] - box.x) < 1.5 || Math.abs(local[0] - box.x - box.w) < 1.5;
      const doc = toPoint(m, local);
      // drejet 90°: siden vender den anden vej
      const turned = Math.abs(m.b) > Math.abs(m.a);
      return { local, frac: toFrac(local, box), doc, axis: side !== turned ? 'h' : 'v' };
    });
  }

  /** Elementer et rør kan tilsluttes: øverste niveau i lagene, ikke rør, ikke baggrunden. */
  function pipeTargets() {
    const content = canvas().getSvgContent();
    return [...content.querySelectorAll('g.layer > *')].filter((el) =>
      el.id && el.id !== 'baggrund' && !isPipe(el) && !RESERVED.has(el.tagName.toLowerCase()) && el.getAttribute('display') !== 'none');
  }

  function pipePoints(el) {
    return (pathVertices(el.getAttribute('d')) || []).map(([x, y]) => [x, y]);
  }

  /** Hvor rørets ende skal være nu (tegningens koordinater), eller null hvis den ikke sidder fast. */
  function endTarget(el, attr) {
    const ref = parseRef(el.getAttribute(attr));
    if (!ref) return null;
    const sym = canvas().getSvgContent().querySelector(`[id="${CSS.escape(ref.id)}"]`);
    if (!sym) return null;   // symbolet er slettet: enden bliver hvor den er
    let bb;
    try { bb = sym.getBBox(); } catch { return null; }
    return toPoint(toDocMatrix(sym), fromFrac(ref.local, { x: bb.x, y: bb.y, w: bb.width, h: bb.height }));
  }

  /**
   * Lad rørene følge deres symboler. `moved` = elementerne i den ændring, der netop er sket: et rør der selv blev
   * flyttet (uden sit symbol) slippes fra symbolet i stedet. Giver ændringerne som ét fortryd-trin (eller null).
   */
  function followPipes(moved) {
    const c = canvas();
    const pipes = [...c.getSvgContent().querySelectorAll('[data-hv-pipe]')].filter((el) => el.hasAttribute('data-hv-from') || el.hasAttribute('data-hv-to'));
    if (!pipes.length) return null;
    const batch = new c.history.BatchCommand('Rør følger med');
    const movedSet = new Set(moved);
    for (const el of pipes) {
      const before = { d: el.getAttribute('d'), 'data-hv-from': el.getAttribute('data-hv-from'), 'data-hv-to': el.getAttribute('data-hv-to'), transform: el.getAttribute('transform') };
      if (movedSet.has(el)) {
        // røret selv er ændret: en ende der ikke længere ligger på sit symbol (røret er flyttet væk) slippes;
        // fx en ny farve rører ikke enderne, så røret bliver siddende
        const pts = pipePoints(el);
        const ends = { 'data-hv-from': pts[0], 'data-hv-to': pts[pts.length - 1] };
        for (const attr of ['data-hv-from', 'data-hv-to']) {
          const target = endTarget(el, attr);
          const end = ends[attr];
          if (target && end && Math.hypot(target[0] - end[0], target[1] - end[1]) > 0.5) el.removeAttribute(attr);
        }
      } else {
        if (el.getAttribute('transform')) continue;   // et transformeret rør (sjældent): rør det ikke
        let pts = pipePoints(el);
        if (pts.length < 2) continue;
        const from = endTarget(el, 'data-hv-from');
        const to = endTarget(el, 'data-hv-to');
        const off = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) > 0.01;
        if (from && off(from, pts[0])) pts = moveEnd(pts, 'start', from);
        if (to && off(to, pts[pts.length - 1])) pts = moveEnd(pts, 'end', to);
        const d = pathD(pts);
        if (d !== el.getAttribute('d')) el.setAttribute('d', d);
      }
      const changed = Object.entries(before).some(([k, v]) => el.getAttribute(k) !== v);
      if (changed) batch.addSubCommand(new c.history.ChangeElementCommand(el, before));
    }
    return batch.isEmpty() ? null : batch;
  }

  /** Hver ny ændring i fortryd-historikken: rørene følger med i samme trin. */
  function hookPipeFollow() {
    const c = canvas();
    const um = c.undoMgr;
    if (!um || um.__hvPipes) return;
    const add = um.addCommandToHistory.bind(um);
    let busy = false;
    um.addCommandToHistory = (cmd) => {
      if (busy) return add(cmd);
      busy = true;
      try {
        let extra = null;
        try { extra = followPipes(cmd?.elements?.() ?? []); } catch (e) { console.warn('Rør kunne ikke følge med', e); }
        if (!extra) return add(cmd);
        const batch = new c.history.BatchCommand(cmd.text ?? 'Ændring');
        batch.addSubCommand(cmd);
        batch.addSubCommand(extra);
        return add(batch);
      } finally {
        busy = false;
      }
    };
    um.__hvPipes = true;
  }

  // ---- værktøjet: klik punkter, klik på et tilslutningspunkt (eller dobbeltklik/Enter) for at slutte, Escape fortryder
  const pipeTool = { on: false, pts: [], from: null, fromAxis: null, cursor: null, hover: null, ports: [], overlay: null, life: null };

  function docPoint(e) {
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(canvas().getrootSctm());
    return [p.x, p.y];
  }
  function snapPipePoint(raw) {
    const tol = 12 / (canvas().getZoom() || 1);
    const port = nearest(pipeTool.ports.map((q) => q.doc), raw, tol);
    if (port) return { p: port, port: pipeTool.ports.find((q) => q.doc === port) };
    if (guides.snapGrid) return { p: [Math.round(raw[0] / guides.step) * guides.step, Math.round(raw[1] / guides.step) * guides.step], port: null };
    return { p: raw, port: null };
  }
  /** Stykket hen til p. Fra et tilslutningspunkt går røret ud i punktets retning; ind i et punkt rammer det i punktets retning. */
  function legTo(p, port = null) {
    const pts = pipeTool.pts;
    const last = pts[pts.length - 1];
    return connect(last, p, pts.length === 1 ? pipeTool.fromAxis ?? undefined : undefined, port?.axis);
  }

  function drawPipeOverlay() {
    const gridHost = host.gridHost();
    const content = canvas()?.getSvgContent?.();
    if (!gridHost || !content) return;
    let layer = pipeTool.overlay;
    if (!pipeTool.on) { layer?.remove(); pipeTool.overlay = null; return; }
    if (!layer) {
      layer = document.createElementNS(NS, 'svg');
      layer.setAttribute('id', 'hvPipeOverlay');
      layer.style.cssText = 'position:absolute; pointer-events:none; z-index:55; overflow:visible;';
      gridHost.appendChild(layer);
      pipeTool.overlay = layer;
    }
    const hr = gridHost.getBoundingClientRect();
    const cr = contentRect(content);
    const vb = (content.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
    layer.style.left = `${cr.left - hr.left + gridHost.scrollLeft}px`;
    layer.style.top = `${cr.top - hr.top + gridHost.scrollTop}px`;
    layer.setAttribute('width', cr.width);
    layer.setAttribute('height', cr.height);
    if (vb.length === 4) layer.setAttribute('viewBox', vb.join(' '));
    const z = canvas().getZoom() || 1;
    const r = 4 / z;
    const dots = pipeTool.ports.map((q) => {
      const hot = pipeTool.hover && q.doc === pipeTool.hover.doc;
      return `<circle cx="${q.doc[0]}" cy="${q.doc[1]}" r="${hot ? r * 1.8 : r}" fill="${hot ? '#2e7d32' : '#fff'}" stroke="#2e7d32" stroke-width="${1.5 / z}"/>`;
    }).join('');
    let preview = '';
    if (pipeTool.pts.length) {
      const pts = pipeTool.cursor ? simplify([...pipeTool.pts, ...legTo(pipeTool.cursor, pipeTool.hover).slice(1)]) : pipeTool.pts;
      preview = `<path d="${pathD(pts)}" fill="none" stroke="${PIPE_STYLE.stroke}" stroke-opacity=".55" stroke-width="${PIPE_STYLE['stroke-width']}"/>` +
        `<path d="${pathD(pts)}" fill="none" stroke="#2e7d32" stroke-width="${1.5 / z}" stroke-dasharray="${4 / z} ${3 / z}"/>`;
    }
    layer.innerHTML = preview + dots;
  }

  function finishPipe() {
    const c = canvas();
    const pts = simplify(pipeTool.pts);
    const fromRef = pipeTool.from;
    const toRef = pipeTool.to ?? null;
    pipeTool.pts = [];
    pipeTool.from = pipeTool.fromAxis = pipeTool.to = null;
    if (pts.length >= 2) {
      const el = document.createElementNS(NS, 'path');
      el.setAttribute('id', c.getNextId());
      for (const [k, v] of Object.entries(PIPE_STYLE)) el.setAttribute(k, v);
      el.setAttribute('d', pathD(pts));
      el.setAttribute('data-hv-pipe', '1');
      if (fromRef) el.setAttribute('data-hv-from', fromRef);
      if (toRef) el.setAttribute('data-hv-to', toRef);
      // bag de symboler det forbinder (rør ligger under ventiler, pumper …)
      const layer = c.getCurrentDrawing().getCurrentLayer();
      const ends = [fromRef, toRef].map((r) => parseRef(r)?.id).filter(Boolean);
      const first = [...layer.children].find((ch) => ends.includes(ch.id));
      layer.insertBefore(el, first ?? null);
      c.undoMgr.addCommandToHistory(new c.history.InsertElementCommand(el));
      c.clearSelection();
      c.addToSelection([el]);
      if (changeListener) changeListener();
    }
    drawPipeOverlay();
  }

  function setPipeTool(on) {
    if (on === pipeTool.on) return;
    pipeTool.on = on;
    pipeTool.life?.abort();
    pipeTool.pts = [];
    pipeTool.cursor = pipeTool.hover = null;
    if (!on) { drawPipeOverlay(); return; }
    if (modeListener) modeListener('pipe');
    const c = canvas();
    c.clearSelection();
    // tilslutningspunkter: symbolets id skal kunne findes igen fra punktet
    pipeTool.ports = pipeTargets().flatMap((el) => portsOf(el).map((q) => ({ ...q, id: el.id })));
    const life = new AbortController();
    pipeTool.life = life;
    const area = host.gridHost();
    const opts = { capture: true, signal: life.signal };
    const swallow = (e) => { e.stopPropagation(); e.preventDefault(); };
    area.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;   // midterknap: panorér som normalt
      swallow(e);
      const { p, port } = snapPipePoint(docPoint(e));
      if (!pipeTool.pts.length) {
        pipeTool.pts = [p];
        pipeTool.from = port ? formatRef(port.id, port.frac) : null;
        pipeTool.fromAxis = port?.axis ?? null;
      } else if (e.detail >= 2) {
        finishPipe();
        return;
      } else {
        pipeTool.pts = simplify([...pipeTool.pts, ...legTo(p, port).slice(1)]);
        if (port) { pipeTool.to = formatRef(port.id, port.frac); finishPipe(); return; }
      }
      drawPipeOverlay();
    }, opts);
    area.addEventListener('mousemove', (e) => {
      const { p, port } = snapPipePoint(docPoint(e));
      pipeTool.cursor = p;
      pipeTool.hover = port;
      drawPipeOverlay();
    }, opts);
    for (const t of ['mouseup', 'click', 'dblclick']) area.addEventListener(t, (e) => { if (e.button === 0) swallow(e); }, opts);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && pipeTool.pts.length) { pipeTool.pts = []; swallow(e); drawPipeOverlay(); }
      else if (e.key === 'Enter' && pipeTool.pts.length) { swallow(e); finishPipe(); }
      else if (e.key === 'Backspace' && pipeTool.pts.length) { pipeTool.pts = pipeTool.pts.slice(0, -1); swallow(e); drawPipeOverlay(); }
    }, opts);
    drawPipeOverlay();
  }

  // ---------------------------------------------------------------- panelet i den nye editor: geometri, stil, orden
  const TEXTY = new Set(['text', 'tspan']);
  const num = (v, d = 0) => { const n = parseFloat(v); return Number.isFinite(n) ? n : d; };

  /** Fortryd: husk alle attributter på elementerne og deres efterkommere, så én ændring kan fortrydes samlet. */
  function snapshot(els) {
    const map = new Map();
    for (const el of els) for (const e of [el, ...el.querySelectorAll('*')]) {
      map.set(e, Object.fromEntries([...e.attributes].map((a) => [a.name, a.value])));
    }
    return map;
  }
  function commitSnapshot(map, label) {
    const c = canvas();
    const batch = new c.history.BatchCommand(label);
    for (const [e, before] of map) {
      const now = Object.fromEntries([...e.attributes].map((a) => [a.name, a.value]));
      const old = {};
      let changed = false;
      for (const k of new Set([...Object.keys(before), ...Object.keys(now)])) {
        if (before[k] !== now[k]) { old[k] = before[k] ?? null; changed = true; }
      }
      if (changed) batch.addSubCommand(new c.history.ChangeElementCommand(e, old));
    }
    if (batch.isEmpty()) return false;
    c.undoMgr.addCommandToHistory(batch);
    return true;
  }
  function afterEdit() {
    const c = canvas();
    for (const el of selectedEls()) c.selectorManager.requestSelector(el).resize();
    rememberBoxes();
    if (changeListener) changeListener();
    if (selectionListener) selectionListener(currentSelection());
  }

  /**
   * Afbild markeringens boks `from` over i `to` (tegningens koordinater) for ét element. Som når man trækker i et
   * hjørne: translate/scale/translate sættes bagest på elementets transform, og lærredet regner det ind i elementets
   * egne mål (x, width, punkter …) — så tegningen forbliver ren. Ligger elementet i en transformeret gruppe, bruges en
   * samlet matrix i stedet (lærredet kan ikke forenkle den).
   */
  function applyBox(el, from, to) {
    const c = canvas();
    const root = c.getSvgRoot();
    const parent = el.parentNode;
    const p = parent && parent !== c.getSvgContent() ? toDocMatrix(parent) : identityMatrix();
    const near = (v, w) => Math.abs(v - w) < 1e-6;   // toDocMatrix har små afrundingsrester
    const plain = near(p.a, 1) && near(p.d, 1) && near(p.b, 0) && near(p.c, 0) && near(p.e, 0) && near(p.f, 0);
    const tlist = el.transform?.baseVal;
    const own = tlist?.consolidate ? (tlist.numberOfItems ? tlist.consolidate().matrix : null) : null;
    const ownM = own ? { a: own.a, b: own.b, c: own.c, d: own.d, e: own.e, f: own.f } : identityMatrix();
    if (own) {
      // consolidate() har lagt listen sammen til én matrix — skriv den ud igen, så lærredet ser én transform
      el.setAttribute('transform', `matrix(${[ownM.a, ownM.b, ownM.c, ownM.d, ownM.e, ownM.f].join(' ')})`);
    }
    const inv = invertMatrix(ownM);
    if (plain && inv && near(ownM.b, 0) && near(ownM.c, 0)) {
      const fromL = transformBox(from, inv);
      const toL = transformBox(to, inv);
      const sx = fromL.w > 0 ? toL.w / fromL.w : 1;
      const sy = fromL.h > 0 ? toL.h / fromL.h : 1;
      const back = root.createSVGTransform();
      const scale = root.createSVGTransform();
      const origin = root.createSVGTransform();
      back.setTranslate(toL.x, toL.y);
      scale.setScale(sx, sy);
      origin.setTranslate(-fromL.x, -fromL.y);
      const list = el.transform.baseVal;
      list.appendItem(back);
      list.appendItem(scale);
      list.appendItem(origin);
    } else {
      const m = boxMapping(from, to);
      const pInv = invertMatrix(p) ?? identityMatrix();
      const local = multiplyMatrix(pInv, multiplyMatrix(m, multiplyMatrix(p, ownM)));
      const r = (v) => Math.round(v * 1e4) / 1e4;
      el.setAttribute('transform', `matrix(${[local.a, local.b, local.c, local.d, local.e, local.f].map(r).join(' ')})`);
    }
    try { c.recalculateDimensions(el); } catch { /* transformen bliver stående — tegningen ser stadig rigtig ud */ }
  }

  function moveDoc(el, dx, dy) {
    if (!dx && !dy) return;
    const b = boxOf(el);
    applyBox(el, b, { ...b, x: b.x + dx, y: b.y + dy });
  }

  function paintOf(el) {
    const cs = getComputedStyle(el);
    const g = (a) => el.getAttribute(a) || cs.getPropertyValue(a) || '';
    return {
      fill: g('fill') || 'none',
      stroke: g('stroke') || 'none',
      strokeWidth: num(g('stroke-width'), 0),
      opacity: num(el.getAttribute('opacity'), 1),
      fontSize: TEXTY.has(el.tagName) ? num(g('font-size'), 16) : null,
      fontFamily: TEXTY.has(el.tagName) ? (g('font-family') || 'sans-serif') : null,
      bold: TEXTY.has(el.tagName) ? /bold|[6-9]00/.test(g('font-weight')) : null,
      rx: el.tagName === 'rect' ? num(el.getAttribute('rx'), 0) : null,
    };
  }

  const scada = {
    /** Rør-værktøjet til/fra (den nye editor). Mens det er til, tager det musen fra lærredet. */
    setPipeTool(on) { setPipeTool(!!on); },
    /** Tegn rørværktøjets lag igen (efter zoom/rulning). */
    redrawPipes() { if (pipeTool.on) drawPipeOverlay(); },

    /** Det markerede til panelet: samlet boks (tegningens koordinater), vinkel og stil for ét element. */
    inspect() {
      const sel = selectedEls();
      if (!sel.length) return null;
      const box = unionBox(sel.map(boxOf));
      if (!box) return null;
      const one = sel.length === 1 ? sel[0] : null;
      return {
        count: sel.length,
        tag: one ? one.tagName : null,
        box: { x: round2(box.x), y: round2(box.y), w: round2(box.w), h: round2(box.h) },
        angle: one ? round2(canvas().getRotationAngle(one) || 0) : 0,
        paint: one && one.tagName !== 'g' ? paintOf(one) : null,
      };
    },

    /** Sæt x, y, bredde eller højde på markeringen (som én enhed). Drejede elementer kan kun flyttes. */
    setBox(field, value, keepRatio = false) {
      const sel = selectedEls();
      const from = unionBox(sel.map(boxOf));
      if (!from) return { error: 'Intet valgt' };
      const to = editBox(from, field, value, keepRatio);
      if (!to) return { error: field === 'w' || field === 'h' ? 'Størrelsen skal være mindst 1' : 'Ugyldigt tal' };
      if ((field === 'w' || field === 'h') && sel.some((el) => canvas().getRotationAngle(el))) {
        return { error: 'Et drejet element kan ikke ændre størrelse her — træk i hjørnet, eller drej det til 0° først' };
      }
      const snap = snapshot(sel);
      for (const el of sel) applyBox(el, from, to);
      commitSnapshot(snap, `Panel: ${field}`);
      afterEdit();
      return { ok: true };
    },

    setAngle(deg) {
      const v = Number(deg);
      if (!Number.isFinite(v) || selectedEls().length !== 1) return { error: 'Vælg ét element' };
      canvas().setRotationAngle(((v % 360) + 540) % 360 - 180);
      afterEdit();
      return { ok: true };
    },

    /** Stil på det markerede: fill, stroke, stroke-width, opacity, font-size, font-family, font-weight, rx. */
    setStyle(attr, value) {
      const sel = selectedEls();
      if (!sel.length) return { error: 'Intet valgt' };
      const allowed = new Set(['fill', 'stroke', 'stroke-width', 'opacity', 'font-size', 'font-family', 'font-weight', 'rx']);
      if (!allowed.has(attr)) return { error: `Ukendt egenskab ${attr}` };
      const snap = snapshot(sel);
      for (const el of sel) {
        if (value === null || value === '') el.removeAttribute(attr);
        else {
          el.setAttribute(attr, String(value));
          if (attr === 'rx') el.setAttribute('ry', String(value));
        }
      }
      commitSnapshot(snap, `Panel: ${attr}`);
      afterEdit();
      return { ok: true };
    },

    /** Justér: l, c, r (vandret), t, m, b (lodret) — i forhold til markeringen; ét element i forhold til tegningen. */
    align(type) {
      const sel = selectedEls();
      if (!sel.length) return 0;
      canvas().alignSelectedElements(type, sel.length === 1 ? 'page' : 'selected');
      afterEdit();
      return sel.length;
    },

    /** Fordel 3 eller flere med lige store mellemrum ('x' vandret, 'y' lodret). */
    distribute(axis) {
      const sel = selectedEls();
      if (sel.length < 3) return 0;
      const deltas = distributeBoxes(sel.map(boxOf), axis);
      const snap = snapshot(sel);
      sel.forEach((el, i) => (axis === 'x' ? moveDoc(el, deltas[i], 0) : moveDoc(el, 0, deltas[i])));
      commitSnapshot(snap, 'Fordel');
      afterEdit();
      return sel.length;
    },

    /** Rækkefølge: 'top', 'bottom' (helt), 'up', 'down' (ét trin). */
    order(where) {
      const c = canvas();
      if (!selectedEls().length) return;
      if (where === 'top') c.moveToTopSelectedElement();
      else if (where === 'bottom') c.moveToBottomSelectedElement();
      else c.moveUpDownSelected(where === 'up' ? 'Up' : 'Down');
      afterEdit();
    },

    flip(dir) {
      if (!selectedEls().length) return;
      canvas().flipSelectedElements(dir === 'h' ? -1 : 1, dir === 'v' ? -1 : 1);
      afterEdit();
    },


    ready: whenReady().then(hookEvents),

    load(svg) {
      const ok = host.loadFromString(svg, { noAlert: true });
      canvas().undoMgr.resetUndoStack();
      drawGrid();
      return ok;
    },

    newDrawing(width, height) {
      host.loadFromString(
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
      if (!sel.length) return null;
      if (sel.length > 1) {
        // En markering af flere dele regnes som ÉN del: samlet boks og samlede figurer (fx en ventil tegnet af løse trekanter)
        const boxes = sel.map(boxOf);
        const u = unionBox(boxes);
        const counts = {};
        for (const el of sel) for (const [k, v] of Object.entries(countShapes(el))) counts[k] = (counts[k] || 0) + v;
        const texts = sel.flatMap((el) => (el.tagName.toLowerCase() === 'text' ? [(el.textContent || '').replace(/\s+/g, ' ').trim()] : [])).filter(Boolean);
        return {
          id: '', tag: 'markering', counts, children: sel.length, w: Math.round(u.w * 10) / 10, h: Math.round(u.h * 10) / 10, angle: 0,
          fill: '', stroke: '', strokeWidth: 0, rx: 0, name: '', symbolType: '', apexAngle: null,
          ids: sel.flatMap((el) => [el.id, ...[...el.querySelectorAll('[id]')].map((e) => e.id)]).filter(Boolean),
          texts, similar: 0, similarAny: 0, similarGroups: [], axisAngle: valveAxisOf(sel),
        };
      }
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
        axisAngle: valveAxisOf([el]),
        ids: affectedIds(el, g),
        texts: textsWithin(el, g).map((t) => t.text),
        similar: similarTo(el).length,
        similarAny: similarTo(el, true).length,
        similarGroups: similarTo(el, true).map((o) => affectedIds(o, geometryOf(o))),   // pr. lignende del: de id'er der forsvinder (delens eget først)
      };
    },

    /**
     * Erstat det valgte element (og evt. alle lignende) med et bibliotekssymbol: samme midte, størrelse og drejning, i ét
     * fortryd-trin. opts: { name, keepId, stretch, useText, similar }. → { ok, replaced, ids } eller { error }.
     */
    replaceSelected(fragment, baseId, opts = {}) {
      const c = canvas();
      const sel = selectedEls();
      if (!sel.length) return { error: 'Vælg mindst ét element' };
      const multi = sel.length > 1;
      // Flere valgte dele erstattes samlet af ét symbol; ét valgt element kan tage lignende med
      const units = multi ? [sel] : [sel[0], ...(opts.similar ? similarTo(sel[0], opts.similar === 'any') : [])].map((o) => [o]);
      const targets = units;
      const batch = new c.history.BatchCommand(`Erstat med symbol (${targets.length})`);
      c.clearSelection();
      const created = [];
      const protect = new Set(opts.protectIds || []);
      let skipped = 0;
      for (const [index, olds] of targets.entries()) {
        const old = olds[olds.length - 1];
        const g = multi ? unionGeometry(olds) : geometryOf(old);
        if (!g) continue;
        // Lignende dele med bindinger (på dem selv, deres dele eller deres tekster) røres ikke — de erstattes enkeltvis
        if (index > 0 && affectedIds(old, g).some((id) => protect.has(id) && !(opts.keepId && id === old.id))) {
          skipped++;
          continue;
        }
        const parent = old.parentNode;
        const anchor = topLevelOf(old);
        const layer = anchor.parentNode;
        const texts = !multi && opts.useText ? textsWithin(old, g) : [];
        const oldId = multi ? '' : old.id;
        // Retningen måles FØR delen fjernes (en frakoblet del har ingen matrix i tegningen)
        const apex = !multi && opts.apexNative !== undefined ? apexAngleOf(old) : null;
        const axis = opts.axisNative !== undefined ? valveAxisOf(olds) : null;
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
        for (const o of olds) removeTracked(o);
        // 2) nyt symbol (bevarer id'et hvis ønsket, så bindinger på elementet følger med)
        const node = buildSymbolNode(fragment, baseId, opts.keepId && oldId ? oldId : undefined);
        if (!node) continue;
        layer.insertBefore(node, insertBeforeNode && insertBeforeNode.parentNode === layer ? insertBeforeNode : null);
        const nb = node.getBBox();
        const sx0 = nb.width > 0 ? g.w / nb.width : 1;
        const sy0 = nb.height > 0 ? g.h / nb.height : 1;
        const sx = opts.stretch ? sx0 : Math.min(sx0, sy0);
        const sy = opts.stretch ? sy0 : Math.min(sx0, sy0);
        const flip = opts.mirror ? -1 : 1;   // spejlvendt vandret om symbolets midte (teksterne spejles ikke — se nedenfor)
        const tx = g.cx - flip * sx * (nb.x + nb.width / 2);
        const ty = g.cy - sy * (nb.y + nb.height / 2);
        // Retningsgivende symboler (pumpe): drej, så symbolets trekant peger samme vej som den tegnede; ellers delens egen drejning
        // Retning (pumpe, kontraventil) eller akse (ventiler) aflæst af den tegnede del — ellers delens egen drejning
        const angle = apex !== null ? turnTo(apex, opts.apexNative) : axis !== null ? turnAxis(axis, opts.axisNative) : g.angle;
        const rot = Math.abs(angle) > 0.01 ? `rotate(${angle.toFixed(3)} ${g.cx.toFixed(3)} ${g.cy.toFixed(3)}) ` : '';
        node.setAttribute('transform', `${rot}translate(${tx.toFixed(3)} ${ty.toFixed(3)}) scale(${(flip * sx).toFixed(5)} ${sy.toFixed(5)})`);
        if (opts.mirror) {
          // Spejlingen skal vende symbolets form, ikke bogstaverne: hver tekst vendes tilbage om sit eget midterlinje
          for (const t of node.querySelectorAll('text')) {
            const tb = t.getBBox();
            t.setAttribute('transform', `translate(${(2 * (tb.x + tb.width / 2)).toFixed(3)} 0) scale(-1 1)`);
          }
        }
        if (texts.length) {
          const slot = node.querySelector('[data-hv-pid="tekst"]');
          if (slot) slot.textContent = texts[0].text;
        }
        // Det valgte element får det indtastede navn; de øvrige "<symbol> <deres egen tekst>" (ellers løbenumre)
        if (opts.name) {
          // lignende dele, der allerede har et navn (fx gamle biblioteksymboler, der opdateres), beholder det
          const kept = index > 0 && !multi ? old.getAttribute('data-hv-name') : null;
          const own = index === 0 ? opts.name : kept || `${opts.namePrefix || opts.name}${texts[0] ? ` ${texts[0].text}` : ''}`;
          node.setAttribute('data-hv-name', uniqueNameIn(own, node));   // uden selve symbolet, ellers får navnet et falsk " 2"
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

    /** Vælg flere elementer på én gang (til en samlet erstatning). Returnerer antal fundne. */
    selectByIds(ids) {
      const content = canvas().getSvgContent();
      const els = ids.map((id) => content.querySelector(`#${CSS.escape(id)}`)).filter(Boolean);
      canvas().clearSelection();
      if (els.length) canvas().addToSelection(els);
      return els.length;
    },

    /** Opløs den valgte gruppe, så dens dele kan vælges enkeltvis. Returnerer fejltekst eller ''. */
    /** Farverne (fyld/streg) i de valgte elementer og alle deres dele. → [{ color: '#rrggbb', uses }], mest brugte først. */
    selectionColors() {
      return collectColors(paintedIn(selectedEls()).map((el) => ({ fill: el.getAttribute('fill'), stroke: el.getAttribute('stroke'), style: el.getAttribute('style') })));
    },

    /** Skift farven `from` til `to` i de valgte elementer og alle deres dele — ét fortryd-trin. → antal ændrede figurer. */
    recolorSelection(from, to) {
      const c = canvas();
      const batch = new c.history.BatchCommand('Skift farve');
      let n = 0;
      for (const el of paintedIn(selectedEls())) {
        const attrs = { fill: el.getAttribute('fill'), stroke: el.getAttribute('stroke'), style: el.getAttribute('style') };
        const next = recolorAttrs(attrs, from, to);
        if (!next) continue;
        const old = {};
        for (const k of Object.keys(next)) { old[k] = el.getAttribute(k); el.setAttribute(k, next[k]); }
        batch.addSubCommand(new c.history.ChangeElementCommand(el, old, 'farve'));
        n++;
      }
      if (!n) return 0;
      c.undoMgr.addCommandToHistory(batch);
      if (changeListener) changeListener();
      if (selectionListener) selectionListener(currentSelection());
      return n;
    },

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
    /**
     * Del et T-stykke eller kryds, der er tegnet som ÉN sti (fra før v0.68.0), i selvstændige rør — `legs` er bibliotekets
     * rør (FITTING_LEGS). Gruppen beholder id, navn, type og transform; ét fortryd-trin. → { ok, removed: [gamle id'er], parts }
     */
    splitFitting(id, legs) {
      const c = canvas();
      const g = c.getSvgContent().querySelector(`[id="${CSS.escape(id)}"]`);
      if (!g || g.tagName !== 'g') return { error: 'Vælg et T-stykke eller kryds' };
      const old = [...g.children].filter((ch) => !RESERVED.has(ch.tagName.toLowerCase()));
      if (old.length !== 1 || old[0].tagName !== 'path') return { error: 'Symbolet er allerede delt i rør' };
      const node = buildSymbolNode(`<g>${legs}</g>`, g.getAttribute('data-hv-type') || 'fitting', `${g.id}_tmp`);
      if (!node) return { error: 'Kunne ikke bygge rørene' };
      const batch = new c.history.BatchCommand('Del i rør');
      const removed = old.map((el) => el.id).filter(Boolean);
      for (const el of old) {
        const next = el.nextSibling, parent = el.parentNode;
        el.remove();
        batch.addSubCommand(new c.history.RemoveElementCommand(el, next, parent));
      }
      const parts = [];
      for (const leg of [...node.children]) {
        // id'er efter gruppen (ikke den midlertidige node)
        leg.setAttribute('id', uniqueId(`${g.id}_${leg.getAttribute('data-hv-pid')}`));
        // overtag den gamle stis farve/streg, så tegningen ser ens ud
        for (const a of ['stroke', 'stroke-width', 'class', 'opacity']) {
          const v = old[0].getAttribute(a);
          if (v) leg.setAttribute(a, v);
        }
        g.appendChild(leg);
        batch.addSubCommand(new c.history.InsertElementCommand(leg));
        parts.push(leg.id);
      }
      c.undoMgr.addCommandToHistory(batch);
      if (changeListener) changeListener();
      if (selectionListener) selectionListener(currentSelection());
      return { ok: true, removed, parts };
    },

    /** Id'er som nye elementer ikke må få (se reservedIds). */
    setReservedIds(ids) {
      reservedIds = new Set((ids || []).map(String));
    },

    uniqueName(base) {
      return uniqueNameIn(base);
    },

    /**
     * Giv elementerne (id'er) navnene "<base>_1", "<base>_2" … (ledige numre, i tegningens rækkefølge) — ét fortryd-trin. Elementer der allerede
     * har et navn, eller ikke findes, røres ikke. → { id: navn } for de navngivne.
     */
    /** Kaldes med værktøjets navn, når et andet værktøj vælges (v0.92.0). */
    onMode(fn) {
      modeListener = fn;
      fn(String(canvas()?.getMode?.() ?? 'select'));
    },

    /** Tegningens størrelse (v0.92.0) i tegningens egne enheder. */
    getSize() {
      const r = canvas().getResolution();
      return { w: Math.round(r.w), h: Math.round(r.h) };
    },

    /**
     * Ny størrelse — ét fortryd-trin. Et baggrundsrektangel, der fyldte hele tegningen (som nye tegninger har), følger med.
     * `fit`: flyt indholdet op i hjørnet og gør tegningen præcis stor nok + `margin` (baggrunden tæller ikke med).
     * → { w, h } eller { error }.
     */
    setSize(w, h, fit = false, margin = 20) {
      const c = canvas();
      const content = c.getSvgContent();
      const old = c.getResolution();
      const oldW = Math.round(old.w), oldH = Math.round(old.h);
      const bg = content.querySelector('#baggrund');
      const fillsAll = (el) => el && Number(el.getAttribute('x') || 0) === 0 && Number(el.getAttribute('y') || 0) === 0 &&
        Math.round(Number(el.getAttribute('width'))) === oldW && Math.round(Number(el.getAttribute('height'))) === oldH && !el.getAttribute('transform');
      const background = fillsAll(bg) ? bg : null;
      const batch = new c.history.BatchCommand(fit ? 'Tilpas til indholdet' : 'Tegningens størrelse');
      if (fit) {
        const els = Array.from(content.querySelectorAll('g.layer > *')).filter((el) =>
          el !== background && !RESERVED.has(el.tagName.toLowerCase()) && el.getAttribute('display') !== 'none');
        const box = unionBox(els.map((el) => { try { return boxOf(el); } catch { return null; } }).filter((b) => b && (b.w > 0 || b.h > 0)));
        if (!box) return { error: 'Tegningen er tom — der er intet at tilpasse til' };
        const dx = Math.round(margin - box.x), dy = Math.round(margin - box.y);
        if (dx || dy) {
          c.clearSelection();
          c.addToSelection(els);
          const cmd = c.moveSelectedElements(els.map(() => dx), els.map(() => dy), false);
          if (cmd) batch.addSubCommand(cmd);
          c.clearSelection();
        }
        w = Math.ceil(box.w + 2 * margin);
        h = Math.ceil(box.h + 2 * margin);
      }
      w = Math.max(100, Math.min(10000, Math.round(w)));
      h = Math.max(100, Math.min(10000, Math.round(h)));
      if (w === oldW && h === oldH && batch.isEmpty()) return { w, h };
      const oldViewBox = content.getAttribute('viewBox');
      content.setAttribute('width', w);
      content.setAttribute('height', h);
      content.setAttribute('viewBox', `0 0 ${w} ${h}`);
      c.contentW = w;
      c.contentH = h;
      batch.addSubCommand(new c.history.ChangeElementCommand(content, { width: oldW, height: oldH, viewBox: oldViewBox }));
      if (background) {
        background.setAttribute('width', w);
        background.setAttribute('height', h);
        batch.addSubCommand(new c.history.ChangeElementCommand(background, { width: oldW, height: oldH }));
      }
      c.undoMgr.addCommandToHistory(batch);
      c.call('changed', [content]);
      host.updateCanvas();
      drawGrid();
      if (changeListener) changeListener();
      return { w, h };
    },

    /** Omskifterens positionsnavne, som de står i tegningen (teksterne uden for grebet), i rækkefølge (v0.91.1). */
    selectorLabels(id) {
      const el = canvas().getSvgContent().querySelector(`#${CSS.escape(id)}`);
      if (!el) return [];
      return [...el.querySelectorAll('text')].filter((t) => !t.closest('[data-hv-pid="greb"]')).map((t) => (t.textContent || '').trim());
    },

    /** Id'et på symbolets del med bibliotekets navn `pid` (fx "greb"), eller null. */
    partIdByPid(id, pid) {
      const el = canvas().getSvgContent().querySelector(`#${CSS.escape(id)}`);
      return el?.querySelector(`[data-hv-pid="${CSS.escape(pid)}"]`)?.id ?? null;
    },

    /** Navne, som flere symboler i tegningen deler (v0.89.0): [{ name, count }]. */
    duplicateNames() {
      return duplicateNames(Array.from(canvas().getSvgContent().querySelectorAll('[data-hv-name]')).map((el) => el.getAttribute('data-hv-name')));
    },

    /** Giv symboler med samme navn unikke navne (det første beholder sit) — ét fortryd-trin. → [{ id, from, to }] */
    fixDuplicateNames() {
      const c = canvas();
      const els = Array.from(c.getSvgContent().querySelectorAll('[data-hv-name]'));
      const renames = uniqueRenames(els.map((el) => el.getAttribute('data-hv-name')));
      const batch = new c.history.BatchCommand('Unikke navne');
      const out = [];
      els.forEach((el, i) => {
        if (renames[i] === null) return;
        const from = el.getAttribute('data-hv-name');
        el.setAttribute('data-hv-name', renames[i]);
        batch.addSubCommand(new c.history.ChangeElementCommand(el, { 'data-hv-name': from }, 'navn'));
        out.push({ id: el.id, from, to: renames[i] });
      });
      if (!out.length) return out;
      c.undoMgr.addCommandToHistory(batch);
      if (changeListener) changeListener();
      if (selectionListener) selectionListener(currentSelection());
      return out;
    },

    nameElements(ids, base) {
      const c = canvas();
      const root = c.getSvgContent();
      const els = ids.map((id) => root.querySelector(`[id="${CSS.escape(id)}"]`)).filter((el) => el && !el.getAttribute('data-hv-name'))
        // løbenumre i tegningens rækkefølge (ikke den rækkefølge delene blev valgt i)
        .sort((x, y) => (x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
      if (!els.length) return {};
      const used = Array.from(root.querySelectorAll('[data-hv-name]')).map((el) => el.getAttribute('data-hv-name'));
      const names = numberedNames(base, els.length, used);
      const batch = new c.history.BatchCommand('Navngiv symboler');
      const out = {};
      els.forEach((el, i) => {
        el.setAttribute('data-hv-name', names[i]);
        batch.addSubCommand(new c.history.ChangeElementCommand(el, { 'data-hv-name': null }, 'navn'));
        out[el.id] = names[i];
      });
      c.undoMgr.addCommandToHistory(batch);
      if (changeListener) changeListener();
      if (selectionListener) selectionListener(currentSelection());
      return out;
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

  scada.dispose = () => life.abort();
  /** Tegn gitteret igen (fx efter zoom i den nye editor, som ikke går gennem lærredets 'zoomed'). */
  scada.redrawGrid = () => drawGrid();
  return scada;
}
