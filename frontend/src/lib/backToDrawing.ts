// "Tilbage til tegningen" på Alarmer, Trends og Energi (v0.76.0): den sidst viste tegning i fanen (Overview gemmer den i
// sessionStorage som "overview.last"); findes den ikke (mere), går knappen til Overview.

export function backTarget(lastId: string | null | undefined, drawings: { id: string; name: string }[] | null): { href: string; label: string } {
  const d = lastId ? drawings?.find((x) => x.id === lastId) : undefined;
  if (d) return { href: `#overview/${encodeURIComponent(d.id)}`, label: `Tilbage til "${d.name}"` };
  return { href: '#overview', label: 'Tilbage til tegningen' };
}

export function lastDrawing(): string | null {
  try {
    return sessionStorage.getItem('overview.last');
  } catch {
    return null;   // blokeret lager (privat vindue): knappen går så til Overview
  }
}
