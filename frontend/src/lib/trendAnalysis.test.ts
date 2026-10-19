import { describe, expect, it } from 'vitest';
import { FROZEN_DEFAULT_S, affectedPoints, analyze, formatSpan, formatShare, hideSpikes, irregularShare } from './trendAnalysis';
import type { Point } from './trendData';

const pts = (vals: (number | null)[], step = 10): Point[] => vals.map((v, i) => [i * step, v, v, v]);
const wave = (n: number) => Array.from({ length: n }, (_, i) => 20 + Math.sin(i / 2));

describe('analyze', () => {
  it('rolig serie: ingen fund', () => expect(analyze(pts(wave(40)))).toEqual([]));
  it('for få punkter eller helt flad serie: ingen fund', () => {
    expect(analyze(pts([1, 50, 1]))).toEqual([]);
    expect(analyze(pts(Array(30).fill(5)))).toEqual([]);
  });
  it('finder en enkelt spike', () => {
    const v = wave(40);
    v[20] = 500;
    const found = analyze(pts(v));
    expect(found.filter((i) => i.kind === 'spike').map((i) => i.t)).toEqual([200]);
  });
  it('et niveauskift er et spring, ikke en spike', () => {
    const v = [...Array(20).fill(10).map((x, i) => x + (i % 2) * 0.1), ...Array(20).fill(100).map((x, i) => x + (i % 2) * 0.1)];
    const found = analyze(pts(v));
    expect(found.some((i) => i.kind === 'spike')).toBe(false);
    expect(found.filter((i) => i.kind === 'jump')).toHaveLength(1);
  });
  it('fastfrosset værdi', () => {
    const v = [...wave(15), ...Array(15).fill(21.5), ...wave(10)];
    const found = analyze(pts(v), { frozenMinS: 100 });
    expect(found.filter((i) => i.kind === 'frozen')).toHaveLength(1);
  });
  it('hul i data', () => {
    const p = pts(wave(30));
    const shifted = p.map((x, i): Point => (i >= 15 ? [x[0] + 500, x[1], x[2], x[3]] : x));
    expect(analyze(shifted).filter((i) => i.kind === 'gap')).toHaveLength(1);
  });
  it('null-værdier (huller) giver ikke fejl', () => {
    const v: (number | null)[] = wave(30);
    v[10] = null;
    v[11] = null;
    expect(() => analyze(pts(v))).not.toThrow();
  });
});

describe('hideSpikes', () => {
  it('udfylder kun spikes ved lineær interpolation og lader rådata være', () => {
    const v = wave(40);
    v[20] = 500;
    const p = pts(v);
    const out = hideSpikes(p, analyze(p));
    const mid = (v[19] + v[21]) / 2;
    expect(out[20][0]).toBe(200);
    expect(out[20][1]).toBeCloseTo(mid);
    expect(out[20][2]).toBeCloseTo(mid);
    expect(out[19]).toBe(p[19]);
    expect(p[20][1]).toBe(500);
  });
  it('uden spikes returneres serien uændret', () => {
    const p = pts(wave(40));
    expect(hideSpikes(p, analyze(p))).toBe(p);
  });
});

describe('andel uregelmæssigheder', () => {
  it('en fastfrosset række tæller hele rækken, øvrige fund ét punkt', () => {
    const f = analyze(pts([...wave(20), ...Array(15).fill(25), ...wave(20)]), { frozenMinS: 100 });
    const frozen = f.find((i) => i.kind === 'frozen')!;
    expect(frozen.n).toBe(15);
    expect(affectedPoints([frozen, { t: 1, kind: 'spike', note: '' }])).toBe(16);
  });
  it('procenten er i forhold til alle punkter og når aldrig over 100 eller under 0', () => {
    expect(irregularShare(5, 200)).toBe(2.5);
    expect(irregularShare(9, 3)).toBe(100);
    expect(irregularShare(0, 0)).toBe(0);
  });
  it('formatering med dansk komma, og små andele bliver ikke til 0', () => {
    expect(formatShare(2.5)).toBe('2,5 %');
    expect(formatShare(0)).toBe('0 %');
    expect(formatShare(0.04)).toBe('< 0,1 %');
    expect(formatShare(100)).toBe('100 %');
  });
});

describe('fastfrosset i tid', () => {
  // en rolig temperaturføler: samme værdi i 8 timer (punkt hvert 10. minut) midt i en ellers varierende serie
  const calm = pts([...wave(30), ...Array(48).fill(21.5), ...wave(30)], 600);
  it('en lang, rolig periode under tærsklen ringes ikke om', () => {
    expect(analyze(calm, { frozenMinS: 12 * 3600 }).filter((i) => i.kind === 'frozen')).toHaveLength(0);
  });
  it('samme periode ringes om, når den er længere end tærsklen — med varighed i noten', () => {
    const f = analyze(calm, { frozenMinS: 6 * 3600 }).filter((i) => i.kind === 'frozen');
    expect(f).toHaveLength(1);
    expect(f[0].note).toContain('7 t 50 min');
  });
  it('standarden er 6 timer, og null slår fastfrosset fra', () => {
    expect(FROZEN_DEFAULT_S).toBe(6 * 3600);
    expect(analyze(calm).filter((i) => i.kind === 'frozen')).toHaveLength(1);
    expect(analyze(calm, { frozenMinS: null }).filter((i) => i.kind === 'frozen')).toHaveLength(0);
  });
  it('varigheder skrives læseligt', () => {
    expect(formatSpan(1500)).toBe('25 min');
    expect(formatSpan(3 * 3600)).toBe('3 t');
    expect(formatSpan(8.5 * 3600)).toBe('8 t 30 min');
    expect(formatSpan(51 * 3600)).toBe('2 døgn 3 t');
  });
  it('et hul i data over lang tid findes stadig', () => {
    const p = pts(wave(40), 3600).map((x, i): Point => (i >= 20 ? [x[0] + 3 * 86400, x[1], x[2], x[3]] : x));
    expect(analyze(p, { frozenMinS: null }).filter((i) => i.kind === 'gap')).toHaveLength(1);
  });
});
