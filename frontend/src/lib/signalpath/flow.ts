// Signalveje: symbolernes porte og veje, løbelys og retning. Del af signalPath.ts (v4.15.1).
import { matchPorts, parseWay, sameWay, waysOf, wayKey, type FlowDefs, type PortDef } from '../symbolFlow';
import { TOL, dist, onLine, roleOf, type Flow, type GNode, type Graph, type Pt, type Step } from './graph';
/** Hvad søgningen ved om symbolernes porte: knuder, definitioner og de veje, brugeren har tvunget (knude → "AB>A"). */
export interface Ctx { byId: Map<string, GNode>; defs?: FlowDefs; forced?: Record<string, string> }

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
export const nameOf = (n: GNode | undefined, id: string) => n?.name || id;

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
