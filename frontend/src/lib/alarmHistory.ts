// Alarmhistorik: filtre → query-streng, delt af listen og CSV-linket så de altid viser det samme.
export interface HistoryFilter { q: string; from: string; to: string; event: string; priority: string; system: string }

export const EMPTY_FILTER: HistoryFilter = { q: '', from: '', to: '', event: '', priority: '', system: '' };

/** Tomme filtre (og søgetekst med kun mellemrum) udelades. `limit` medtages kun hvis angivet. */
export function historyQuery(f: HistoryFilter, limit?: number): URLSearchParams {
  const p = new URLSearchParams();
  if (limit !== undefined) p.set('limit', String(limit));
  if (f.q.trim()) p.set('q', f.q.trim());
  if (f.from) p.set('from', f.from);
  if (f.to) p.set('to', f.to);
  if (f.event) p.set('event', f.event);
  if (f.priority) p.set('priority', f.priority);
  if (f.system) p.set('system', f.system);
  return p;
}

export const historyUrl = (f: HistoryFilter, limit: number): string => `/api/alarms/history?${historyQuery(f, limit)}`;
export function exportUrl(f: HistoryFilter): string {
  const qs = historyQuery(f).toString();
  return `/api/alarms/history/export${qs ? `?${qs}` : ''}`;
}

export const isFiltered = (f: HistoryFilter): boolean => historyQuery({ ...f, system: '' }).size > 0;
