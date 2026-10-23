import { describe, expect, it } from 'vitest';
import { groupsOf, ofKind, withMembers, withoutMembers, type SymbolGroup } from './symbolGroups';

const g = (id: number, kind: SymbolGroup['kind'], members: string[]): SymbolGroup => ({ id, name: 'G' + id, kind, members });

describe('symbolgrupper', () => {
  it('tilføjer uden dubletter og bevarer rækkefølgen', () => {
    expect(withMembers(['A', 'B'], ['B', 'C', 'C'])).toEqual(['A', 'B', 'C']);
  });
  it('fjerner medlemmer', () => {
    expect(withoutMembers(['A', 'B', 'C'], ['B', 'X'])).toEqual(['A', 'C']);
  });
  it('samme element i flere grupper (overlap)', () => {
    const groups = [g(1, 'function', ['A', 'B']), g(2, 'selection', ['B']), g(3, 'selection', ['C'])];
    expect(groupsOf(groups, 'B').map((x) => x.id)).toEqual([1, 2]);
    expect(groupsOf(groups, 'Z')).toEqual([]);
  });
  it('sorterer efter art', () => {
    const groups = [g(1, 'function', []), g(2, 'selection', []), g(3, 'function', [])];
    expect(ofKind(groups, 'function').map((x) => x.id)).toEqual([1, 3]);
    expect(ofKind(groups, 'selection').map((x) => x.id)).toEqual([2]);
  });
});
