import { describe as group, expect, it } from 'vitest';
import { answerFrom, conditionsFrom, contacts, describe, endpoints, findPaths, flowsFor, pickNext, roleOf, suggestAnswer, summary, type GNode, type Graph, type Pt, type TagInfo } from './signalPath';

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

group('findPaths', () => {
  it('finds the route through the T-piece in the right direction', () => {
    const g = plant();
    const [p] = findPaths(g, 'kedel', 'rad');
    expect(p.map((s) => s.id)).toEqual(['kedel', 'r1', 'p1', 'r2', 't1', 'r3', 'v2', 'r4', 'rad']);
    const rows = describe(g, p);
    expect(rows.find((r) => r.id === 't1')!.flows).toEqual([{ part: 't1_a', reverse: false }, { part: 't1_b', reverse: false }]);
    expect(rows.find((r) => r.id === 'r3')!.flows).toEqual([{ part: 'all', reverse: true }]);   // tegnet baglæns
    expect(rows.find((r) => r.id === 'p1')!.flows).toEqual([]);                                 // pumpen: spørgsmål, intet løbelys
    expect(summary(rows)).toBe('Kedel → P1 → V2 → Radiator (9 dele)');
  });
  it('takes the branch and runs the light out of it', () => {
    const g = plant();
    const [p] = findPaths(g, 'kedel', 'rad2');
    expect(p.map((s) => s.id)).toEqual(['kedel', 'r1', 'p1', 'r2', 't1', 'r5', 'rad2']);
    expect(describe(g, p).find((r) => r.id === 't1')!.flows).toEqual([{ part: 't1_a', reverse: false }, { part: 't1_c', reverse: false }]);
    // og den modsatte vej: lyset løber ind fra afgreningen
    const [back] = findPaths(g, 'rad2', 'kedel');
    expect(describe(g, back).find((r) => r.id === 't1')!.flows).toEqual([{ part: 't1_a', reverse: true }, { part: 't1_c', reverse: true }]);
  });
  it('never passes through an element it only touches', () => {
    const g = plant();
    expect(findPaths(g, 'kedel', 'foeler')[0].map((s) => s.id)).toEqual(['kedel', 'r1', 'p1', 'r2', 'foeler']);
    // følerens eneste punkt kan ikke være både ind og ud: ingen vej gennem den
    expect(findPaths(g, 'kedel', 'rad', 3).every((p) => !p.some((s) => s.id === 'foeler'))).toBe(true);
  });
  it('offers alternatives, shortest first, and nothing when not connected', () => {
    const g = plant();
    g.nodes.push(pipe('omloeb1', [100, 30], [100, 80]), pipe('omloeb2', [100, 80], [200, 80]), pipe('omloeb3', [200, 80], [200, 30]));
    const paths = findPaths(g, 'kedel', 'rad', 3);
    expect(paths.length).toBe(2);
    expect(paths[0].map((s) => s.id)).toContain('p1');
    expect(paths[1].map((s) => s.id)).toContain('omloeb2');
    g.nodes.push(sym('ensom', 'Ensom', 'tank', [[900, 900]]));
    expect(findPaths(g, 'kedel', 'ensom')).toEqual([]);
  });
});

group('flowsFor', () => {
  it('uses the nearest end for a single scaled pipe that misses the contact points', () => {
    const n = sym('roer', '', 'roer_l', [], [{ part: 'all', a: [0, 0], b: [0, 90] }]);
    expect(flowsFor(n, [0, 95], [0, -40])).toEqual([{ part: 'all', reverse: true }]);
    expect(flowsFor(sym('v', '', 'kugleventil', [], []), [0, 0], [1, 0])).toEqual([]);
  });
});

group('endpoints', () => {
  it('lists symbols (not pipes) by name', () => {
    expect(endpoints(plant()).map((e) => e.label)).toEqual(['Kedel', 'P1', 'Radiator', 'Radiator 2', 'TT1', 'V2']);
  });
});


group('answers → conditions', () => {
  const tags: TagInfo[] = [{ name: 'P1_drift', is_bool: true, unit: '', description: '' },
    { name: 'V2_pct', is_bool: false, unit: '%', description: '' }];
  it('suggests the symbol\'s own on/off tag first', () => {
    expect(suggestAnswer('p1', tags.slice().reverse())).toEqual({ element: 'p1', src: 'P1_drift', on: true, cmp: '', value: null });
    expect(suggestAnswer('v2', [tags[1]])).toMatchObject({ src: 'V2_pct', cmp: 'ge', value: 1 });
    expect(suggestAnswer('x', []).src).toBe('');
  });
  it('builds conditions and reports what is missing', () => {
    const r = conditionsFrom([
      { element: 'p1', src: 'P1_drift', on: false, cmp: '', value: null },
      { element: 'v2', src: 'V2_pct', on: true, cmp: 'ge', value: 50 },
      { element: 'v3', src: '', on: true, cmp: '', value: null },
      { element: 'v4', src: 'V2_pct', on: true, cmp: '', value: null },
      { element: 'v5', src: 'Ukendt', on: true, cmp: '', value: null },
    ], tags);
    expect(r.conditions).toEqual([{ element: 'p1', src: 'P1_drift', neg: true, cmp: '', value: null },
      { element: 'v2', src: 'V2_pct', neg: false, cmp: 'ge', value: 50 }]);
    expect(r.errors).toEqual(['V2_pct: vælg ≥, ≤ eller = og en grænseværdi', "Tagget 'Ukendt' findes ikke"]);
    expect(answerFrom(r.conditions[0])).toEqual({ element: 'p1', src: 'P1_drift', on: false, cmp: '', value: null });
  });
});

group('branches without a T-piece', () => {
  it('finds a pipe that ends in the middle of another and runs the light the right way', () => {
    const g: Graph = { nodes: [
      sym('a', 'A', 'kedel', [[0, 0]]),
      { ...pipe('hoved', [0, 0], [200, 0]), lines: [{ part: 'all', a: [0, 0], b: [200, 0], pts: [[0, 0], [100, 0], [200, 0]] }] },
      pipe('gren', [100, 4], [100, 80]),                         // ender (næsten) midt på hovedrøret
      sym('b', 'B', 'radiator', [[100, 80]]),
      sym('c', 'C', 'radiator', [[200, 0]]),
    ] };
    const [p] = findPaths(g, 'a', 'b');
    expect(p.map((s) => s.id)).toEqual(['a', 'hoved', 'gren', 'b']);
    expect(describe(g, p).map((r) => r.flows)).toEqual([[], [{ part: 'all', reverse: false }], [{ part: 'all', reverse: false }], []]);
    const [back] = findPaths(g, 'c', 'b');                     // fra den anden ende: hovedrøret løber baglæns
    expect(describe(g, back)[1].flows).toEqual([{ part: 'all', reverse: true }]);
  });
});

group('passable', () => {
  it('never routes through display symbols or loose shapes', () => {
    const g: Graph = { nodes: [
      sym('a', 'A', 'kedel', [[0, 0]]), sym('felt', 'Status', 'statusfelt', [[0, 0], [50, 0]]),
      sym('cirkel', '', '', [[50, 0], [60, 0]]), sym('b', 'B', 'tank', [[50, 0]]),
    ] };
    expect(findPaths(g, 'a', 'b')).toEqual([]);
    expect(endpoints(g).map((e) => e.label)).toEqual(['A', 'B']);
  });
});

group('pickNext', () => {
  const allowed = new Set(['kedel', 'rad']);
  it('takes the first allowed symbol in the selection and explains the rest', () => {
    expect(pickNext('start', ['r1', 'kedel'], allowed, '')).toEqual({ id: 'kedel' });
    expect(pickNext('start', ['r1'], allowed, '').error).toMatch(/rør/);
    expect(pickNext('end', ['kedel'], allowed, 'kedel').error).toMatch(/startsymbolet/);
    expect(pickNext('end', ['rad'], allowed, 'kedel')).toEqual({ id: 'rad' });
  });
});
