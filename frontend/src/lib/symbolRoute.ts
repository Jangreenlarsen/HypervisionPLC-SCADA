// Genvej mellem Tegn og symbol-editoren (v3.7.0): #symbols/<tegning>/<symboltype>. Tegningen bruges til "Tilbage til
// tegningen", symboltypen til at åbne editoren på det valgte symbol. Begge kan mangle.
// v6.11.0 (symbolet i centrum): et fjerde led vælger fanen i symbolets panel (#symbols/<tegning>/<type>/punkter|veje), og
// tegningen "-" betyder "ikke åbnet fra Tegn" (så siden kan skrive det valgte symbol i adressen uden en Tilbage-knap).

export type SymbolTab = 'punkter' | 'veje';
export interface SymbolRoute { drawing: string | null; type: string | null }

export function symbolsHref(drawing: string | null | undefined, type: string | null | undefined, tab?: SymbolTab | null): string {
  const d = drawing ? encodeURIComponent(drawing) : '';
  const t = type ? encodeURIComponent(type) : '';
  if (!d && !t) return '#symbols/ny';
  return `#symbols/${d || 'ny'}${t ? `/${t}` : ''}${t && tab ? `/${tab}` : ''}`;
}

/** Adressen for det valgte symbol på siden selv: tegningen beholdes (åbnet fra Tegn), ellers "-". */
export function panelHref(drawing: string | null, fromDraw: boolean, type: string, tab: SymbolTab): string {
  const d = drawing ? encodeURIComponent(drawing) : fromDraw ? 'ny' : '-';
  return `#symbols/${d}/${encodeURIComponent(type)}/${tab}`;
}

/** route = "symbols", "symbols/<tegning>", "symbols/<tegning>/<type>" eller "…/<type>/<fane>"; "ny" = en ny, ikke gemt
 *  tegning; "-" = ikke åbnet fra Tegn. */
export function parseSymbolRoute(route: string): SymbolRoute & { fromDraw: boolean; tab: SymbolTab | null } {
  const [page, d, t, f] = route.split('/');
  if (page !== 'symbols' || d === undefined) return { drawing: null, type: null, fromDraw: false, tab: null };
  const dec = (v: string | undefined) => { try { return v ? decodeURIComponent(v) : null; } catch { return null; } };
  const drawing = dec(d);
  const tab = f === 'punkter' || f === 'veje' ? f : null;
  if (drawing === '-' || drawing === 'organiser') return { drawing: null, type: dec(t), fromDraw: false, tab };   // ("organiser" = Organisér bibliotek)
  return { drawing: drawing === 'ny' ? null : drawing, type: dec(t), fromDraw: true, tab };
}

export const drawHref = (drawing: string | null): string => (drawing ? `#draw/${encodeURIComponent(drawing)}` : '#draw');
