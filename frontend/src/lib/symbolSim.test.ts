import { describe, expect, it } from 'vitest';
import { SYMBOLS } from './symbols';
import { ROOT, librarySetup, testParts, type LibrarySetup } from './symbolTest';
import type { AnimType, SrcKind } from './symbolConfig';
import {
  PALETTE, addThreshold, applyAlarmMarks, clampCount, clampValue, clearSim, defaultParams, fromOwn, fromSetup, kindFor, liveOfTag, newAnim, newTag,
  paramFields, removeThreshold, retune, setItem, setParam, setThreshold, syncSim, tagRange, toHex6, type Applied, type SimAnim, type SimTag,
} from './symbolSim';

const def = (id: string) => SYMBOLS.find((s) => s.id === id)!;
const host = (svg: string) => {
  const h = document.createElement('div');
  h.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg">${svg}</svg>`;
  return h.firstElementChild!;
};
const ALL: AnimType[] = ['fill', 'stroke', 'blink', 'visible', 'spin', 'flicker', 'level', 'opacity', 'text', 'rotate', 'move', 'scale', 'flow'];
const KINDS: SrcKind[] = ['bool', 'num', 'pos'];

describe('tags', () => {
  it('nye tags får unikke navne, og art styrer område og værdi', () => {
    const a = newTag([], 'bool'), b = newTag([a], 'num'), c = newTag([a, b], 'pos');
    expect(new Set([a.name, b.name, c.name]).size).toBe(3);
    expect(tagRange(a)).toEqual({ min: 0, max: 1 });
    expect(tagRange({ ...c, count: 5 })).toEqual({ min: 0, max: 4 });
    expect(tagRange({ ...b, min: 10, max: 5 })).toEqual({ min: 0, max: 100 });   // ugyldigt område falder tilbage
  });
  it('værdien holdes inden for tagget, og 0 bevares', () => {
    const t = newTag([], 'num');
    t.value = 250; expect(clampValue(t)).toBe(100);
    t.value = -5; expect(clampValue(t)).toBe(0);
    t.value = 0; expect(clampValue(t)).toBe(0);
    const p = { ...newTag([], 'pos'), count: 3, value: 7 };
    expect(clampValue(p)).toBe(2);
    expect(clampCount(99)).toBe(8);
    expect(clampCount('x')).toBe(2);
  });
  it('en simuleret værdi der mangler giver ingen live-værdi, og kvaliteten følger tagget', () => {
    const t = { ...newTag([], 'num'), value: 42, missing: true, quality: 'bad' as const };
    expect(liveOfTag(t).value).toBeNull();
    expect(liveOfTag(t).quality).toBe('bad');
    expect(liveOfTag({ ...t, missing: false }).value).toBe(42);
  });
});

describe('parametre', () => {
  it('en position bruger kun positionsparametre for de typer der har dem', () => {
    const pos = newTag([], 'pos');
    expect(kindFor('fill', pos)).toBe('pos');
    expect(kindFor('level', pos)).toBe('num');
    expect(defaultParams('fill', pos).pos).toBe(true);
    expect(defaultParams('level', pos).pos).toBeUndefined();
  });
  it('alle typer og arter har felter, og ethvert krævet felt findes i standardparametrene', () => {
    for (const anim of ALL) {
      for (const kind of KINDS) {
        const tag = { ...newTag([], kind), count: 3 };
        const fields = paramFields(anim, tag);
        expect(fields.length, `${anim}/${kind}`).toBeGreaterThan(0);
        const params = defaultParams(anim, tag);
        for (const f of fields) {
          const optional = 'optional' in f && f.optional;
          // valgfrie felter og felter der først får værdi ved redigering har ingen standard
          if (optional || ['dir_tag', 'arm', 'arm_flow', 'show_unit', 'labels', 'palette'].includes(f.key)) continue;
          expect(Object.keys(params), `${anim}/${kind}: ${f.key}`).toContain(f.key);
        }
      }
    }
  });
  it('lister har det antal elementer tagget har positioner', () => {
    const tag = { ...newTag([], 'pos'), count: 4 };
    for (const f of paramFields('rotate', tag)) if (f.type === 'numbers') expect(f.n).toBe(4);
    expect((defaultParams('rotate', tag).angles as number[]).length).toBe(4);
  });
  it('tal gøres til tal, tomme valgfrie felter fjernes, og 0 bevares', () => {
    const f = paramFields('text', newTag([], 'num')).find((x) => x.key === 'decimals')!;
    expect(setParam({}, f, '2')).toEqual({ decimals: 2 });
    expect(setParam({ decimals: 2 }, f, '')).toEqual({});
    expect(setParam({}, f, '0')).toEqual({ decimals: 0 });
    const glide = paramFields('rotate', newTag([], 'bool')).find((x) => x.key === 'glide_s')!;
    expect(setParam({ glide_s: 1 }, glide, '')).toEqual({});
    expect(setParam({}, glide, '0')).toEqual({ glide_s: 0 });
    expect(setParam({}, glide, 'abc')).toEqual({});   // ikke et tal: uændret
  });
  it('liste-elementer og grænser redigeres uden at røre originalen', () => {
    const p = { colors: ['#111111', '#222222'] };
    const q = setItem(p, 'colors', 1, '#abcdef', 2);
    expect(q.colors).toEqual(['#111111', '#abcdef']);
    expect(p.colors[1]).toBe('#222222');
    const t = { thresholds: [{ value: 50, color: '#aaaaaa' }] };
    const added = addThreshold(t);
    expect(added.thresholds).toHaveLength(2);
    expect(added.thresholds[1].value).toBe(60);
    expect(setThreshold(added, 1, { value: 75 }).thresholds[1].value).toBe(75);
    expect(removeThreshold(added, 0).thresholds).toHaveLength(1);
    expect(t.thresholds).toHaveLength(1);
  });
  it('skift af art eller antal positioner giver animationerne nye standardparametre', () => {
    const tag = newTag([], 'bool');
    const a = newAnim(tag, ROOT, 'fill');
    expect(a.params.on).toBeDefined();
    tag.kind = 'pos'; tag.count = 3;
    retune([a], tag);
    expect(a.params.colors).toHaveLength(3);
  });
  it('paletten er symbolfarverne og animationernes signalfarver, uden dubletter', () => {
    expect(new Set(PALETTE).size).toBe(PALETTE.length);
    expect(PALETTE).toContain('#2e7d32');
    expect(PALETTE).toContain('#1f1f1f');
    expect(toHex6('#abc')).toBe('#aabbcc');
    expect(toHex6('rød')).toBe('#000000');
    expect(toHex6('#7CC47F')).toBe('#7cc47f');
  });
});

describe('anvendelse på symbolet', () => {
  const fill = (el: Element) => (el as SVGElement).style.fill;
  it('flere animationer på forskellige tags virker samtidig', () => {
    const h = host(def('varmepumpe').svg);
    const parts = testParts(def('varmepumpe').svg, 'varmepumpe').map((p) => p.id);
    expect(parts).toEqual(expect.arrayContaining(['rotor', 'lampe']));
    const t1 = { ...newTag([], 'bool'), value: 1 }, t2 = { ...newTag([t1], 'bool'), value: 0 };
    const tags = [t1, t2];
    const anims = [newAnim(t1, 'lampe', 'fill'), newAnim(t2, 'rotor', 'spin')];
    const applied = new Map<string, Applied>();
    expect(syncSim(h, anims, tags, applied)).toEqual([]);
    expect(fill(h.querySelector('#lampe')!)).toBeTruthy();
    expect(h.querySelector('#rotor')!.classList.contains('hv-spin')).toBe(false);
    t2.value = 1;
    syncSim(h, anims, tags, applied);
    expect(h.querySelector('#rotor')!.classList.contains('hv-spin')).toBe(true);
  });
  it('ændrede parametre nulstiller det gamle, og en fjernet animation efterlader delen som tegnet', () => {
    const h = host(def('lampe').svg);
    const t = { ...newTag([], 'bool'), value: 1 };
    const a = newAnim(t, 'glas', 'fill');
    const applied = new Map<string, Applied>();
    syncSim(h, [a], [t], applied);
    const green = fill(h.querySelector('#glas')!);
    a.params = { ...a.params, on: '#c62828' };
    syncSim(h, [a], [t], applied);
    expect(fill(h.querySelector('#glas')!)).not.toBe(green);
    syncSim(h, [], [t], applied);
    expect(fill(h.querySelector('#glas')!)).toBe('');
    expect(applied.size).toBe(0);
  });
  it('en del der ikke findes rapporteres, og de øvrige animationer virker stadig', () => {
    const h = host(def('lampe').svg);
    const t = { ...newTag([], 'bool'), value: 1 };
    const missing = syncSim(h, [newAnim(t, 'findes_ikke', 'fill'), newAnim(t, 'glas', 'fill')], [t], new Map());
    expect(missing).toEqual(['findes_ikke']);
    expect(fill(h.querySelector('#glas')!)).toBeTruthy();
  });
  it('en tekst viser tagværdien med enhed, og — når værdien mangler', () => {
    const h = host(def('setpunkt').svg);
    const t = { ...newTag([], 'num'), value: 21.5, unit: '°C' };
    const a = newAnim(t, 'vaerdi', 'text');
    const applied = new Map<string, Applied>();
    syncSim(h, [a], [t], applied);
    expect(h.querySelector('#vaerdi')!.textContent).toContain('21.5 °C');
    t.missing = true;
    syncSim(h, [a], [t], applied);
    expect(h.querySelector('#vaerdi')!.textContent).toContain('—');
  });
  it('en position vælger farven pr. position', () => {
    const h = host(def('lampe').svg);
    const t = { ...newTag([], 'pos'), count: 3, value: 0 };
    const a = newAnim(t, 'glas', 'fill');
    a.params.colors = ['#111111', '#222222', '#333333'];
    const applied = new Map<string, Applied>();
    syncSim(h, [a], [t], applied);
    const c0 = fill(h.querySelector('#glas')!);
    t.value = 2;
    syncSim(h, [a], [t], applied);
    expect(fill(h.querySelector('#glas')!)).not.toBe(c0);
  });
  it('nulstil rydder alt', () => {
    const h = host(def('lampe').svg);
    const t = { ...newTag([], 'bool'), value: 1 };
    const applied = new Map<string, Applied>();
    syncSim(h, [newAnim(t, 'glas', 'fill')], [t], applied);
    clearSim(h, applied);
    expect(fill(h.querySelector('#glas')!)).toBe('');
  });
  it('alarmmarkering kun på dele der viser værdien, og ukvitteret vinder over kvitteret', () => {
    const h = host(def('setpunkt').svg);
    const t1: SimTag = { ...newTag([], 'num'), alarm: 'ack' }, t2: SimTag = { ...newTag([t1], 'num'), alarm: 'unack' };
    const anims: SimAnim[] = [newAnim(t1, 'vaerdi', 'text'), newAnim(t2, 'vaerdi', 'text'), newAnim(t1, ROOT, 'fill')];
    applyAlarmMarks(h, anims, [t1, t2]);
    expect(h.querySelector('#vaerdi')!.classList.contains('hv-alarm-unack')).toBe(true);
    expect(h.querySelector('#vaerdi')!.classList.contains('hv-alarm-ack')).toBe(false);
    expect(h.firstElementChild!.classList.contains('hv-alarm-ack')).toBe(false);
    t1.alarm = ''; t2.alarm = '';
    applyAlarmMarks(h, anims, [t1, t2]);
    expect(h.querySelector('#vaerdi')!.classList.contains('hv-alarm-unack')).toBe(false);
  });
});

describe('fra biblioteket', () => {
  it('opsætningen bliver ét positions-tag med navne og animationerne på det', () => {
    const setup = librarySetup(def('vippe_onoffon').svg, 'vippe_onoffon') as LibrarySetup;
    const { tags, anims } = fromSetup(setup);
    expect(tags).toHaveLength(1);
    expect(tags[0].kind).toBe('pos');
    expect(tags[0].labels).toEqual(['ON 1', 'OFF', 'ON 2']);
    expect(anims.length).toBeGreaterThan(0);
    expect(anims.every((a) => a.tag === tags[0].id)).toBe(true);
    const h = host(def('vippe_onoffon').svg);
    expect(syncSim(h, anims, tags, new Map())).toEqual([]);
  });
  it('symbolets egne animationer bliver til animationer på ét til/fra-tag', () => {
    const { tags, anims } = fromOwn(testParts(def('vippekontakt').svg, 'vippekontakt'));
    expect(tags[0].kind).toBe('bool');
    expect(anims.some((a) => a.anim === 'move')).toBe(true);
    expect(syncSim(host(def('vippekontakt').svg), anims, tags, new Map())).toEqual([]);
  });
});
