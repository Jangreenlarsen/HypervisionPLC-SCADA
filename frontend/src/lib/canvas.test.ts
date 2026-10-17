import { describe, expect, it } from 'vitest';
import { addTooltips, bindingTags, byTag, fitSize, renderBinding } from './canvas';
import type { Binding } from './api';

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

describe('bindingTags / byTag (løbelys med retnings-tag)', () => {
  const flow: Binding = { element: 'R1', tag: 'Pumpe', anim: 'flow', params: { dir_tag: 'Retning' } };
  const text: Binding = { element: 'T', tag: 'Pumpe', anim: 'text', params: { dir_tag: 'Ignoreres' } };
  it('løbelys læser to tags; andre animationer kun deres eget', () => {
    expect(bindingTags(flow)).toEqual(['Pumpe', 'Retning']);
    expect(bindingTags(text)).toEqual(['Pumpe']);
    expect(bindingTags({ ...flow, params: { dir_tag: '' } })).toEqual(['Pumpe']);
    expect(bindingTags({ tag: '', anim: 'click:goto', params: {} })).toEqual([]);
    expect(bindingTags({ tag: 'Lys', anim: 'fill', params: { pos_tag: 'sym:d:V1:pos' } })).toEqual(['Lys', 'sym:d:V1:pos']);
  });
  it('en ændring på retnings-tagget gentegner løbelyset', () => {
    const map = byTag([flow, text]);
    expect(map.get('Retning')).toEqual([flow]);
    expect(map.get('Pumpe')).toEqual([flow, text]);
  });
});

describe('kilden "Altid til" (@on, v0.71.0)', () => {
  it('er ikke et tag (hentes aldrig live) og er altid aktiv', () => {
    const b: Binding = { element: 'f', tag: '@on', anim: 'flicker', params: { palette: ['#ff0000', '#00ff00', '#0000ff'] } };
    expect(bindingTags(b)).toEqual([]);
    expect(bindingTags({ ...b, anim: 'flow', params: { dir_tag: 'Retning' } })).toEqual(['Retning']);
    const box = document.createElement('div');
    box.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg"><path id="f" d="M0 0 H10"/></svg>';
    document.body.appendChild(box);
    renderBinding(box, b, {}, {});
    const f = box.querySelector('#f') as SVGElement;
    expect(f.classList.contains('hv-flicker')).toBe(true);
    expect(f.getAttribute('data-hv-quality')).toBe('good');
    renderBinding(box, { ...b, anim: 'flicker', params: {} }, {}, {});
    box.remove();
  });
});
