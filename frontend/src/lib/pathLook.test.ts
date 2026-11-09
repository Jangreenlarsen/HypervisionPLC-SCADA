import { describe, expect, it } from 'vitest';
import { FLOW_DEFAULTS, mergeDefs } from './symbolFlow';
import { WAYS_PART, WHOLE, animsFor, anyChosen, defaultLook, groupOf, paramsFor, restoreLook, wayParts, type Look } from './pathLook';
import type { NetRow } from './signalPath';

const row = (over: Partial<NetRow>): NetRow => ({ id: 'x', name: 'X', type: '', role: 'pipe', flows: [], branches: [0], uses: [], ...over });
const DEFS = mergeDefs(null);
const PARTS = [{ id: 'v3_port_a', pid: 'port_a' }, { id: 'v3_port_b', pid: 'port_b' }, { id: 'v3_port_ab', pid: 'port_ab' }, { id: 'v3_motor', pid: 'motor' }];

describe('udseende af en signalvej', () => {
  it('starts as before: flow on the pipes, nothing else', () => {
    const l = defaultLook();
    expect(l.pipe.filter((a) => a.on).map((a) => a.type)).toEqual(['flow']);
    expect(['valve', 'threeway', 'pump', 'switch'].flatMap((g) => l[g as keyof Look].filter((a) => a.on))).toEqual([]);
    expect(l.pipe.some((a) => a.type === 'opacity' as never)).toBe(false);          // gennemsigtighed kan ikke styres af en logikblok
    expect(l.valve.some((a) => a.type === 'flow')).toBe(false);                      // løbelys kræver en streg
  });

  it('puts flow on the pipe parts, and other animations on the same parts', () => {
    const l = defaultLook();
    l.pipe.find((a) => a.type === 'fill')!.on = true;
    const t = row({ role: 'pipe', type: 't_stykke', flows: [{ part: 't_a', reverse: false }, { part: 't_b', reverse: true }] });
    const r = animsFor(t, l, DEFS);
    expect(r.flows).toEqual(t.flows);
    expect(r.anims.map((a) => [a.part, a.type, a.params, a.when])).toEqual([['t_a', 'fill', { on: '#66bb6a' }, true], ['t_b', 'fill', { on: '#66bb6a' }, true]]);
    l.pipe.find((a) => a.type === 'flow')!.on = false;
    expect(animsFor(t, l, DEFS).flows).toEqual([]);                                  // løbelys fra: kun farven
  });

  it('colours a valve as a whole, or a chosen part, and blinks with a speed', () => {
    const l = defaultLook();
    const fill = l.valve.find((a) => a.type === 'fill')!;
    fill.on = true;
    fill.color = '#00aa00';
    const blink = l.valve.find((a) => a.type === 'blink')!;
    blink.on = true;
    blink.speed = 'fast';
    blink.part = 'kugle';
    const v = row({ id: 'v', role: 'valve', type: 'kugleventil' });
    expect(animsFor(v, l, DEFS).anims).toEqual([
      { part: WHOLE, type: 'fill', params: { on: '#00aa00' }, when: true }, { part: 'kugle', type: 'blink', params: { speed: 'fast' }, when: true }]);
    l.valve.find((a) => a.type === 'visible')!.on = true;
    expect(animsFor(v, l, DEFS).anims.find((a) => a.type === 'visible')).toMatchObject({ part: WHOLE, when: false });   // skjult, når vejen er inaktiv
    expect(animsFor({ ...v, role: 'check' }, l, DEFS).anims).toHaveLength(3);        // en kontraventil følger ventilerne
  });

  it('a 3-way valve only animates the ports of the way the path uses', () => {
    const l = defaultLook();
    l.threeway.find((a) => a.type === 'fill')!.on = true;
    const v3 = row({ id: 'v3', role: 'threeway', type: 'trevejs_motorventil', uses: [{ branch: 0, way: 'AB>A', entry: null, exit: null }] });
    expect(wayParts(v3, v3.type, DEFS, PARTS)).toEqual(['v3_port_a', 'v3_port_ab']);
    expect(animsFor(v3, l, DEFS, PARTS).anims.map((a) => a.part)).toEqual(['v3_port_a', 'v3_port_ab']);
    const both = { ...v3, uses: [...v3.uses, { branch: 1, way: 'AB>B', entry: null, exit: null }] };
    expect(wayParts(both, both.type, DEFS, PARTS).sort()).toEqual(['v3_port_a', 'v3_port_ab', 'v3_port_b']);   // to grene, to veje
    // uden navngivne dele (symbol uden port-id'er): hele ventilen
    expect(animsFor(v3, l, DEFS, []).anims.map((a) => a.part)).toEqual([WHOLE]);
    // hele symbolet vælges udtrykkeligt
    l.threeway.find((a) => a.type === 'fill')!.part = WHOLE;
    expect(animsFor(v3, l, DEFS, PARTS).anims.map((a) => a.part)).toEqual([WHOLE]);
    expect(WAYS_PART).toBe('ways');
  });

  it('elements that are not on the list get nothing', () => {
    const l = defaultLook();
    l.valve[0].on = true;
    expect(animsFor(row({ role: 'unit' }), l, DEFS)).toEqual({ flows: [], anims: [] });
    expect(groupOf('unit')).toBeNull();
    expect(groupOf('check')).toBe('valve');
  });

  it('restores a saved look, ignoring bad values', () => {
    const l = defaultLook();
    l.pump.find((a) => a.type === 'spin')!.on = true;
    l.valve.find((a) => a.type === 'fill')!.color = '#112233';
    const back = restoreLook(JSON.parse(JSON.stringify(l)));
    expect(back.pump.find((a) => a.type === 'spin')!.on).toBe(true);
    expect(back.valve.find((a) => a.type === 'fill')!.color).toBe('#112233');
    const broken = restoreLook({ valve: [{ type: 'fill', on: true, color: 'rød', speed: 'hurtig', part: 5 }], pump: 'x', ukendt: [] });
    expect(broken.valve.find((a) => a.type === 'fill')).toMatchObject({ on: true, color: '#66bb6a', speed: 'normal', part: WHOLE });
    expect(restoreLook(null)).toEqual(defaultLook());
  });

  it('knows whether anything is chosen for the kinds of element on the path', () => {
    const l = defaultLook();
    expect(anyChosen(l, new Set(['pipe']))).toBe(true);
    expect(anyChosen(l, new Set(['valve', 'pump']))).toBe(false);
    l.pump.find((a) => a.type === 'spin')!.on = true;
    expect(anyChosen(l, new Set(['valve', 'pump']))).toBe(true);
    expect(paramsFor({ type: 'spin', on: true, part: WHOLE, color: '#000000', speed: 'normal' })).toEqual({});
    expect(FLOW_DEFAULTS.trevejs_motorventil.ports.every((p) => !!p.part)).toBe(true);
  });
});
