// Flow-model runde 2 (v6.3.0): retning pr. delstreg på rørstykker, flow-profilen pr. symboltype, guidens standarder og
// preview-kaldets krop.
import { describe, expect, it } from 'vitest';
import { bindingActive, colorFor, flowGroup, parsePortFlows, portDirection, portFlow, speedFor } from './animate';
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
  it('hvert ben har sit eget flow — til sin egen fart (v6.12.0)', () => {
    // flowet kommer ind ad to ben (pumpe-loopet 15, kontraventilen 5) og ud ad det tredje (20)
    const pf = { '0,1': 15, '1,1': 5, '0.5,0': -20 };
    expect(portFlow([1, 1], [0.5, 1], pf)).toEqual({ forward: true, q: 5 });
    expect(portFlow([0, 1], [0.5, 1], pf)).toEqual({ forward: true, q: 15 });
    expect(portFlow([0.5, 0.9], [0.5, 0], pf)).toEqual({ forward: true, q: 20 });
    const p = { flow_max: 20, speed: 40 };
    expect([speedFor(5, p), speedFor(15, p), speedFor(20, p)]).toEqual([10, 30, 40]);   // benet mod kontraventilen løber langsommere
  });
  it('forbindelsernes løbelys er ét forløb på tværs af elementernes egne tags (v6.12.4)', () => {
    expect(flowGroup('flow:d:r1', { chain: 'conn', mode: 'signed' })).toBe(flowGroup('flowp:d:t', { chain: 'conn', mode: 'onoff' }));
    expect(flowGroup('A', {})).not.toBe(flowGroup('B', {}));                // ellers som før: pr. tag
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
    expect(v.port_colors).toBeNull();                            // v6.7.0: typens tilstande farver selv portene
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

describe('ventiltilstande (Jan: tilstand 1 = A igennem AB, B blokeret …)', async () => {
  const { describeState, stateOf, guessState, FLOW_DEFAULTS: D, validateDef: vd } = await import('./symbolFlow');
  const three = D.trevejs_motorventil_ab;
  const four = D.firevejsventil;
  it('betydningen i ord, med de blokerede porte', () => {
    expect(describeState(three, ['AB>A'])).toBe('A igennem AB · B blokeret');
    expect(describeState(three, ['AB>B'])).toBe('B igennem AB · A blokeret');
    expect(describeState(four, ['A>B'])).toBe('A igennem B · C og D blokeret');
    expect(describeState(four, ['C>D'])).toBe('C igennem D · A og B blokeret');
    expect(describeState(four, [])).toBe('alle porte blokeret');
  });
  it('hvilken tilstand en position har, og gæt ud fra navn eller nummer', () => {
    expect(stateOf(three, ['A>AB'])).toBe(0);
    expect(stateOf(three, ['AB>A', 'AB>B'])).toBeNull();
    expect(guessState(three, 'B → AB', 0)).toBe(1);
    expect(guessState(four, 'Varme', 1)).toBe(1);
    expect(guessState(four, 'Ekstra', 5)).toBeNull();
  });
  it('guiden starter med tilstandene', () => {
    expect(defaultFlow('firevejsventil', ['Varme', 'Køl'], ['A>B', 'C>D'], four).open).toEqual([['A>B'], ['C>D']]);
  });
  it('en tilstand skal bruge kendte veje og have et unikt navn', () => {
    expect(vd({ ...four, states: [{ name: 'X', open: ['A>C'] }] })).toMatch(/findes ikke/);
    expect(vd({ ...four, states: [{ name: 'X', open: [] }, { name: 'x', open: [] }] })).toMatch(/to gange/);
    expect(vd(four)).toBeNull();
  });
});

describe('design B: tilstande med udseende på symboltypen', async () => {
  const { effectiveLook, FLOW_DEFAULTS: D, hasProfile: hp } = await import('./symbolFlow');
  it('typens udseende, med symbolets afvigelser ovenpå', () => {
    const st = D.trevejs_motorventil_ab.states;
    const base = effectiveLook(st, {}, 'A → AB');
    expect(base.find((l) => l.part === 'port_b')?.value).toBe('#000000');
    const ov = effectiveLook(st, { 'A → AB': [{ part: 'port_a', anim: 'fill', value: '#1e88e5' }] }, 'A → AB');
    expect(ov.find((l) => l.part === 'port_a')?.value).toBe('#1e88e5');
    expect(ov.find((l) => l.part === 'port_ab')?.value).toBe('#2e7d32');      // resten følger typen
    expect(effectiveLook(st, {}, null)).toEqual([]);
  });
  it('omskifteren har tilstandene med grebets vinkel', () => {
    expect(D.omskifter3.states?.map((s) => [s.name, s.look?.[0].value])).toEqual([['Hånd', -45], ['0', 0], ['Auto', 45]]);
    expect(hp({ ports: [], states: [{ name: 'X', open: [] }] })).toBe(true);
  });
  it('portfarverne fra v6.3.0 slås ikke til, når tilstandene selv farver portene', () => {
    expect(defaultFlow('trevejs_motorventil_ab', ['A → AB', 'B → AB'], ['AB>A', 'AB>B'], D.trevejs_motorventil_ab).port_colors).toBeNull();
  });
});

describe('typePortMap (v6.8.5)', () => {
  it('giver Tegn typens punkter — pumpen kun IND/UD i venstre og højre side', async () => {
    const { typePortMap, mergeDefs } = await import('./symbolFlow');
    const m = typePortMap(mergeDefs(null));
    expect(m.pumpe).toEqual([[0, 0.5], [1, 0.5]]);
    expect(m.kontraventil).toEqual([[0, 0.67], [1, 0.67]]);
    expect(typePortMap({ x: { ports: [] } } as never)).toEqual({});
  });
});
