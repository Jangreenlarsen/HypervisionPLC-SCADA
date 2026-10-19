import { describe, expect, it } from 'vitest';
import {
  axisNumber, axisTime, chartFont, chartLayout, chartPoints, defaultChart, legendOf, niceTicks, refreshSeconds, textWidth,
  timeTicks, wrapLegend, yRange, type Point,
} from './chartGraphic';

const box = { x: 0, y: 0, w: 240, h: 130 };

describe('trendgraf i tegningen (v0.91.0)', () => {
  it('Y-aksen: valgt, fra data, søjler med 0, fladt forløb får luft', () => {
    const s: Point[][] = [[[0, 10], [1, 20]]];
    expect(yRange(s, { style: 'line', y_min: 0, y_max: 100 })).toEqual([0, 100]);
    expect(yRange(s, { style: 'line', y_min: null, y_max: null })).toEqual([9.5, 20.5]);
    expect(yRange(s, { style: 'bar', y_min: null, y_max: null })).toEqual([0, 21]);
    expect(yRange([[[0, 5], [1, 5]]], { style: 'line', y_min: null, y_max: null })).toEqual([4.5, 5.5]);
  });

  it('kurve: huller afbryder linjen; første og sidste punkt ved plottets kanter', () => {
    const cfg = { ...defaultChart(), y_min: 0, y_max: 100 };
    const l = chartLayout(box, [[[0, 0], [50, 100], [60, null], [100, 50]]], 0, 100, cfg);
    const p = l.plot;
    expect(l.lines[0]).toHaveLength(2);
    const [first, last] = [l.lines[0][0].split(' ')[0], l.lines[0][1]];
    expect(first).toBe(`${p.x},${Math.round((p.y + p.h) * 10) / 10}`);                     // 0 nederst til venstre
    expect(Number(last.split(',')[0])).toBeCloseTo(p.x + p.w, 0);                            // nu yderst til højre
    expect(Number(last.split(',')[1])).toBeCloseTo(p.y + p.h / 2, 0);                        // 50 midt i
  });

  it('søjler: én pr. tidsspand og serie side om side; værdien FØR perioden springes over', () => {
    const cfg = { ...defaultChart(), style: 'bar' as const, bars: 2, y_min: 0, y_max: 100 };
    const l = chartLayout(box, [[[0, 99], [25, 50], [75, 100]], [[25, 10]]], 0, 100, cfg);
    expect(l.bars.map((b) => b.series)).toEqual([0, 0, 1]);
    const [a, b, c] = l.bars;
    expect(b.x).toBeGreaterThan(a.x + a.w);          // anden periode til højre for første
    expect(c.x).toBeCloseTo(a.x + a.w, 0);           // serie 2 lige ved siden af serie 1
    expect(b.h).toBeCloseTo(2 * a.h, 0);             // 100 er dobbelt så høj som 50
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

describe('opløsning, diagramlinjer og tekst på to linjer (v0.95.0)', () => {
  it('skriften vokser langsommere end grafen; en bredere graf henter flere punkter', () => {
    expect(chartFont(130)).toBe(10.6);
    expect(chartFont(520)).toBe(24.2);
    expect(chartFont(2000)).toBe(28);                     // loft
    expect(chartFont(10)).toBe(7);                        // gulv
    expect(chartPoints({ style: 'line', bars: 24 }, 200)).toBe(100);
    expect(chartPoints({ style: 'line', bars: 24 }, 1600)).toBe(600);
    expect(chartPoints({ style: 'bar', bars: 24 }, 1600)).toBe(24);
    expect(refreshSeconds({ style: 'line', bars: 24, range_s: 3600 }, 400)).toBe(18);
  });

  it('runde værdier på Y-aksen', () => {
    expect(niceTicks(0, 100, 5)).toEqual([0, 25, 50, 75, 100]);
    expect(niceTicks(9.5, 20.5, 5)).toEqual([10, 15, 20]);
    expect(niceTicks(9.5, 20.5, 8)).toEqual([10, 12, 14, 16, 18, 20]);
    expect(niceTicks(-2.3, 49.1, 4)).toEqual([0, 20, 40]);
    expect(niceTicks(5, 5)).toEqual([5]);
  });

  it('runde tider i lokal tid', () => {
    const start = Date.UTC(2026, 9, 19, 10, 7) / 1000;   // 10:07 UTC
    expect(timeTicks(start, start + 3600, 5, 0).map((t) => new Date(t * 1000).getUTCMinutes())).toEqual([15, 30, 45, 0]);
    expect(timeTicks(start, start + 3600, 5, 7200).map((t) => (t + 7200) % 900)).toEqual([0, 0, 0, 0]);   // runde i lokal tid
    expect(timeTicks(start, start + 86400, 6, 0).length).toBeLessThanOrEqual(6);
  });

  it('forklaringen på højst to linjer inden for bredden — ellers mindre skrift', () => {
    const items = ['Fremløbstemperatur 56,5 °C', 'Returtemperatur 41,2 °C', 'Tryk 2,3 bar'];
    expect(wrapLegend(items, 10, 1000)).toEqual({ font: 10, lines: [[0, 1, 2]] });          // alt på én linje
    const two = wrapLegend(items, 10, 240);
    expect(two.lines).toHaveLength(2);
    for (const line of two.lines) {
      const w = line.reduce((sum, i, k) => sum + textWidth(items[i], two.font) + (k ? two.font * 0.9 : 0), 0);
      expect(w).toBeLessThanOrEqual(240);
    }
    const tight = wrapLegend(items, 10, 100);
    expect(tight.font).toBe(6);                                                             // skriften skrumper til mindst
    for (const line of tight.lines) {                                                       // og hver linje holder sig inden for
      expect(line.reduce((sum, i, k) => sum + textWidth(items[i], 6) + (k ? 6 * 0.9 : 0), 0)).toBeLessThanOrEqual(100);
    }
  });

  it('forklaringen over/under/skjult — også for grafer gemt før — og plads til to linjer', () => {
    const base = { ...defaultChart(), y_min: 0, y_max: 100 };
    const { legend: _l, font_scale: _f, bold: _b, values: _v, ...old } = base;
    const top = chartLayout(box, [], 0, 100, old as typeof base, ['Tryk 2,3 bar']);
    const bottom = chartLayout(box, [], 0, 100, { ...base, legend: 'bottom' }, ['Tryk 2,3 bar']);
    const none = chartLayout(box, [], 0, 100, { ...base, legend: 'none' }, ['Tryk 2,3 bar']);
    expect(top.legendLines[0].y).toBeLessThan(top.plot.y);
    expect(bottom.legendLines[0].y).toBeGreaterThan(bottom.plot.y + bottom.plot.h);
    expect(none.legendLines).toEqual([]);
    expect(none.plot.h).toBeGreaterThan(top.plot.h);
    const twoLines = chartLayout(box, [], 0, 100, base, ['Fremløbstemperatur 56,5 °C', 'Returtemperatur 41,2 °C', 'Tryk 2,3 bar']);
    expect(twoLines.legendLines).toHaveLength(2);
    expect(twoLines.plot.y).toBeGreaterThan(top.plot.y);                                     // plottet rykker ned
    expect(legendOf({})).toEqual({ place: 'top', scale: 1, bold: true, values: true });
  });

  it('diagramlinjer inden for plottet', () => {
    const l = chartLayout({ x: 0, y: 0, w: 480, h: 260 }, [], 1000, 1000 + 3600, { ...defaultChart(), y_min: 0, y_max: 100 });
    expect(l.yTicks.map((t) => t.label)).toEqual(['0', '25', '50', '75', '100']);
    for (const t of l.yTicks) expect(t.y).toBeGreaterThanOrEqual(l.plot.y - 0.1);
    expect(l.xTicks.length).toBeGreaterThanOrEqual(2);
    for (const t of l.xTicks) expect(t.x).toBeGreaterThan(l.plot.x);
  });
});
