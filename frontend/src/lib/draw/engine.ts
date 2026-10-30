// Den nye tegne-editors motor: SVG-Edits lærred (`@svgedit/svgcanvas`) direkte i siden — uden SVG-Edits brugerflade og
// uden iframe. Al vores egen logik (gitter, fang, id'er, symboler, API'et Tegn bruger) er den samme som i den gamle
// editor: svgedit-host/scada-core.js. Her ligger kun det, SVG-Edit-appen ellers gjorde: rulleflade, zoom og tastatur.
import SvgCanvas from '@svgedit/svgcanvas';
// @ts-expect-error — ren JS-modul uden typer (deles med den gamle værtsside)
import { createScada } from '../../../svgedit-host/scada-core.js';

/* eslint-disable @typescript-eslint/no-explicit-any */
export type Canvas = any;

/** Lærredets grundopsætning (som SVG-Edits standard, men med SCADA-venlige startfarver). */
export const CANVAS_CONFIG = {
  canvas_expansion: 3,
  initFill: { color: 'FFFFFF', opacity: 1 },
  initStroke: { color: '000000', opacity: 1, width: 2 },
  text: { stroke_width: 0, font_size: 16, font_family: 'sans-serif' },
  initOpacity: 1,
  imgPath: '/svgedit/images',
  dimensions: [1200, 700] as [number, number],
  baseUnit: 'px',
  gridSnapping: false,
  snappingStep: 10,
  showRulers: false,
  dynamicOutput: false,
  show_outside_canvas: true,
};

export const ZOOM_MIN = 0.05;
export const ZOOM_MAX = 20;
export const clampZoom = (z: number): number => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));

/** Næste zoomtrin op/ned (1, 1.25, 1.5, 2 … og tilsvarende ned) — rundt tal at læse i statuslinjen. */
export function zoomStep(z: number, dir: 1 | -1): number {
  const steps = [0.05, 0.1, 0.25, 0.33, 0.5, 0.67, 0.75, 1, 1.25, 1.5, 2, 3, 4, 6, 8, 12, 16, 20];
  if (dir > 0) return steps.find((s) => s > z + 1e-6) ?? ZOOM_MAX;
  return [...steps].reverse().find((s) => s < z - 1e-6) ?? ZOOM_MIN;
}

export interface Engine {
  canvas: Canvas;
  /** Det samme API som den gamle værtsside lagde på `window.scada` (se ScadaApi i DrawEditor.svelte). */
  api: any;
  setMode(mode: string): void;
  zoomTo(z: number, center?: { x: number; y: number }): void;
  zoomFit(): void;
  undo(): void;
  redo(): void;
  canUndo(): boolean;
  canRedo(): boolean;
  destroy(): void;
}

/** Tastaturgenvej → handling. Ren funktion (testet), så tasterne er de samme overalt. */
export function shortcutFor(e: { key: string; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean; altKey: boolean }): string | null {
  const mod = e.ctrlKey || e.metaKey;
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if (mod && !e.altKey) {
    if (k === 'z') return e.shiftKey ? 'redo' : 'undo';
    if (k === 'y') return 'redo';
    if (k === 'c') return 'copy';
    if (k === 'x') return 'cut';
    if (k === 'v') return 'paste';
    if (k === 'd') return 'duplicate';
    if (k === 'a') return 'selectAll';
    if (k === 'g') return e.shiftKey ? 'ungroup' : 'group';
    if (k === '0') return 'zoomFit';
    if (k === '+' || k === '=') return 'zoomIn';
    if (k === '-') return 'zoomOut';
    return null;
  }
  if (e.altKey) return null;
  if (k === 'Delete' || k === 'Backspace') return 'delete';
  if (k === 'Escape') return 'escape';
  if (k.startsWith('Arrow')) return `nudge${k.slice(5)}${e.shiftKey ? '10' : '1'}`;
  const tools: Record<string, string> = { v: 'select', l: 'line', r: 'rect', e: 'ellipse', p: 'path', t: 'text', f: 'fhpath' };
  return !e.shiftKey && tools[k] ? `tool:${tools[k]}` : null;
}

/**
 * Start motoren i `workarea` (rullefladen). `textInput` er et skjult felt, som lærredet skriver tekst gennem.
 * `onMode` får det aktive værktøj, `onZoom` den aktuelle zoom, `onHistory` når fortryd/gentag kan have skiftet.
 */
export function createEngine(workarea: HTMLElement, textInput: HTMLInputElement, hooks: {
  onMode?: (mode: string) => void; onZoom?: (zoom: number) => void; onHistory?: () => void;
} = {}): Engine {
  const host = document.createElement('div');
  host.className = 'svgcanvas';
  workarea.appendChild(host);
  const canvas: Canvas = new SvgCanvas(host, structuredClone(CANVAS_CONFIG) as any);
  canvas.textActions.setInputElem(textInput);
  textInput.addEventListener('input', () => canvas.setTextContent(textInput.value));

  /** Rullefladens indhold er lærredet × 3 (som SVG-Edit), tegningen i midten; rulningen bevarer midtpunktet. */
  function updateCanvas(center = false, newCtr?: { x: number; y: number }): void {
    const zoom = canvas.getZoom();
    const wOrig = workarea.clientWidth;
    const hOrig = workarea.clientHeight;
    const oldCtr = { x: workarea.scrollLeft + wOrig / 2, y: workarea.scrollTop + hOrig / 2 };
    const w = Math.max(wOrig, canvas.contentW * zoom * CANVAS_CONFIG.canvas_expansion);
    const h = Math.max(hOrig, canvas.contentH * zoom * CANVAS_CONFIG.canvas_expansion);
    const oldW = host.offsetWidth || w;
    const oldH = host.offsetHeight || h;
    host.style.width = `${w}px`;
    host.style.height = `${h}px`;
    const offset = canvas.updateCanvas(w, h);
    if (center) {
      workarea.scrollLeft = (w - wOrig) / 2;
      workarea.scrollTop = (h - hOrig) / 2;
      if (canvas.contentW * zoom > wOrig) { workarea.scrollLeft = offset.x - 10; workarea.scrollTop = offset.y - 10; }
      return;
    }
    const target = newCtr
      ? { x: newCtr.x + offset.x, y: newCtr.y + offset.y }
      : { x: w / 2 + (oldCtr.x - oldW / 2) * (w / oldW), y: h / 2 + (oldCtr.y - oldH / 2) * (h / oldH) };
    workarea.scrollLeft = target.x - wOrig / 2;
    workarea.scrollTop = target.y - hOrig / 2;
  }

  let api: any = null;   // vores API (scada-core) — sættes nedenfor, når lærredet er klar

  function zoomTo(z: number, center?: { x: number; y: number }): void {
    const zoom = clampZoom(z);
    // punktet under musen (i tegningens koordinater) bliver under musen
    const ctr = center ?? null;
    canvas.setZoom(zoom);
    updateCanvas(false, ctr ? { x: ctr.x * zoom, y: ctr.y * zoom } : undefined);
    // markeringsrammerne og gitteret følger zoomen (det gjorde SVG-Edit-appen i zoomDone)
    for (const el of canvas.getSelectedElements() || []) if (el) canvas.selectorManager.requestSelector(el).resize();
    api?.redrawGrid?.();
    hooks.onZoom?.(zoom);
  }

  function zoomFit(): void {
    const scrbar = 15;
    const info = canvas.setBBoxZoom('canvas', workarea.clientWidth - scrbar, workarea.clientHeight - scrbar);
    if (!info) return;
    zoomTo(info.zoom * 0.95);
    updateCanvas(true);
  }

  // Lærredets egne hændelser: zoom-værktøjets rubberbånd, og tilbage til Vælg efter en figur
  canvas.bind('zoomed', (_win: unknown, bbox: { x: number; y: number; width: number; height: number; factor?: number }) => {
    const info = canvas.setBBoxZoom(bbox, workarea.clientWidth - 15, workarea.clientHeight - 15);
    if (info) zoomTo(info.zoom, { x: info.bbox.x + info.bbox.width / 2, y: info.bbox.y + info.bbox.height / 2 });
  });
  canvas.bind('changed', (_win: unknown, elems: Element[]) => {
    if (elems.some((el) => el?.tagName === 'svg')) updateCanvas();   // tegningens størrelse ændret
    hooks.onHistory?.();
  });
  canvas.bind('selected', () => hooks.onHistory?.());

  const setMode = (mode: string): void => {
    canvas.setMode(mode);
    hooks.onMode?.(mode);
  };

  api = createScada({
    canvas: () => canvas,
    loadFromString: (svg: string) => {
      const ok = canvas.setSvgString(svg) !== false;
      if (ok) { updateCanvas(true); zoomFit(); }
      return ok;
    },
    updateCanvas: () => updateCanvas(),
    gridHost: () => workarea,
    curConfig: () => canvas.getCurConfig?.(),
  });
  // API'ets onMode følger værktøjsskift fra både os og lærredet (fx tilbage til Vælg efter tekst)
  api.ready.then(() => api.onMode?.((m: string) => hooks.onMode?.(m)));

  // ---- tastatur (det gjorde SVG-Edit-appen før)
  const editingText = (): boolean => canvas.getMode() === 'textedit' || document.activeElement === textInput;
  const typingInForm = (t: EventTarget | null): boolean =>
    t instanceof HTMLElement && t !== textInput && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
  function onKey(e: KeyboardEvent): void {
    if (typingInForm(e.target) || editingText()) {
      if (e.key === 'Escape' && editingText()) { canvas.textActions.toSelectMode(true); e.preventDefault(); }
      return;
    }
    const act = shortcutFor(e);
    if (!act) return;
    const sel = (canvas.getSelectedElements() || []).filter(Boolean);
    const nudge = /^nudge(Up|Down|Left|Right)(\d+)$/.exec(act);
    if (nudge) {
      if (!sel.length) return;
      const d = Number(nudge[2]);
      const [dx, dy] = ({ Up: [0, -d], Down: [0, d], Left: [-d, 0], Right: [d, 0] } as Record<string, number[]>)[nudge[1]];
      canvas.moveSelectedElements(dx, dy);
    } else if (act.startsWith('tool:')) {
      setMode(act.slice(5));
    } else {
      switch (act) {
        case 'undo': canvas.undoMgr.undo(); break;
        case 'redo': canvas.undoMgr.redo(); break;
        case 'copy': if (!sel.length) return; canvas.copySelectedElements(); break;
        case 'cut': if (!sel.length) return; canvas.cutSelectedElements(); break;
        case 'paste': canvas.pasteElements('in_place'); break;
        case 'duplicate': if (!sel.length) return; canvas.cloneSelectedElements(20, 20); break;
        case 'selectAll': canvas.selectAllInCurrentLayer(); break;
        case 'group': if (sel.length < 2) return; canvas.groupSelectedElements(); break;
        case 'ungroup': if (!sel.length) return; canvas.ungroupSelectedElement(); break;
        case 'delete': if (!sel.length) return; canvas.deleteSelectedElements(); break;
        case 'escape': canvas.clearSelection(); setMode('select'); break;
        case 'zoomFit': zoomFit(); break;
        case 'zoomIn': zoomTo(zoomStep(canvas.getZoom(), 1)); break;
        case 'zoomOut': zoomTo(zoomStep(canvas.getZoom(), -1)); break;
      }
    }
    hooks.onHistory?.();
    e.preventDefault();
  }
  // Ctrl + musehjul zoomer om musen; uden Ctrl ruller fladen som normalt
  function onWheel(e: WheelEvent): void {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    const content = canvas.getSvgContent() as SVGSVGElement;
    const r = content.getBoundingClientRect();
    const z = canvas.getZoom();
    const pt = { x: (e.clientX - r.left) / z, y: (e.clientY - r.top) / z };
    const before = { x: e.clientX, y: e.clientY };
    zoomTo(zoomStep(z, e.deltaY < 0 ? 1 : -1), pt);
    // hold punktet under musen
    const r2 = content.getBoundingClientRect();
    const nz = canvas.getZoom();
    workarea.scrollLeft += r2.left + pt.x * nz - before.x;
    workarea.scrollTop += r2.top + pt.y * nz - before.y;
  }
  // Midterknap eller mellemrum + træk: panorér
  let space = false;
  let pan: { x: number; y: number } | null = null;
  const onSpace = (e: KeyboardEvent): void => {
    if (e.code !== 'Space' || typingInForm(e.target) || editingText()) return;
    space = e.type === 'keydown';
    workarea.style.cursor = space ? 'grab' : '';
    e.preventDefault();
  };
  const onDown = (e: MouseEvent): void => {
    if (e.button !== 1 && !(space && e.button === 0)) return;
    pan = { x: e.clientX, y: e.clientY };
    e.preventDefault();
    e.stopPropagation();
  };
  const onMove = (e: MouseEvent): void => {
    if (!pan) return;
    workarea.scrollLeft -= e.clientX - pan.x;
    workarea.scrollTop -= e.clientY - pan.y;
    pan = { x: e.clientX, y: e.clientY };
  };
  const onUp = (): void => { pan = null; };
  const life = new AbortController();
  const o = { signal: life.signal };
  document.addEventListener('keydown', onKey, o);
  document.addEventListener('keydown', onSpace, o);
  document.addEventListener('keyup', onSpace, o);
  workarea.addEventListener('wheel', onWheel, { signal: life.signal, passive: false });
  workarea.addEventListener('mousedown', onDown, { signal: life.signal, capture: true });
  document.addEventListener('mousemove', onMove, o);
  document.addEventListener('mouseup', onUp, o);
  const ro = new ResizeObserver(() => updateCanvas());
  ro.observe(workarea);

  updateCanvas(true);
  return {
    canvas,
    api,
    setMode,
    zoomTo,
    zoomFit,
    undo: () => { canvas.undoMgr.undo(); hooks.onHistory?.(); },
    redo: () => { canvas.undoMgr.redo(); hooks.onHistory?.(); },
    canUndo: () => canvas.undoMgr.getUndoStackSize() > 0,
    canRedo: () => canvas.undoMgr.getRedoStackSize() > 0,
    destroy: () => { life.abort(); ro.disconnect(); api.dispose?.(); host.remove(); },
  };
}
