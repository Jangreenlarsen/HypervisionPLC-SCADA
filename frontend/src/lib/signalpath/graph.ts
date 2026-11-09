// Signalveje: grafen fra tegningen (typer, geometri, roller, naboer). Del af signalPath.ts (v4.15.1).
export type Pt = [number, number];
export interface GLine { part: string; a: Pt; b: Pt; pts?: Pt[]; w?: number; dash?: boolean }   // w: tykkelse, dash: stiplet
export interface GNode {
  id: string; name: string; type: string; pipe: boolean; terminals: Pt[]; lines: GLine[]; refs: (string | null)[];
  fracs?: Pt[] | null;   // punkternes placering som brøkdele af symbolets boks (samme rækkefølge som terminals) — til navne og roller
}
export interface Graph { nodes: GNode[] }
export interface Contact { to: string; p: Pt }

/** Et fingeraftryk af grafens geometri (id'er, punkter, streger): uændret = tegningen er den samme, og vejen skal ikke regnes forfra. */
export function graphKey(g: Graph): string {
  const r = (v: number) => Math.round(v * 10) / 10;
  return g.nodes.map((n) => `${n.id}|${n.type}|${n.terminals.map((t) => `${r(t[0])},${r(t[1])}`).join(';')}|` +
    n.lines.map((l) => `${l.part}:${r(l.a[0])},${r(l.a[1])}-${r(l.b[0])},${r(l.b[1])}:${l.w ?? ''}${l.dash ? 'd' : ''}`).join(';')).join('\n');
}
export interface Step { id: string; entry: Pt | null; exit: Pt | null }
export type Role = 'pipe' | 'valve' | 'threeway' | 'pump' | 'switch' | 'check' | 'unit';
export interface Flow { part: string; reverse: boolean }

export const TOL = 8;          // to punkter inden for så mange enheder hænger sammen (rør er typisk 10 brede)
export const MAX_STEPS = 200;
/** En tegnet streg uden symboltype er kun et rør, hvis den er mindst så tyk (rør er typisk 10) og ikke stiplet: tynde og stiplede
 * streger er føler-, kapillar- og signallinjer (v4.13.0). Uden kendt tykkelse (ældre grafer) regnes den som et rør. */
export const MIN_PIPE_WIDTH = 5;
const pipeLike = (l: GLine) => !l.dash && (l.w === undefined || l.w >= MIN_PIPE_WIDTH);

export const dist = (p: Pt, q: Pt) => Math.hypot(p[0] - q[0], p[1] - q[1]);
export const mid = (p: Pt, q: Pt): Pt => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];

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

/** Symboler man kan vælge som start/slut: alle ikke-rør med navn eller type, sorteret efter navn. */
export function endpoints(g: Graph): { id: string; label: string }[] {
  return g.nodes.filter((n) => !n.pipe && roleOf(n) !== 'pipe' && !DISPLAY.has(n.type) && (n.name || n.type))
    .map((n) => ({ id: n.id, label: n.name || `${n.type} (${n.id})` }))
    .sort((a, b) => a.label.localeCompare(b.label, 'da'));
}
