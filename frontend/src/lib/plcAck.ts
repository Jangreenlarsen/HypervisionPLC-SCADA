// Kvittering af PLC-fejl på Overview (v1.9.0): en kvitteret fejl skjules som banner, til PLC'en har været i orden igen — så vises
// en NY fejl på den. Kvitteringen gælder kun denne browserfane (sessionStorage) og ændrer intet på serveren.
const KEY = 'overview.ackedPlcErrors';

export interface PlcLike { name?: string; state: string; message?: string }

/** PLC'er i fejl, delt i dem der skal vises som banner (ukvitterede) og de kvitterede. */
export function splitProblems<T extends PlcLike>(plcs: Record<string, T>, acked: ReadonlySet<string>): { open: [string, T][]; acked: [string, T][] } {
  const errors = Object.entries(plcs).filter(([, p]) => p.state === 'error');
  return { open: errors.filter(([k]) => !acked.has(k)), acked: errors.filter(([k]) => acked.has(k)) };
}

/** Fjern kvitteringen for PLC'er, der ikke (længere) er i fejl — så en ny fejl senere vises igen. */
export function pruneAcked(acked: ReadonlySet<string>, plcs: Record<string, PlcLike>): Set<string> {
  return new Set([...acked].filter((k) => plcs[k]?.state === 'error'));
}

export function loadAcked(): Set<string> {
  try {
    const raw = sessionStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(list) ? list.filter((x): x is string => typeof x === 'string') : []);
  } catch {
    return new Set();   // huskes bare ikke — ingen funktion afhænger af det
  }
}

export function saveAcked(acked: ReadonlySet<string>): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify([...acked]));
  } catch {
    // ingen lagring tilgængelig
  }
}
