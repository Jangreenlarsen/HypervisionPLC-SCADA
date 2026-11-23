import { describe, expect, it } from 'vitest';
import { alarmPayload, rationaleLines, alarmStatus, alarmSummary, formFrom, hasAlarm } from './tagAlarm';

const none = { alarm_hh: null, alarm_h: null, alarm_l: null, alarm_ll: null, alarm_deadband: 0, alarm_delay_s: 0, alarm_on: null, alarm_priority: null } as const;

const noWhy = { alarm_consequence: null, alarm_action: null, alarm_response_min: null };

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
    expect(alarmPayload(f, 'num')).toEqual({ data: { alarm_hh: 90, alarm_h: 80.5, alarm_l: null, alarm_ll: null, alarm_deadband: 2, alarm_delay_s: 0, alarm_on: null, alarm_priority: null, ...noWhy } });
    expect(alarmPayload({ ...f, on: 'true', delay: '3' }, 'bool')).toEqual({ data: { alarm_on: 'true', alarm_hh: null, alarm_h: null, alarm_l: null, alarm_ll: null, alarm_delay_s: 3, alarm_priority: null, ...noWhy } });
    expect(alarmPayload({ ...f, on: '' }, 'bool')).toMatchObject({ data: { alarm_on: null } });
    expect(alarmPayload({ ...f, h: 'høj' }, 'num')).toEqual({ error: 'H skal være et tal' });
    expect(alarmPayload({ ...f, delay: '-1' }, 'num')).toEqual({ error: 'Forsinkelse kan ikke være negativ' });
    expect(formFrom({ ...none, alarm_l: 0, alarm_on: null })).toMatchObject({ l: '0', deadband: '', delay: '' });
  });

  it('prioritet: tom = som niveau (null); high/medium/low sendes; formularen læser den fra tagget', () => {
    const f = { ...formFrom(none), h: '80' };
    expect(f.priority).toBe('');
    expect(alarmPayload(f, 'num')).toMatchObject({ data: { alarm_priority: null } });
    expect(alarmPayload({ ...f, priority: 'low' }, 'num')).toMatchObject({ data: { alarm_priority: 'low' } });
    expect(alarmPayload({ ...f, on: 'true', priority: 'high' }, 'bool')).toMatchObject({ data: { alarm_priority: 'high' } });
    expect(alarmPayload({ ...f, priority: 'medium' }, 'num')).toMatchObject({ data: { alarm_priority: 'medium' } });
    expect(formFrom({ ...none, alarm_priority: 'low' }).priority).toBe('low');
    expect(formFrom({}).priority).toBe('');
  });

  it('status ud fra de to live-værdier', () => {
    expect(alarmStatus(undefined, undefined).level).toBe('unknown');
    expect(alarmStatus(false, false)).toEqual({ text: 'Ingen alarm', level: 'none' });
    expect(alarmStatus(true, true)).toEqual({ text: 'Aktiv — ukvitteret', level: 'unack' });
    expect(alarmStatus(true, false)).toEqual({ text: 'Aktiv — kvitteret', level: 'active' });
    expect(alarmStatus(false, true)).toEqual({ text: 'Ophørt — ukvitteret', level: 'unack' });
  });
});

describe('rationalisering (v6.20.0, B6)', () => {
  const base = { ...none, alarm_h: 80 };

  it('formFrom indlæser tagets værdier, og alarmPayload sender dem tilbage uden tab (også 0)', () => {
    const t = { ...base, alarm_consequence: 'Kedlen stopper', alarm_action: 'Åbn V2', alarm_response_min: 0 };
    const f = formFrom(t);
    expect(f).toMatchObject({ consequence: 'Kedlen stopper', action: 'Åbn V2', responseMin: '0' });
    expect(alarmPayload(f, 'num')).toMatchObject({ data: { alarm_consequence: 'Kedlen stopper', alarm_action: 'Åbn V2', alarm_response_min: 0 } });
    expect(alarmPayload(formFrom(t), 'bool')).toMatchObject({ data: { alarm_consequence: 'Kedlen stopper', alarm_response_min: 0 } });
    // rettelse af et andet felt nulstiller dem ikke
    expect(alarmPayload({ ...f, h: '75' }, 'num')).toMatchObject({ data: { alarm_h: 75, alarm_action: 'Åbn V2', alarm_response_min: 0 } });
  });

  it('tomt felt (også mellemrum) sendes som null; ikke angivet på tagget giver tomme felter', () => {
    expect(formFrom(base)).toMatchObject({ consequence: '', action: '', responseMin: '' });
    const f = { ...formFrom(base), consequence: '   ', action: '', responseMin: '  ' };
    expect(alarmPayload(f, 'num')).toMatchObject({ data: { alarm_consequence: null, alarm_action: null, alarm_response_min: null } });
  });

  it('tekst trimmes og mellemrum kollapses; længde 200 kodepunkter', () => {
    const f = { ...formFrom(base), action: '  Åbn   ventil  ' };
    expect(alarmPayload(f, 'num')).toMatchObject({ data: { alarm_action: 'Åbn ventil' } });
    expect(alarmPayload({ ...f, action: 'æ'.repeat(200) }, 'num')).toMatchObject({ data: { alarm_action: 'æ'.repeat(200) } });
    expect(alarmPayload({ ...f, action: 'x'.repeat(201) }, 'num')).toEqual({ error: 'Handling må højst være 200 tegn' });
    expect(alarmPayload({ ...f, action: '', consequence: 'x'.repeat(201) }, 'num')).toEqual({ error: 'Konsekvens må højst være 200 tegn' });
  });

  it('svartid: 0..1440 hele minutter; fejltekst nævner feltet', () => {
    const f = formFrom(base);
    for (const ok of ['0', '1', '1440', ' 15 ']) expect(alarmPayload({ ...f, responseMin: ok }, 'num')).toMatchObject({ data: { alarm_response_min: Number(ok) } });
    for (const bad of ['-1', '1441', '5,5', '5.5', 'abc', '1e2'])
      expect(alarmPayload({ ...f, responseMin: bad }, 'num')).toEqual({ error: 'Svartid skal være et helt antal minutter fra 0 til 1440' });
  });

  it('rationaleLines: kun sat felter, 0 min vises', () => {
    expect(rationaleLines({})).toEqual([]);
    expect(rationaleLines({ consequence: null, action: '', response_min: null })).toEqual([]);
    expect(rationaleLines({ consequence: 'Stop', action: 'Åbn V2', response_min: 0 })).toEqual(['Handling: Åbn V2', 'Konsekvens: Stop', 'Svar inden 0 min']);
    expect(rationaleLines({ response_min: 30 })).toEqual(['Svar inden 30 min']);
  });
});
