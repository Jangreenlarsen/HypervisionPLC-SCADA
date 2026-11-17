import { describe, expect, it } from 'vitest';
import { inSystem, NO_SYSTEM, systemsOf, type AlarmSystem } from './alarmSystems';

const vand: AlarmSystem = { id: 'vandvaerk', name: 'Vandværk', tags: ['VW_AL_P1', 'VW_AL_TRIP'] };
const test: AlarmSystem = { id: 'test', name: 'Test', tags: ['TNE_ALARM'] };
const all = [vand, test];

describe('alarmer pr. system', () => {
  it('uden valgt system vises alt', () => {
    expect(inSystem(all, '', { key: 'tag:X:state', tag: 'X' })).toBe(true);
  });
  it('tag-alarmer hører til systemer, der bruger tagget', () => {
    expect(inSystem(all, 'vandvaerk', { key: 'tag:VW_AL_P1:state', tag: 'VW_AL_P1' })).toBe(true);
    expect(inSystem(all, 'vandvaerk', { key: 'tag:TNE_ALARM:state', tag: 'TNE_ALARM' })).toBe(false);
    expect(systemsOf(all, { key: 'tag:TNE_ALARM:state', tag: 'TNE_ALARM' }).map((s) => s.name)).toEqual(['Test']);
  });
  it('symbolalarmer hører til deres tegning', () => {
    expect(inSystem(all, 'vandvaerk', { key: 'sym:vandvaerk:broend:alarm', kind: 'symbol', tag: '' })).toBe(true);
    expect(inSystem(all, 'vandvaerk', { key: 'sym:varme:svg_1:alarm', kind: 'symbol', tag: '' })).toBe(false);
  });
  it('alarmer, der ikke står på nogen tegning, ses under "Uden system" — og ikke under et bestemt system', () => {
    const x = { key: 'tag:ORPHAN:state', tag: 'ORPHAN' };
    expect(systemsOf(all, x)).toEqual([]);
    expect(inSystem(all, NO_SYSTEM, x)).toBe(true);
    expect(inSystem(all, 'vandvaerk', x)).toBe(false);
    expect(inSystem(all, NO_SYSTEM, { key: 'tag:VW_AL_P1:state', tag: 'VW_AL_P1' })).toBe(false);
  });
  it('SCADA- og forbindelsesalarmer og hændelser uden tag vises altid', () => {
    expect(inSystem(all, 'vandvaerk', { key: 'sys:x', kind: 'sys', tag: '' })).toBe(true);
    expect(inSystem(all, 'vandvaerk', { key: 'plc:demo', kind: 'comm', tag: '' })).toBe(true);
    expect(inSystem(all, NO_SYSTEM, { key: 'plc:demo', tag: '' })).toBe(true);
    expect(systemsOf(all, { key: 'plc:demo', kind: 'comm', tag: '' })).toEqual([]);
  });
});
