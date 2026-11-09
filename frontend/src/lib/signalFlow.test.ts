import { describe as group, expect, it } from 'vitest';
import { FLOW_DEFAULTS, matchPorts, mergeDefs, parseWay, sameWay, validateDef, waysOf, wayKey, wayLabel } from './symbolFlow';
import { describeNet, endpoints, findPaths, graphKey, orient, passable, portAt, questionsOf, roleOf, wayUsed, type GNode, type Graph, type Pt } from './signalPath';

const pipe = (id: string, a: Pt, b: Pt): GNode => ({ id, name: '', type: '', pipe: true, terminals: [a, b], lines: [{ part: 'all', a, b }], refs: [null, null] });
const sym = (id: string, name: string, type: string, terminals: Pt[], fracs: Pt[] | null = null): GNode =>
  ({ id, name, type, pipe: false, terminals, lines: [], refs: [], fracs });
const DEFS = mergeDefs(null);

/** Kedel → r1 → pumpe (ind til venstre, ud til højre) → r2 → radiator. */
function pumpLine(): Graph {
  return { nodes: [
    sym('kedel', 'Kedel', 'kedel', [[40, 30]]),
    pipe('r1', [40, 30], [100, 30]),
    sym('p1', 'P1', 'pumpe', [[100, 30], [140, 30]], [[0, 0.5], [1, 0.5]]),
    pipe('r2', [140, 30], [200, 30]),
    sym('rad', 'Radiator', 'radiator', [[200, 30]]),
  ] };
}

/** Kilde → rIn → 3-vejsventil (A til venstre, B øverst, AB til højre) → rA → radA og rB → radB. */
function threeWay(): Graph {
  return { nodes: [
    sym('src', 'Kilde', 'kedel', [[300, 100]]),
    pipe('rIn', [300, 100], [200, 100]),
    sym('v3', 'V3', 'trevejs_motorventil', [[100, 100], [150, 60], [200, 100]], [[0.07, 0.46], [0.46, 0.08], [0.84, 0.46]]),
    pipe('rA', [100, 100], [50, 100]),
    sym('radA', 'Radiator A', 'radiator', [[50, 100]]),
    pipe('rB', [150, 60], [150, 0]),
    sym('radB', 'Radiator B', 'radiator', [[150, 0]]),
  ] };
}

group('symbolFlow', () => {
  it('derives the ways from the common port, unless they are given', () => {
    expect(waysOf(FLOW_DEFAULTS.trevejs_motorventil).map(wayLabel)).toEqual(['AB → A', 'AB → B']);
    expect(waysOf(FLOW_DEFAULTS.pumpe)).toEqual([]);                                // ingen fælles port: ingen veje
    const four = { ports: [{ x: 0, y: 0, name: 'P', role: 'both' as const, common: true }, { x: 1, y: 0, name: 'T', role: 'both' as const, common: true },
      { x: 0, y: 1, name: 'A', role: 'both' as const }, { x: 1, y: 1, name: 'B', role: 'both' as const }] };
    expect(waysOf(four).map(wayKey)).toEqual(['P>A', 'P>B', 'T>A', 'T>B']);
    expect(waysOf({ ...four, ways: [['P', 'A'], ['B', 'T']] }).map(wayKey)).toEqual(['P>A', 'B>T']);
    expect(parseWay('AB>A')).toEqual(['AB', 'A']);
    expect(parseWay('AB')).toBeNull();
    expect(sameWay(['AB', 'A'], 'A', 'AB')).toBe(true);
    expect(sameWay(['AB', 'A'], 'B', 'AB')).toBe(false);
  });

  it('matches points to port definitions by position, each definition once', () => {
    const m = matchPorts(FLOW_DEFAULTS.trevejs_motorventil, [[0.07, 0.46], [0.46, 1], [0.84, 0.46], [0.46, 0.08]]);
    expect(m.map((p) => p?.name ?? null)).toEqual(['A', null, 'AB', 'B']);          // motorens punkt (nederst) hører ikke til noget
    expect(matchPorts(undefined, [[0, 0]])).toEqual([null]);
  });

  it('validates a definition like the backend', () => {
    expect(validateDef({ ports: [{ x: 0, y: 0, name: 'A', role: 'in' }, { x: 1, y: 1, name: 'B', role: 'out' }], ways: [['A', 'B']] })).toBeNull();
    expect(validateDef({ ports: [{ x: 0, y: 0, name: 'A', role: 'in' }, { x: 1, y: 1, name: 'A', role: 'out' }] })).toMatch(/to gange/);
    expect(validateDef({ ports: [{ x: 0, y: 0, name: 'A b', role: 'in' }] })).toMatch(/ugyldigt/);
    expect(validateDef({ ports: [{ x: 0, y: 0, name: 'A', role: 'in' }], ways: [['A', 'X']] })).toMatch(/ukendt/);
  });
});

group('orient — retning fra pumpen', () => {
  it('keeps a path that already runs with the pump', () => {
    const g = pumpLine();
    const [p] = findPaths(g, 'kedel', 'rad', 3, 8, { defs: DEFS });
    const o = orient(g, p, DEFS);
    expect(o.flipped).toBe(false);
    expect(o.steps.map((s) => s.id)).toEqual(['kedel', 'r1', 'p1', 'r2', 'rad']);
  });

  it('flips a path chosen the other way round, so the flow follows the pump', () => {
    const g = pumpLine();
    const [p] = findPaths(g, 'rad', 'kedel', 3, 8, { defs: DEFS });
    expect(p.map((s) => s.id)).toEqual(['rad', 'r2', 'p1', 'r1', 'kedel']);
    const o = orient(g, p, DEFS);
    expect(o.flipped).toBe(true);
    expect(o.steps.map((s) => s.id)).toEqual(['kedel', 'r1', 'p1', 'r2', 'rad']);
    const net = describeNet(g, [p], DEFS);
    // rørene er tegnet i vejens retning (a → b = mod radiatoren), så ingen er vendt
    expect(net.rows.find((r) => r.id === 'r1')!.flows).toEqual([{ part: 'all', reverse: false }]);
    expect(net.flipped).toEqual([true]);
  });

  it('does nothing without direction-giving symbols or without definitions', () => {
    const g = pumpLine();
    const [p] = findPaths(g, 'rad', 'kedel');
    expect(orient(g, p, undefined).flipped).toBe(false);
    expect(orient(g, p, DEFS).flipped).toBe(true);
    const plain: Graph = { nodes: g.nodes.map((n) => (n.id === 'p1' ? { ...n, fracs: null } : n)) };
    expect(orient(plain, p, DEFS)).toMatchObject({ flipped: false, warnings: [] });
  });

  it('names the symbols that disagree instead of guessing', () => {
    const g: Graph = { nodes: [
      sym('a', 'A', 'kedel', [[0, 0]]), pipe('r0', [0, 0], [10, 0]),
      sym('p1', 'P1', 'pumpe', [[10, 0], [20, 0]], [[0, 0.5], [1, 0.5]]),     // med vejen
      pipe('r1', [20, 0], [30, 0]),
      sym('p2', 'P2', 'pumpe', [[40, 0], [30, 0]], [[0, 0.5], [1, 0.5]]),     // mod vejen (ind ved 40, ud ved 30)
      pipe('r2', [40, 0], [50, 0]), sym('b', 'B', 'kedel', [[50, 0]]),
    ] };
    const [p] = findPaths(g, 'a', 'b', 1, 8, { defs: DEFS });
    const o = orient(g, p, DEFS);
    expect(o.flipped).toBe(false);
    expect(o.warnings[0]).toMatch(/uenig: P1 løber med vejen, P2 mod den/);
  });
});

group('flervejs-ventiler', () => {
  it('finds the path through the way that fits, and only that', () => {
    const g = threeWay();
    expect(findPaths(g, 'src', 'radA', 3, 8, { defs: DEFS })[0].map((s) => s.id)).toEqual(['src', 'rIn', 'v3', 'rA', 'radA']);
    expect(findPaths(g, 'src', 'radB', 3, 8, { defs: DEFS })[0].map((s) => s.id)).toEqual(['src', 'rIn', 'v3', 'rB', 'radB']);
    // A og B er ikke forbundet i ventilen: ingen vej fra radA til radB
    expect(findPaths(g, 'radA', 'radB', 3, 8, { defs: DEFS })).toEqual([]);
    expect(findPaths(g, 'radA', 'radB', 3, 8)).not.toEqual([]);                      // uden definitioner: som før
  });

  it('forces a way: no path when the way does not lead there', () => {
    const g = threeWay();
    expect(findPaths(g, 'src', 'radA', 3, 8, { defs: DEFS, forced: { v3: 'AB>B' } })).toEqual([]);
    expect(findPaths(g, 'src', 'radA', 3, 8, { defs: DEFS, forced: { v3: 'AB>A' } })).toHaveLength(1);
  });

  it('knows which way a path uses and the port at a point', () => {
    const g = threeWay();
    const v3 = g.nodes.find((n) => n.id === 'v3')!;
    const [p] = findPaths(g, 'src', 'radB', 3, 8, { defs: DEFS });
    const st = p.find((s) => s.id === 'v3')!;
    expect(wayUsed(v3, st, DEFS)).toBe('AB>B');
    expect(portAt(v3, [200, 100], DEFS)?.name).toBe('AB');
    expect(portAt(v3, [999, 999], DEFS)).toBeNull();
  });

  it('finds the port from the valve part when a pipe ends on the symbol line, not in a connection point', () => {
    const v3: GNode = { ...sym('v3', 'V3', 'trevejs_motorventil', [[100, 100], [150, 60], [200, 100]], [[0.07, 0.46], [0.46, 0.08], [0.84, 0.46]]),
      lines: [{ part: 'v3_port_ab', a: [200, 100], b: [260, 100] }, { part: 'v3_port_a', a: [100, 100], b: [40, 100] }] };
    expect(portAt(v3, [235, 100], DEFS)?.name).toBe('AB');                         // 35 fra punktet, men på AB-delens streg
    expect(portAt(v3, [70, 100], DEFS)?.name).toBe('A');
    expect(portAt(v3, [235, 160], DEFS)).toBeNull();                                // hverken nær punkt eller streg
  });

  it('builds a net with branches: the trunk is shared and the valve is asked once per way', () => {
    const g = threeWay();
    const paths = [findPaths(g, 'src', 'radA', 1, 8, { defs: DEFS })[0], findPaths(g, 'src', 'radB', 1, 8, { defs: DEFS })[0]];
    const net = describeNet(g, paths, DEFS);
    const row = (id: string) => net.rows.find((r) => r.id === id)!;
    expect(net.rows.map((r) => r.id)).toEqual(['src', 'rIn', 'v3', 'rA', 'radA', 'rB', 'radB']);
    expect(row('rIn').branches).toEqual([0, 1]);                                      // stammen
    expect(row('rA').branches).toEqual([0]);
    expect(row('rB').branches).toEqual([1]);
    expect(questionsOf(net.rows)).toEqual([
      { key: 'v3@AB>A', element: 'v3', role: 'threeway', way: 'AB>A', branches: [0] },
      { key: 'v3@AB>B', element: 'v3', role: 'threeway', way: 'AB>B', branches: [1] },
    ]);
    expect(net.warnings).toEqual([]);
  });

  it('asks a plain valve once, under its own name', () => {
    const g: Graph = { nodes: [sym('a', 'A', 'kedel', [[0, 0]]), pipe('r', [0, 0], [10, 0]), sym('v', 'V', 'kugleventil', [[10, 0], [20, 0]]),
      pipe('r2', [20, 0], [30, 0]), sym('b', 'B', 'kedel', [[30, 0]])] };
    const net = describeNet(g, [findPaths(g, 'a', 'b')[0]], DEFS);
    expect(questionsOf(net.rows)).toEqual([{ key: 'v', element: 'v', role: 'valve', way: null, branches: [0] }]);
  });
});

group('tynde og stiplede streger er ikke rør', () => {
  const stroke = (id: string, a: Pt, b: Pt, w?: number, dash?: boolean): GNode =>
    ({ id, name: '', type: '', pipe: false, terminals: [a, b], lines: [{ part: 'all', a, b, w, dash }], refs: [] });

  it('classifies drawn lines by thickness and dashes', () => {
    expect(roleOf(stroke('x', [0, 0], [10, 0], 10))).toBe('pipe');
    expect(roleOf(stroke('x', [0, 0], [10, 0], 5))).toBe('pipe');
    expect(roleOf(stroke('x', [0, 0], [10, 0], 3))).toBe('unit');                   // følerlinje
    expect(roleOf(stroke('x', [0, 0], [10, 0], 10, true))).toBe('unit');            // stiplet
    expect(roleOf(stroke('x', [0, 0], [10, 0]))).toBe('pipe');                      // ældre graf uden tykkelse
    expect(passable(stroke('x', [0, 0], [10, 0], 3))).toBe(false);
  });

  it('does not route through a thin sensor line, but does through a pipe', () => {
    const net = (w: number): Graph => ({ nodes: [sym('a', 'A', 'kedel', [[0, 0]]), stroke('l', [0, 0], [20, 0], w),
      sym('b', 'B', 'regventil', [[20, 0], [40, 0]]), stroke('m', [40, 0], [60, 0], 10), sym('c', 'C', 'radiator', [[60, 0]])] });
    expect(findPaths(net(3), 'a', 'c')).toEqual([]);
    expect(findPaths(net(10), 'a', 'c')[0].map((s) => s.id)).toEqual(['a', 'l', 'b', 'm', 'c']);
    expect(endpoints(net(3)).map((e) => e.id)).not.toContain('l');                  // den tynde streg kan heller ikke vælges
  });
});

group('graphKey', () => {
  it('changes when something moves, and not otherwise', () => {
    const a = pumpLine();
    const b = pumpLine();
    expect(graphKey(a)).toBe(graphKey(b));
    b.nodes[1] = pipe('r1', [40, 30], [100, 70]);                                    // røret er flyttet
    expect(graphKey(a)).not.toBe(graphKey(b));
    const c = pumpLine();
    c.nodes[0] = { ...c.nodes[0], terminals: [[40.04, 30.03]] };                      // under en tiendedel: samme tegning
    expect(graphKey(a)).toBe(graphKey(c));
  });
});
