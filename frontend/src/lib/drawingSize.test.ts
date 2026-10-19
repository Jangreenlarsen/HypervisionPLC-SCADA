import { describe, expect, it } from 'vitest';
import { parseSize, presetFor, sizeText } from './drawingSize';

describe('tegningens størrelse (v0.92.0)', () => {
  it('hele tal inden for grænserne; komma og mellemrum', () => {
    expect(parseSize('1920', ' 1080 ')).toEqual({ w: 1920, h: 1080 });
    expect(parseSize('1280,4', '800')).toEqual({ w: 1280, h: 800 });
  });
  it('fejl med feltets navn — også tomt og kun mellemrum', () => {
    expect(parseSize('', '800')).toEqual({ error: 'Skriv en bredde' });
    expect(parseSize('1200', '   ')).toEqual({ error: 'Skriv en højde' });
    expect(parseSize('stor', '800')).toEqual({ error: 'Bredde skal være et tal' });
    expect(parseSize('1200', '50')).toEqual({ error: 'Højde skal være mellem 100 og 10000' });
    expect(parseSize('20000', '800')).toEqual({ error: 'Bredde skal være mellem 100 og 10000' });
  });
  it('tekst og fast valg', () => {
    expect(sizeText(1919.6, 1080)).toBe('1920 × 1080');
    expect(presetFor(1920, 1080)?.label).toBe('Full HD-skærm (1920 × 1080)');
    expect(presetFor(1000, 1000)).toBeNull();
  });
});
