import { describe, expect, it } from 'vitest';
import { activeFor, colorFor, speedFor } from './animate';
import { connAnimError, describeConnAnims, newConnAnim, pickConnections } from './connGroups';
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
    expect(isLogicRef(FLOW)).toBe(false);
  });
});
