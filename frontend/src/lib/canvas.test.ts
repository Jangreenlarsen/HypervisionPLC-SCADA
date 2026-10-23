import { describe, expect, it } from 'vitest';
import { addTooltips, bindingTags, byTag, fitSize, groupWinner, priorityGroups, renderAll, renderBinding } from './canvas';
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

describe('aktiv/passiv og prioritering (v0.72.0)', () => {
  const lv = (value: unknown) => ({ value, quality: 'good' as const, ts: 0, error: null });
  const flowB = (tag: string, light: string, position: number, when = true): Binding =>
    ({ element: 'r', tag, anim: 'flow', params: { light, base: '#555555', ...(when ? { when: true } : {}) }, position, source: 'symbol' });
  const mount = () => {
    const box = document.createElement('div');
    box.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg"><path id="r" d="M0 0 H100" stroke="#555" stroke-width="10" fill="none"/></svg>';
    document.body.appendChild(box);
    return box;
  };
  const light = (box: HTMLElement) => box.querySelector('.hv-flow > *')?.getAttribute('stroke') ?? null;

  it('den øverste aktive vinder; ingen aktive → standarden; uden standard → som tegnet', () => {
    const A = flowB('A', '#ff0000', 1000), B = flowB('B', '#00ff00', 1001), D = flowB('@on', '#8fc8ea', 1002, false);
    const box = mount();
    const values: Record<string, ReturnType<typeof lv>> = { A: lv(true), B: lv(true) };
    renderAll(box, [A, B, D], values, {});
    expect(light(box)).toBe('#ff0000');                 // A og B er aktive: A står øverst
    values.A = lv(false);
    renderBinding(box, A, values, {});
    expect(light(box)).toBe('#00ff00');                 // kun B
    values.B = lv(false);
    renderBinding(box, B, values, {});
    expect(light(box)).toBe('#8fc8ea');                 // ingen: standarden (altid til)
    renderAll(box, [A, B], values, {});
    expect(light(box)).toBeNull();                      // uden standard: røret som tegnet
    values.B = lv(true);
    renderBinding(box, B, values, {});
    expect(light(box)).toBe('#00ff00');
    box.remove();
  });

  it('grupper med en aktiv/passiv eller flere tags bliver prioriteret; Farve og Blafrer er samme slags', () => {
    const plain = [flowB('A', '#f00', 1, false), flowB('B', '#0f0', 2, false)];
    const pg = priorityGroups(plain);                   // flere tags på samme del og slags: den sidste i rækkefølgen vinder, uanset hvilket tag der ændrede sig sidst
    expect(pg.size).toBe(1);
    expect(groupWinner([...pg.values()][0], {})).toBe(plain[1]);
    expect(priorityGroups([flowB('A', '#f00', 1, false), flowB('A', '#0f0', 2, false)]).size).toBe(0);   // samme tag: som før
    const fillW: Binding = { element: 'r', tag: 'A', anim: 'fill', params: { when: true, on: '#f00' }, position: 1 };
    const flick: Binding = { element: 'r', tag: '@on', anim: 'flicker', params: {}, position: 2 };
    const g = priorityGroups([fillW, flick]);
    expect([...g.values()].map((l) => l.map((b) => b.anim))).toEqual([['fill', 'flicker']]);
    expect(groupWinner([fillW, flick], { A: lv(false) })).toBe(flick);
    expect(groupWinner([fillW, flick], { A: lv(true) })).toBe(fillW);
    expect(groupWinner([fillW], { A: lv(null) })).toBeNull();   // ukendt værdi er ikke aktiv
  });
});

describe('flere ejere på samme del (symbol + grupper)', () => {
  const live = (value: unknown) => ({ value, quality: 'good', ts: 0, error: null }) as never;

  it('uden passiv vinder den sidste AKTIVE (eller mellem kilderne): første aktiv, sidste inaktiv → første', () => {
    const p1: Binding = { element: 'r', tag: 'P1', anim: 'visible', params: {}, position: 1 };
    const p2: Binding = { element: 'r', tag: 'P2', anim: 'visible', params: {}, position: 2 };
    expect(groupWinner([p1, p2], { P1: live(true), P2: live(false) })).toBe(p1);
    expect(groupWinner([p1, p2], { P1: live(true), P2: live(true) })).toBe(p2);
    expect(groupWinner([p1, p2], { P1: live(false), P2: live(false) })).toBe(p2);   // ingen aktive: den sidstes fra-tilstand
  });

  it('delvis gentegning giver samme vinder som en samlet: aktive vinder, den sidste af dem', () => {
    const box = document.createElement('div');
    box.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="r"/></svg>';
    const own: Binding = { element: 'r', tag: 'A', anim: 'fill', params: { on: '#ff0000', off: '#aaaaaa' }, position: 1000 };
    const grp: Binding = { element: 'r', tag: 'B', anim: 'fill', params: { on: '#00ff00', off: '#0000ff' }, position: 2000 };
    const values = { A: live(true), B: live(false) };
    const fill = () => (box.querySelector('#r') as SVGElement).style.fill;
    renderAll(box, [own, grp], values, {});
    const ownOn = fill();                               // kun symbolets egen er aktiv → den vinder
    values.A = live(false);
    renderBinding(box, own, values, {});                // ingen aktive → den sidstes (gruppens) fra-tilstand
    const grpOff = fill();
    values.B = live(true);
    renderBinding(box, grp, values, {});                // kun gruppens er aktiv
    const grpOn = fill();
    values.A = live(true);
    renderBinding(box, own, values, {});                // begge aktive → den sidste (gruppens)
    expect(new Set([ownOn, grpOff, grpOn]).size).toBe(3);
    expect(fill()).toBe(grpOn);
  });
});
