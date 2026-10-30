import { describe, expect, it } from 'vitest';
import { POS_TAG, buildPreview, playState, previewValues } from './animPreview';
import { renderAll } from './canvas';
import { alarmRef, emptyConfig, setOp, type Anim, type SymbolConfig } from './symbolConfig';

const kindOf = (tag: string): 'bool' | 'num' | 'unknown' => (tag.startsWith('DO') ? 'bool' : tag.startsWith('AI') ? 'num' : 'unknown');
const anim = (over: Partial<Anim>): Anim => ({ part: 'lampe', type: 'fill', src: 'DO1', params: { on: '#00ff00', off: '#222222' }, only: null, ...over });
const cfgWith = (anims: Anim[], positions: string[] = []): SymbolConfig => {
  const c = emptyConfig('x');
  if (positions.length) { setOp(c, 'positions'); c.positions = positions.map((label) => ({ label })); }
  c.anims = anims;
  return c;
};

describe('animationer → bindinger og kontroller', () => {
  it('et til/fra-tag giver en Fra/Til-kontrol og en binding på delen', () => {
    const p = buildPreview(cfgWith([anim({})]), 'sym', kindOf);
    expect(p.controls).toEqual([{ name: 'DO1', label: 'DO1', kind: 'bool', min: 0, max: 1, step: 1, labels: [] }]);
    expect(p.bindings).toHaveLength(1);
    expect(p.bindings[0]).toMatchObject({ element: 'lampe', tag: 'DO1', anim: 'fill', position: 1000 });
  });
  it('"hele symbolet" peger på symbolets eget element', () => {
    expect(buildPreview(cfgWith([anim({ part: 'all' })]), 'pumpe_1', kindOf).bindings[0].element).toBe('pumpe_1');
  });
  it('et tal-tag får en skyder: animationernes Min/Max, ellers grænserne, ellers 0–100', () => {
    const num = (params: Record<string, any>) => buildPreview(cfgWith([anim({ src: 'AI1', type: 'level', params })]), 's', kindOf).controls[0];
    expect(num({ min: 10, max: 50 })).toMatchObject({ kind: 'num', min: 10, max: 50 });
    expect(num({ thresholds: [{ value: 50, color: '#fff' }, { value: 80, color: '#f00' }] })).toMatchObject({ min: 0, max: 100 });
    expect(num({})).toMatchObject({ min: 0, max: 100 });
  });
  it('symbolets position giver én kontrol med positionernes navne, også når flere animationer bruger den', () => {
    const c = cfgWith([
      anim({ src: '@pos', params: { colors: ['#111111', '#222222', '#333333'] } }),
      anim({ part: 'greb', type: 'rotate', src: '@pos', params: { angles: [0, 45, 90] } }),
    ], ['Fra', 'Auto', 'Hånd']);
    const p = buildPreview(c, 's', kindOf);
    expect(p.controls).toEqual([{ name: POS_TAG, label: 'Symbolets position', kind: 'pos', min: 0, max: 2, step: 1, labels: ['Fra', 'Auto', 'Hånd'] }]);
    expect(p.bindings.map((b) => [b.tag, b.params.pos])).toEqual([[POS_TAG, true], [POS_TAG, true]]);
  });
  it('"pr. værdi" styres af positionen direkte (fra-værdierne udelades)', () => {
    const c = cfgWith([anim({ src: 'AI5', by_value: true, pos_values: [0, 10, 20], params: { colors: ['#111111', '#222222', '#333333'] } })], ['A', 'B', 'C']);
    const p = buildPreview(c, 's', kindOf);
    expect(p.bindings[0].tag).toBe(POS_TAG);
    expect(p.bindings[0].params.pos_values).toBeUndefined();
    expect(p.controls.map((x) => x.kind)).toEqual(['pos']);
  });
  it('"gælder i positionerne" og aktiv/passiv oversættes som serveren gør', () => {
    const c = cfgWith([anim({ only: [true, false], when: true })], ['A', 'B']);
    const p = buildPreview(c, 's', kindOf);
    expect(p.bindings[0].params).toMatchObject({ only: [true, false], pos_tag: POS_TAG, when: true });
    expect(p.controls.map((x) => x.name).sort()).toEqual(['DO1', POS_TAG].sort());
  });
  it('logikblok, alarm, altid til og fast værdi', () => {
    const c = cfgWith([
      anim({ src: '@L1' }), anim({ src: alarmRef('active', 'AI9') }), anim({ src: '@on' }), anim({ type: 'level', src: '@val:40', params: { min: 0, max: 100 } }),
    ]);
    const p = buildPreview(c, 's', kindOf);
    expect(p.controls.map((x) => [x.name, x.kind])).toEqual([['preview:logic:L1', 'bool'], ['preview:alarm:active:AI9', 'bool']]);
    expect(p.bindings.map((b) => b.tag)).toEqual(['preview:logic:L1', 'preview:alarm:active:AI9', '@on', '@val:40']);
  });
  it('en animation uden kilde vises ikke, men tælles', () => {
    const p = buildPreview(cfgWith([anim({ src: '' }), anim({})]), 's', kindOf);
    expect([p.bindings.length, p.unset]).toEqual([1, 1]);
  });
  it('løbelysets retnings-tag får sin egen kontrol', () => {
    const p = buildPreview(cfgWith([anim({ type: 'flow', params: { mode: 'signed', dir_tag: 'AI3' } })]), 's', kindOf);
    expect(p.controls.map((c) => c.name)).toEqual(['AI3', 'DO1']);
    expect(p.bindings[0].params.dir_tag).toBe('AI3');
  });
});

describe('skyderens område', () => {
  const num = (params: Record<string, any>, own: { min: number; max: number } | null) =>
    buildPreview(cfgWith([anim({ src: 'AI1', type: 'level', params })]), 's', kindOf, () => own).controls[0];
  it('tagets egne min/max bruges, når animationen ikke har et område', () => {
    expect(num({}, { min: 0, max: 400 })).toMatchObject({ min: 0, max: 400 });
  });
  it('animationens eget område går forud, og et ugyldigt område ignoreres', () => {
    expect(num({ min: 5, max: 20 }, { min: 0, max: 400 })).toMatchObject({ min: 5, max: 20 });
    expect(num({}, { min: 10, max: 10 })).toMatchObject({ min: 0, max: 100 });
    expect(num({}, null)).toMatchObject({ min: 0, max: 100 });
  });
});

describe('værdier og afspilning', () => {
  const p = buildPreview(cfgWith([anim({}), anim({ part: 'greb', type: 'rotate', src: 'AI1', params: { min: 0, max: 100, angle_min: 0, angle_max: 90 } })]), 's', kindOf);
  it('til/fra som sand/falsk, tal og positioner som tal, og holdt inden for området', () => {
    const v = previewValues(p.controls, { DO1: 1, AI1: 250 });
    expect([v.DO1.value, v.AI1.value]).toEqual([true, 100]);
    expect(previewValues(p.controls, {}).DO1.value).toBe(false);
    expect(previewValues(p.controls, {}).AI1.value).toBe(0);
  });
  it('afspilning løber gennem områderne', () => {
    expect(playState(p.controls, 0).DO1).toBe(1);
    expect(playState(p.controls, 4.5).DO1).toBe(0);
    expect(playState(p.controls, 3).AI1).toBe(100);   // halvvejs i runden: toppen
  });
});

describe('preview vist med den rigtige animationsmotor', () => {
  const SVGNS = 'http://www.w3.org/2000/svg';
  it('aktiv/passiv: den øverste aktive vinder', () => {
    const host = document.createElementNS(SVGNS, 'svg');
    host.innerHTML = '<g id="sym"><circle id="lampe" cx="5" cy="5" r="4"/></g>';
    const c = cfgWith([anim({ src: 'DO1', when: true, params: { on: '#ff0000', off: '#222222' } }), anim({ src: 'DO2', when: true, params: { on: '#00ff00', off: '#222222' } })]);
    const p = buildPreview(c, 'sym', kindOf);
    const fill = () => (host.querySelector('#lampe') as SVGElement).style.fill || host.querySelector('#lampe')!.getAttribute('fill');
    renderAll(host as unknown as HTMLElement, p.bindings, previewValues(p.controls, { DO1: 0, DO2: 1 }), {});
    expect(fill()).toBe('rgb(0, 255, 0)');
    renderAll(host as unknown as HTMLElement, p.bindings, previewValues(p.controls, { DO1: 1, DO2: 1 }), {});
    expect(fill()).toBe('rgb(255, 0, 0)');   // den øverste aktive vinder
  });
});
