import { describe as group, expect, it } from 'vitest';
import { contacts, graphKey, passable, roleOf, type GNode, type Graph, type Pt } from './signalPath';

const pipe = (id: string, a: Pt, b: Pt, refs: (string | null)[] = [null, null]): GNode =>
  ({ id, name: '', type: '', pipe: true, terminals: [a, b], lines: [{ part: 'all', a, b }], refs });
const sym = (id: string, name: string, type: string, terminals: Pt[], lines: GNode['lines'] = []): GNode =>
  ({ id, name, type, pipe: false, terminals, lines, refs: [] });

// Kedel → r1 → P1 → r2 → T1 → r3 (tegnet baglæns) → V2 → r4 → Radiator, og fra T1's afgrening r5 → Radiator 2
function plant(): Graph {
  return {
    nodes: [
      sym('kedel', 'Kedel', 'kedel', [[40, 30]]),
      pipe('r1', [40, 30], [100, 30], ['kedel', 'p1']),
      sym('p1', 'P1', 'pumpe', [[100, 30], [140, 30]], [{ part: 'pil', a: [110, 20], b: [130, 20] }]),
      pipe('r2', [140, 30], [200, 30]),
      sym('t1', 'T1', 't_stykke', [[200, 30], [290, 30], [245, 0]], [
        { part: 't1_a', a: [200, 30], b: [245, 30] }, { part: 't1_b', a: [245, 30], b: [290, 30] },
        { part: 't1_c', a: [245, 25], b: [245, 0] }]),
      pipe('r3', [350, 30], [290, 30]),
      sym('v2', 'V2', 'kugleventil', [[350, 30], [380, 30]]),
      pipe('r4', [380, 30], [440, 30]),
      sym('rad', 'Radiator', 'radiator', [[440, 30]]),
      pipe('r5', [245, 0], [245, -60]),
      sym('rad2', 'Radiator 2', 'radiator', [[245, -60]]),
      sym('foeler', 'TT1', 'foeler', [[200, 30]]),            // følger i samme punkt som r2/T1: kun berøring
    ],
  };
}

/** Kedel → r1 → pumpe (ind til venstre, ud til højre) → r2 → radiator. */
function pumpLine(): Graph {
  return { nodes: [
    sym('kedel', 'Kedel', 'kedel', [[40, 30]]),
    pipe('r1', [40, 30], [100, 30]),
    sym('p1', 'P1', 'pumpe', [[100, 30], [140, 30]]),
    pipe('r2', [140, 30], [200, 30]),
    sym('rad', 'Radiator', 'radiator', [[200, 30]]),
  ] };
}

group('roleOf', () => {
  it('classifies pipes, valves, pumps and passive parts', () => {
    const g = plant();
    const role = (id: string) => roleOf(g.nodes.find((n) => n.id === id)!);
    expect(['r1', 't1', 'p1', 'v2', 'kedel'].map(role)).toEqual(['pipe', 'pipe', 'pump', 'valve', 'unit']);
    expect(roleOf({ type: 'trevejs_motorventil', pipe: false, lines: [] })).toBe('threeway');
    expect(roleOf({ type: 'kontraventil', pipe: false, lines: [] })).toBe('check');
    expect(roleOf({ type: '', pipe: false, lines: [{ part: 'all', a: [0, 0], b: [1, 0] }] })).toBe('pipe');
  });
});

group('contacts', () => {
  it('connects touching terminals and pipe refs', () => {
    const adj = contacts(plant());
    expect(adj.get('t1')!.map((c) => c.to).sort()).toEqual(['foeler', 'r2', 'r3', 'r5']);
    const g: Graph = { nodes: [pipe('x', [0, 0], [10, 0], ['s', null]), sym('s', 'S', 'tank', [[500, 500]])] };
    expect(contacts(g).get('s')!.map((c) => c.to)).toEqual(['x']);   // fast i symbolet, selv om punktet er flyttet
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
