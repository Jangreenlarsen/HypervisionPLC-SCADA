import { describe, expect, it } from 'vitest';
import { GROUP_COLORS, groupColor, groupsOf, movedOrder, ofKind, withMembers, withoutMembers, type SymbolGroup } from './symbolGroups';

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

describe('gruppefarver', () => {
  it('samme gruppe får altid samme farve, og farverne går rundt', () => {
    expect(groupColor(3)).toBe(groupColor(3));
    expect(groupColor(1)).not.toBe(groupColor(2));
    expect(groupColor(GROUP_COLORS.length + 2)).toBe(groupColor(2));
  });
});

describe('rækkefølge', () => {
  const groups = [g(1, 'function', []), g(2, 'selection', []), g(3, 'function', []), g(4, 'selection', [])];
  it('bytter med nærmeste nabo af samme art', () => {
    expect(movedOrder(groups, 3, -1)).toEqual([3, 2, 1, 4]);
    expect(movedOrder(groups, 2, 1)).toEqual([1, 4, 3, 2]);
  });
  it('kan ikke flyttes ud over enderne', () => {
    expect(movedOrder(groups, 1, -1)).toBeNull();
    expect(movedOrder(groups, 4, 1)).toBeNull();
    expect(movedOrder(groups, 99, 1)).toBeNull();
  });
});
