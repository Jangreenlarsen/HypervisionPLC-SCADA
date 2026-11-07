// Flervalg i lister med afkrydsning (v4.7.0): klik skifter ét element, Shift+klik skifter hele intervallet fra det sidst
// klikkede. Bruges af Tags (og samme regel som Symboler › Bibliotek). Ren logik — testet i multiPick.test.ts.

/** Nyt valg efter et klik på element nr. `index` (id `id`) i `ids`. `last`: indeks for det forrige klik (-1 = intet). */
export function pickInList(ids: string[], selected: string[], id: string, index: number, last: number, shift: boolean): string[] {
  const on = !selected.includes(id);
  const range = shift && last >= 0 && last < ids.length ? ids.slice(Math.min(last, index), Math.max(last, index) + 1) : [id];
  return on ? [...new Set([...selected, ...range])] : selected.filter((x) => !range.includes(x));
}
