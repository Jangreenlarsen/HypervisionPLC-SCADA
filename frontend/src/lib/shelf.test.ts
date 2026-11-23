import { describe, expect, it } from 'vitest';
import {
  DEFAULT_SHELVE_MINUTES, REASON_MAX, REASON_MIN, SHELVE_OPTIONS, canShelve, normalizeReason, reasonError, reasonLength, remainingNow, remainingText,
} from './shelf';

describe('shelf', () => {
  it('resttid som tekst', () => {
    expect(remainingText(0)).toBe('udløber nu');
    expect(remainingText(-5)).toBe('udløber nu');
    expect(remainingText(NaN)).toBe('udløber nu');
    expect(remainingText(1)).toBe('1 min');            // rundes op
    expect(remainingText(60)).toBe('1 min');
    expect(remainingText(61)).toBe('2 min');
    expect(remainingText(12 * 60)).toBe('12 min');
    expect(remainingText(59 * 60)).toBe('59 min');
    expect(remainingText(59 * 60 + 1)).toBe('1 t');     // 59 min 1 s rundes op til 60 min
    expect(remainingText(60 * 60)).toBe('1 t');
    expect(remainingText(65 * 60)).toBe('1 t 5 min');
    expect(remainingText(24 * 3600)).toBe('24 t');
  });

  it('varighedsvalg: 5-1440 min og standard 1 time', () => {
    expect(SHELVE_OPTIONS.map((o) => o.minutes)).toEqual([15, 60, 240, 480, 1440]);
    expect(SHELVE_OPTIONS.every((o) => Number.isInteger(o.minutes) && o.minutes >= 5 && o.minutes <= 1440)).toBe(true);
    expect(SHELVE_OPTIONS.find((o) => o.minutes === DEFAULT_SHELVE_MINUTES)?.label).toBe('1 time');
  });

  it('begrundelsens grænser (trimmet)', () => {
    expect(reasonError('')).not.toBe('');
    expect(reasonError('   ')).not.toBe('');
    expect(reasonError('ab')).toContain('mindst');
    expect(reasonError('  ab  ')).toContain('mindst');
    expect(reasonError('a'.repeat(REASON_MIN))).toBe('');
    expect(reasonError('  abc  ')).toBe('');
    expect(reasonError('x'.repeat(REASON_MAX))).toBe('');
    expect(reasonError('x'.repeat(REASON_MAX + 1))).toContain('højst');
  });

  it('begrundelsen normaliseres og tælles i kodepunkter som i backend', () => {
    expect(normalizeReason('  Sensor   mistænkes\u00a0\u00a0defekt  ')).toBe('Sensor mistænkes defekt');
    expect(reasonLength('a' + ' '.repeat(50) + 'bc')).toBe(4);
    expect(reasonError('\u{1F600}'.repeat(REASON_MAX))).toBe('');            // 200 kodepunkter = 400 UTF-16-enheder
    expect(reasonError('\u{1F600}'.repeat(REASON_MAX + 1))).toContain('højst');
    expect(reasonError('\u{1F600}\u{1F600}')).toContain('mindst');
    expect(reasonError('\u{1F600}\u{1F600}\u{1F600}')).toBe('');
  });

  it('kontrol- og formattegn afvises', () => {
    for (const bad of ['abc\ndef', 'abc\tdef', 'abc\u0000', 'ab\u200bc', '\u202eabc', 'abc\r']) {
      expect(reasonError(bad), JSON.stringify(bad)).toContain('kontroltegn');
    }
    expect(reasonError('abc def')).toBe('');
  });

  it('kommunikations- og systemalarmer og ophørte alarmer kan ikke udsættes', () => {
    expect(canShelve({ kind: 'high', state: 'active_unack' })).toBe(true);
    expect(canShelve({ kind: 'symbol', state: 'active_ack' })).toBe(true);
    expect(canShelve({ kind: 'comm', state: 'active_unack' })).toBe(false);
    expect(canShelve({ kind: 'sys', state: 'active_ack' })).toBe(false);
    expect(canShelve({ kind: 'state', state: 'rtn_unack' })).toBe(false);
  });

  it('resttid regnes fra serverens svar, ikke fra klientens ur', () => {
    expect(remainingNow(600, 1_000_000, 1_000_000)).toBe(600);
    expect(remainingNow(600, 1_000_000, 1_030_000)).toBe(570);
    expect(remainingNow(600, 1_000_000, 999_000)).toBe(600);   // et ur der går baglæns giver ikke mere tid
  });
});
