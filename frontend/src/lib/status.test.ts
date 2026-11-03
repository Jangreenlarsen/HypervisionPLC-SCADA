import { describe, expect, it } from 'vitest';
import { certSummary, fmtBytes, fmtDuration, fmtMs, fmtPercent, issuerName, levelClass } from './status';

describe('status-formatering', () => {
  it('bytes', () => {
    expect(fmtBytes(null)).toBe('—');
    expect(fmtBytes(0)).toBe('0 kB');
    expect(fmtBytes(1_500_000)).toBe('1.5 MB');
    expect(fmtBytes(32_000_000_000)).toBe('32.0 GB');
  });
  it('varighed', () => {
    expect(fmtDuration(null)).toBe('—');
    expect(fmtDuration(0)).toBe('0 s');
    expect(fmtDuration(59)).toBe('59 s');
    expect(fmtDuration(3 * 60)).toBe('3 min');
    expect(fmtDuration(3600 + 120)).toBe('1 t 2 min');
    expect(fmtDuration(93784)).toBe('1 d 2 t 3 min');
    expect(fmtDuration(86400)).toBe('1 d 0 t 0 min');
  });
  it('ms og procent (0 er en gyldig værdi)', () => {
    expect(fmtMs(0)).toBe('0.0 ms');
    expect(fmtMs(0.0042)).toBe('4.2 ms');
    expect(fmtMs(0.25)).toBe('250 ms');
    expect(fmtMs(null)).toBe('—');
    expect(fmtPercent(0, 100)).toBe('0 %');
    expect(fmtPercent(1, 4)).toBe('25 %');
    expect(fmtPercent(1, 0)).toBe('—');
  });
  it('niveau → badge', () => {
    expect([levelClass('ok'), levelClass('warn'), levelClass('error')]).toEqual(['ok', 'warn', 'error']);
  });
});

describe('certifikatkortet', () => {
  const tls = { issuer: "C=US, O=Let's Encrypt, CN=R11", subject: 'CN=scada.laces.dk', self_signed: false, fingerprint: '', not_after_ts: 0, days_left: 42 };
  it('udsteder', () => {
    expect(issuerName(tls.issuer)).toBe("Let's Encrypt");
    expect(issuerName('CN=Hypervision-SCADA')).toBe('Hypervision-SCADA');
    expect(issuerName('uden felter')).toBe('uden felter');
  });
  it('overskrift og note', () => {
    expect(certSummary(tls)).toEqual({ big: '42 dage', note: "Let's Encrypt · scada.laces.dk" });
    expect(certSummary({ ...tls, days_left: 1 }).big).toBe('1 dag');
    expect(certSummary({ ...tls, days_left: 0 }).big).toBe('0 dage');            // 0 er en gyldig værdi
    expect(certSummary({ ...tls, days_left: -2 }).big).toBe('udløbet');
    expect(certSummary({ ...tls, self_signed: true }).note).toContain('Selvsigneret');
  });
});
