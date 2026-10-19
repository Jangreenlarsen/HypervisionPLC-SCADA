// Symboltest: afprøv et biblioteksymbol uden PLC. Logikken (delene, symbolets egne animationer og de simulerede
// bindinger) ligger her, så den kan testes; siden pages/SymbolTest.svelte viser den.
import type { Binding, LiveValue } from './api';
import { applyBinding, resetAnim } from './animate';
import { animDefaults, partLabel, type AnimType, type SrcKind, type SymbolInfo } from './symbolConfig';

export interface TestPart {
  /** SVG-id, eller ROOT for hele symbolet */
  id: string;
  label: string;
  tag: string;
  /** de animationer symbolet selv erklærer på delen (`data-hv-part`) */
  own: OwnAnim[];
}
export interface OwnAnim { anim: Binding['anim']; params: Record<string, any> }

export const ROOT = 'all';
export const QUALITY_GOOD: LiveValue['quality'] = 'good';

/** Alle typer der kan afprøves frit på en del. */
export const TEST_ANIMS: AnimType[] = ['fill', 'stroke', 'blink', 'visible', 'spin', 'flicker', 'level', 'opacity', 'text', 'rotate', 'move', 'scale'];

const asList = (v: unknown): OwnAnim[] => (Array.isArray(v) ? v : v ? [v] : []).filter((x) => x && typeof x.anim === 'string')
  .map((x) => ({ anim: x.anim, params: x.params ?? {} }));

/** Delene i et symbol: roden og hvert element med id (de navngivne dele), med de animationer symbolet selv erklærer. */
export function testParts(svg: string, type = 'custom'): TestPart[] {
  const doc = new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${svg}</svg>`, 'image/svg+xml');
  const root = doc.documentElement.firstElementChild;
  if (!root) return [];
  const info: SymbolInfo = { type, name: null, tag: 'g', line: false, parts: {} };
  const out: TestPart[] = [];
  for (const e of root.querySelectorAll('[id]')) {
    info.parts[e.id] = { tag: e.tagName, line: false, pid: e.id, text: e.tagName === 'text' ? e.textContent ?? '' : undefined };
  }
  for (const e of root.querySelectorAll('[id]')) {
    let own: OwnAnim[] = [];
    try {
      own = asList(JSON.parse(e.getAttribute('data-hv-part') ?? 'null'));
    } catch {
      own = [];   // ugyldig erklæring: delen vises uden egne animationer (symbols.test.ts fanger fejlen i biblioteket)
    }
    out.push({ id: e.id, label: partLabel(e.id, info), tag: e.tagName, own });
  }
  return [{ id: ROOT, label: 'Hele symbolet', tag: root.tagName, own: asList(JSON.parse(root.getAttribute('data-hv-part') ?? 'null')) }, ...out];
}

/** Talområdet en animation forventer (min/max i parametrene) — til skyderen. */
export function valueRange(params: Record<string, any>): { min: number; max: number } {
  const min = Number(params.min ?? 0), max = Number(params.max ?? 1);
  return Number.isFinite(min) && Number.isFinite(max) && max > min ? { min, max } : { min: 0, max: 1 };
}

/** En simuleret binding med standardparametre for animationen (som guiden ville foreslå dem). */
export function testBinding(element: string, anim: AnimType, kind: SrcKind): Binding {
  const params = animDefaults(anim, kind, 0);
  return { element, tag: 'test', anim, params };
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
