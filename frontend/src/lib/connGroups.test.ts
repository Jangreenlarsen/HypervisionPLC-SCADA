import { describe, expect, it } from 'vitest';
import { activeFor, colorFor, speedFor } from './animate';
import { ON_MIN, connAnimError, defaultOnOff, describeConnAnims, describeOnOff, fromOnOff, newConnAnim, pickConnections, toOnOff } from './connGroups';
import { FLOW, defaultFlow, flowSourceMode, isLogicRef } from './symbolConfig';

describe('forbindelsesgrupper', () => {
  it('only connections can be picked from the selection', () => {
    expect(pickConnections(['r1', 'rad', 'r2', 'r1'], [{ id: 'r1' }, { id: 'r2' }])).toEqual(['r1', 'r2']);
  });
  it('new animations have backend-compatible defaults and a readable summary', () => {
    expect(newConnAnim('flow')).toMatchObject({ type: 'flow', speed: 60, full: 0 });
    expect(describeConnAnims([newConnAnim('flow'), newConnAnim('blink')])).toBe('løbelys + blink ved ≤ 0 l/min');
    expect(describeConnAnims([])).toBe('ingen animation');
  });
  it('checks the rules like the backend', () => {
    expect(connAnimError({ type: 'color', limits: [{ value: 10, color: '#000' }, { value: 5, color: '#fff' }] })).toMatch(/stigende/);
    expect(connAnimError({ type: 'blink', at_least: null, at_most: null })).toMatch(/grænse/);
    expect(connAnimError({ type: 'flow', speed: 2 })).toMatch(/Farten/);
    expect(connAnimError(newConnAnim('fixed'))).toBeNull();
  });
});

describe('tegnemotoren og flowet', () => {
  it('the running light speed follows the flow, in steps, never below 5', () => {
    const p = { speed: 60, flow_max: 120 };
    expect(speedFor(120, p)).toBe(60);
    expect(speedFor(-60, p)).toBe(30);                 // retningen tæller ikke for farten
    expect(speedFor(1, p)).toBe(5);
    expect(speedFor(500, p)).toBe(60);
    expect(speedFor(10, { speed: 40 })).toBe(40);      // uden flow_max: den faste fart
  });
  it('abs makes colour and blink ignore the direction; at_most blinks at no flow', () => {
    const c = { abs: true, off: '#999', thresholds: [{ value: 10, color: '#00f' }] };
    expect(colorFor(-20, c)).toBe('#00f');
    expect(colorFor(-20, { ...c, abs: false })).toBe('#999');
    expect(activeFor(0, { abs: true, at_most: 0 })).toBe(true);
    expect(activeFor(-3, { abs: true, at_most: 0 })).toBe(false);
    expect(activeFor(-30, { abs: true, at_least: 20 })).toBe(true);
  });
});

describe('flow i symbolets opsætning', () => {
  it('a pump type pumps; a valve gets all ways open in every position', () => {
    expect(defaultFlow('pumpe', [], [])).toMatchObject({ pump: true, capacity: 100, open: null });
    expect(defaultFlow('trevejs_motorventil', ['Fra', 'Til'], ['AB>A', 'AB>B']).open).toEqual([['AB>A', 'AB>B'], ['AB>A', 'AB>B']]);
    expect(defaultFlow('trevejs_motorventil', ['AB → A', 'B'], ['AB>A', 'AB>B']).open).toEqual([['AB>A'], ['AB>B']]);
  });
  it('source modes and the flow source are not a logic block', () => {
    expect(flowSourceMode({ src: '', max: 1 })).toBe('none');
    expect(flowSourceMode({ src: '@val:0.5', max: 1 })).toBe('val');
    expect(flowSourceMode({ src: 'P1_hz', max: 50 })).toBe('tag');
    expect(flowSourceMode({ src: '@pos', max: 1 })).toBe('pos');                                  // v6.9.4
    expect(defaultFlow('pumpe', ['Fra', 'Til'], []).rate.src).toBe('@pos');                     // pumpe med positioner: start/stop
    expect(defaultFlow('pumpe', [], []).rate.src).toBe('@val:1');                                // uden positioner: fast værdi
    expect(isLogicRef(FLOW)).toBe(false);
  });
});

describe('Til og Fra (v6.12.0)', () => {
  it('the default group (running light) reads as Til: løbelys, Fra: som tegnet', () => {
    const m = toOnOff([{ type: 'flow' }])!;
    expect(m.on.show).toBe('flow');
    expect(m.off.color).toBe('');
    expect(describeOnOff([{ type: 'flow' }])).toBe('Til: løbelys · Fra: som tegnet');
  });

  it('round-trips every combination', () => {
    for (const show of ['flow', 'color', 'none'] as const) {
      for (const offColor of ['', '#9e9e9e']) {
        for (const [onB, offB] of [[false, false], [true, false], [false, true], [true, true]]) {
          const m = defaultOnOff();
          Object.assign(m.on, { show, color: '#00ff00', blink: onB, rate: 'fast' });
          Object.assign(m.off, { color: offColor, blink: offB, rate: offB && !onB ? 'slow' : 'fast' });
          const anims = fromOnOff(m);
          expect(anims.every((a) => !connAnimError(a)), JSON.stringify(anims)).toBe(true);
          const back = toOnOff(anims)!;
          expect(fromOnOff(back), `${show} ${offColor} ${onB} ${offB}`).toEqual(anims);     // det gemte er stabilt
          expect([back.on.show, back.off.color, back.on.blink, back.off.blink]).toEqual([show, offColor, onB, offB]);
        }
      }
    }
  });

  it('Til and Fra become the right colors and blink in the engine', () => {
    const m = defaultOnOff();
    Object.assign(m.on, { show: 'color', color: '#00ff00' });
    Object.assign(m.off, { color: '#ff0000', blink: true });
    const [color, blink] = fromOnOff(m);
    const p = { abs: true, off: color.off, on: color.off, thresholds: color.limits };
    expect(colorFor(0, p)).toBe('#ff0000');
    expect(colorFor(ON_MIN, p)).toBe('#00ff00');
    expect(activeFor(0, { abs: true, at_most: blink.at_most })).toBe(true);
    expect(activeFor(5, { abs: true, at_most: blink.at_most })).toBe(false);
    // Til som tegnet med en Fra-farve: tom farve = som tegnet
    Object.assign(m.on, { show: 'none' });
    expect(colorFor(5, { off: '#ff0000', thresholds: fromOnOff(m)[0].limits })).toBe('');
  });

  it('lists that are not on/off stay advanced', () => {
    expect(toOnOff([{ type: 'fixed', color: '#123456' }])).toBeNull();
    expect(toOnOff([{ type: 'color', off: '#000000', limits: [{ value: 5, color: '#111111' }, { value: 10, color: '#222222' }] }])).toBeNull();
    expect(toOnOff([{ type: 'blink', at_least: 20, at_most: null }])).toBeNull();
    expect(describeOnOff([{ type: 'fixed', color: '#123456' }])).toBe('avanceret: fast farve');
    expect(toOnOff([])).toEqual({ ...defaultOnOff(), on: { ...defaultOnOff().on, show: 'none' } });
  });
});
