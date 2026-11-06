import { describe, expect, it } from 'vitest';
import { usageText, type TagUsage } from './tagUsage';

const none: TagUsage = { tags: 1, in_use: false, history: 0, symbols: 0, alarms: 0, auto: [], drawings: [], schedules: [], trend_views: [], api_keys: [] };

describe('usageText', () => {
  it('ubrugt tag → ingen linjer', () => {
    expect(usageText(none)).toEqual([]);
  });

  it('en linje pr. sted, ental/flertal og afkortning', () => {
    const lines = usageText({
      ...none, in_use: true, alarms: 1, auto: ['Temp (Anlæg)'],
      drawings: [{ id: 'd1', name: 'Anlæg', bindings: 1, symbols: 2 }, { id: 'd2', name: 'Tank', bindings: 3, symbols: 0 }],
      schedules: ['Nat'], trend_views: ['a', 'b', 'c', 'd', 'e', 'f', 'g'], api_keys: ['Måler'],
    });
    expect(lines).toEqual([
      '• Tegningen Anlæg: 1 binding, 2 symbolopsætninger',
      '• Tegningen Tank: 3 bindinger',
      '• Ugeprogrammer (slettes): Nat',
      '• Trendvisninger: a, b, c, d, e, f …',
      '• API-nøgler: Måler',
      '• Vises automatisk (element med samme navn): Temp (Anlæg)',
      '• 1 aktiv alarm (ryddes)',
    ]);
  });
});
