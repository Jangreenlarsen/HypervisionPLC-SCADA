import { describe, expect, it } from 'vitest';
import { buildTree, countSymbols, filterTree, type GroupRow, type SymbolRow } from './symbolTree';

const SYMS: SymbolRow[] = [
  { element: 'kedel', name: 'Kedel', type: 'kedel', configured: true },
  { element: 'p1', name: 'P1', type: 'pumpe', configured: false },
  { element: 'rad', name: null, type: 'custom', configured: false },
];
const GROUPS: GroupRow[] = [{ id: 2, name: 'Pumper', kind: 'function', members: ['p1', 'findes_ikke'] }];

describe('buildTree', () => {
  const tree = buildTree(SYMS, GROUPS);
  it('has the two sections on level 1', () => {
    expect(tree.map((s) => s.label)).toEqual(['Grundsymboler', 'Grupper']);
    expect(tree[0].children.map((c) => c.label)).toEqual(['Kedel', 'P1', 'rad']);
  });
  it('splits a group into its members; a member may be in several places', () => {
    const g = tree[1].children[0];
    expect(g.ids).toEqual(['p1', 'findes_ikke']);
    expect(g.children.map((c) => c.key)).toEqual(['group:2:p1', 'group:2:findes_ikke']);
    expect(g.children[0].guide).toEqual({ id: 'p1', name: 'P1' });      // et grundsymbol i gruppen kan opsættes herfra
    expect(g.children[1].guide).toBeNull();                              // et element, der ikke er et symbol, har ingen guide
  });
  it('leaves out empty sections', () => {
    expect(buildTree([], []).length).toBe(0);
    expect(buildTree(SYMS, []).map((s) => s.label)).toEqual(['Grundsymboler']);
  });
});

describe('filterTree', () => {
  const tree = buildTree(SYMS, GROUPS);
  it('keeps everything without a filter', () => expect(filterTree(tree, '', false)).toBe(tree));
  it('search keeps the parents of a hit', () => {
    const r = filterTree(tree, 'pumpe', false);
    expect(r.map((s) => s.label)).toEqual(['Grundsymboler', 'Grupper']);   // P1 (type pumpe) begge steder
    expect(r[0].children.map((c) => c.label)).toEqual(['P1']);
  });
  it('only not-set-up shows what still lacks a setup', () => {
    const r = filterTree(tree, '', true);
    expect(r[0].children.map((c) => c.label)).toEqual(['P1', 'rad']);
  });
  it('no hit gives an empty tree', () => expect(filterTree(tree, 'zzz', false)).toEqual([]));
});

describe('countSymbols', () => {
  it('counts each symbol once', () => expect(countSymbols(SYMS)).toEqual({ total: 3, configured: 1 }));
});
