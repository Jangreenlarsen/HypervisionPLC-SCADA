// "Forlad siden"-vagt (BUGS v3.7.0): en side med ugemte ændringer (Tegn, Symboler) tilmelder en vagt, og App spørger
// den, før der skiftes til en anden side via menuen, adresselinjen eller browserens tilbage-knap.
export type LeaveGuard = () => boolean | Promise<boolean>;

let guard: LeaveGuard | null = null;

/** Tilmeld en vagt (true = må forlades). Returnerer en funktion der fjerner den, hvis den stadig er den aktive. */
export function setLeaveGuard(g: LeaveGuard): () => void {
  guard = g;
  return () => { if (guard === g) guard = null; };
}

/** Må den aktuelle side forlades? En vagt der fejler, blokerer ikke (man må aldrig sidde fast). */
export async function mayLeave(): Promise<boolean> {
  if (!guard) return true;
  try {
    return await guard();
  } catch (e) {
    console.error('Forlad-siden-vagten fejlede:', e);
    return true;
  }
}
