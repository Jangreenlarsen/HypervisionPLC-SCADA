import { describe, expect, it } from 'vitest';
import { buildTree, countSymbols, filterTree, type GroupRow, type PathRow, type SymbolRow } from './symbolTree';

const SYMS: SymbolRow[] = [
  { element: 'kedel', name: 'Kedel', type: 'kedel', configured: true },
  { element: 'p1', name: 'P1', type: 'pumpe', configured: false },
  { element: 'rad', name: null, type: 'custom', configured: false },
];
const PATHS: PathRow[] = [{ id: 7, name: 'Kedel til radiator', symbol: 'sv~7', configured: false,
  elements: [{ element: 'r1' }, { element: 'p1' }, { element: 'r1' }] }];
const GROUPS: GroupRow[] = [{ id: 2, name: 'Pumper', kind: 'function', members: ['p1', 'findes_ikke'] }];

describe('buildTree', () => {
  const tree = buildTree(SYMS, PATHS, GROUPS);
  it('has the three sections on level 1', () => {
    expect(tree.map((s) => s.label)).toEqual(['Grundsymboler', 'Signalveje', 'Grupper']);
    expect(tree[0].children.map((c) => c.label)).toEqual(['Kedel', 'P1', 'rad']);
  });
  it('splits a path into its elements (each once) and opens the path as symbol sv~id', () => {
    const p = tree[1].children[0];
    expect(p.guide).toEqual({ id: 'sv~7', name: 'Kedel til radiator' });
    expect(p.ids).toEqual(['r1', 'p1']);
    expect(p.children.map((c) => c.label)).toEqual(['r1', 'P1']);
    expect(p.children[1].guide).toEqual({ id: 'p1', name: 'P1' });      // et grundsymbol på vejen kan opsættes herfra
    expect(p.children[0].guide).toBeNull();                              // et rør uden navn har ingen guide
  });
  it('splits a group into its members; a member may be in several places', () => {
    const g = tree[2].children[0];
    expect(g.ids).toEqual(['p1', 'findes_ikke']);
    expect(g.children.map((c) => c.key)).toEqual(['group:2:p1', 'group:2:findes_ikke']);
    expect(new Set(tree.flatMap((s) => s.children.flatMap((c) => c.children.map((x) => x.key)))).size).toBe(4);
  });
  it('leaves out empty sections', () => {
    expect(buildTree([], [], []).length).toBe(0);
    expect(buildTree(SYMS, [], []).map((s) => s.label)).toEqual(['Grundsymboler']);
  });
});

describe('filterTree', () => {
  const tree = buildTree(SYMS, PATHS, GROUPS);
  it('keeps everything without a filter', () => expect(filterTree(tree, '', false)).toBe(tree));
  it('search keeps the parents of a hit', () => {
    const r = filterTree(tree, 'pumpe', false);
    expect(r.map((s) => s.label)).toEqual(['Grundsymboler', 'Signalveje', 'Grupper']);   // P1 (type pumpe) i alle tre
    expect(r[0].children.map((c) => c.label)).toEqual(['P1']);
    expect(filterTree(tree, 'radiator', false).map((s) => s.label)).toEqual(['Signalveje']);
  });
  it('only not-set-up shows what still lacks a setup', () => {
    const r = filterTree(tree, '', true);
    expect(r[0].children.map((c) => c.label)).toEqual(['P1', 'rad']);
    expect(r[1].children[0].label).toBe('Kedel til radiator');
  });
  it('no hit gives an empty tree', () => expect(filterTree(tree, 'zzz', false)).toEqual([]));
});

describe('countSymbols', () => {
  it('counts each symbol once', () => expect(countSymbols(SYMS)).toEqual({ total: 3, configured: 1 }));
});
