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
/** En dels udseende i en tilstand (v6.7.0, design B): farve (fill/stroke), vinkel (rotate) eller Til/Fra (visible/blink/spin). */
export type LookAnim = 'fill' | 'stroke' | 'rotate' | 'visible' | 'blink' | 'spin';
export interface LookItem { part: string; anim: LookAnim; value: string | number | boolean }
export const LOOK_TXT: Record<LookAnim, string> = { fill: 'Farve', stroke: 'Stregfarve', rotate: 'Vinkel', visible: 'Synlig', blink: 'Blink', spin: 'Roterer' };
/** Startværdien for en ny udseende-linje. */
export const lookDefault = (a: LookAnim): string | number | boolean => (a === 'fill' || a === 'stroke' ? '#2e7d32' : a === 'rotate' ? 0 : true);
/** En navngiven tilstand (v6.6.0, Jan): de veje, der er åbne — fx "A → AB" = A igennem AB, B blokeret; v6.7.0: og udseendet. */
export interface FlowState { name: string; open: string[]; look?: LookItem[] }
export interface FlowDef {
  ports: PortDef[]; ways?: [string, string][];
  kind?: FlowKind; medium?: FlowMedium; capacity?: number; restrict?: number;
  states?: FlowState[];
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
  (!!d.kind && d.kind !== 'consumer') || (!!d.medium && d.medium !== 'water') || d.capacity != null || d.restrict != null || !!d.states?.length;
export const MATCH_TOL = 0.2;   // et symbols punkt hører til en definition, hvis de ligger højst så langt fra hinanden (brøkdel af boksen)

/** Portenes farve (samme som backend flow_defs): på en åben vej grøn, blokeret sort (Jan: "AB og A grønne, B sort"). */
const portsLook = (open: string[], all: string[]): LookItem[] =>
  all.map((p) => ({ part: `port_${p.toLowerCase()}`, anim: 'fill' as const, value: open.includes(p) ? '#2e7d32' : '#000000' }));
/** 3-vejsventilernes standardtilstande (Jan): tilstand 1 = A igennem AB (B blokeret), tilstand 2 = B igennem AB (A blokeret). */
const THREE_WAY_STATES: FlowState[] = [
  { name: 'A → AB', open: ['AB>A'], look: portsLook(['A', 'AB'], ['A', 'B', 'AB']) },
  { name: 'B → AB', open: ['AB>B'], look: portsLook(['B', 'AB'], ['A', 'B', 'AB']) }];
const greb = (deg: number): LookItem[] => [{ part: 'greb', anim: 'rotate', value: deg }];

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
    states: THREE_WAY_STATES,
  },
  trevejs_motorventil_ab: {
    ports: [{ x: 0.07, y: 0.5, name: 'A', role: 'both', part: 'port_a' }, { x: 0.85, y: 0.5, name: 'B', role: 'both', part: 'port_b' },
      { x: 0.46, y: 0.86, name: 'AB', role: 'both', common: true, part: 'port_ab' }],
    states: THREE_WAY_STATES,
  },
  trevejsventil: {
    ports: [{ x: 0, y: 0.44, name: 'A', role: 'both' }, { x: 1, y: 0.44, name: 'B', role: 'both' },
      { x: 0.5, y: 1, name: 'AB', role: 'both', common: true }],
    states: THREE_WAY_STATES,
  },
  // 4-vejsventil (v6.6.0, Jan): tilstand 1 = A igennem B (C og D blokeret), tilstand 2 = C igennem D (A og B blokeret)
  firevejsventil: {
    ports: [{ x: 0, y: 0.5, name: 'A', role: 'both', part: 'port_a' }, { x: 1, y: 0.5, name: 'B', role: 'both', part: 'port_b' },
      { x: 0.5, y: 0, name: 'C', role: 'both', part: 'port_c' }, { x: 0.5, y: 1, name: 'D', role: 'both', part: 'port_d' }],
    ways: [['A', 'B'], ['C', 'D']],
    states: [{ name: 'A → B', open: ['A>B'], look: portsLook(['A', 'B'], ['A', 'B', 'C', 'D']) },
      { name: 'C → D', open: ['C>D'], look: portsLook(['C', 'D'], ['A', 'B', 'C', 'D']) }],
  },
  // Omskiftere og vippekontakter (v6.7.0): tilstandene og grebets vinkel (som bibliotekets tegning)
  omskifter3: { ports: [], states: [{ name: 'Hånd', open: [], look: greb(-45) }, { name: '0', open: [], look: greb(0) }, { name: 'Auto', open: [], look: greb(45) }] },
  drejeomskifter: { ports: [], states: [{ name: '0', open: [], look: greb(-45) }, { name: '1', open: [], look: greb(45) }] },
  vippe_onoff: { ports: [], states: [{ name: 'OFF', open: [], look: greb(0) }, { name: 'ON', open: [], look: greb(180) }] },
};

/** Tilstandens udseende for et symbol (samme regel som backend symbols.effective_look): typens, med symbolets afvigelser ovenpå. */
export function effectiveLook(states: FlowState[] | undefined, overrides: Record<string, LookItem[]> | undefined, state: string | null | undefined): LookItem[] {
  if (!state) return [];
  const out = new Map<string, LookItem>();
  for (const it of states?.find((s) => s.name === state)?.look ?? []) out.set(`${it.part}|${it.anim}`, it);
  for (const it of overrides?.[state] ?? []) out.set(`${it.part}|${it.anim}`, it);
  return [...out.values()];
}

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

// ---------------------------------------------------------------- tilstande (v6.6.0)
/** Normaliseret sæt af veje (retningen tæller ikke): "AB>A" og "A>AB" er den samme vej. */
const wayNorm = (k: string): string => k.split('>').sort().join('|');
const waySet = (keys: string[]): string => [...new Set(keys.map(wayNorm))].sort().join(';');

/** Hvilken tilstand svarer de åbne veje til? → indeks, eller null (egen kombination). */
export function stateOf(def: FlowDef | undefined, open: string[] | undefined): number | null {
  if (!def?.states?.length || !open) return null;
  const s = waySet(open);
  const i = def.states.findIndex((st) => waySet(st.open) === s);
  return i >= 0 ? i : null;
}

/**
 * Hvad tilstanden betyder i ord: hver åben vej ("A igennem AB" — fra den ikke-fælles port igennem den fælles) og de porte, der er
 * blokeret. Fx "A igennem AB · B blokeret"; ingen åbne veje = "alle porte blokeret".
 */
export function describeState(def: FlowDef | undefined, open: string[]): string {
  if (!def) return '';
  const common = new Set(def.ports.filter((p) => p.common).map((p) => p.name));
  const used = new Set<string>();
  const parts: string[] = [];
  for (const k of [...new Set(open.map(wayNorm))]) {
    const [a, b] = k.split('|');
    used.add(a); used.add(b);
    const orig = open.find((o) => wayNorm(o) === k)?.split('>') ?? [a, b];
    const [x, y] = common.has(orig[0]) && !common.has(orig[1]) ? [orig[1], orig[0]] : [orig[0], orig[1]];
    parts.push(`${x} igennem ${y}`);
  }
  const blocked = def.ports.map((p) => p.name).filter((n) => !used.has(n));
  if (!parts.length) return 'alle porte blokeret';
  return blocked.length ? `${parts.join(', ')} · ${blocked.join(' og ')} blokeret` : parts.join(', ');
}

/** Gæt tilstanden for en position: navnet (fx "A → AB"), ellers samme nummer som positionen. */
export function guessState(def: FlowDef | undefined, label: string, j: number): number | null {
  const states = def?.states ?? [];
  if (!states.length) return null;
  const norm = (s: string) => s.replace(/\s+/g, '').replace(/→|->/g, '>').toUpperCase();
  const hit = states.findIndex((s) => norm(s.name) === norm(label));
  return hit >= 0 ? hit : j < states.length ? j : null;
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
  const known = new Set(waysOf(def).map((w) => wayNorm(wayKey(w))));
  const seen = new Set<string>();
  for (const st of def.states ?? []) {
    const n = st.name.trim();
    if (!n || n.length > 30) return 'Giv hver tilstand et navn (højst 30 tegn)';
    if (seen.has(n.toLowerCase())) return `Tilstanden '${n}' findes to gange`;
    seen.add(n.toLowerCase());
    for (const k of st.open) if (!known.has(wayNorm(k))) return `Tilstanden '${n}': vejen ${k} findes ikke på symbolet`;
  }
  return null;
}

/** Typernes tilslutningspunkter til Tegn (v6.8.5): { type: [[x, y], …] } fra "Ind/ud og veje" — så Tegn og flowberegningen
 *  kender de samme punkter. Typer uden punkter er ikke med (de får Tegns automatiske punkter). */
export function typePortMap(defs: FlowDefs): Record<string, [number, number][]> {
  const out: Record<string, [number, number][]> = {};
  for (const [t, d] of Object.entries(defs)) {
    const pts = (d?.ports ?? []).filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)).map((p): [number, number] => [p.x, p.y]);
    if (pts.length) out[t] = pts;
  }
  return out;
}
