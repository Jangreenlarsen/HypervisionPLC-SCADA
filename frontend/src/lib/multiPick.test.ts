import { describe, expect, it } from 'vitest';
import { pickInList } from './multiPick';

const ids = ['a', 'b', 'c', 'd', 'e'];

describe('pickInList', () => {
  it('toggles one item', () => {
    expect(pickInList(ids, [], 'b', 1, -1, false)).toEqual(['b']);
    expect(pickInList(ids, ['b', 'c'], 'b', 1, 2, false)).toEqual(['c']);
  });
  it('shift selects or clears the whole range from the last click', () => {
    expect(pickInList(ids, ['b'], 'd', 3, 1, true)).toEqual(['b', 'c', 'd']);
    expect(pickInList(ids, ['a', 'b', 'c', 'd'], 'd', 3, 1, true)).toEqual(['a']);      // d var valgt: intervallet fravælges
    expect(pickInList(ids, [], 'a', 0, 4, true)).toEqual(['a', 'b', 'c', 'd', 'e']);     // også baglæns
  });
  it('ignores a stale last index', () => {
    expect(pickInList(ids, [], 'c', 2, 9, true)).toEqual(['c']);
  });
});
