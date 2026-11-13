// Simulatoren (v6.5.0): panelets hjælpere — start fra live, filtrering, skydertrin, værditabellen.
import { describe, expect, it } from 'vitest';
import { emptyState, fromLive, isSimulated, liveText, matches, startValue, stepFor, toLive, type SimVariables } from './simulator';

const vars: SimVariables = {
  tags: [
    { name: 'Pumpe', kind: 'bool', unit: '', min: null, max: null, decimals: null, description: 'Drift', plc: 'p', used: ['Pumpe 1 · Blink'], elements: ['p1'], live: { value: true, quality: 'good' } },
    { name: 'Tryk', kind: 'num', unit: 'bar', min: 0, max: 10, decimals: 1, description: '', plc: 'p', used: ['Tank · Farve'], elements: ['tank'], live: { value: null, quality: 'comm_error' } },
  ],
  positions: [{ element: 'v1', name: 'V1', labels: ['A', 'B'], display: 'remote', live: 1 }],
  alarms: [{ name: 'alarm:Tryk:active', tag: 'Tryk', kind: 'active', used: [], elements: [], live: { value: false, quality: 'good' } }],
};

describe('simulatoren', () => {
  it('start fra live tager kun gode værdier med', () => {
    expect(fromLive(vars)).toEqual({ values: { Pumpe: true, 'alarm:Tryk:active': false }, positions: { v1: 1 } });
  });
  it('en simuleret komm.fejl er null og stadig simuleret', () => {
    const s = { ...emptyState(), values: { Tryk: null } };
    expect(isSimulated(s, 'Tryk')).toBe(true);
    expect(isSimulated(s, 'Pumpe')).toBe(false);
  });
  it('startværdien er den live værdi, ellers et nul', () => {
    expect(startValue(vars.tags[0])).toBe(true);
    expect(startValue(vars.tags[1])).toBe(0);
  });
  it('søg i navn, beskrivelse og hvor den bruges', () => {
    expect(matches(vars.tags[1], 'tank', false, false)).toBe(true);
    expect(matches(vars.tags[0], 'drift', false, false)).toBe(true);
    expect(matches(vars.tags[0], '', false, true)).toBe(false);
  });
  it('skyderens trin følger intervallet', () => {
    expect(stepFor({ min: 0, max: 10, decimals: 1 })).toBe(0.1);
    expect(stepFor({ min: 0, max: 1000, decimals: null })).toBe(10);
    expect(stepFor({ min: null, max: null, decimals: 0 })).toBe(1);
  });
  it('svaret bliver Overview-motorens værditabel', () => {
    expect(toLive({ values: { a: { value: 1, quality: 'good' } }, notes: [], ms: 1, simulated: 0 }).a).toEqual({ value: 1, quality: 'good', ts: 0, error: null });
    expect(liveText({ value: true, quality: 'good' })).toBe('Til');
    expect(liveText({ value: null, quality: 'comm_error' })).toBe('komm.fejl');
    expect(liveText({ value: 2.5, quality: 'good' }, 'bar')).toBe('2.5 bar');
  });
});
