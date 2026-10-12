import { describe, expect, it } from 'vitest';
import { addTooltips, fitSize } from './canvas';

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

describe('addTooltips', () => {
  const doc = () => new DOMParser().parseFromString(
    '<svg xmlns="http://www.w3.org/2000/svg">' +
    '<g id="a" data-hv-name="Ventilator" data-hv-desc="Starter ventilatoren"><rect id="r"/></g>' +
    '<g id="b" data-hv-desc="Kun forklaring"/><g id="c"/><text id="t" data-hv-name="Tekst">1</text></svg>', 'image/svg+xml');

  it('navn og forklaring bliver til <title> — ikke på tekst-elementer og ikke uden tekst', () => {
    const d = doc();
    addTooltips(d.documentElement);
    const title = (id: string) => d.getElementById(id)!.querySelector(':scope > title')?.textContent ?? null;
    expect(title('a')).toBe('Ventilator\nStarter ventilatoren');
    expect(title('b')).toBe('Kun forklaring');
    expect(title('c')).toBeNull();
    expect(title('t')).toBeNull();
    expect(d.getElementById('t')!.textContent).toBe('1');
  });
  it('null er ok', () => expect(() => addTooltips(null)).not.toThrow());
});
