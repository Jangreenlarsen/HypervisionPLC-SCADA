import { describe, expect, it } from 'vitest';
import { daysLeft, emptySubject, hostCovered, parseSans, subjectBody } from './certificates';

describe('certificates', () => {
  it('navnelisten renses og dubletter fjernes', () => {
    expect(parseSans(' Scada.local, 10.1.1.31\nscada.local  ')).toEqual(['scada.local', '10.1.1.31']);
    expect(parseSans('')).toEqual([]);
  });
  it('kroppen udelader tomme felter', () => {
    const b = subjectBody({ ...emptySubject('pi.local'), o: ' Laces ', c: '' }, { days: 825 });
    expect(b).toEqual({ cn: 'pi.local', sans: ['pi.local'], key_type: 'ec256', o: 'Laces', days: 825 });
  });
  it('adressen dækkes af navn, IP eller wildcard på ét niveau', () => {
    expect(hostCovered('10.1.1.31', ['scada.local', '10.1.1.31'])).toBe(true);
    expect(hostCovered('SCADA.laces.dk', ['*.laces.dk'])).toBe(true);
    expect(hostCovered('a.b.laces.dk', ['*.laces.dk'])).toBe(false);
    expect(hostCovered('laces.dk', ['*.laces.dk'])).toBe(false);
    expect(hostCovered('[::1]', ['::1'])).toBe(true);
    expect(hostCovered('other', ['scada.local'])).toBe(false);
  });
  it('dage tilbage', () => {
    expect(daysLeft(86400 * 10 + 5, 0)).toBe(10);
    expect(daysLeft(-1, 0)).toBe(-1);
  });
});

import { leBusy, leHostOk } from './certificates';

describe("Let's Encrypt", () => {
  it('kun offentlige DNS-navne', () => {
    expect(leHostOk('scada.laces.dk')).toBe(true);
    expect(leHostOk('10.1.1.31')).toBe(false);
    expect(leHostOk('scada')).toBe(false);
    expect(leHostOk('-x.dk')).toBe(false);
  });
  it('i gang, mens anmodningen venter eller hjælperen kører', () => {
    expect(leBusy(null)).toBe(false);
    expect(leBusy({ info: null, status: null, log: [], waiting: true })).toBe(true);
    const st = { id: 'a', action: 'issue', state: 'running' as const, message: '', started: 0, ts: 0 };
    expect(leBusy({ info: null, status: st, log: [], waiting: false })).toBe(true);
    expect(leBusy({ info: null, status: { ...st, state: 'ok' }, log: [], waiting: false })).toBe(false);
  });
});
