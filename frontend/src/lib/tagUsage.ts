// Oversigt over hvad sletning af tags rammer (v3.35.0, POST /api/tags/usage) — én linje pr. sted, til bekræftelsen.

export interface TagUsage {
  tags: number; in_use: boolean; history: number; symbols: number; alarms: number; auto: string[];
  drawings: { id: string; name: string; bindings: number; symbols: number }[];
  schedules: string[]; trend_views: string[]; api_keys: string[];
}

const n = (k: number, one: string, many: string) => `${k} ${k === 1 ? one : many}`;

/** Linjer til bekræftelsen; tom liste = tagget bruges ingen steder. */
export function usageText(u: TagUsage): string[] {
  const list = (xs: string[], max = 6) => xs.slice(0, max).join(', ') + (xs.length > max ? ' …' : '');
  return [
    ...u.drawings.map((d) => `• Tegningen ${d.name}: ${[d.bindings ? n(d.bindings, 'binding', 'bindinger') : '',
      d.symbols ? n(d.symbols, 'symbolopsætning', 'symbolopsætninger') : ''].filter(Boolean).join(', ')}`),
    ...(u.schedules.length ? [`• Ugeprogrammer (slettes): ${list(u.schedules)}`] : []),
    ...(u.trend_views.length ? [`• Trendvisninger: ${list(u.trend_views)}`] : []),
    ...(u.api_keys.length ? [`• API-nøgler: ${list(u.api_keys)}`] : []),
    ...(u.auto.length ? [`• Vises automatisk (element med samme navn): ${list(u.auto)}`] : []),
    ...(u.alarms ? [`• ${n(u.alarms, 'aktiv alarm', 'aktive alarmer')} (ryddes)`] : []),
  ];
}
