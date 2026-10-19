// Symboltest: afprøv et biblioteksymbol uden PLC. Logikken (delene, symbolets egne animationer og de simulerede
// bindinger) ligger her, så den kan testes; siden pages/SymbolTest.svelte viser den.
import type { Binding, LiveValue } from './api';
import { applyBinding, resetAnim } from './animate';
import { POS, animDefaults, libraryDefault, partLabel, typesFor, type Anim, type AnimType, type PartInfo, type SrcKind, type SymbolInfo } from './symbolConfig';

export interface TestPart {
  /** SVG-id, eller ROOT for hele symbolet */
  id: string;
  label: string;
  tag: string;
  /** de animationer symbolet selv erklærer på delen (`data-hv-part`) */
  own: OwnAnim[];
  /** de animationer delen kan have (som i guiden) */
  types: AnimType[];
}
export interface OwnAnim { anim: Binding['anim']; params: Record<string, any> }

export const ROOT = 'all';
export const QUALITY_GOOD: LiveValue['quality'] = 'good';

/** Typer der har en værdi pr. position (som i guiden); de øvrige følger et tal eller til/fra. */
export const POS_ANIMS: AnimType[] = ['fill', 'stroke', 'blink', 'visible', 'spin', 'flicker', 'rotate', 'move', 'flow', 'text'];
export const MIN_POSITIONS = 2, MAX_POSITIONS = 8;

const asList = (v: unknown): OwnAnim[] => (Array.isArray(v) ? v : v ? [v] : []).filter((x) => x && typeof x.anim === 'string')
  .map((x) => ({ anim: x.anim, params: x.params ?? {} }));

const STROKE_SHAPES = ['path', 'line', 'polyline', 'polygon', 'circle', 'ellipse'];
/** Har delen streger/rør (løbelys)? Samme regel som serverens `_shape_info`. */
function hasLine(el: Element): boolean {
  for (const s of [el, ...el.querySelectorAll('*')]) {
    const stroke = (s.getAttribute('stroke') ?? '').trim();
    if (s.tagName === 'rect' || (STROKE_SHAPES.includes(s.tagName) && stroke && stroke !== 'none')) return true;
  }
  return false;
}

const parseSvg = (svg: string): Element | null =>
  new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${svg}</svg>`, 'image/svg+xml').documentElement.firstElementChild;

/** Symbolets del-oplysninger i samme form som serveren giver dem til guiden. */
export function testInfo(svg: string, type = 'custom'): SymbolInfo {
  const root = parseSvg(svg);
  const info: SymbolInfo = { type, name: null, tag: root?.tagName ?? 'g', line: root ? hasLine(root) : false, parts: {} };
  for (const e of root?.querySelectorAll('[id]') ?? []) {
    info.parts[e.id] = { tag: e.tagName, line: hasLine(e), pid: e.id, text: e.tagName === 'text' ? e.textContent ?? '' : undefined };
  }
  return info;
}

/** Delene i et symbol: roden og hvert element med id (de navngivne dele), med de animationer symbolet selv erklærer. */
export function testParts(svg: string, type = 'custom'): TestPart[] {
  const root = parseSvg(svg);
  if (!root) return [];
  const info = testInfo(svg, type);
  const ownOf = (e: Element): OwnAnim[] => {
    try {
      return asList(JSON.parse(e.getAttribute('data-hv-part') ?? 'null'));
    } catch {
      return [];   // ugyldig erklæring: delen vises uden egne animationer (symbols.test.ts fanger fejlen i biblioteket)
    }
  };
  const out: TestPart[] = [];
  for (const e of root.querySelectorAll('[id]')) {
    out.push({ id: e.id, label: partLabel(e.id, info), tag: e.tagName, own: ownOf(e), types: typesFor(info.parts[e.id]) });
  }
  const rootPart: PartInfo = { tag: root.tagName, line: info.line };
  return [{ id: ROOT, label: 'Hele symbolet', tag: root.tagName, own: ownOf(root), types: typesFor(rootPart) }, ...out];
}

/** Talområdet en animation forventer (min/max i parametrene) — til skyderen. */
export function valueRange(params: Record<string, any>): { min: number; max: number } {
  const min = Number(params.min ?? 0), max = Number(params.max ?? 1);
  return Number.isFinite(min) && Number.isFinite(max) && max > min ? { min, max } : { min: 0, max: 1 };
}

/**
 * En simuleret binding med standardparametre for animationen (som guiden ville foreslå dem). Med kilden *position*
 * er værdien positionens nummer (0 …), og der er `n` positioner.
 */
export function testBinding(element: string, anim: AnimType, kind: SrcKind, n = MIN_POSITIONS): Binding {
  const params = animDefaults(anim, kind, n);
  if (kind === 'pos') {
    params.pos = true;
    if (anim === 'text') params.labels = Array.from({ length: n }, (_, j) => `Position ${j + 1}`);
  }
  return { element, tag: 'test', anim, params };
}

/** Animationer en test kan afprøve for kilden (positioner kun for de typer der har en værdi pr. position). */
export const animsFor = (types: AnimType[], kind: SrcKind): AnimType[] => (kind === 'pos' ? types.filter((t) => POS_ANIMS.includes(t)) : types);

/** Bibliotekets egen opsætning af et symbol (som guiden foreslår den), klar til afprøvning. */
export interface LibrarySetup {
  note: string;
  /** positionernes navne; tom = ingen positioner (til/fra eller tal) */
  positions: string[];
  bindings: Binding[];
  kind: SrcKind;
}

const asBinding = (a: Anim): Binding => ({
  element: a.part, tag: 'test', anim: a.type,
  params: { ...a.params, ...(a.src === POS ? { pos: true } : {}), ...(a.only ? { only: a.only } : {}) },
});

/** Null hvis biblioteket ikke har en opsætning til symbolet (så er kun den frie afprøvning mulig). */
export function librarySetup(svg: string, type: string): LibrarySetup | null {
  const proposal = libraryDefault(testInfo(svg, type));
  if (!proposal) return null;
  const { config, note } = proposal;
  const bindings = config.anims.map(asBinding);
  if (!bindings.length) return null;   // fx grafen: ingen animationer at afprøve
  const positions = bindings.some((b) => b.params.pos) ? config.positions.map((p, j) => p.label || `Position ${j + 1}`) : [];
  const numeric = bindings.some((b) => Array.isArray(b.params.thresholds));
  return { note, positions, bindings, kind: positions.length ? 'pos' : numeric ? 'num' : 'bool' };
}

/** Anvend hele opsætningen med én værdi (positionens nummer, til/fra eller tal). Returnerer de dele der ikke fandtes. */
export function runSetup(host: Element, setup: LibrarySetup, value: unknown): string[] {
  return setup.bindings.filter((b) => !applyTest(host, b.element, b, value)).map((b) => b.element);
}

/** Skaber live-værdien en simuleret værdi svarer til. */
export const liveOf = (value: unknown): LiveValue => ({ value, quality: QUALITY_GOOD, ts: Date.now() / 1000, error: null });

/** Anvend en binding på delen i det viste symbol. Returnerer false hvis delen ikke findes (fx efter et skift af symbol). */
export function applyTest(host: Element, part: string, b: Binding, value: unknown): boolean {
  const el = part === ROOT ? host.firstElementChild : host.querySelector(`[id="${CSS.escape(part)}"]`);
  if (!el) return false;
  applyBinding(el, b, liveOf(value));
  return true;
}

/** Sæt alle dele tilbage som tegnet. */
export function resetTest(host: Element, anims: Binding[]): void {
  for (const b of anims) {
    const el = b.element === ROOT ? host.firstElementChild : host.querySelector(`[id="${CSS.escape(b.element)}"]`);
    if (el) resetAnim(el, b.anim, b.params);
  }
}
