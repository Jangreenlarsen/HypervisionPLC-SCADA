// Flow-model runde 2 (v6.3.0): retning pr. delstreg på rørstykker, flow-profilen pr. symboltype, guidens standarder og
// preview-kaldets krop.
import { describe, expect, it } from 'vitest';
import { bindingActive, colorFor, parsePortFlows, portDirection } from './animate';
import { bindingTags } from './canvas';
import { overlayData, previewBody, type Preview } from './flowLive';
import { defaultFlow } from './symbolConfig';
import { FLOW_DEFAULTS, hasProfile, kindOf, mergeDefs, unitOf, validateDef } from './symbolFlow';

describe('retning pr. delstreg på et rørstykke', () => {
  it('læser flowet pr. punkt', () => {
    expect(parsePortFlows('0,0:+100.0;1,1:-100.0')).toEqual({ '0,0': 100, '1,1': -100 });
    expect(parsePortFlows('')).toBeNull();
    expect(parsePortFlows(null)).toBeNull();
  });
  it('lyset løber væk fra punktet, hvor flowet kommer ind', () => {
    const pf = { '0,0': 100, '1,1': -100 };
    expect(portDirection([0, 0], [1, 1], pf)).toBe(true);      // tegnet fra ind mod ud: frem
    expect(portDirection([1, 1], [0, 0], pf)).toBe(false);     // tegnet modsat: baglæns
  });
  it('et T-stykkes ben: fra punktet ind mod midten', () => {
    const pf = { '0,0.5': 100, '1,0.5': -50, '0.5,1': -50 };
    expect(portDirection([0.5, 1], [0.5, 0.55], pf)).toBe(false);   // afgreningen tegnet fra punktet: flowet går ud dér
    expect(portDirection([0.5, 0.55], [0.5, 1], pf)).toBe(true);
  });
  it('kan ikke afgøres langt fra punkterne', () => {
    expect(portDirection([0.5, 0.5], [0.5, 0.45], { '0,0': 1 })).toBeNull();
  });
  it('rørstykkets punkt-tag hentes med bindingen', () => {
    expect(bindingTags({ tag: 'flow:d:b', anim: 'flow', params: { port_tag: 'flowp:d:b' } })).toEqual(['flow:d:b', 'flowp:d:b']);
  });
});

describe('flow-profilen pr. symboltype', () => {
  const defs = mergeDefs({ kilde: { ports: [], kind: 'pump', medium: 'electric', capacity: 16 }, rad: { ports: [], restrict: 0.5 } });
  it('rolle og enhed', () => {
    expect(kindOf(defs, 'kilde')).toBe('pump');
    expect(kindOf(defs, 'pumpe')).toBe('pump');
    expect(kindOf(defs, 'boejning90')).toBe('piece');
    expect(kindOf(defs, 'radiator')).toBe('consumer');
    expect(unitOf(defs, 'kilde')).toBe('A');
    expect(unitOf(defs, 'pumpe')).toBe('l/min');
  });
  it('en profil kan gemmes uden punkter, men ikke en tom definition', () => {
    expect(hasProfile({ ports: [], restrict: 0.5 })).toBe(true);
    expect(validateDef({ ports: [], kind: 'pump' })).toBeNull();
    expect(validateDef({ ports: [] })).toMatch(/mindst ét punkt/);
    expect(validateDef({ ports: [], restrict: 1.5 })).toMatch(/0,00 og 1,00/);
  });
  it('guidens standard følger profilen', () => {
    const f = defaultFlow('kilde', [], [], defs.kilde);
    expect(f.pump).toBe(true);
    expect(f.capacity).toBe(16);
    expect(defaultFlow('rad', [], [], defs.rad).restrict.src).toBe('@val:0.5');
    const v = defaultFlow('trevejs_motorventil_ab', ['AB → A', 'AB → B'], ['AB>A', 'AB>B'], FLOW_DEFAULTS.trevejs_motorventil_ab);
    expect(v.open).toEqual([['AB>A'], ['AB>B']]);
    expect(v.port_colors?.open).toBe('#2e7d32');                // punkterne har dele: portfarver fra start
    expect(defaultFlow('pumpe', [], []).port_colors).toBeNull();
  });
});

describe('preview i Tegn', () => {
  it('live sender kun tegningen; simuleringen holder værdierne i 0,00–1,00', () => {
    expect(previewBody('<svg/>', null)).toEqual({ svg: '<svg/>' });
    expect(previewBody('<svg/>', { rates: { p: 1.7 }, positions: { v: 1 }, restricts: { r: 0.333 } }))
      .toEqual({ svg: '<svg/>', rates: { p: 1 }, positions: { v: 1 }, restricts: { r: 0.33 } });
  });
  it('overlayets fulde flow er den største pumpe', () => {
    const p = { flows: { r1: 40 }, ports: {}, pumps: [{ id: 'p', name: 'P', configured: true, capacity: 120 }], pieces: ['t_stykke'] } as unknown as Preview;
    expect(overlayData(p)).toMatchObject({ max: 120, unit: 'l/min', pieces: ['t_stykke'] });
  });
});

describe('farve på et tal-tag med en aktiv-grænse (Jan: aktiv ved ≥ 50, ikke aktiv ved ≤ 49)', () => {
  const p = { on: '#00ff00', off: '#000000', at_least: 50 };
  it('farven skifter ved grænsen', () => {
    expect(colorFor(50, p)).toBe('#00ff00');
    expect(colorFor(49, p)).toBe('#000000');
    expect(colorFor(49.9, p)).toBe('#000000');
  });
  it('aktiv/passiv følger grænsen', () => {
    const live = (value: number) => ({ value, quality: 'good' as const, ts: 0, error: null });
    expect(bindingActive({ anim: 'fill', params: p }, live(50))).toBe(true);
    expect(bindingActive({ anim: 'fill', params: p }, live(49))).toBe(false);
  });
  it('uden grænse: som før (≠ 0)', () => {
    expect(colorFor(1, { on: '#00ff00', off: '#000000' })).toBe('#00ff00');
    expect(colorFor(1, { on: '#00ff00', off: '#000000', at_least: null })).toBe('#00ff00');
  });
});

describe('målt flow med baseline → flow-niveau (Jan: lavt 15,1 / højt 16,5)', () => {
  it('niveauet mellem lavt og højt flow', async () => {
    const { flowLevel } = await import('./symbolConfig');
    expect(flowLevel(15.85, 15.1, 16.5)).toBe(0.536);
    expect(flowLevel(14, 15.1, 16.5)).toBe(0);
    expect(flowLevel(20, 15.1, 16.5)).toBe(1);
    expect(flowLevel(15, 16.5, 15.1)).toBeNull();
  });
  it('rate og restriktion starter som faste værdier', () => {
    const f = defaultFlow('pumpe', [], []);
    expect(f.rate.src).toBe('@val:1');
    expect(f.restrict.src).toBe('@val:1');
    expect(f.measured).toEqual({ src: '', max: 1, low: 0, high: 100 });
  });
});
