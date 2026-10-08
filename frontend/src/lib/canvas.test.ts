import { describe, expect, it } from 'vitest';
import { fitSize } from './canvas';

describe('fitSize', () => {
  it('bred tegning begrænses af bredden', () => expect(fitSize(2000, 1000, 1000, 900)).toEqual({ width: 1000, height: 500 }));
  it('høj tegning / lavt vindue begrænses af højden', () => expect(fitSize(1840, 850, 1880, 600)).toEqual({ width: 1298, height: 600 }));
  it('vokser på store skærme (ingen loft)', () => expect(fitSize(820, 400, 1880, 980)).toEqual({ width: 1880, height: 917 }));
  it('minimumshøjde ved meget lavt vindue', () => expect(fitSize(1000, 1000, 800, 50).height).toBe(200));
  it('ugyldig viewBox eller ingen bredde', () => {
    expect(fitSize(0, 100, 500, 500)).toEqual({ width: 500, height: 0 });
    expect(fitSize(100, 100, 0, 500)).toEqual({ width: 0, height: 0 });
  });
});
