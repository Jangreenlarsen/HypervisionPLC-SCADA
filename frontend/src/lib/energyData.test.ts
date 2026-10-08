import { describe, expect, it } from 'vitest';
import { fmtKwh, fmtTick, niceTicks } from './energyData';

describe('niceTicks', () => {
  it('pæne trin der dækker max', () => {
    expect(niceTicks(87)).toEqual([0, 20, 40, 60, 80, 100]);
    expect(niceTicks(4.2)).toEqual([0, 1, 2, 3, 4, 5]);
    expect(niceTicks(1200)).toEqual([0, 250, 500, 750, 1000, 1250]);
  });
  it('0, negativ eller ugyldig giver en enkel akse', () => {
    expect(niceTicks(0)).toEqual([0, 1]);
    expect(niceTicks(Number.NaN)).toEqual([0, 1]);
  });
});

describe('fmtKwh', () => {
  it('decimaler efter størrelse og dansk komma', () => {
    expect(fmtKwh(1234.4)).toBe('1.234');
    expect(fmtKwh(12.34)).toBe('12,3');
    expect(fmtKwh(0.0567)).toBe('0,057');
  });
  it('null er ingen data, 0 er nul', () => {
    expect(fmtKwh(null)).toBe('—');
    expect(fmtKwh(0)).toBe('0,000');
  });
});

describe('fmtTick', () => {
  it('samme decimaler på hele aksen', () => {
    expect([0, 10, 40].map((v) => fmtTick(v, 10))).toEqual(['0', '10', '40']);
    expect([0, 0.5, 1.5].map((v) => fmtTick(v, 0.5))).toEqual(['0,0', '0,5', '1,5']);
    expect(fmtTick(2500, 500)).toBe('2.500');
  });
});
