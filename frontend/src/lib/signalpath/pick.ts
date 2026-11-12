// Vælg start/slut for en signalvej ved klik i tegningen (v4.5.0; flyttet hertil i v6.0.0, hvor vejens betingelser er fjernet).

/** Det element, der netop er valgt i tegningen, som start eller slut — eller en forklaring på, hvorfor det ikke kan bruges. */
export function pickNext(which: 'start' | 'end', selected: string[], allowed: Set<string>, start: string): { id?: string; error?: string } {
  const id = selected.find((s) => allowed.has(s));
  if (!id) return { error: 'Det valgte er et rør, en tekst eller en visning — klik på et anlægssymbol (fx kedel, pumpe, radiator)' };
  if (which === 'end' && id === start) return { error: 'Det er startsymbolet — klik på et andet symbol som slut' };
  return { id };
}
