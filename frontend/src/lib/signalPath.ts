// Signalveje i Tegn (v4.2.0, PLAN.md › Signalvej): find rørvejen mellem to symboler ud fra tegningens forbindelser og
// beregn, hvilke dele der skal have løbelys og i hvilken retning. Rene beregninger på grafen fra scada-core
// `connectionGraph()` — testet i signalPath.test.ts. Gemmes af backend (services/signal_paths.py).

import { matchPorts, parseWay, sameWay, waysOf, wayKey, type FlowDefs, type PortDef } from './symbolFlow';

export type Pt = [number, number];
export interface GLine { part: string; a: Pt; b: Pt; pts?: Pt[]; w?: number; dash?: boolean }   // w: tykkelse, dash: stiplet
export interface GNode {
  id: string; name: string; type: string; pipe: boolean; terminals: Pt[]; lines: GLine[]; refs: (string | null)[];
  fracs?: Pt[] | null;   // punkternes placering som brøkdele af symbolets boks (samme rækkefølge som terminals) — til navne og roller
}
export interface Graph { nodes: GNode[] }
export interface Contact { to: string; p: Pt }
export interface Step { id: string; entry: Pt | null; exit: Pt | null }
export type Role = 'pipe' | 'valve' | 'threeway' | 'pump' | 'switch' | 'check' | 'unit';
export interface Flow { part: string; reverse: boolean }

export const TOL = 8;          // to punkter inden for så mange enheder hænger sammen (rør er typisk 10 brede)
export const MAX_STEPS = 200;
/** En tegnet streg uden symboltype er kun et rør, hvis den er mindst så tyk (rør er typisk 10) og ikke stiplet: tynde og stiplede
 * streger er føler-, kapillar- og signallinjer (v4.13.0). Uden kendt tykkelse (ældre grafer) regnes den som et rør. */
export const MIN_PIPE_WIDTH = 5;
const pipeLike = (l: GLine) => !l.dash && (l.w === undefined || l.w >= MIN_PIPE_WIDTH);

const dist = (p: Pt, q: Pt) => Math.hypot(p[0] - q[0], p[1] - q[1]);
const mid = (p: Pt, q: Pt): Pt => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];

/** Afstand fra p til linjestykket a–b og hvor langt ude ad stykket det nærmeste punkt ligger (0–1). */
function toSegment(p: Pt, a: Pt, b: Pt): { d: number; t: number } {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy;
  const t = l2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0;
  return { d: dist(p, [a[0] + t * dx, a[1] + t * dy]), t };
}
/** Nærmeste sted på en streg: afstand og position (0 = a-enden, 1 = b-enden) målt i antal stykker. */
export function onLine(p: Pt, l: GLine): { d: number; pos: number } {
  const pts = l.pts && l.pts.length >= 2 ? l.pts : [l.a, l.b];
  let best = { d: Infinity, pos: 0 };
  for (let i = 1; i < pts.length; i++) {
    const r = toSegment(p, pts[i - 1], pts[i]);
    if (r.d < best.d) best = { d: r.d, pos: (i - 1 + r.t) / (pts.length - 1) };
  }
  return best;
}

const PIPE_TYPES = new Set(['roer_l', 'roer_v', 'boejning45', 'boejning90', 't_stykke', 'kryds', 'reduktion', 'flange',
  'ledning_l', 'ledning_v', 'forbindelse', 'klemme']);
const VALVES = new Set(['kugleventil', 'magnetventil', 'motorventil', 'regventil', 'ventil']);
const THREEWAY = new Set(['trevejs_motorventil', 'trevejsventil']);
const PUMPS = new Set(['pumpe', 'motor', 'motor3', 'varmepumpe']);
const SWITCHES = new Set(['kontakt_no', 'kontakt_nc', 'kontaktor', 'kontakt2', 'kontakt3', 'ac_afbryder', 'dc_afbryder',
  'hovedafbryder', 'automatsikring', 'sikring', 'motorvaern', 'omskifter3']);

// Visning og betjening (ikke en del af anlægget): en vej kan hverken gå igennem dem eller starte/slutte i dem
const DISPLAY = new Set(['statusfelt', 'trendgraf', 'segdisplay7', 'segdisplay11', 'setpunkt', 'knap', 'startstop', 'signallampe',
  'lampe', 'genvej_alarmer', 'genvej_trends', 'genvej_energi', 'flowpil', 'energipil', 'automanuel', 'drejeomskifter', 'noedstop']);

/** Kan en vej gå igennem elementet? Rør, ventiler, pumper og anlægsdele (kedel, tank …) — ikke visning og løse figurer. */
export function passable(n: Pick<GNode, 'type' | 'pipe' | 'lines'>): boolean {
  if (DISPLAY.has(n.type)) return false;
  return roleOf(n) !== 'unit' || n.type !== '';
}

/** Hvad et element gør på vejen: rør (får løbelys), noget der spørges om (ventil, pumpe, kontakt …) eller passivt. */
export function roleOf(n: Pick<GNode, 'type' | 'pipe' | 'lines'>): Role {
  if (n.pipe || PIPE_TYPES.has(n.type)) return 'pipe';
  if (VALVES.has(n.type)) return 'valve';
  if (THREEWAY.has(n.type)) return 'threeway';
  if (PUMPS.has(n.type)) return 'pump';
  if (SWITCHES.has(n.type)) return 'switch';
  if (n.type === 'kontraventil') return 'check';
  if (!n.type && n.lines.some(pipeLike)) return 'pipe';      // en tegnet streg/figur uden symboltype (ikke en tynd/stiplet føler-linje)
  return 'unit';
}
export const ASKS: Role[] = ['valve', 'threeway', 'pump', 'switch'];
export const QUESTION: Record<Role, string> = {
  valve: 'Hvornår er ventilen åben?', threeway: 'Hvornår leder 3-vejsventilen flowet denne vej?',
  pump: 'Hvornår kører den?', switch: 'Hvornår er kontakten sluttet?', pipe: '', check: '', unit: '',
};

/** Naboer: tilslutningspunkter der falder sammen, og rør-ender der sidder fast i et symbol. */
export function contacts(g: Graph, tol = TOL): Map<string, Contact[]> {
  const out = new Map<string, Contact[]>(g.nodes.map((n) => [n.id, []]));
  const add = (a: string, b: string, p: Pt) => {
    if (a === b || !out.has(a) || !out.has(b)) return;
    const list = out.get(a)!;
    if (!list.some((c) => c.to === b && dist(c.p, p) <= tol)) list.push({ to: b, p });
  };
  const ns = g.nodes;
  for (let i = 0; i < ns.length; i++) {
    for (let j = i + 1; j < ns.length; j++) {
      for (const p of ns[i].terminals) {
        for (const q of ns[j].terminals) {
          if (dist(p, q) <= tol) {
            add(ns[i].id, ns[j].id, mid(p, q));
            add(ns[j].id, ns[i].id, mid(p, q));
          }
        }
      }
    }
  }
  // Afgrening uden T-stykke: et punkt (ende/tilslutning) der ligger midt på et andet elements streg
  for (const n of ns) {
    for (const p of n.terminals) {
      for (const o of ns) {
        if (o === n || o.lines.length === 0) continue;
        if (o.lines.some((l) => onLine(p, l).d <= tol)) {
          add(n.id, o.id, p);
          add(o.id, n.id, p);
        }
      }
    }
  }
  for (const n of ns) {
    n.refs.forEach((ref, k) => {
      const p = n.terminals[k === 0 ? 0 : n.terminals.length - 1];
      if (ref && p) {
        add(n.id, ref, p);
        add(ref, n.id, p);
      }
    });
  }
  return out;
}

/** Korteste vej (færrest elementer) fra start til slut. Et element på vejen skal forlades et andet sted end det blev
 * nået (ellers "rører" vejen det kun). `banned`: elementer vejen ikke må gå igennem. */
/** Hvad søgningen ved om symbolernes porte: knuder, definitioner og de veje, brugeren har tvunget (knude → "AB>A"). */
interface Ctx { byId: Map<string, GNode>; defs?: FlowDefs; forced?: Record<string, string> }

const portCache = new WeakMap<GNode, { defs: FlowDefs; ports: (PortDef | null)[] }>();
/** Portene på et symbol (efter definitionen for dets type): en pr. punkt, null hvor intet passer. */
export function portsOfNode(n: GNode, defs?: FlowDefs): (PortDef | null)[] {
  if (!defs || n.pipe || !n.fracs || n.fracs.length !== n.terminals.length || !defs[n.type]) return [];
  const c = portCache.get(n);
  if (c && c.defs === defs) return c.ports;
  const ports = matchPorts(defs[n.type], n.fracs);
  portCache.set(n, { defs, ports });
  return ports;
}
/** Porten ved et punkt (det nærmeste tilslutningspunkt inden for `tol`), eller null. */
export function portAt(n: GNode, p: Pt | null, defs?: FlowDefs, tol = TOL * 2): PortDef | null {
  const ports = portsOfNode(n, defs);
  if (!p || !ports.length) return null;
  let best = -1, bd = Infinity;
  n.terminals.forEach((t, i) => { const d = dist(t, p); if (d < bd) { bd = d; best = i; } });
  if (best >= 0 && bd <= tol) return ports[best];
  // Et rør, der ender på selve ventilens streg (ikke i et tilslutningspunkt): porten, hvis del (port_ab …) ligger nærmest
  let hit: PortDef | null = null;
  let hd = tol * 1.5;
  for (const port of ports) {
    if (!port?.part) continue;
    for (const l of n.lines) {
      if (l.part !== port.part && !l.part.endsWith(`_${port.part}`)) continue;
      const d = onLine(p, l).d;
      if (d <= hd) { hd = d; hit = port; }
    }
  }
  return hit;
}
/** Må vejen gå ind ved `a` og ud ved `b` i dette symbol? Kun gennem symbolets veje (eller den tvungne); uden veje: altid. */
export function passAllowed(n: GNode, a: PortDef | null, b: PortDef | null, defs?: FlowDefs, forced?: string): boolean {
  const ways = waysOf(defs?.[n.type]);
  if (!ways.length) return true;
  if (!a || !b) return !forced;
  const want = forced ? parseWay(forced) : null;
  return want ? sameWay(want, a.name, b.name) : ways.some((w) => sameWay(w, a.name, b.name));
}

function shortest(adj: Map<string, Contact[]>, pass: Set<string>, start: string, end: string, banned: Set<string>, tol: number,
  ctx?: Ctx): Step[] | null {
  interface S { id: string; entry: Pt | null; prev: number; via: Pt | null }
  const states: S[] = [{ id: start, entry: null, prev: -1, via: null }];
  const seen = new Set<string>([`${start}`]);
  const key = (id: string, p: Pt) => `${id}@${Math.round(p[0] / tol)},${Math.round(p[1] / tol)}`;
  for (let i = 0; i < states.length; i++) {
    const s = states[i];
    if (s.id === end) {
      const steps: Step[] = [];
      let k = i;
      let exit: Pt | null = null;
      while (k >= 0) {
        steps.unshift({ id: states[k].id, entry: states[k].entry, exit });
        exit = states[k].entry;
        k = states[k].prev;
      }
      return steps.length <= MAX_STEPS ? steps : null;
    }
    if (i > 0 && s.id !== end && !pass.has(s.id)) continue;   // kan ikke gå videre gennem visning/løse figurer
    const here = ctx && i > 0 ? ctx.byId.get(s.id) : undefined;
    for (const c of adj.get(s.id) ?? []) {
      if (banned.has(c.to) || (s.entry && dist(c.p, s.entry) <= tol)) continue;
      // et flervejs-symbol (3-vejsventil) kan kun passeres gennem en af sine veje
      if (here && ctx && !passAllowed(here, portAt(here, s.entry, ctx.defs), portAt(here, c.p, ctx.defs), ctx.defs, ctx.forced?.[s.id])) continue;
      const k = key(c.to, c.p);
      if (seen.has(k) || states.some((x, idx) => x.id === c.to && onPath(states, i, idx))) continue;
      seen.add(k);
      states.push({ id: c.to, entry: c.p, prev: i, via: c.p });
    }
  }
  return null;
}
/** Er state `idx` et af forgængerne til state `i` (så vejen ikke går i ring)? */
function onPath(states: { prev: number }[], i: number, idx: number): boolean {
  for (let k = i; k >= 0; k = states[k].prev) if (k === idx) return true;
  return false;
}

/** Op til `k` forskellige veje fra start til slut, korteste først. */
export interface PathOpts { defs?: FlowDefs; forced?: Record<string, string> }
export function findPaths(g: Graph, start: string, end: string, k = 3, tol = TOL, opts: PathOpts = {}): Step[][] {
  const adj = contacts(g, tol);
  const pass = new Set(g.nodes.filter(passable).map((n) => n.id));
  const ctx: Ctx | undefined = opts.defs || opts.forced ? { byId: new Map(g.nodes.map((n) => [n.id, n])), ...opts } : undefined;
  const best = shortest(adj, pass, start, end, new Set(), tol, ctx);
  if (!best) return [];
  const found = [best];
  const sig = (p: Step[]) => p.map((s) => s.id).join('>');
  // Alternativer: forbyd ét element ad gangen fra den bedste vej
  for (const s of best.slice(1, -1)) {
    const alt = shortest(adj, pass, start, end, new Set([s.id]), tol, ctx);
    if (alt && !found.some((f) => sig(f) === sig(alt))) found.push(alt);
  }
  return found.sort((a, b) => a.length - b.length).slice(0, k);
}

/** Løbelys for et rør-element på vejen: de streger der rører ind- eller udgangen, i vejens retning. */
export function flowsFor(n: GNode, entry: Pt | null, exit: Pt | null, tol = TOL * 2): Flow[] {
  if (roleOf(n) !== 'pipe') return [];
  const near = (p: Pt, q: Pt | null) => q !== null && dist(p, q) <= tol;
  const out: Flow[] = [];
  for (const l of n.lines) {
    const aIn = near(l.a, entry), bIn = near(l.b, entry), aOut = near(l.a, exit), bOut = near(l.b, exit);
    if (aIn || bOut) out.push({ part: l.part, reverse: false });        // løber fra a (ind) mod b (ud)
    else if (bIn || aOut) out.push({ part: l.part, reverse: true });
  }
  // Ingen ende ramte ind- eller udgangen (vejen går ind/ud midt på stregen, eller et skaleret rør-symbol):
  // retningen ud fra hvor langt ude ad stregen ind- og udgangen ligger
  if (!out.length && (entry || exit)) {
    for (const l of n.lines) {
      const pin = entry ? onLine(entry, l) : null;
      const pout = exit ? onLine(exit, l) : null;
      if ((pin?.d ?? Infinity) > tol && (pout?.d ?? Infinity) > tol && n.lines.length > 1) continue;
      const from = pin ? pin.pos : (pout!.pos > 0.5 ? 0 : 1);
      const to = pout ? pout.pos : (pin!.pos > 0.5 ? 0 : 1);
      out.push({ part: l.part, reverse: to < from });
    }
  }
  return out;
}

// ---------------------------------------------------------------- retning fra symbolerne (v4.13.0)
export interface Oriented { steps: Step[]; flipped: boolean; warnings: string[]; by: string[] }   // by: de symboler, der gav retningen
const nameOf = (n: GNode | undefined, id: string) => n?.name || id;

/**
 * Vejens retning ud fra symbolernes ind/ud: sidder der en pumpe (eller kontraventil) på vejen, løber flowet fra dens udgang
 * mod resten, uanset hvilket symbol der blev valgt som start. Går vejen mod ALLE retningsgivende symboler, vendes den; er de
 * uenige, bevares start → slut, og de uenige nævnes. Uden retningsgivende symboler: uændret.
 */
export function orient(g: Graph, steps: Step[], defs?: FlowDefs): Oriented {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const fwd: string[] = [], back: string[] = [], warnings: string[] = [];
  for (const s of steps) {
    const n = byId.get(s.id);
    if (!n) continue;
    const a = portAt(n, s.entry, defs), b = portAt(n, s.exit, defs);
    const f = a?.role === 'in' || b?.role === 'out';
    const r = a?.role === 'out' || b?.role === 'in';
    if (f && r) warnings.push(`${nameOf(n, s.id)}: vejen går ind og ud af samme side`);
    else if (f) fwd.push(nameOf(n, s.id));
    else if (r) back.push(nameOf(n, s.id));
  }
  if (back.length && !fwd.length) {
    return { steps: steps.slice().reverse().map((s) => ({ id: s.id, entry: s.exit, exit: s.entry })), flipped: true, warnings, by: back };
  }
  if (back.length && fwd.length) warnings.push(`Retningen er uenig: ${fwd.join(', ')} løber med vejen, ${back.join(', ')} mod den`);
  return { steps, flipped: false, warnings, by: fwd };
}

/** Flervejs-ventilens vej, vejen bruger (fælles port først: "AB>A"), eller null. */
export function wayUsed(n: GNode, s: Step, defs?: FlowDefs): string | null {
  const ways = waysOf(defs?.[n.type]);
  if (!ways.length) return null;
  const a = portAt(n, s.entry, defs), b = portAt(n, s.exit, defs);
  if (!a || !b) return null;
  const w = ways.find((x) => sameWay(x, a.name, b.name));
  return w ? wayKey(w) : null;
}

export interface PathRow { id: string; name: string; type: string; role: Role; flows: Flow[] }

/** Vejen som rækker til guiden og til backend. */
export function describe(g: Graph, steps: Step[]): PathRow[] {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  return steps.map((s) => {
    const n = byId.get(s.id)!;
    return { id: n.id, name: n.name, type: n.type, role: roleOf(n), flows: flowsFor(n, s.entry, s.exit) };
  });
}

/** Kort beskrivelse af en vej: "Kedel → P1 → V2 → Radiator (12 dele)". */
export function summary(rows: PathRow[]): string {
  const named = rows.filter((r, i) => i === 0 || i === rows.length - 1 || (r.role !== 'pipe' && r.name));
  return `${named.map((r) => r.name || r.id).join(' → ')} (${rows.length} dele)`;
}

/** Symboler man kan vælge som start/slut: alle ikke-rør med navn eller type, sorteret efter navn. */
export function endpoints(g: Graph): { id: string; label: string }[] {
  return g.nodes.filter((n) => !n.pipe && roleOf(n) !== 'pipe' && !DISPLAY.has(n.type) && (n.name || n.type))
    .map((n) => ({ id: n.id, label: n.name || `${n.type} (${n.id})` }))
    .sort((a, b) => a.label.localeCompare(b.label, 'da'));
}

// ---------------------------------------------------------------- svar → betingelser (backend: services/signal_paths.py)
export interface TagInfo { name: string; is_bool: boolean; unit: string; description: string }
export type Cmp = '' | 'ge' | 'le' | 'eq';
/** Svaret for ét symbol: ingen betingelse, eller et tag (til/fra, eller et tal sammenlignet med en grænse). */
export interface Answer { element: string; src: string; on: boolean; cmp: Cmp; value: number | null }
export interface Condition { element: string; src: string; neg: boolean; cmp: Cmp; value: number | null }

/** Forslag ud fra symbolets egne tags: helst et til/fra-tag (tilbagemelding), ellers ingen betingelse. */
export function suggestAnswer(element: string, own: TagInfo[]): Answer {
  const t = own.find((x) => x.is_bool) ?? own[0];
  if (!t) return { element, src: '', on: true, cmp: '', value: null };
  return t.is_bool ? { element, src: t.name, on: true, cmp: '', value: null } : { element, src: t.name, on: true, cmp: 'ge', value: 1 };
}

/** Svarene → betingelser til backend. Tomme svar (ingen betingelse) springes over. → { conditions, errors } */
export function conditionsFrom(answers: Answer[], tags: TagInfo[]): { conditions: Condition[]; errors: string[] } {
  const byName = new Map(tags.map((t) => [t.name, t]));
  const conditions: Condition[] = [];
  const errors: string[] = [];
  for (const a of answers) {
    if (!a.src) continue;
    const t = byName.get(a.src);
    if (!t) {
      errors.push(`Tagget '${a.src}' findes ikke`);
      continue;
    }
    if (t.is_bool) conditions.push({ element: a.element, src: a.src, neg: !a.on, cmp: '', value: null });
    else if (!a.cmp || a.value === null || !Number.isFinite(a.value)) errors.push(`${a.src}: vælg ≥, ≤ eller = og en grænseværdi`);
    else conditions.push({ element: a.element, src: a.src, neg: false, cmp: a.cmp, value: a.value });
  }
  return { conditions, errors };
}

/** En gemt betingelse tilbage til et svar (når en signalvej rettes). */
export function answerFrom(c: Condition): Answer {
  return { element: c.element, src: c.src, on: !c.neg, cmp: c.cmp, value: c.value };
}

// ---------------------------------------------------------------- vælg start/slut ved klik i tegningen (v4.5.0)
/** Det element, der netop er valgt i tegningen, som start eller slut — eller en forklaring på, hvorfor det ikke kan bruges. */
export function pickNext(which: 'start' | 'end', selected: string[], allowed: Set<string>, start: string): { id?: string; error?: string } {
  const id = selected.find((s) => allowed.has(s));
  if (!id) return { error: 'Det valgte er et rør, en tekst eller en visning — klik på et anlægssymbol (fx kedel, pumpe, radiator)' };
  if (which === 'end' && id === start) return { error: 'Det er startsymbolet — klik på et andet symbol som slut' };
  return { id };
}


// ---------------------------------------------------------------- net med grene (v4.13.0): ét start, flere slutpunkter
export const MAX_ENDS = 4;
/** Hvordan en gren bruger et element: hvilken vej gennem en flervejs-ventil, og hvor den går ind og ud. */
export interface Use { branch: number; way: string | null; entry: Pt | null; exit: Pt | null }
export interface NetRow extends PathRow { branches: number[]; uses: Use[] }
export interface Net { rows: NetRow[]; warnings: string[]; flipped: boolean[]; by: string[][] }   // by: hvem gav grenens retning

/**
 * Grenene (en vej pr. slutpunkt) samlet til ét net. Hvert element står én gang med de dele, mindst én gren bruger, hver i sin
 * retning. Grenenes retning følger symbolernes ind/ud (`orient`). To grene, der bruger samme del i hver sin retning, nævnes.
 */
export function describeNet(g: Graph, paths: Step[][], defs?: FlowDefs): Net {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const rows = new Map<string, NetRow>();
  const warnings: string[] = [];
  const flipped: boolean[] = [];
  const by: string[][] = [];
  paths.forEach((path, b) => {
    const o = orient(g, path, defs);
    flipped.push(o.flipped);
    by.push(o.by);
    warnings.push(...(paths.length === 1 ? o.warnings : o.warnings.map((w) => `Gren ${b + 1}: ${w}`)));
    for (const st of o.steps) {
      const n = byId.get(st.id);
      if (!n) continue;
      const flows = flowsFor(n, st.entry, st.exit);
      let row = rows.get(st.id);
      if (!row) {
        row = { id: n.id, name: n.name, type: n.type, role: roleOf(n), flows: [], branches: [], uses: [] };
        rows.set(st.id, row);
      }
      for (const f of flows) {
        const have = row.flows.find((x) => x.part === f.part);
        if (!have) row.flows.push(f);
        else if (have.reverse !== f.reverse) warnings.push(`${nameOf(n, n.id)}: grenene løber i hver sin retning gennem samme del`);
      }
      if (!row.branches.includes(b)) row.branches.push(b);
      row.uses.push({ branch: b, way: wayUsed(n, st, defs), entry: st.entry, exit: st.exit });
    }
  });
  return { rows: [...rows.values()], warnings: [...new Set(warnings)], flipped, by };
}

/** Et spørgsmål i guiden: "hvornår går der flow gennem V1?" — for en flervejs-ventil ét pr. vej, der bruges. */
export interface Question { key: string; element: string; role: Role; way: string | null; branches: number[] }
export function questionsOf(rows: NetRow[]): Question[] {
  const out: Question[] = [];
  for (const r of rows) {
    if (!ASKS.includes(r.role)) continue;
    const ways = [...new Set(r.uses.map((u) => u.way))];
    const keyed = ways.length > 1 || ways[0] !== null;
    for (const w of ways) {
      const branches = [...new Set(r.uses.filter((u) => u.way === w).map((u) => u.branch))].sort((a, b) => a - b);
      out.push({ key: keyed && w ? `${r.id}@${w}` : r.id, element: r.id, role: r.role, way: w, branches });
    }
  }
  return out;
}
