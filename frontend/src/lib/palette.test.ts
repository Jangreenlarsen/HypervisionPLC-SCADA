import { describe, expect, it } from 'vitest';
import { knownFavorites, moveFavorite, toggleFavorite } from './palette';

describe('Mine symboler (v0.78.0)', () => {
  it('læg ind bagerst / tag ud', () => {
    expect(toggleFavorite([], 'pumpe')).toEqual(['pumpe']);
    expect(toggleFavorite(['pumpe', 'kedel'], 'roer_v')).toEqual(['pumpe', 'kedel', 'roer_v']);
    expect(toggleFavorite(['pumpe', 'kedel'], 'pumpe')).toEqual(['kedel']);
  });
  it('flyt frem og tilbage; ved kanten sker intet', () => {
    expect(moveFavorite(['a', 'b', 'c'], 'b', -1)).toEqual(['b', 'a', 'c']);
    expect(moveFavorite(['a', 'b', 'c'], 'b', 1)).toEqual(['a', 'c', 'b']);
    expect(moveFavorite(['a', 'b', 'c'], 'a', -1)).toEqual(['a', 'b', 'c']);
    expect(moveFavorite(['a', 'b', 'c'], 'c', 1)).toEqual(['a', 'b', 'c']);
    expect(moveFavorite(['a'], 'x', 1)).toEqual(['a']);
  });
  it('ukendte og dubletter fjernes', () => {
    expect(knownFavorites(['pumpe', 'væk', 'kedel', 'pumpe'], new Set(['pumpe', 'kedel']))).toEqual(['pumpe', 'kedel']);
  });
});
