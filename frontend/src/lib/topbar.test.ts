import { describe, expect, it } from 'vitest';
import { clockTitle, formatClock, plcChip, shortName } from './topbar';

const plc = (state: string, name = 'PLC A', message = '') => ({ name, state, message, sse: null });

describe('formatClock / clockTitle', () => {
  it('formaterer med foranstillede nuller', () => {
    expect(formatClock(new Date(2026, 10, 3, 4, 5, 6))).toBe('04:05:06');
    expect(formatClock(new Date(2026, 10, 3, 23, 59, 59))).toBe('23:59:59');
  });
  it('titlen har dato og tidszone', () => {
    const t = clockTitle(new Date(2026, 10, 3, 4, 5, 6));
    expect(t).toMatch(/^2026-11-03 · /);
    expect(t).toMatch(/UTC[+-]\d\d:\d\d/);
  });
});

describe('shortName', () => {
  it('lader korte navne være', () => expect(shortName('jan')).toBe('jan'));
  it('afkorter lange navne med ellipsis', () => expect(shortName('abcdefghijklmnop')).toBe('abcdefghi…'));
  it('præcis grænsen afkortes ikke', () => expect(shortName('abcdefghij')).toBe('abcdefghij'));
  it('tomme/manglende strenge', () => {
    expect(shortName('')).toBe('');
    expect(shortName('   ')).toBe('');
    expect(shortName(null)).toBe('');
    expect(shortName(undefined)).toBe('');
  });
});

describe('plcChip', () => {
  it('ingen forbindelse er rød og lister PLC\'erne', () => {
    const c = plcChip({ a: plc('ok') }, false);
    expect(c.level).toBe('error');
    expect(c.label).toBe('Ingen forbindelse');
    expect(c.title).toContain('PLC A');
  });
  it('ingen PLC\'er endnu = henter', () => {
    expect(plcChip({}, true).level).toBe('pending');
    expect(plcChip(null, true).level).toBe('pending');
  });
  it('alle ok', () => {
    const c = plcChip({ a: plc('ok'), b: plc('connected', 'B') }, true);
    expect(c).toMatchObject({ label: 'PLC 2/2', level: 'ok' });
  });
  it('kun nogle ok', () => {
    const c = plcChip({ a: plc('ok'), b: plc('error', 'B', 'Timeout') }, true);
    expect(c).toMatchObject({ label: 'PLC 1/2', level: 'error' });
    expect(c.title).toContain('B: fejl — Timeout');
  });
  it('stoppet/ukendt tilstand er gul', () => {
    expect(plcChip({ a: plc('stopped') }, true)).toMatchObject({ label: 'PLC 0/1', level: 'warn' });
    expect(plcChip({ a: plc('mystisk') }, true).level).toBe('warn');
    expect(plcChip({ a: plc('') }, true).title).toContain('PLC A: ukendt');
  });
  it('connecting er neutral', () => {
    expect(plcChip({ a: plc('connecting') }, true)).toMatchObject({ label: 'PLC 0/1', level: 'pending' });
  });
  it('tomt navn falder tilbage til nøglen; lange navne bevares i titlen', () => {
    const long = 'N'.repeat(80);
    const c = plcChip({ k1: plc('ok', ''), k2: plc('ok', long) }, true);
    expect(c.title).toContain('k1: ok');
    expect(c.title).toContain(long);
  });
});
