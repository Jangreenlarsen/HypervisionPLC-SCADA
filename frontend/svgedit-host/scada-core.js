// Kernen i Tegn: alt vores eget oven på SVG-Edits tegnemotor (`@svgedit/svgcanvas`) — gitter, fang, id'er, navne,
// symboler og API'et som Tegn-siden bruger. Kender ikke SVG-Edits brugerflade: værten giver lærredet og de få ting,
// der afhænger af den omgivende side (genindlæsning, lærredets størrelse, laget til gitteret).
import {
  axisAngle, centroid, directionAngle, gridCorrection, identityMatrix, invertMatrix, isDrag, fieldResize, multiplyMatrix, pathVertices, recenterOffset, rotationCenter, snapToObjects, transformBox, triangleApex, turnAxis, turnTo, unionBox,
} from './snap.js';
import { collectColors, recolorAttrs } from './colors.js';
import { duplicateNames, nextFreeName, numberedNames, uniqueRenames } from './names.js';
import { boxMapping, distribute as distributeBoxes, editBox, round2 } from './edit.js';
import { autoPortsWithSide, boxOfRoot, formatPorts, parsePorts } from './symbolPorts.js';
import { PIPE_STYLE, axisOf, axisOfDir, branchSide, endDir, mergeRoutes, moveSegment, segmentHandles, extendRoute, formatRef, fracSide, fromFrac, nearest, nearestOnRoute, parseRef, pathD, pipeCorners, pipePath, reroute, sideDir, simplify, splitRoute, turnDir } from './pipes.js';

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
      drawHandles();
    });
    const prevChanged = c.bind('changed', (win, elems) => {
      // før editorens egen håndtering: den skriver contentW/H tilbage i viewBox (updateCanvas)
      syncContentSize();
      if (prevChanged) prevChanged(win, elems);
      if (changeListener) changeListener();
      if (selectionListener) selectionListener(currentSelection());
      drawHandles();
    });
    // SVG-Edit sender ikke 'changed' efter en flytning med musen, så vi lytter selv på museknappen (efter editorens egen
    // håndtering): ved nedtryk huskes de valgte elementers placering, ved slip fanges der — hvis det var et træk.
    document.addEventListener('mousedown', () => setTimeout(rememberBoxes, 0), { capture: true, signal: life.signal });
    document.addEventListener('mouseup', () => setTimeout(() => { if (!snapping && !handles.busy) settleAfterMouseUp(); handles.busy = false; drawHandles(); }, 0), { capture: true, signal: life.signal });
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
  let libraryPorts = {};   // symboltype → rettede punkter (sat af Tegn fra /api/symbol-ports)

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
    const type = String(baseId).toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 40);
    node.setAttribute('data-hv-type', type);
    // Rettede tilslutningspunkter (symbol-editoren) følger med det nye symbol — symboler der allerede står i
    // tegningen beholder deres egne
    const lp = libraryPorts[type];
    if (Array.isArray(lp) && lp.length) node.setAttribute('data-hv-ports', formatPorts(lp));
    else node.removeAttribute('data-hv-ports');
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

  /** Symbolets tilslutningspunkter: [{ local, doc, axis }] — axis = retningen et rør bør starte i ('h' fra en sidekant). */
  function portsOf(el) {
    const box = boxOfRoot(el);
    if (!box) return [];
    const m = toDocMatrix(el);
    // rettede punkter fra symbol-editoren (bygget ind ved indsættelse) går forud for de automatiske
    const fixed = parsePorts(el.getAttribute('data-hv-ports'));
    const list = fixed ? fixed.map((f) => ({ frac: [f[0], f[1]], side: f[2] ?? fracSide(f) })) : autoPortsWithSide(el);
    return list.map(({ frac, side }) => {
      const local = fromFrac(frac, box);
      // udadgående retning — drejer og spejler med symbolet, så røret altid går ind fra den rigtige side
      const dir = turnDir(sideDir(side), m);
      return { local, frac, side, doc: toPoint(m, local), dir, axis: axisOfDir(dir) };
    });
  }

  /** Elementer et rør kan tilsluttes: øverste niveau i lagene, ikke rør, ikke baggrunden. */
  function pipeTargets() {
    const content = canvas().getSvgContent();
    return [...content.querySelectorAll('g.layer > *')].filter((el) =>
      el.id && el.id !== 'baggrund' && !isPipe(el) && !RESERVED.has(el.tagName.toLowerCase()) && el.getAttribute('display') !== 'none');
  }

  /** Rørets knækpunkter (også når det er tegnet med bløde bøjninger). */
  function pipePoints(el) {
    return pipeCorners(el.getAttribute('d'));
  }
  const radiusOf = (el) => Math.max(0, Number(el.getAttribute('data-hv-radius')) || 0);
  /** Tegn røret ud fra knækpunkterne med rørets bøjningsradius. */
  function drawPipe(el, pts) {
    const d = pipePath(pts, radiusOf(el));
    if (d !== el.getAttribute('d')) el.setAttribute('d', d);
  }

  /** Hvor rørets ende skal være nu: { p, dir } i tegningens koordinater, eller null hvis den ikke sidder fast. */
  function endTarget(el, attr) {
    const ref = parseRef(el.getAttribute(attr));
    if (!ref) return null;
    const sym = canvas().getSvgContent().querySelector(`[id="${CSS.escape(ref.id)}"]`);
    if (!sym) return null;   // symbolet er slettet: enden bliver hvor den er
    let bb;
    try { bb = sym.getBBox(); } catch { return null; }
    const m = toDocMatrix(sym);
    const dir = turnDir(sideDir(ref.side ?? fracSide(ref.local)), m);
    return { p: toPoint(m, fromFrac(ref.local, { x: bb.x, y: bb.y, w: bb.width, h: bb.height })), dir };
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
          const target = endTarget(el, attr)?.p;
          const end = ends[attr];
          if (target && end && Math.hypot(target[0] - end[0], target[1] - end[1]) > 0.5) el.removeAttribute(attr);
          // fri ende, der er landet på et tilslutningspunkt: sæt den fast igen (v3.3.0)
          if (end && !el.hasAttribute(attr)) {
            const hit = portNear(end, RECONNECT_TOL);
            if (hit) {
              el.setAttribute(attr, formatRef(hit.id, hit.frac, hit.side));
              drawPipe(el, reroute(pipePoints(el), attr === 'data-hv-from' ? 'start' : 'end', hit.doc, hit.dir));
            }
          }
        }
      } else {
        if (el.getAttribute('transform')) continue;   // et transformeret rør (sjældent): rør det ikke
        let pts = pipePoints(el);
        if (pts.length < 2) continue;
        const from = endTarget(el, 'data-hv-from');
        const to = endTarget(el, 'data-hv-to');
        const off = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) > 0.01;
        // går det sidste stykke ind i punktet fra den forkerte side (fx efter drejning), lægges enden også om
        const wrongWay = (end, prev, dir) => {
          const dx = end[0] - prev[0], dy = end[1] - prev[1];
          return dx * dir[0] + dy * dir[1] > 0.01;   // bevæger sig udad ind i punktet = kommer gennem symbolet
        };
        if (from && (off(from.p, pts[0]) || wrongWay(pts[0], pts[1], from.dir))) pts = reroute(pts, 'start', from.p, from.dir);
        const n = pts.length;
        if (to && (off(to.p, pts[n - 1]) || wrongWay(pts[n - 1], pts[n - 2], to.dir))) pts = reroute(pts, 'end', to.p, to.dir);
        drawPipe(el, pts);
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

  // ---- rør-ende på rør-ende (v3.4.0)
  /** Nærmeste rør-ende inden for tol (ikke `except`): { el, which, p, dist } eller null. */
  function pipeEndNear(p, tol, except = null) {
    let best = null;
    for (const el of canvas().getSvgContent().querySelectorAll('[data-hv-pipe]')) {
      if (el === except || el.getAttribute('transform')) continue;
      const pts = pipePoints(el);
      if (pts.length < 2) continue;
      for (const [which, q] of [['start', pts[0]], ['end', pts[pts.length - 1]]]) {
        const dist = Math.hypot(q[0] - p[0], q[1] - p[1]);
        if (dist <= tol && (!best || dist < best.dist)) best = { el, which, p: q, dist };
      }
    }
    return best;
  }
  /** Nærmeste punkt midt på et rør (til et T-stykke) inden for tol: { el, k, q, dist } eller null. */
  function pipeMidNear(p, tol, except = null) {
    let best = null;
    for (const el of canvas().getSvgContent().querySelectorAll('[data-hv-pipe]')) {
      if (el === except || el.getAttribute('transform')) continue;
      const hit = nearestOnRoute(pipePoints(el), p);
      if (hit && hit.dist <= tol && (!best || hit.dist < best.dist)) best = { el, k: hit.k, q: hit.q, dist: hit.dist };
    }
    return best;
  }
  const attrsOf = (el) => Object.fromEntries([...el.attributes].map((x) => [x.name, x.value]));
  /** Fortryd-kommando for ændringerne på el siden `before` (attributterne). */
  function changeCmd(el, before) {
    const old = {};
    for (const k of new Set([...Object.keys(before), ...[...el.attributes].map((x) => x.name)])) {
      if (before[k] !== el.getAttribute(k)) old[k] = before[k] ?? null;
    }
    return new (canvas().history.ChangeElementCommand)(el, old);
  }
  function removeCmd(el) {
    const parent = el.parentNode, next = el.nextSibling;
    el.remove();
    return new (canvas().history.RemoveElementCommand)(el, next, parent);
  }
  /** Rørets anden endes reference: den ende der IKKE er `which`. */
  const otherRef = (el, which) => el.getAttribute(which === 'start' ? 'data-hv-to' : 'data-hv-from');
  const named = (el) => !!el.getAttribute('data-hv-name');

  /**
   * Læg to rør sammen, hvor A's ende `aWhich` (punkterne `aPts`) møder B's ende `bWhich`. Det rør, der har en opsætning
   * (navn), bevares; har begge, lægges de ikke sammen (→ null). → { keep, cmds }.
   */
  function joinPipes(A, aPts, aWhich, B, bWhich) {
    if (named(A) && named(B)) return null;
    const route = mergeRoutes(aPts, aWhich, pipePoints(B), bWhich);   // fra A's anden ende til B's anden ende
    const refStart = otherRef(A, aWhich);
    const refEnd = otherRef(B, bWhich);
    const keep = named(B) ? B : A;
    const drop = keep === A ? B : A;
    const before = attrsOf(keep);
    drawPipe(keep, route);
    if (refStart) keep.setAttribute('data-hv-from', refStart); else keep.removeAttribute('data-hv-from');
    if (refEnd) keep.setAttribute('data-hv-to', refEnd); else keep.removeAttribute('data-hv-to');
    return { keep, cmds: [changeCmd(keep, before), removeCmd(drop)] };
  }
  function commitCmds(label, cmds) {
    const c = canvas();
    const batch = new c.history.BatchCommand(label);
    for (const cmd of cmds) batch.addSubCommand(cmd);
    if (!batch.isEmpty()) c.undoMgr.addCommandToHistory(batch);
  }

  // ---- genforbind: håndtag på det valgte rørs ender (v3.3.0)
  const RECONNECT_TOL = 6;   // en flyttet rør-ende inden for så mange enheder af et punkt sættes fast igen
  /** Alle tilslutningspunkter i tegningen (med symbolets id). */
  const allPorts = () => pipeTargets().flatMap((el) => portsOf(el).map((q) => ({ ...q, id: el.id })));
  function portNear(p, tol) {
    let best = null;
    for (const q of allPorts()) {
      const d = Math.hypot(q.doc[0] - p[0], q.doc[1] - p[1]);
      if (d <= tol && (!best || d < best.d)) best = { ...q, d };
    }
    return best;
  }

  // busy: et håndtag-træk er i gang/netop slut — så må "fang efter træk" ikke flytte røret bagefter (BUGS.md v3.6.0)
  const handles = { layer: null, drag: null, busy: false };
  function selectedPipe() {
    const sel = selectedEls();
    return sel.length === 1 && isPipe(sel[0]) && !sel[0].getAttribute('transform') ? sel[0] : null;
  }

  /** Tegn håndtagene (og under træk: punkterne og det nye forløb). */
  function drawHandles() {
    const gridHost = host.gridHost();
    const content = canvas()?.getSvgContent?.();
    if (!gridHost || !content) return;
    const el = handles.drag?.el ?? (pipeTool.on ? null : selectedPipe());
    if (!el) { handles.layer?.remove(); handles.layer = null; return; }
    let layer = handles.layer;
    if (!layer) {
      layer = document.createElementNS(NS, 'svg');
      layer.setAttribute('id', 'hvPipeHandles');
      layer.style.cssText = 'position:absolute; pointer-events:none; z-index:56; overflow:visible;';
      gridHost.appendChild(layer);
      handles.layer = layer;
      layer.addEventListener('mousedown', startHandleDrag);
      // Håndtagene tegnes, så snart røret er valgt — ofte lige under musen. Lander museslippet så på et håndtag, får
      // lærredet det aldrig og tror, at knappen stadig er nede (næste træk flyttede hele røret). Send det videre.
      layer.addEventListener('mouseup', (ev) => { const c = canvas(); if (c.getStarted?.()) c.mouseUpEvent?.(ev); });
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
    const drag = handles.drag;
    const pts = drag ? drag.preview : pipePoints(el);
    let out = '';
    if (drag && drag.seg !== undefined) {
      out += `<path d="${pipePath(pts, radiusOf(el))}" fill="none" stroke="#1565c0" stroke-width="${2 / z}" stroke-dasharray="${5 / z} ${3 / z}"/>`;
    } else if (drag) {
      out += drag.ports.map((q) => {
        const hot = drag.hit && q.doc === drag.hit.doc;
        return `<circle cx="${q.doc[0]}" cy="${q.doc[1]}" r="${(hot ? 7 : 4) / z}" fill="${hot ? '#2e7d32' : '#fff'}" stroke="#2e7d32" stroke-width="${1.5 / z}"/>`;
      }).join('');
      const spot = drag.hitEnd?.p ?? drag.hitMid?.q;
      if (spot) out += `<circle cx="${spot[0]}" cy="${spot[1]}" r="${7 / z}" fill="#ef6c00" stroke="#fff" stroke-width="${1.5 / z}"/>`;
      out += `<path d="${pipePath(pts, radiusOf(el))}" fill="none" stroke="#2e7d32" stroke-width="${2 / z}" stroke-dasharray="${5 / z} ${3 / z}"/>`;
    }
    // håndtag midt på hvert stykke: træk på tværs for at flytte stykket (enderne bliver siddende, v3.6.0)
    if (!drag || drag.seg !== undefined) {
      for (const h of segmentHandles(pts, 24 / z)) {
        const w = (h.axis === 'h' ? 18 : 8) / z, hgt = (h.axis === 'h' ? 8 : 18) / z;
        out += `<rect data-seg="${h.k}" x="${h.mid[0] - w / 2}" y="${h.mid[1] - hgt / 2}" width="${w}" height="${hgt}" rx="${3 / z}" ` +
          `fill="#fff" stroke="#1565c0" stroke-width="${1.5 / z}" style="pointer-events:all; cursor:${h.axis === 'h' ? 'ns-resize' : 'ew-resize'}">` +
          `<title>Træk for at flytte dette stykke af røret — enderne bliver siddende</title></rect>`;
      }
    }
    for (const which of ['start', 'end']) {
      const p = which === 'start' ? pts[0] : pts[pts.length - 1];
      if (!p) continue;
      const attr = which === 'start' ? 'data-hv-from' : 'data-hv-to';
      const fixed = (!drag || drag.seg !== undefined) && el.hasAttribute(attr);
      out += `<rect data-end="${which}" x="${p[0] - 6 / z}" y="${p[1] - 6 / z}" width="${12 / z}" height="${12 / z}" ` +
        `fill="${fixed ? '#2e7d32' : '#ef6c00'}" stroke="#fff" stroke-width="${1.5 / z}" style="pointer-events:all; cursor:move">` +
        `<title>${fixed ? 'Sidder fast — træk for at flytte enden til et andet punkt' : 'Fri ende — træk hen på et tilslutningspunkt for at sætte den fast'}</title></rect>`;
    }
    layer.innerHTML = out;
  }

  /** Træk et stykke af det valgte rør på tværs. */
  function startSegmentDrag(e, el, k) {
    e.stopPropagation();
    e.preventDefault();
    const base = pipePoints(el);
    const axis = axisOf(base[k], base[k + 1]);
    const from = docPoint(e);
    handles.drag = { el, seg: k, base, preview: base, ports: [] };
    handles.busy = true;
    const life = new AbortController();
    const move = (ev) => {
      const p = docPoint(ev);
      let delta = axis === 'h' ? p[1] - from[1] : p[0] - from[0];
      if (guides.snapGrid) {
        // det flyttede stykke lægges på gitteret
        const at = (axis === 'h' ? base[k][1] : base[k][0]) + delta;
        delta = Math.round(at / guides.step) * guides.step - (axis === 'h' ? base[k][1] : base[k][0]);
      }
      handles.drag.preview = moveSegment(base, k, delta);
      drawHandles();
    };
    const up = () => {
      life.abort();
      const d = handles.drag;
      handles.drag = null;
      if (d && d.preview !== d.base) {
        const before = attrsOf(el);
        drawPipe(el, d.preview);
        commitCmds('Rør-stykke flyttet', [changeCmd(el, before)]);
        afterEdit();
      }
      drawHandles();
    };
    document.addEventListener('mousemove', move, { signal: life.signal, capture: true });
    document.addEventListener('mouseup', up, { signal: life.signal, capture: true });
    drawHandles();
  }

  function startHandleDrag(e) {
    const seg = e.target?.getAttribute?.('data-seg');
    if (seg !== null && seg !== undefined && e.button === 0) {
      const el = selectedPipe();
      if (el) startSegmentDrag(e, el, Number(seg));
      return;
    }
    const which = e.target?.getAttribute?.('data-end');
    const el = selectedPipe();
    if (!which || !el || e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    const base = pipePoints(el);
    handles.drag = { el, which, base, preview: base, hit: null, ports: allPorts() };
    handles.busy = true;
    const life = new AbortController();
    const move = (ev) => {
      const raw = docPoint(ev);
      const z = canvas().getZoom() || 1;
      const tol = 12 / z;
      const d = handles.drag;
      const hit = nearest(d.ports.map((q) => q.doc), raw, tol);
      const port = hit ? d.ports.find((q) => q.doc === hit) : null;
      // ellers: en anden rør-ende (lægges sammen) eller midt på et rør (T-stykke)
      const end = port ? null : pipeEndNear(raw, tol, el);
      const mid = port || end ? null : pipeMidNear(raw, tol, el);
      d.hit = port;
      d.hitEnd = end;
      d.hitMid = mid;
      const neighbor = which === 'start' ? base[1] : base[base.length - 2];
      if (port) d.preview = reroute(base, which, port.doc, port.dir);
      else if (end) d.preview = reroute(base, which, end.p, endDir(pipePoints(end.el), end.which));
      else if (mid) d.preview = reroute(base, which, mid.q, acrossDir(mid, neighbor));
      else d.preview = reroute(base, which, guides.snapGrid ? raw.map((v) => Math.round(v / guides.step) * guides.step) : raw, null);
      drawHandles();
    };
    const up = () => {
      life.abort();
      const d = handles.drag;
      handles.drag = null;
      if (d && d.preview !== d.base) {
        const attr = which === 'start' ? 'data-hv-from' : 'data-hv-to';
        const before = attrsOf(el);
        let done = false;
        if (d.hitEnd) {
          // rør-ende på rør-ende: ét rør
          const j = joinPipes(el, d.preview, which, d.hitEnd.el, d.hitEnd.which);
          if (j) {
            commitCmds('Rør lagt sammen', j.cmds);
            canvas().clearSelection();
            canvas().addToSelection([j.keep]);
            done = true;
          }
        } else if (d.hitMid) {
          // midt på et rør: T-stykke
          const neighbor = which === 'start' ? d.preview[1] : d.preview[d.preview.length - 2];
          const t = makeTee(d.hitMid, neighbor);
          if (t) {
            drawPipe(el, reroute(d.base, which, t.port.doc, t.port.dir));
            el.setAttribute(attr, formatRef(t.node.id, t.port.frac, t.port.side));
            commitCmds('Rør med T-stykke', [...t.cmds, changeCmd(el, before)]);
            done = true;
          }
        }
        if (!done) {
          drawPipe(el, d.preview);
          if (d.hit) el.setAttribute(attr, formatRef(d.hit.id, d.hit.frac, d.hit.side));
          else el.removeAttribute(attr);
          commitCmds(d.hit ? 'Rør sat fast' : 'Rør-ende flyttet', [changeCmd(el, before)]);
        }
        afterEdit();
      }
      drawHandles();
    };
    document.addEventListener('mousemove', move, { signal: life.signal, capture: true });
    document.addEventListener('mouseup', up, { signal: life.signal, capture: true });
    drawHandles();
  }

  // ---- værktøjet: klik punkter, klik på et tilslutningspunkt (eller dobbeltklik/Enter) for at slutte, Escape fortryder
  const pipeDefaults = { radius: 0 };   // bøjningsradius for nye rør (senest brugte)
  const pipeTool = { on: false, pts: [], from: null, fromDir: null, cursor: null, hover: null, ports: [], overlay: null, life: null };

  /**
   * Skærmpunkt → tegningens koordinater, beregnet frisk som lærredet gør det (første gruppe i tegningen). Ikke
   * getrootSctm(): den sættes først, når lærredet selv får et museklik — forældet efter zoom/rulning og ved
   * træk-og-slip (BUGS.md v2.17.0).
   */
  function screenToDoc(clientX, clientY) {
    const g = canvas().getSvgContent()?.querySelector('g');
    const m = g?.getScreenCTM?.();
    if (!m) return [clientX, clientY];
    const p = new DOMPoint(clientX, clientY).matrixTransform(m.inverse());
    return [p.x, p.y];
  }
  const docPoint = (e) => screenToDoc(e.clientX, e.clientY);
  function snapPipePoint(raw) {
    const tol = 12 / (canvas().getZoom() || 1);
    const port = nearest(pipeTool.ports.map((q) => q.doc), raw, tol);
    if (port) return { p: port, port: pipeTool.ports.find((q) => q.doc === port) };
    // en rør-ende: røret fortsættes / lægges sammen
    const pipeEnd = pipeEndNear(raw, tol);
    if (pipeEnd) return { p: pipeEnd.p, port: null, pipeEnd };
    // på et eksisterende rør: her bliver der et T-stykke (røret deles)
    let onPipe = null;
    for (const el of canvas().getSvgContent().querySelectorAll('[data-hv-pipe]')) {
      if (el.getAttribute('transform')) continue;
      const hit = nearestOnRoute(pipePoints(el), raw);
      if (hit && hit.dist <= tol && (!onPipe || hit.dist < onPipe.dist)) onPipe = { el, k: hit.k, q: hit.q, dist: hit.dist };
    }
    if (onPipe) return { p: onPipe.q, port: null, onPipe };
    if (guides.snapGrid) return { p: [Math.round(raw[0] / guides.step) * guides.step, Math.round(raw[1] / guides.step) * guides.step], port: null };
    return { p: raw, port: null };
  }
  /** Røret forlænget hen til p: ud af startpunktets retning, ind i et punkt langs dets retning (pipes.js extendRoute). */
  function routeTo(p, port = null, onPipe = null) {
    const pts = pipeTool.pts;
    let startDir = pipeTool.fromDir;
    if (!startDir && pipeTool.fromTee && pts.length === 1) startDir = acrossDir(pipeTool.fromTee, p);
    const endDir = port?.dir ?? (onPipe ? acrossDir(onPipe, pts[pts.length - 1]) : null);
    return extendRoute(pts, p, startDir, endDir);
  }
  /** Retningen på tværs af røret i punktet info.q, mod `toward`. */
  function acrossDir(info, toward) {
    const pts = pipePoints(info.el);
    const axis = axisOf(pts[info.k], pts[info.k + 1]);
    if (axis === 'h') return [0, toward[1] < info.q[1] ? -1 : 1];
    return [toward[0] < info.q[0] ? -1 : 1, 0];
  }

  // ---- T-stykke: røret deles, og bibliotekets T-stykke sættes ind (tre ben, hvert med sit eget løbelys i guiden)
  let teeSymbol = null;   // { fragment, label } — sat af Tegn fra symbolbiblioteket
  const TEE_ANGLE = { t: 0, r: 90, b: 180, l: -90 };   // T-stykket har grenen opad; drej så den vender mod grenen
  /**
   * Del røret info.el i info.q og indsæt et T-stykke dér, med grenen mod `toward`. Halvdelene sættes fast i T-stykkets
   * gennemløb. → { cmds, port } (port = grenens tilslutningspunkt) eller null.
   */
  function makeTee(info, toward) {
    const c = canvas();
    if (!teeSymbol) return null;
    const el = info.el;
    const pts = pipePoints(el);
    const [p1, p2] = splitRoute(pts, info.k, info.q);
    if (p1.length < 2 || p2.length < 2) return null;
    const axis = axisOf(pts[info.k], pts[info.k + 1]);
    if (!axis) return null;
    const side = branchSide(axis === 'h' ? ['l', 'r'] : ['t', 'b'], info.q, toward) ?? 't';
    const node = buildSymbolNode(teeSymbol.fragment, 't_stykke');
    if (!node) return null;
    node.setAttribute('data-hv-name', uniqueNameIn(teeSymbol.label));
    // benenes ender som punkter med side (gennemløb venstre/højre, gren op) — medmindre biblioteket har rettede punkter
    if (!node.hasAttribute('data-hv-ports')) node.setAttribute('data-hv-ports', '0,1,l;1,1,r;0.5,0,t');
    el.after(node);
    const bb = node.getBBox();
    const cx = bb.x + bb.width / 2, cy = bb.y + bb.height / 2;
    const a = TEE_ANGLE[side] * Math.PI / 180;
    // samlingspunktet (gennemløbets midte: bund-midten af benene) skal ligge i q
    const jx = bb.x + bb.width / 2, jy = bb.y + bb.height;
    const rx = cx + (jx - cx) * Math.cos(a) - (jy - cy) * Math.sin(a);
    const ry = cy + (jx - cx) * Math.sin(a) + (jy - cy) * Math.cos(a);
    const r = (v) => Math.round(v * 100) / 100;
    node.setAttribute('transform', `translate(${r(info.q[0] - rx)} ${r(info.q[1] - ry)})${TEE_ANGLE[side] ? ` rotate(${TEE_ANGLE[side]} ${r(cx)} ${r(cy)})` : ''}`);
    const ports = portsOf(node);
    const pick = (towardPt, taken) => ports.filter((q) => !taken.includes(q)).sort((u, v) => {
      const d = (q) => { const dx = towardPt[0] - info.q[0], dy = towardPt[1] - info.q[1]; return q.dir[0] * dx + q.dir[1] * dy; };
      return d(v) - d(u);
    })[0];
    const portA = pick(p1[p1.length - 2], []);
    const portB = pick(p2[1], [portA]);
    const portC = ports.find((q) => q !== portA && q !== portB);
    if (!portA || !portB || !portC) { node.remove(); return null; }
    const before = Object.fromEntries([...el.attributes].map((x) => [x.name, x.value]));
    // første halvdel: det eksisterende rør (beholder id, navn og opsætning)
    drawPipe(el, reroute(p1, 'end', portA.doc, portA.dir));
    el.setAttribute('data-hv-to', formatRef(node.id, portA.frac, portA.side));
    // anden halvdel: nyt rør med samme udseende, uden navn/opsætning
    const el2 = el.cloneNode(false);
    el2.setAttribute('id', c.getNextId());
    for (const k of ['data-hv-name', 'data-hv-desc']) el2.removeAttribute(k);
    el2.setAttribute('data-hv-from', formatRef(node.id, portB.frac, portB.side));
    if (before['data-hv-to']) el2.setAttribute('data-hv-to', before['data-hv-to']); else el2.removeAttribute('data-hv-to');
    drawPipe(el2, reroute(p2, 'start', portB.doc, portB.dir));
    el.after(el2);
    const old = {};
    for (const k of new Set([...Object.keys(before), ...[...el.attributes].map((x) => x.name)])) {
      if (before[k] !== el.getAttribute(k)) old[k] = before[k] ?? null;
    }
    const cmds = [new c.history.ChangeElementCommand(el, old), new c.history.InsertElementCommand(el2), new c.history.InsertElementCommand(node)];
    return { cmds, port: portC, node };
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
    if (!pipeTool.pts.length && pipeTool.hoverPipe) {
      const q = pipeTool.hoverPipe.q;
      preview += `<circle cx="${q[0]}" cy="${q[1]}" r="${7 / z}" fill="#ef6c00" stroke="#fff" stroke-width="${1.5 / z}"/>`;
    }
    if (pipeTool.pts.length) {
      const pts = pipeTool.cursor ? routeTo(pipeTool.cursor, pipeTool.hover, pipeTool.hoverPipe?.el ? pipeTool.hoverPipe : null) : pipeTool.pts;
      if (pipeTool.hoverPipe) {
        const q = pipeTool.hoverPipe.q;
        preview += `<circle cx="${q[0]}" cy="${q[1]}" r="${7 / z}" fill="#ef6c00" stroke="#fff" stroke-width="${1.5 / z}"/>`;
      }
      const d = pipePath(pts, pipeDefaults.radius);
      preview += `<path d="${d}" fill="none" stroke="${PIPE_STYLE.stroke}" stroke-opacity=".55" stroke-width="${PIPE_STYLE['stroke-width']}"/>` +
        `<path d="${d}" fill="none" stroke="#2e7d32" stroke-width="${1.5 / z}" stroke-dasharray="${4 / z} ${3 / z}"/>`;
    }
    layer.innerHTML = preview + dots;
  }

  function finishPipe() {
    const c = canvas();
    let pts = simplify(pipeTool.pts);
    let fromRef = pipeTool.from;
    let toRef = pipeTool.to ?? null;
    const fromTee = pipeTool.fromTee;
    let toTee = pipeTool.toTee;
    const fromEnd = pipeTool.fromEnd;
    const toEnd = pipeTool.toEnd;
    pipeTool.pts = [];
    pipeTool.from = pipeTool.fromDir = pipeTool.to = pipeTool.fromTee = pipeTool.toTee = pipeTool.fromEnd = pipeTool.toEnd = null;
    const teeCmds = [];
    if (pts.length >= 2) {
      // begge ender på samme rør: kun starten bliver et T (det andet punkt ligger på et rør, der netop er delt)
      if (fromTee && toTee && fromTee.el === toTee.el) toTee = null;
      if (fromTee) {
        const t = makeTee(fromTee, pts[1]);
        if (t) {
          teeCmds.push(...t.cmds);
          pts = reroute(pts, 'start', t.port.doc, t.port.dir);
          fromRef = formatRef(t.node.id, t.port.frac, t.port.side);
        }
      }
      if (toTee) {
        const t = makeTee(toTee, pts[pts.length - 2]);
        if (t) {
          teeCmds.push(...t.cmds);
          pts = reroute(pts, 'end', t.port.doc, t.port.dir);
          toRef = formatRef(t.node.id, t.port.frac, t.port.side);
        }
      }
    }
    if (pts.length >= 2 && (fromEnd || toEnd)) {
      // startet/sluttet på en rør-ende: det nye stykke bliver en del af det eksisterende rør
      const cmds = [...teeCmds];
      let keep = null;
      let route = pts;
      if (fromEnd) {
        const before = attrsOf(fromEnd.el);
        route = mergeRoutes(pipePoints(fromEnd.el), fromEnd.which, route, 'start');
        const refStart = otherRef(fromEnd.el, fromEnd.which);
        keep = fromEnd.el;
        drawPipe(keep, route);
        if (refStart) keep.setAttribute('data-hv-from', refStart); else keep.removeAttribute('data-hv-from');
        if (toRef) keep.setAttribute('data-hv-to', toRef); else keep.removeAttribute('data-hv-to');
        cmds.push(changeCmd(keep, before));
      }
      if (toEnd && toEnd.el !== keep) {
        if (keep) {
          const j = joinPipes(keep, pipePoints(keep), 'end', toEnd.el, toEnd.which);
          if (j) { cmds.push(...j.cmds); keep = j.keep; }
        } else {
          const before = attrsOf(toEnd.el);
          keep = toEnd.el;
          route = mergeRoutes(route, 'end', pipePoints(keep), toEnd.which);
          const refEnd = otherRef(keep, toEnd.which);
          drawPipe(keep, route);
          if (fromRef) keep.setAttribute('data-hv-from', fromRef); else keep.removeAttribute('data-hv-from');
          if (refEnd) keep.setAttribute('data-hv-to', refEnd); else keep.removeAttribute('data-hv-to');
          cmds.push(changeCmd(keep, before));
        }
      }
      if (keep) {
        commitCmds('Rør forlænget', cmds);
        c.clearSelection();
        c.addToSelection([keep]);
        if (changeListener) changeListener();
        drawPipeOverlay();
        return;
      }
    }
    if (pts.length >= 2) {
      const el = document.createElementNS(NS, 'path');
      el.setAttribute('id', c.getNextId());
      for (const [k, v] of Object.entries(PIPE_STYLE)) el.setAttribute(k, v);
      el.setAttribute('data-hv-pipe', '1');
      if (pipeDefaults.radius > 0) el.setAttribute('data-hv-radius', String(pipeDefaults.radius));
      el.setAttribute('d', pipePath(pts, pipeDefaults.radius));
      if (fromRef) el.setAttribute('data-hv-from', fromRef);
      if (toRef) el.setAttribute('data-hv-to', toRef);
      // bag de symboler det forbinder (rør ligger under ventiler, pumper …)
      const layer = c.getCurrentDrawing().getCurrentLayer();
      const ends = [fromRef, toRef].map((r) => parseRef(r)?.id).filter(Boolean);
      const first = [...layer.children].find((ch) => ends.includes(ch.id));
      layer.insertBefore(el, first ?? null);
      if (teeCmds.length) {
        // røret, de delte rør og T-stykkerne fortrydes samlet
        const batch = new c.history.BatchCommand('Rør med T-stykke');
        for (const cmd of teeCmds) batch.addSubCommand(cmd);
        batch.addSubCommand(new c.history.InsertElementCommand(el));
        c.undoMgr.addCommandToHistory(batch);
      } else c.undoMgr.addCommandToHistory(new c.history.InsertElementCommand(el));
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
    if (!on) { drawPipeOverlay(); drawHandles(); return; }
    if (modeListener) modeListener('pipe');
    handles.layer?.remove(); handles.layer = null;
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
      const { p, port, onPipe, pipeEnd } = snapPipePoint(docPoint(e));
      if (!pipeTool.pts.length) {
        pipeTool.pts = [p];
        pipeTool.fromTee = onPipe ?? null;
        pipeTool.fromEnd = pipeEnd ?? null;
        // fra en rør-ende: fortsæt i rørets retning
        if (pipeEnd) pipeTool.fromDir = endDir(pipePoints(pipeEnd.el), pipeEnd.which);
        pipeTool.from = port ? formatRef(port.id, port.frac, port.side) : null;
        pipeTool.fromDir = port?.dir ?? null;
      } else if (e.detail >= 2) {
        finishPipe();
        return;
      } else {
        // ind i en rør-ende: kom ind langs rørets retning (som et tilslutningspunkt, der peger ud af røret)
        pipeTool.pts = routeTo(p, port ?? (pipeEnd ? { dir: endDir(pipePoints(pipeEnd.el), pipeEnd.which) } : null), onPipe);
        if (pipeEnd && pipeEnd.el !== pipeTool.fromEnd?.el) { pipeTool.toEnd = pipeEnd; finishPipe(); return; }
        if (port) { pipeTool.to = formatRef(port.id, port.frac, port.side); finishPipe(); return; }
        if (onPipe) { pipeTool.toTee = onPipe; finishPipe(); return; }
      }
      drawPipeOverlay();
    }, opts);
    area.addEventListener('mousemove', (e) => {
      const { p, port, onPipe, pipeEnd } = snapPipePoint(docPoint(e));
      pipeTool.cursor = p;
      pipeTool.hover = port ?? (pipeEnd ? { dir: endDir(pipePoints(pipeEnd.el), pipeEnd.which), doc: pipeEnd.p } : null);
      pipeTool.hoverPipe = onPipe ?? (pipeEnd ? { q: pipeEnd.p } : null);
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
    queueMicrotask(() => drawHandles());
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
    // Elementets egen transform LÆSES uden consolidate(): den skriver listen om til én matrix, så fx en drejning
    // (rotate(…)) går tabt for lærredet (BUGS.md v2.15.1)
    const ownM = listMatrix(el);
    const inv = invertMatrix(ownM);
    const pureMove = near(from.w, to.w) && near(from.h, to.h);
    if (plain && pureMove) {
      // flyt: translate forrest (som lærredet selv gør), så en drejning bevares som rotate(…)
      const t = root.createSVGTransform();
      t.setTranslate(to.x - from.x, to.y - from.y);
      el.transform.baseVal.insertItemBefore(t, 0);
    } else if (plain && inv && near(ownM.b, 0) && near(ownM.c, 0)) {
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

  /** Elementets egen transform som matrix — uden at ændre transform-listen. */
  function listMatrix(el) {
    const tl = el.transform?.baseVal;
    let m = identityMatrix();
    for (let i = 0; i < (tl?.numberOfItems ?? 0); i++) {
      const t = tl.getItem(i).matrix;
      m = multiplyMatrix(m, { a: t.a, b: t.b, c: t.c, d: t.d, e: t.e, f: t.f });
    }
    return m;
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
    /** Bibliotekets T-stykke ({ fragment, label }) — bruges, når et rør kobles på et andet rør. */
    setTeeSymbol(def) { teeSymbol = def && def.fragment ? def : null; },

    /** Bibliotekets rettede tilslutningspunkter ({type: [[fx, fy], …]}) — bruges ved indsættelse af nye symboler. */
    setLibraryPorts(map) { libraryPorts = map && typeof map === 'object' ? map : {}; },

    /** Rør-værktøjet til/fra (den nye editor). Mens det er til, tager det musen fra lærredet. */
    setPipeTool(on) { setPipeTool(!!on); },
    /** Tegn rørværktøjets lag igen (efter zoom/rulning). */
    redrawPipes() { if (pipeTool.on) drawPipeOverlay(); drawHandles(); },

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
        pipeRadius: one && isPipe(one) ? radiusOf(one) : null,
      };
    },

    /** Bøjningsradius på de valgte rør (0 = skarpe knæk); bruges også til nye rør. */
    setPipeRadius(value) {
      const r = Number(value);
      if (!Number.isFinite(r) || r < 0 || r > 500) return { error: 'Radius skal være et tal mellem 0 og 500' };
      const pipes = selectedEls().filter(isPipe);
      if (!pipes.length) return { error: 'Vælg et rør' };
      const snap = snapshot(pipes);
      for (const el of pipes) {
        const pts = pipePoints(el);
        if (r > 0) el.setAttribute('data-hv-radius', String(r)); else el.removeAttribute('data-hv-radius');
        drawPipe(el, pts);
      }
      pipeDefaults.radius = r;
      commitSnapshot(snap, 'Bøjningsradius');
      afterEdit();
      return { ok: true };
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
      guides.keepRatio = !!opts.keepRatio;
      const step = Number(opts.step);
      guides.step = Number.isFinite(step) && step >= 1 ? step : 10;
      applyGuides();
    },

    /** "Skalér symmetrisk" er slået til (læses af tegnemotoren ved træk i et hjørne). */
    keepsRatio() { return !!guides.keepRatio; },

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
    /**
     * Objekttræet: lagene og deres elementer, øverst (forrest) først. → [{ layer, items: [{ id, name, type, tag, pipe, selected }] }]
     */
    objectList() {
      const content = canvas().getSvgContent();
      const sel = new Set(selectedEls());
      return [...content.querySelectorAll(':scope > g.layer')].reverse().map((layer) => ({
        layer: layer.querySelector(':scope > title')?.textContent?.trim() || 'Lag',
        items: [...layer.children].filter((el) => !RESERVED.has(el.tagName.toLowerCase())).reverse().map((el) => ({
          id: el.id,
          name: el.getAttribute('data-hv-name') || '',
          type: el.getAttribute('data-hv-type') || '',
          tag: el.tagName.toLowerCase(),
          pipe: isPipe(el),
          selected: sel.has(el),
        })),
      }));
    },

    /** Tilføj/fjern ét element fra markeringen (Ctrl/Shift-klik i objekttræet). */
    toggleSelected(id) {
      const c = canvas();
      const el = c.getSvgContent().querySelector(`[id="${CSS.escape(id)}"]`);
      if (!el) return;
      if (selectedEls().includes(el)) c.removeFromSelection([el]);
      else c.addToSelection([el]);
    },

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
    /** Musens skærmpunkt → tegningens koordinater (fx hvor et symbol slippes). */
    docPointAt(clientX, clientY) {
      const [x, y] = screenToDoc(clientX, clientY);
      return { x, y };
    },

    /** Indsæt et bibliotekssymbol. `at` (tegningens koordinater): symbolets midte lægges dér (træk-og-slip). */
    insertSymbol(fragment, baseId, at = null) {
      const c = canvas();
      const node = buildSymbolNode(fragment, baseId);
      if (!node) return '';
      const res = c.getResolution();
      const step = (insertCount++ % 6) * 30; // forskyd hvert nyt symbol, så de ikke ligger oven i hinanden
      node.setAttribute('transform', `translate(${Math.round(res.w / 2 - 40 + step)} ${Math.round(res.h / 2 - 40 + step)})`);
      c.getCurrentDrawing().getCurrentLayer().appendChild(node);
      if (at && Number.isFinite(at.x) && Number.isFinite(at.y)) {
        const box = boxOfRoot(node);   // symbolets egen boks (uden translate)
        const cx = box ? box.x + box.w / 2 : 40;
        const cy = box ? box.y + box.h / 2 : 40;
        node.setAttribute('transform', `translate(${Math.round(at.x - cx)} ${Math.round(at.y - cy)})`);
      }
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
