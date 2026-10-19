import { describe, expect, it } from 'vitest';
import { axisNumber, axisTime, chartLayout, chartPoints, defaultChart, refreshSeconds, yRange, type Point } from './chartGraphic';

const box = { x: 0, y: 0, w: 220, h: 110 };   // font 10 → plot x 32, y 19, w 182, h 74

describe('trendgraf i tegningen (v0.91.0)', () => {
  it('antal punkter og opdatering', () => {
    expect(chartPoints({ style: 'bar', bars: 24 })).toBe(24);
    expect(chartPoints({ style: 'line', bars: 24 })).toBe(120);
    expect(refreshSeconds({ style: 'line', bars: 24, range_s: 900 })).toBe(8);      // 900/120
    expect(refreshSeconds({ style: 'line', bars: 24, range_s: 120 })).toBe(5);      // mindst 5 s
    expect(refreshSeconds({ style: 'bar', bars: 24, range_s: 86400 })).toBe(60);    // højst 60 s
  });

  it('Y-aksen: valgt, fra data, søjler med 0, fladt forløb får luft', () => {
    const s: Point[][] = [[[0, 10], [1, 20]]];
    expect(yRange(s, { style: 'line', y_min: 0, y_max: 100 })).toEqual([0, 100]);
    expect(yRange(s, { style: 'line', y_min: null, y_max: null })).toEqual([9.5, 20.5]);
    expect(yRange(s, { style: 'bar', y_min: null, y_max: null })).toEqual([0, 21]);
    expect(yRange([[[0, 5], [1, 5]]], { style: 'line', y_min: null, y_max: null })).toEqual([4.5, 5.5]);
    expect(yRange([[[0, null]]], { style: 'line', y_min: null, y_max: null })).toEqual([-0.05, 1.05]);
  });

  it('kurve: huller afbryder linjen; tid og værdi placeres i plot-området', () => {
    const cfg = { ...defaultChart(), y_min: 0, y_max: 100 };
    const l = chartLayout(box, [[[0, 0], [50, 100], [60, null], [100, 50]]], 0, 100, cfg);
    expect(l.plot).toEqual({ x: 32, y: 19, w: 182, h: 74 });
    expect(l.lines).toEqual([['32,93 123,19', '214,56']]);
    expect(l.bars).toEqual([]);
  });

  it('søjler: én pr. tidsspand og serie, side om side; værdien FØR perioden springes over', () => {
    const cfg = { ...defaultChart(), style: 'bar' as const, bars: 2, y_min: 0, y_max: 100 };
    const l = chartLayout(box, [[[0, 99], [25, 50], [75, 100]], [[25, 10]]], 0, 100, cfg);
    expect(l.bars.map((b) => [b.series, b.x, b.h])).toEqual([[0, 41.1, 37], [0, 132.1, 74], [1, 77.5, 7.4]]);
  });

  it('tal og tider på akserne', () => {
    expect(axisNumber(1234.56)).toBe('1235');
    expect(axisNumber(23.46)).toBe('23,5');
    expect(axisNumber(0.123)).toBe('0,12');
    const t = new Date(2026, 9, 18, 7, 5).getTime() / 1000;
    expect(axisTime(t, 3600)).toBe('07:05');
    expect(axisTime(t, 7 * 86400)).toBe('18/10 07:05');
  });
});
