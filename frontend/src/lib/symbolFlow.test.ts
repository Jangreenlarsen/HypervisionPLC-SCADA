import { describe as group, expect, it } from 'vitest';
import { FLOW_DEFAULTS, matchPorts, mergeDefs, parseWay, sameWay, validateDef, waysOf, wayKey, wayLabel } from './symbolFlow';

const DEFS = mergeDefs(null);

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
