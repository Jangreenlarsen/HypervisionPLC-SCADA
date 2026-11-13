// Ind/ud og veje på VVS-symboler (v4.13.0, PLAN.md › Signalveje 2): hvert tilslutningspunkt kan have et navn (A, B, AB …), en
// rolle (ind, ud, begge) og kan være "fælles" (AB på en 3-vejsventil). Et symbol har desuden en liste af VEJE: de forbindelser
// ventilen kan lave (AB → A, AB → B). Bruges kun af signalveje: en pumpe bestemmer vejens retning, og en 3-vejsventil kan kun
// bruges gennem én af sine veje. Resten af tegningen ændres ikke.
//
// Punkterne er brøkdele [x, y] af symbolets egen boks (som tilslutningspunkterne), så de følger symbolet, når det flyttes,
// skaleres, drejes eller spejles. Her ligger standarderne for de indbyggede symboler; en tekniker kan rette dem pr. symboltype
// (Symboler › Tilslutningspunkter, gemmes af backend: services/symbol_flow.py) — de rettede går forud for standarderne.

export type PortRole = 'in' | 'out' | 'both';
export interface PortDef { x: number; y: number; name: string; role: PortRole; common?: boolean; part?: string }
/** Flow-profilen pr. symboltype (v6.3.0): rollen i flowberegningen, mediet og standarderne (uden egen opsætning i guiden). */
export type FlowKind = 'consumer' | 'pump' | 'piece';
export type FlowMedium = 'water' | 'air' | 'electric' | 'other';
export interface FlowDef {
  ports: PortDef[]; ways?: [string, string][];
  kind?: FlowKind; medium?: FlowMedium; capacity?: number; restrict?: number;
}
export type FlowDefs = Record<string, FlowDef>;

export const ROLE_LABEL: Record<PortRole, string> = { in: 'Ind', out: 'Ud', both: 'Begge' };
export const KIND_LABEL: Record<FlowKind, string> = { consumer: 'Forbruger (radiator, tank, ventil …)', pump: 'Pumpe / kilde (strømforsyning …)', piece: 'Rørstykke / ledning (bøjning, klemme …)' };
export const MEDIUM_LABEL: Record<FlowMedium, string> = { water: 'Vand', air: 'Luft', electric: 'El', other: 'Andet' };
/** Enheden, flowet vises i (kun visning) — samme som backend flow_defs.UNITS. */
export const UNITS: Record<FlowMedium, string> = { water: 'l/min', air: 'm³/h', electric: 'A', other: '' };
/** Indbyggede rørstykker — samme liste som backend flow_defs.PIPE_SYMBOL_TYPES. */
export const PIECE_TYPES = new Set(['roer_l', 'roer_v', 'boejning45', 'boejning90', 't_stykke', 'kryds', 'reduktion', 'flange',
  'ledning_l', 'ledning_v', 'forbindelse', 'klemme']);
/** Typens rolle: profilen, ellers de indbyggede rørstykker/pumper, ellers forbruger. */
export function kindOf(defs: FlowDefs, type: string): FlowKind {
  const k = defs[type]?.kind;
  if (k) return k;
  return PIECE_TYPES.has(type) ? 'piece' : type === 'pumpe' ? 'pump' : 'consumer';
}
export const unitOf = (defs: FlowDefs, type: string): string => UNITS[defs[type]?.medium ?? 'water'];
/** Har definitionen en profil ud over standarden (så den kan gemmes uden punkter)? */
export const hasProfile = (d: FlowDef): boolean =>
  (!!d.kind && d.kind !== 'consumer') || (!!d.medium && d.medium !== 'water') || d.capacity != null || d.restrict != null;
export const MATCH_TOL = 0.2;   // et symbols punkt hører til en definition, hvis de ligger højst så langt fra hinanden (brøkdel af boksen)

const IN_OUT = (y: number): PortDef[] => [
  { x: 0, y, name: 'IND', role: 'in' }, { x: 1, y, name: 'UD', role: 'out' },
];

/** Standarder for de indbyggede symboler (målt på symbolerne i Tegn; pil/trekant peger mod højre ved 0°). */
export const FLOW_DEFAULTS: FlowDefs = {
  pumpe: { ports: IN_OUT(0.5), kind: 'pump' },
  kontraventil: { ports: IN_OUT(0.67) },
  trevejs_motorventil: {
    ports: [{ x: 0.07, y: 0.46, name: 'A', role: 'both', part: 'port_a' }, { x: 0.46, y: 0.08, name: 'B', role: 'both', part: 'port_b' },
      { x: 0.84, y: 0.46, name: 'AB', role: 'both', common: true, part: 'port_ab' }],
  },
  trevejs_motorventil_ab: {
    ports: [{ x: 0.07, y: 0.5, name: 'A', role: 'both', part: 'port_a' }, { x: 0.85, y: 0.5, name: 'B', role: 'both', part: 'port_b' },
      { x: 0.46, y: 0.86, name: 'AB', role: 'both', common: true, part: 'port_ab' }],
  },
  trevejsventil: {
    ports: [{ x: 0, y: 0.44, name: 'A', role: 'both' }, { x: 1, y: 0.44, name: 'B', role: 'both' },
      { x: 0.5, y: 1, name: 'AB', role: 'both', common: true }],
  },
};

/** De rettede definitioner går forud for standarderne (pr. symboltype). */
export const mergeDefs = (custom: FlowDefs | null | undefined): FlowDefs => ({ ...FLOW_DEFAULTS, ...(custom ?? {}) });

/** Vejene gennem symbolet: de angivne, ellers hver fælles port parret med hver ikke-fælles. Uden fælles port: ingen (alt tilladt). */
export function waysOf(def: FlowDef | undefined): [string, string][] {
  if (!def) return [];
  if (def.ways?.length) return def.ways;
  const common = def.ports.filter((p) => p.common).map((p) => p.name);
  const rest = def.ports.filter((p) => !p.common).map((p) => p.name);
  return common.flatMap((c) => rest.map((r): [string, string] => [c, r]));
}

/** "AB>A" — en vejs nøgle (fra fælles til anden port). */
export const wayKey = (w: [string, string]): string => `${w[0]}>${w[1]}`;
export const wayLabel = (w: [string, string]): string => `${w[0]} → ${w[1]}`;
export function parseWay(key: string): [string, string] | null {
  const m = /^([^>]+)>([^>]+)$/.exec(key);
  return m ? [m[1], m[2]] : null;
}
/** Passer en forbindelse mellem to porte (i vilkårlig rækkefølge) til vejen? */
export const sameWay = (w: [string, string], a: string, b: string): boolean => (w[0] === a && w[1] === b) || (w[0] === b && w[1] === a);

/** Hvilken definition et punkt (brøkdel af symbolets boks) hører til: den nærmeste inden for MATCH_TOL, hver højst én gang. */
export function matchPorts(def: FlowDef | undefined, fracs: [number, number][] | null | undefined): (PortDef | null)[] {
  if (!def || !fracs) return fracs ? fracs.map(() => null) : [];
  const taken = new Set<number>();
  const out: (PortDef | null)[] = fracs.map(() => null);
  // alle par, nærmeste først, så to punkter ikke stjæler hinandens definition
  const pairs: { i: number; k: number; d: number }[] = [];
  fracs.forEach((f, i) => def.ports.forEach((p, k) => pairs.push({ i, k, d: Math.hypot(f[0] - p.x, f[1] - p.y) })));
  pairs.sort((a, b) => a.d - b.d);
  const done = new Set<number>();
  for (const { i, k, d } of pairs) {
    if (d > MATCH_TOL || done.has(i) || taken.has(k)) continue;
    out[i] = def.ports[k];
    done.add(i);
    taken.add(k);
  }
  return out;
}

/** Kontrol af en definition (samme regler som backend services/symbol_flow.py) → fejltekst eller null. */
export function validateDef(def: FlowDef): string | null {
  const names = new Set<string>();
  if (!def.ports.length && !hasProfile(def)) return 'Angiv mindst ét punkt (eller en rolle, et medie eller en standard)';
  if (def.capacity != null && !(Number.isInteger(def.capacity) && def.capacity >= 0 && def.capacity <= 65535)) return 'Standard-kapaciteten skal være et helt tal 0–65535';
  if (def.restrict != null && !(def.restrict >= 0 && def.restrict <= 1)) return 'Standard-restriktionen skal være mellem 0,00 og 1,00';
  for (const p of def.ports) {
    if (!/^[A-Za-z0-9_+-]{1,12}$/.test(p.name)) return `Punktets navn '${p.name}' er ugyldigt (bogstaver, tal, _ + -; højst 12 tegn)`;
    if (names.has(p.name)) return `Navnet '${p.name}' er brugt to gange`;
    names.add(p.name);
  }
  for (const w of def.ways ?? []) if (!names.has(w[0]) || !names.has(w[1]) || w[0] === w[1]) return `Vejen ${w[0]} → ${w[1]} bruger et ukendt punkt`;
  return null;
}
