import { describe, expect, it } from 'vitest';
import { inSystem, type AlarmSystem } from './alarmSystems';

const vand: AlarmSystem = { id: 'vandvaerk', name: 'vandvaerk', tags: ['VW_AL_P1', 'VW_AL_TRIP'] };

describe('alarmer pr. system', () => {
  it('uden valgt system vises alt', () => {
    expect(inSystem(null, { key: 'tag:X:state', tag: 'X' })).toBe(true);
  });
  it('tag-alarmer hører til systemer, der bruger tagget', () => {
    expect(inSystem(vand, { key: 'tag:VW_AL_P1:state', tag: 'VW_AL_P1' })).toBe(true);
    expect(inSystem(vand, { key: 'tag:TNE_ALARM:state', tag: 'TNE_ALARM' })).toBe(false);
  });
  it('symbolalarmer hører til deres tegning', () => {
    expect(inSystem(vand, { key: 'sym:vandvaerk:broend:alarm', kind: 'symbol', tag: '' })).toBe(true);
    expect(inSystem(vand, { key: 'sym:varme:svg_1:alarm', kind: 'symbol', tag: '' })).toBe(false);
  });
  it('SCADA- og forbindelsesalarmer og hændelser uden tag vises altid', () => {
    expect(inSystem(vand, { key: 'sys:x', kind: 'sys', tag: '' })).toBe(true);
    expect(inSystem(vand, { key: 'plc:demo', kind: 'comm', tag: '' })).toBe(true);
    expect(inSystem(vand, { key: 'plc:demo', tag: '' })).toBe(true);
  });
});
