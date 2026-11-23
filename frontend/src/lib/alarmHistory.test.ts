import { describe, expect, it } from 'vitest';
import { EMPTY_FILTER, exportUrl, historyQuery, historyUrl, isFiltered } from './alarmHistory';

describe('alarmHistory', () => {
  it('udelader tomme filtre', () => {
    expect(historyQuery(EMPTY_FILTER).toString()).toBe('');
    expect(historyQuery({ ...EMPTY_FILTER, q: '   ' }).toString()).toBe('');
    expect(historyUrl(EMPTY_FILTER, 500)).toBe('/api/alarms/history?limit=500');
    expect(exportUrl(EMPTY_FILTER)).toBe('/api/alarms/history/export');
  });

  it('bygger alle filtre og trimmer søgningen', () => {
    const f = { q: ' pumpe ', from: '2026-11-01', to: '2026-11-02', event: 'raise', priority: 'high', system: 'vand' };
    const p = historyQuery(f, 300);
    expect(Object.fromEntries(p)).toEqual({ limit: '300', q: 'pumpe', from: '2026-11-01', to: '2026-11-02', event: 'raise', priority: 'high', system: 'vand' });
    expect(exportUrl(f)).not.toContain('limit');
    expect(exportUrl(f)).toContain('system=vand');
  });

  it('koder specialtegn og medtager system "-"', () => {
    expect(historyQuery({ ...EMPTY_FILTER, q: 'æ & ø', system: '-' }).toString()).toBe('q=%C3%A6+%26+%C3%B8&system=-');
  });

  it('isFiltered ignorerer system', () => {
    expect(isFiltered({ ...EMPTY_FILTER, system: 'x' })).toBe(false);
    expect(isFiltered({ ...EMPTY_FILTER, priority: 'low' })).toBe(true);
  });
});
