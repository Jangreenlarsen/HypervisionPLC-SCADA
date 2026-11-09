// Signalveje: nettet med grene og spørgsmålene til guiden. Del af signalPath.ts (v4.15.1).
import type { FlowDefs } from '../symbolFlow';
import { ASKS, roleOf, type Flow, type Graph, type Pt, type Role, type Step } from './graph';
import { flowsFor, nameOf, orient, wayUsed } from './flow';
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
