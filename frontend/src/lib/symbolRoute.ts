// Genvej mellem Tegn og symbol-editoren (v3.7.0): #symbols/<tegning>/<symboltype>. Tegningen bruges til "Tilbage til
// tegningen", symboltypen til at åbne editoren på det valgte symbol. Begge kan mangle.

export interface SymbolRoute { drawing: string | null; type: string | null }

export function symbolsHref(drawing: string | null | undefined, type: string | null | undefined): string {
  const d = drawing ? encodeURIComponent(drawing) : '';
  const t = type ? encodeURIComponent(type) : '';
  if (!d && !t) return '#symbols/ny';
  return `#symbols/${d || 'ny'}${t ? `/${t}` : ''}`;
}

/** route = "symbols", "symbols/<tegning>" eller "symbols/<tegning>/<type>"; "ny" = en ny, ikke gemt tegning. */
export function parseSymbolRoute(route: string): SymbolRoute & { fromDraw: boolean } {
  const [page, d, t] = route.split('/');
  if (page !== 'symbols' || d === undefined) return { drawing: null, type: null, fromDraw: false };
  const dec = (v: string | undefined) => { try { return v ? decodeURIComponent(v) : null; } catch { return null; } };
  const drawing = dec(d);
  return { drawing: drawing === 'ny' ? null : drawing, type: dec(t), fromDraw: true };
}

export const drawHref = (drawing: string | null): string => (drawing ? `#draw/${encodeURIComponent(drawing)}` : '#draw');
