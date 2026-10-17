import { describe, expect, it } from 'vitest';
import { alarmPayload, alarmStatus, alarmSummary, formFrom, hasAlarm } from './tagAlarm';

const none = { alarm_hh: null, alarm_h: null, alarm_l: null, alarm_ll: null, alarm_deadband: 0, alarm_delay_s: 0, alarm_on: null } as const;

describe('tag-alarm i guiden (v0.74.0)', () => {
  it('kort tekst', () => {
    expect(hasAlarm(none)).toBe(false);
    expect(alarmSummary(none)).toBe('ingen alarm');
    expect(alarmSummary({ ...none, alarm_h: 80, alarm_hh: 90, alarm_deadband: 2 }, 'bar')).toBe('HH 90 · H 80 bar · dødbånd 2');
    expect(alarmSummary({ ...none, alarm_l: 0, alarm_delay_s: 5 })).toBe('L 0 · 5 s forsinkelse');   // 0 er en gyldig grænse
    expect(alarmSummary({ ...none, alarm_on: 'false', alarm_deadband: 3 })).toBe('når Fra');
  });

  it('formular → data: tal-tag og til/fra-tag; tomt og mellemrum = ingen; komma; fejl med feltnavn', () => {
    const f = { ...formFrom(none), h: '80,5', hh: ' 90 ', l: '  ', deadband: '2' };
    expect(alarmPayload(f, 'num')).toEqual({ data: { alarm_hh: 90, alarm_h: 80.5, alarm_l: null, alarm_ll: null, alarm_deadband: 2, alarm_delay_s: 0, alarm_on: null } });
    expect(alarmPayload({ ...f, on: 'true', delay: '3' }, 'bool')).toEqual({ data: { alarm_on: 'true', alarm_hh: null, alarm_h: null, alarm_l: null, alarm_ll: null, alarm_delay_s: 3 } });
    expect(alarmPayload({ ...f, on: '' }, 'bool')).toMatchObject({ data: { alarm_on: null } });
    expect(alarmPayload({ ...f, h: 'høj' }, 'num')).toEqual({ error: 'H skal være et tal' });
    expect(alarmPayload({ ...f, delay: '-1' }, 'num')).toEqual({ error: 'Forsinkelse kan ikke være negativ' });
    expect(formFrom({ ...none, alarm_l: 0, alarm_on: null })).toMatchObject({ l: '0', deadband: '', delay: '' });
  });

  it('status ud fra de to live-værdier', () => {
    expect(alarmStatus(undefined, undefined).level).toBe('unknown');
    expect(alarmStatus(false, false)).toEqual({ text: 'Ingen alarm', level: 'none' });
    expect(alarmStatus(true, true)).toEqual({ text: 'Aktiv — ukvitteret', level: 'unack' });
    expect(alarmStatus(true, false)).toEqual({ text: 'Aktiv — kvitteret', level: 'active' });
    expect(alarmStatus(false, true)).toEqual({ text: 'Ophørt — ukvitteret', level: 'unack' });
  });
});
