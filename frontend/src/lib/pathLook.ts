// Udseende af en signalvej (v4.14.0, PLAN.md › Signalveje 2): hvilke animationer vejen lægger på hvilke slags elementer — løbelys på
// rør, men fx farve på ventiler, blink på en pumpe eller at en 3-vejsventils porte i vejen skifter farve. Rene beregninger, testet i
// pathLook.test.ts. Backend lægger animationerne på (services/signal_paths.py), styret af vejens logikblokke ("aktiv/passiv": er
// vejen ikke aktiv, røres delen ikke). "Gennemsigtighed" (opacity) kræver et tal-tag og kan ikke styres af en logikblok — brug Synlig.
import type { Flow, NetRow, Role } from './signalPath';
import { waysOf, parseWay, type FlowDefs } from './symbolFlow';

export type LookGroup = 'pipe' | 'valve' | 'threeway' | 'pump' | 'switch';
export type LookType = 'flow' | 'fill' | 'stroke' | 'blink' | 'visible' | 'spin';
export const GROUPS: LookGroup[] = ['pipe', 'valve', 'threeway', 'pump', 'switch'];
export const GROUP_LABEL: Record<LookGroup, string> = {
  pipe: 'Rør, bøjninger og T-stykker', valve: 'Ventiler', threeway: '3-vejsventiler', pump: 'Pumper', switch: 'Kontakter',
};
export const TYPE_LABEL: Record<LookType, string> = {
  flow: 'Løbelys', fill: 'Farve', stroke: 'Stregfarve', blink: 'Blink', visible: 'Vises kun når vejen er aktiv', spin: 'Roterer',
};
/** Hvilke animationer der giver mening for hvilken slags element (løbelys kræver en streg: kun rør). */
export const TYPES: Record<LookGroup, LookType[]> = {
  pipe: ['flow', 'fill', 'stroke', 'blink'],
  valve: ['fill', 'stroke', 'blink', 'visible'],
  threeway: ['fill', 'stroke', 'blink'],
  pump: ['fill', 'blink', 'spin', 'stroke', 'visible'],
  switch: ['fill', 'stroke', 'blink', 'visible'],
};
export const WAYS_PART = 'ways';        // en 3-vejsventil: kun portene i vejen, vejen bruger
export const WHOLE = 'all';             // hele symbolet

export interface LookAnim { type: LookType; on: boolean; part: string; color: string; speed: 'slow' | 'normal' | 'fast' }
export type Look = Record<LookGroup, LookAnim[]>;

const DEFAULT_COLOR: Record<LookType, string> = {
  flow: '#8fc8ea', fill: '#66bb6a', stroke: '#2e7d32', blink: '#ffb300', visible: '#000000', spin: '#000000',
};

/** Standard: som før — løbelys på rørene, intet andet. */
export function defaultLook(): Look {
  const out = {} as Look;
  for (const g of GROUPS) {
    out[g] = TYPES[g].map((type) => ({
      type, on: g === 'pipe' && type === 'flow', part: g === 'threeway' ? WAYS_PART : WHOLE, color: DEFAULT_COLOR[type], speed: 'normal',
    }));
  }
  return out;
}

/** En gemt opsætning (fra `ui.look`), flettet ind i standarden — ukendte felter og typer ignoreres. */
export function restoreLook(saved: unknown): Look {
  const out = defaultLook();
  if (!saved || typeof saved !== 'object') return out;
  for (const g of GROUPS) {
    const list = (saved as Record<string, unknown>)[g];
    if (!Array.isArray(list)) continue;
    out[g] = out[g].map((a) => {
      const s = list.find((x) => x && typeof x === 'object' && (x as LookAnim).type === a.type) as Partial<LookAnim> | undefined;
      if (!s) return a;
      return {
        ...a, on: !!s.on, part: typeof s.part === 'string' && s.part ? s.part : a.part,
        color: typeof s.color === 'string' && /^#[0-9a-fA-F]{6}$/.test(s.color) ? s.color : a.color,
        speed: s.speed === 'slow' || s.speed === 'fast' ? s.speed : 'normal',
      };
    });
  }
  return out;
}

export function groupOf(role: Role): LookGroup | null {
  switch (role) {
    case 'pipe': return 'pipe';
    case 'valve': case 'check': return 'valve';
    case 'threeway': return 'threeway';
    case 'pump': return 'pump';
    case 'switch': return 'switch';
    default: return null;
  }
}

export interface PartInfo { id: string; pid?: string }
export interface PartAnim { part: string; type: Exclude<LookType, 'flow'>; params: Record<string, unknown>; when: boolean }

/** Animationens parametre til symbolopsætningen (valideres af backend). */
export function paramsFor(a: LookAnim): Record<string, unknown> {
  switch (a.type) {
    case 'fill': case 'stroke': return { on: a.color };
    case 'blink': return { speed: a.speed };
    default: return {};
  }
}

/** Delene på en 3-vejsventil, der hører til de porte, vejen bruger (AB → A: portene AB og A), som delens id i tegningen. */
export function wayParts(row: NetRow, type: string, defs: FlowDefs, parts: PartInfo[]): string[] {
  const def = defs[type];
  if (!def) return [];
  const names = new Set<string>();
  for (const u of row.uses) {
    const w = u.way ? parseWay(u.way) : null;
    if (w) { names.add(w[0]); names.add(w[1]); }
  }
  const out: string[] = [];
  for (const port of def.ports) {
    if (!names.has(port.name) || !port.part) continue;
    const hit = parts.find((p) => p.pid === port.part) ?? parts.find((p) => p.id === port.part || p.id.endsWith(`_${port.part}`));
    if (hit && !out.includes(hit.id)) out.push(hit.id);
  }
  return out;
}

/**
 * Hvad et element får på vejen: løbelys på rørets dele (`flows`) og de øvrige animationer (`anims`) efter udseendet for dets slags.
 * Rør: på de dele, der får løbelys. 3-vejsventil: som standard kun portene i vejen. Andre: hele symbolet eller den valgte del.
 */
export function animsFor(row: NetRow, look: Look, defs: FlowDefs, parts: PartInfo[] = []): { flows: Flow[]; anims: PartAnim[] } {
  const g = groupOf(row.role);
  if (!g) return { flows: [], anims: [] };
  const chosen = look[g].filter((a) => a.on);
  const flows = g === 'pipe' && chosen.some((a) => a.type === 'flow') ? row.flows : [];
  const anims: PartAnim[] = [];
  for (const a of chosen) {
    if (a.type === 'flow') continue;
    let targets: string[];
    if (g === 'pipe') targets = row.flows.length ? [...new Set(row.flows.map((f) => f.part))] : [WHOLE];
    else if (a.part === WAYS_PART) targets = wayParts(row, row.type, defs, parts);
    else targets = [a.part || WHOLE];
    if (g === 'threeway' && a.part === WAYS_PART && !targets.length) targets = [WHOLE];   // ingen navngivne porte: hele ventilen
    // "Vises kun når vejen er aktiv": er vejen ikke aktiv, viser delen sin fra-tilstand (skjult). De øvrige røres ikke, når vejen er inaktiv
    for (const part of targets) anims.push({ part, type: a.type as PartAnim['type'], params: paramsFor(a), when: a.type !== 'visible' });
  }
  return { flows, anims };
}

/** Er der valgt mindst én animation til en slags element, der findes på vejen? */
export const anyChosen = (look: Look, present: Set<LookGroup>): boolean => [...present].some((g) => look[g].some((a) => a.on));
