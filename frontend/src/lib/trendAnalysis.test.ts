import { describe, expect, it } from 'vitest';
import { analyze, hideSpikes } from './trendAnalysis';
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
    const found = analyze(pts(v));
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
  it('gør kun spikes til huller og lader rådata være', () => {
    const v = wave(40);
    v[20] = 500;
    const p = pts(v);
    const out = hideSpikes(p, analyze(p));
    expect(out[20]).toEqual([200, null, null, null]);
    expect(out[19]).toBe(p[19]);
    expect(p[20][1]).toBe(500);
  });
  it('uden spikes returneres serien uændret', () => {
    const p = pts(wave(40));
    expect(hideSpikes(p, analyze(p))).toBe(p);
  });
});
