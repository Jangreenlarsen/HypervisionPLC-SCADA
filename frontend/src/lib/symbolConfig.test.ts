import { describe, expect, it } from 'vitest';
import {
  activeAt, animDefaults, opChoices, cycleCell, isLogicRef, keepSuggestion, emptyConfig, foundPosition, parseValRef, partLabel, preset, resize, setOp, tagKind, template, typesFor, valRef,
  type PartInfo, type SymbolConfig, type SymbolInfo,
} from './symbolConfig';

const positions = (labels: string[]): SymbolConfig => {
  const c = emptyConfig();
  setOp(c, 'positions');
  c.positions = labels.map((label) => ({ label }));
  return c;
};

describe('tagKind', () => {
  it('til/fra, tal og ukendt', () => {
    expect(tagKind('plc1:coil:3')).toBe('bool');
    expect(tagKind('plc1:di:3')).toBe('bool');
    expect(tagKind('plc1:hr:30')).toBe('num');
    expect(tagKind('plc1:hr:30:real')).toBe('num');
    expect(tagKind('plc1:logic:1:Niveau')).toBe('unknown');
  });
});

describe('skabeloner og eksemplet dec → bin', () => {
  it('7-trins vælger: 3 signaler, 3 planer, tallet j+1 binært', () => {
    const c = emptyConfig();
    preset(c);
    expect(c.signals.map((s) => s.id)).toEqual(['S1', 'S2', 'S3']);
    expect(c.planes.map((p) => p.values)).toEqual([[1, 0, 1, 0, 1, 0, 1], [0, 1, 1, 0, 0, 1, 1], [0, 0, 0, 1, 1, 1, 1]]);
  });
  it('dec → bin tæller fra 0 når første position hedder "0"', () => {
    const c = positions(['0', '1', '2', '3']);
    template(c, 'D');
    expect(c.planes.map((p) => p.values)).toEqual([[0, 1, 0, 1], [0, 0, 1, 1]]);
  });
  it('A ét register, B ét signal pr. position, C bitmaske', () => {
    const c = positions(['Hand', '0', 'Auto']);
    template(c, 'A');
    expect(c.planes).toEqual([{ signal: 'S1', values: [0, 1, 2] }]);
    template(c, 'B');
    expect(c.planes.map((p) => p.values)).toEqual([[1, 0, 0], [0, 1, 0], [0, 0, 1]]);
    template(c, 'C');
    expect(c.planes).toEqual([{ signal: 'S1', values: [1, 2, 4] }]);
  });
});

describe('struktur', () => {
  it('flere positioner: celler, lås, "gælder i" og værdier pr. position følger med', () => {
    const c = positions(['A', 'B']);
    c.signals = [{ id: 'S1', tag: 'Bit', fb: '', write: 'set', ms: 500, rest: null }, { id: 'S2', tag: 'Reg', fb: '', write: 'set', ms: 500, rest: null }];
    c.planes = [{ signal: 'S1', values: [0, 1] }, { signal: 'S2', values: [5, 6] }];
    c.anims = [{ part: 'all', type: 'fill', src: '@pos', params: { colors: ['#000', '#111'] }, only: [true, false] }];
    c.positions.push({ label: 'C' });
    resize(c, (id) => (id === 'S1' ? 'bool' : 'num'));
    expect(c.planes.map((p) => p.values)).toEqual([[0, 1, 0], [5, 6, null]]);
    expect(c.lock.positions).toEqual([false, false, false]);
    expect(c.anims[0].only).toEqual([true, false, true]);
    expect(c.anims[0].params.colors).toEqual(['#000', '#111', '#e4e4e4']);
  });
  it('aktive signaler pr. position og cyklus Til → Fra → røres ikke', () => {
    const c = emptyConfig();
    preset(c);
    expect(activeAt(c, 4, () => 'bool')).toEqual(['S1', 'S3']);       // 5 = 101
    expect(cycleCell(1)).toBe(0);
    expect(cycleCell(0)).toBe(null);
    expect(cycleCell(null)).toBe(1);
  });
  it('fundet position ud fra live-værdier (tilbagemelding foran kommando)', () => {
    const c = emptyConfig();
    preset(c);
    c.signals[0].tag = 'B0'; c.signals[0].fb = 'B0_fb'; c.signals[1].tag = 'B1'; c.signals[2].tag = 'B2';
    const live: Record<string, unknown> = { B0_fb: true, B0: false, B1: true, B2: false };   // 3 = 011
    expect(foundPosition(c, (t) => live[t])).toBe(2);
    live.B2 = true;   // 7
    expect(foundPosition(c, (t) => live[t])).toBe(6);
    expect(foundPosition(c, () => undefined)).toBe(null);
  });
  it('skift betjeningsform rydder det der ikke passer', () => {
    const c = emptyConfig();
    preset(c);
    c.anims = [{ part: 'all', type: 'fill', src: '@pos', params: { colors: [] }, only: null }];
    setOp(c, 'pulse');
    expect([c.positions.length, c.planes.length, c.signals.length, c.anims.length]).toEqual([0, 0, 1, 0]);
    setOp(c, 'view');
    expect(c.signals).toEqual([]);
  });
});

describe('animationer', () => {
  it('typer efter delens geometri', () => {
    expect(typesFor({ tag: 'rect', line: true })).toContain('level');
    expect(typesFor({ tag: 'circle', line: false })).not.toContain('level');
    expect(typesFor({ tag: 'text', line: false })).toContain('text');
    expect(typesFor({ tag: 'path', line: true })).toContain('flow');
  });
  it('standardparametre efter kilden', () => {
    expect(animDefaults('fill', 'pos', 2)).toEqual({ colors: ['#d6d6d6', '#7cc47f'] });
    expect(animDefaults('rotate', 'pos', 3)).toEqual({ angles: [-45, 0, 45] });
    // coil (Til/Fra) står som 0 og 100: niveau, gennemsigtighed og størrelse bruger 0–100 for både coil og tal
    for (const t of ['level', 'opacity', 'scale'] as const) {
      expect(animDefaults(t, 'bool', 0).max, t).toBe(100);
      expect(animDefaults(t, 'num', 0).max, t).toBe(100);
    }
    expect(animDefaults('blink', 'num', 0)).toEqual({ at_least: 50, speed: 'normal' });
    expect(animDefaults('flow', 'pos', 3).dirs).toEqual([0, 1, 1]);
  });
});

describe('delnavne i guiden (v0.81.0)', () => {
  const info = (type: string, parts: Record<string, PartInfo>): SymbolInfo => ({ tag: 'g', line: false, type, name: 'X', parts });
  it('biblioteksnavn, ramme, nummererede figurer og tekst', () => {
    const kedel = info('kedel', { svg_2: { tag: 'rect', line: true }, svg_39_flamme: { tag: 'path', line: true, pid: 'flamme' } });
    expect(partLabel('all', kedel)).toBe('Hele symbolet');
    expect(partLabel('svg_39_flamme', kedel)).toBe('Flamme');
    expect(partLabel('svg_2', kedel)).toBe('Ramme (svg_2)');
    const kedel2 = info('kedel', { svg_2: { tag: 'rect', line: true }, svg_7: { tag: 'rect', line: true }, svg_8: { tag: 'rect', line: true } });
    expect(['svg_2', 'svg_7', 'svg_8'].map((k) => partLabel(k, kedel2))).toEqual(['Ramme (svg_2)', 'Rektangel 1 (svg_7)', 'Rektangel 2 (svg_8)']);
    const egen = info('custom', {
      a: { tag: 'rect', line: true }, b: { tag: 'rect', line: true }, c: { tag: 'circle', line: false },
      d: { tag: 'text', line: false, text: 'STF' }, e: { tag: 'text', line: false, text: '' }, f: { tag: 'foo', line: false },
    });
    expect(['a', 'b', 'c', 'd', 'e', 'f'].map((k) => partLabel(k, egen)))
      .toEqual(['Rektangel 1 (a)', 'Rektangel 2 (b)', 'Cirkel (c)', 'Tekst "STF" (d)', 'Tekst 2 (e)', 'Del (f)']);
    expect(partLabel('ukendt', egen)).toBe('ukendt');
  });
});

describe('biblioteksforslag bevares, når det første tag vælges (v0.94.0)', () => {
  const fresh = { min: 0, max: 1, angle_min: 0, angle_max: 90 };
  it('kun fra tom kilde og med samme felter', () => {
    expect(keepSuggestion('', { min: 0, max: 1, angle_min: 0, angle_max: 32 }, fresh)).toBe(true);
    expect(keepSuggestion('Andet', { min: 0, max: 1, angle_min: 0, angle_max: 32 }, fresh)).toBe(false);   // skift af tag
    expect(keepSuggestion(undefined, { min: 0, max: 1, angle_min: 0, angle_max: 32 }, fresh)).toBe(false); // skift af del/type
    expect(keepSuggestion('', { angles: [0, 32] }, fresh)).toBe(false);                                      // andre felter
    expect(keepSuggestion('', {}, fresh)).toBe(false);
    // v0.97.1: Drej valgt FØR tagget har tal-standarden — et til/fra-tag skal give til/fra-standarden
    const numDefault = { min: 0, max: 100, angle_min: -120, angle_max: 120 };
    expect(keepSuggestion('', { ...numDefault }, fresh, numDefault)).toBe(false);
    expect(keepSuggestion('', { min: 0, max: 1, angle_min: 0, angle_max: 32 }, fresh, numDefault)).toBe(true);   // forslaget
  });
});

describe('fast værdi (@val:)', () => {
  it('læser tal, og afviser alt andet', () => {
    expect(parseValRef('@val:75')).toBe(75);
    expect(parseValRef('@val:-12.5')).toBe(-12.5);
    expect(parseValRef('@val:0')).toBe(0);                 // nul er en gyldig værdi
    for (const bad of ['@val:', '@val:abc', '@val:NaN', '@val:Infinity', 'Pumpe', '@on', '@L1', undefined, null]) expect(parseValRef(bad), String(bad)).toBeNull();
    expect(valRef(40)).toBe('@val:40');
  });
  it('er ikke en logikblok-henvisning', () => {
    expect(isLogicRef('@val:5')).toBe(false);
    expect(isLogicRef('@L1')).toBe(true);
  });
});

describe('betjeningsformer i trin 1 (v1.11.1)', () => {
  it('en form man har valgt fra, kan vælges igen', () => {
    // ny omskifter: starter som "Kun visning" → både visning og positioner tilbydes
    expect(opChoices('omskifter3', 'view', ['view'])).toEqual(['view', 'positions']);
    // efter valg af Positioner står "Kun visning" der stadig (før forsvandt den)
    expect(opChoices('omskifter3', 'positions', ['view', 'positions'])).toEqual(['view', 'positions']);
    // uden historik: kun de former, der giver mening for typen (+ den aktuelle)
    expect(opChoices('omskifter3', 'positions', ['positions'])).toEqual(['positions']);
    expect(opChoices('tank', 'view', ['view'])).toEqual(['view']);
  });
});
