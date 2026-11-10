// Signalveje: grafen fra tegningen (typer, geometri, roller, naboer). Del af signalPath.ts (v4.15.1).
export type Pt = [number, number];
export interface GLine { part: string; a: Pt; b: Pt; pts?: Pt[]; w?: number; dash?: boolean }   // w: tykkelse, dash: stiplet
export interface GNode {
  id: string; name: string; type: string; pipe: boolean; terminals: Pt[]; lines: GLine[]; refs: (string | null)[];
  fracs?: Pt[] | null;   // punkternes placering som brøkdele af symbolets boks (samme rækkefølge som terminals) — til navne og roller
  keys?: string[];       // en nøgle pr. punkt (til "ikke i brug"), samme rækkefølge som terminals (v4.22.0)
  unused?: number[];     // numrene på de punkter, brugeren har markeret som ikke i brug (data-hv-unused)
  exempt?: boolean;      // hele symbolet er udeladt fra tjekket af forbindelser
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

// ---------------------------------------------------------------- tjek af forbindelser (v4.18.0)
/** ok: alle tilslutningspunkter sidder fast i noget · open: nogle er åbne · isolated: elementet hænger slet ikke sammen med noget. */
export type ConnStatus = 'ok' | 'open' | 'isolated';
export interface ConnItem {
  id: string; name: string; type: string; pipe: boolean; status: ConnStatus;
  exempt: boolean;                           // brugeren har udeladt hele symbolet (status er så altid ok)
  open: Pt[]; openKeys: string[];            // åbne punkter og deres nøgler
  ignored: Pt[]; ignoredKeys: string[];      // punkter, brugeren har markeret som ikke i brug
}

/**
 * Hvilke symboler og rør der hænger fast i resten af tegningen. Et tilslutningspunkt er forbundet, når et andet elements punkt
 * falder sammen med det, det ligger på et andet elements streg, eller et rør er knyttet til det. Samme regler som signalvejene
 * (`contacts`). Visning (statusfelter, trendgrafer …) og løse figurer uden symboltype og uden tilslutningspunkter springes over.
 */
/** Rørstykkernes (bøjning, T-stykke …) egentlige ender: tilslutningspunkter, der blot er et styrepunkt tæt ved en ende (bøjningens
 * kurve), eller ligger midt mellem to andre (T-stykkets midte), er ikke steder, et rør kan sidde fast. */
function realEnds(n: GNode, tol: number): Pt[] {
  const ts = n.terminals;
  if (n.pipe || roleOf(n) !== 'pipe' || ts.length <= 2) return ts;
  const between = (p: Pt, a: Pt, b: Pt) => {
    const d = dist(a, b);
    return d > 0 && Math.abs(dist(a, p) + dist(p, b) - d) <= tol / 2;
  };
  const kept = ts.filter((p, i) => !ts.some((a, j) => j !== i && ts.some((b, k) => k > j && k !== i && between(p, a, b))));
  const seen: Pt[] = [];
  for (const p of kept) {                    // punkter tæt ved hinanden er én ende (den, der er forbundet, tæller)
    const near = seen.findIndex((q) => dist(p, q) <= tol * 2);
    if (near < 0) seen.push(p);
  }
  return seen.length ? seen : ts;
}

export function connectionCheck(g: Graph, tol = TOL): ConnItem[] {
  const adj = contacts(g, tol);
  const out: ConnItem[] = [];
  for (const n of g.nodes) {
    if (!passable(n) || !n.terminals.length) continue;
    const mine = adj.get(n.id) ?? [];
    if (n.exempt) {
      out.push({ id: n.id, name: n.name, type: n.type, pipe: n.pipe || roleOf(n) === 'pipe', exempt: true, status: 'ok', open: [], openKeys: [], ignored: [], ignoredKeys: [] });
      continue;
    }
    const ends = realEnds(n, tol);
    const skipIdx = (n.unused ?? []).filter((i) => i >= 0 && i < n.terminals.length);
    const isSkipped = (p: Pt) => skipIdx.some((i) => dist(n.terminals[i], p) <= 0.01);
    const keyOf = (p: Pt) => { const i = n.terminals.findIndex((t) => dist(t, p) <= 0.01); return n.keys?.[i] ?? `#${i}`; };
    // tæt-på-punkter i en bøjning er én ende: den er forbundet, hvis et af dem er det. Punkter markeret som ikke i brug tæller ikke.
    const open = ends.filter((t) => !isSkipped(t) && !mine.some((c) => dist(c.p, t) <= tol * 2));
    const ignored = skipIdx.map((i) => n.terminals[i]);
    out.push({ id: n.id, name: n.name, type: n.type, pipe: n.pipe || roleOf(n) === 'pipe', exempt: false, open, openKeys: open.map(keyOf),
      ignored, ignoredKeys: ignored.map(keyOf), status: !open.length ? 'ok' : mine.length ? 'open' : 'isolated' });
  }
  return out;
}

const STRAIGHT_PIPES = new Set(['roer_l', 'roer_v']);      // lige rør-symboler (kan forlænges/forkortes)
/** En foreslået rettelse: flyt enden `from` på elementet `id` hen til `to` (en ende/et punkt på elementet `toId`). */
export interface FixMove { id: string; from: Pt; to: Pt; toId: string; gap: number }

/**
 * Brudte forbindelser, der tydeligvis skal sidde sammen: en åben ende på et rør (eller rørstykke), der ligger tæt (over en
 * almindelig forbindelses afstand, men højst `maxGap`) på en anden ende eller et tilslutningspunkt. Den nærmeste vælges (en
 * ende, der selv er åben, foretrækkes ved næsten lige afstand). Kun rørene flyttes — aldrig symbolerne.
 */
export function planFixes(g: Graph, items: ConnItem[], maxGap = 25, tol = TOL): FixMove[] {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const openAt = new Map(items.map((i) => [i.id, i.open]));
  const moves: FixMove[] = [];
  for (const it of items) {
    const me = byId.get(it.id);
    if (!me || !it.open.length || !(me.pipe || STRAIGHT_PIPES.has(me.type))) continue;     // kun rør og lige rør-symboler kan flyttes
    for (const p of it.open) {
      // et lige rør-symbol kan kun forlænges/forkortes i sin egen retning: målet skal ligge på dets akse
      const l = !me.pipe ? me.lines[0] : null;
      const u: Pt | null = l ? [l.b[0] - l.a[0], l.b[1] - l.a[1]] : null;
      const len = u ? Math.hypot(u[0], u[1]) : 0;
      let best: FixMove | null = null;
      let bestOpen = false;
      for (const o of g.nodes) {
        if (o.id === it.id || !passable(o) || !byId.has(o.id)) continue;
        const theirOpen = openAt.get(o.id) ?? [];
        for (const q of realEnds(o, tol)) {
          const d = dist(p, q);
          if (d <= tol || d > maxGap) continue;           // inden for en almindelig forbindelse er der intet at rette
          if (u && len > 0 && Math.abs(((q[0] - p[0]) * u[1] - (q[1] - p[1]) * u[0]) / len) > tol * 2) continue;   // ikke på rørets akse
          const open = theirOpen.some((x) => dist(x, q) <= 0.5);
          if (!best || d < best.gap - 1 || (Math.abs(d - best.gap) <= 1 && open && !bestOpen)) {
            best = { id: it.id, from: p, to: q, toId: o.id, gap: Math.round(d * 10) / 10 };
            bestOpen = open;
          }
        }
      }
      if (best) moves.push(best);
    }
  }
  return moves;
}
