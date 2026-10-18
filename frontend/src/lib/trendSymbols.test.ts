import { describe, expect, it } from 'vitest';
import { byDrawing, keyFromRoute, symbolKey, symbolSeries, type TrendSymbol } from './trendSymbols';

const sym = (name: string, tags: string[], drawing_name = 'Kedelrum'): TrendSymbol =>
  ({ drawing: drawing_name.toLowerCase(), drawing_name, element: name.replace(/\s/g, '_'), name, tags });

describe('Trends ud fra symbolerne (v0.80.0)', () => {
  it('rute ↔ nøgle', () => {
    expect(symbolKey({ drawing: 'kedelrum', element: 'svg_12' })).toBe('kedelrum/svg_12');
    expect(keyFromRoute('trends/kedelrum/svg_12')).toBe('kedelrum/svg_12');
    expect(keyFromRoute('trends')).toBeNull();
    expect(keyFromRoute('trends/kedelrum')).toBeNull();
    expect(keyFromRoute('overview/kedelrum/svg_12')).toBeNull();
  });

  it('kun tags med historik vises; resten er "mangler"; ukendte springes over; højst max', () => {
    const tags = [
      { name: 'Tryk', trend: true, samples: 0 },
      { name: 'Drift', trend: false, samples: 12 },   // slået fra, men har gemte værdier
      { name: 'Start', trend: false, samples: 0 },
      { name: 'Temp', trend: true, samples: 5 },
    ];
    expect(symbolSeries(sym('Pumpe 1', ['Start', 'Tryk', 'Væk', 'Drift', 'Temp']), tags, 8))
      .toEqual({ show: ['Tryk', 'Drift', 'Temp'], missing: ['Start'], over: [] });
    expect(symbolSeries(sym('Pumpe 1', ['Tryk', 'Drift', 'Temp']), tags, 2))
      .toEqual({ show: ['Tryk', 'Drift'], missing: [], over: ['Temp'] });
  });

  it('grupperet pr. tegning, sorteret (Pumpe 2 før Pumpe 10)', () => {
    const g = byDrawing([sym('Pumpe 10', ['a']), sym('Ventil', ['a'], 'Anlæg'), sym('Pumpe 2', ['a'])]);
    expect(g.map(([d, l]) => [d, l.map((s) => s.name)])).toEqual([['Anlæg', ['Ventil']], ['Kedelrum', ['Pumpe 2', 'Pumpe 10']]]);
  });
});
