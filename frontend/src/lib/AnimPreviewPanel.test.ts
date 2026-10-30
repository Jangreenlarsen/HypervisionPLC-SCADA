import { flushSync, mount, tick, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import AnimPreview from './AnimPreview.svelte';
import Harness from './AnimPreviewHarness.svelte';
import { emptyConfig, setOp, type SymbolConfig } from './symbolConfig';

const SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><g id="pumpe"><circle id="hjul" cx="20" cy="20" r="10"/></g><g id="andet"/></svg>';
const settle = async () => { flushSync(); await tick(); flushSync(); };
let target: HTMLElement;
let app: Record<string, any>;

const cfg = (): SymbolConfig => {
  const c = emptyConfig('pumpe');
  c.anims = [{ part: 'hjul', type: 'fill', src: 'DO1', params: { on: '#00ff00', off: '#333333' }, only: null }];
  return c;
};
const mountIt = (c: SymbolConfig, svg = SVG, element = 'pumpe') => {
  app = mount(AnimPreview, { target, props: { cfg: c, element, svg, kindOf: () => 'bool' as const, metaOf: () => undefined } });
  flushSync();
};
const button = (text: string) => [...target.querySelectorAll<HTMLButtonElement>('button')].find((b) => (b.textContent ?? '').trim() === text)!;
const fill = () => { const e = target.querySelector<SVGElement>('#hjul')!; return e.style.fill || e.getAttribute('fill'); };

beforeEach(() => { target = document.createElement('div'); document.body.appendChild(target); });
afterEach(() => { unmount(app); target.remove(); });

describe('preview ved animationerne', () => {
  it('tegner symbolet og skifter farve, når Til trykkes', async () => {
    mountIt(cfg());
    await settle();
    expect(target.querySelector('svg #hjul')).toBeTruthy();
    // symbolet står i en indpakning uden transform, så viewBox kan måles ud fra symbolets placering i tegningen
    expect(target.querySelector('svg > g > g#pumpe')).toBeTruthy();
    expect(fill()).toBe('rgb(51, 51, 51)');
    button('Til').click();
    await settle();
    expect(fill()).toBe('rgb(0, 255, 0)');
    button('Fra').click();
    await settle();
    expect(fill()).toBe('rgb(51, 51, 51)');
  });
  it('ændres en indstilling i opsætningen, følger preview-et med', async () => {
    app = mount(Harness, { target, props: { anims: cfg().anims, svg: SVG, element: 'pumpe' } });
    await settle();
    button('Til').click();
    await settle();
    expect(fill()).toBe('rgb(0, 255, 0)');
    app.setOn('#ff0000');
    await settle();
    expect(fill()).toBe('rgb(255, 0, 0)');
  });
  it('en fjernet animation sætter ikke spor: delen står som tegnet', async () => {
    app = mount(Harness, { target, props: { anims: cfg().anims, svg: SVG, element: 'pumpe' } });
    await settle();
    button('Til').click();
    await settle();
    app.clear();
    await settle();
    expect(fill()).toBeNull();
    expect(target.textContent).toContain('Tilføj en animation');
  });
  it('positioner: en knap pr. position med navn', async () => {
    const c = emptyConfig('pumpe');
    setOp(c, 'positions');
    c.positions = [{ label: 'Stop' }, { label: 'Start' }];
    c.anims = [{ part: 'hjul', type: 'fill', src: '@pos', params: { colors: ['#111111', '#22aa22'] }, only: null }];
    mountIt(c);
    await settle();
    expect(fill()).toBe('rgb(17, 17, 17)');
    button('Start').click();
    await settle();
    expect(fill()).toBe('rgb(34, 170, 34)');
  });
  it('animationer uden kilde nævnes, og et symbol der ikke findes giver en besked', async () => {
    const c = cfg();
    c.anims.push({ part: 'hjul', type: 'visible', src: '', params: {}, only: null });
    mountIt(c);
    await settle();
    expect(target.textContent).toContain('1 animation mangler en kilde');
    unmount(app);
    mountIt(cfg(), SVG, 'findes_ikke');
    await settle();
    expect(target.textContent).toContain('kunne ikke vises');
  });
  it('Afspil starter og Stop stopper uden fejl', async () => {
    mountIt(cfg());
    await settle();
    button('Afspil').click();
    await settle();
    expect(button('Stop')).toBeTruthy();
    button('Stop').click();
    await settle();
    expect(button('Afspil')).toBeTruthy();
    button('Nulstil').click();
    await settle();
    expect(fill()).toBe('rgb(51, 51, 51)');
  });
});
