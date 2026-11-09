// Signalveje: rutesøgning mellem to symboler, evt. via udvalgte punkter. Del af signalPath.ts (v4.15.1).
import type { FlowDefs } from '../symbolFlow';
import { MAX_STEPS, TOL, contacts, dist, passable, type Contact, type Graph, type GNode, type Pt, type Step } from './graph';
import { passAllowed, portAt, type Ctx } from './flow';
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

// ---------------------------------------------------------------- gå via (v4.15.0)
export interface ViaResult { path: Step[] | null; missing: string[] }

/**
 * Vejen fra start til slut, der går igennem `via` — elementer, brugeren har klikket på (rør eller symboler). Punkterne tages i
 * den rækkefølge, de ligger fra start (færrest elementer), og vejen er den korteste mellem hvert par. Et punkt, der ikke kan nås,
 * eller som ville få vejen til at vende om (samme element to gange), springes over og returneres i `missing`. Uden brugbare
 * punkter er det den almindelige korteste vej.
 */
export function findViaPath(g: Graph, start: string, end: string, via: string[], tol = TOL, opts: PathOpts = {}): ViaResult {
  const missing: string[] = [];
  const first = (a: string, b: string): Step[] | null => findPaths(g, a, b, 1, tol, opts)[0] ?? null;
  const dist = new Map<string, number>();
  for (const v of via) {
    const p = v === start || v === end ? null : first(start, v);
    if (p) dist.set(v, p.length);
    else missing.push(v);
  }
  const stops = [...dist.keys()].sort((a, b) => dist.get(a)! - dist.get(b)!);

  /** Vejen gennem punkterne i rækkefølge, eller hvilket punkt (indeks) der ikke kan bruges (stops.length = slutpunktet). */
  const build = (list: string[]): { path: Step[] } | { bad: number } => {
    let chain: Step[] = [];
    let last = start;
    for (let i = 0; i <= list.length; i++) {
      const stop = i < list.length ? list[i] : end;
      const seg = first(last, stop);
      if (!seg) return { bad: i };
      const used = new Set(chain.map((x) => x.id));
      // krydser vejen sig selv (et punkt på en blindgyde, eller en vej tilbage gennem det samme), kan punktet ikke bruges
      if (chain.length && (seg.slice(1, -1).some((x) => used.has(x.id)) || (i < list.length && used.has(stop)))) return { bad: i };
      if (!chain.length) chain = seg.map((x) => ({ ...x }));
      else {
        const join = chain[chain.length - 1];          // elementet, de to stykker mødes i: ind fra det første, ud af det andet
        join.exit = seg[0].exit;
        chain.push(...seg.slice(1).map((x) => ({ ...x })));
      }
      last = stop;
    }
    return { path: chain };
  };

  let list = stops;
  for (;;) {
    const r = build(list);
    if ('path' in r) return { path: r.path.length <= MAX_STEPS ? r.path : null, missing };
    if (!list.length) return { path: null, missing };
    // slutpunktet kan ikke nås fra det sidste punkt: det er det sidste punkt, der er i vejen
    const drop = Math.min(r.bad, list.length - 1);
    missing.push(list[drop]);
    list = list.filter((_, i) => i !== drop);
  }
}
