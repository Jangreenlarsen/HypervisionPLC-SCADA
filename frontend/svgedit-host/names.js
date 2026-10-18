// Navne til symboler i Tegn (v0.62.0): rene funktioner — testes i src/lib/names.test.ts.

export const MAX_NAME = 60;   // samme grænse som feltet Navn (data-hv-name)

/**
 * Et ledigt navn til en kopi (Ctrl+V / Ctrl+D) af et symbol med navnet `name`: et afsluttende løbenummer skiftes til
 * det første ledige — "Bøjning 90° 6" → "Bøjning 90° 7" (eller næste ledige), "rør_2" → "rør_3"; uden nummer: "Pumpe" → "Pumpe 2".
 * `used`: navne der findes i forvejen (uden kopien selv).
 */
export function nextFreeName(name, used) {
  const taken = new Set(used);
  const clean = String(name ?? '').replace(/\s+/g, ' ').trim();
  if (!clean) return '';
  if (!taken.has(clean)) return clean;
  const m = /^(.*?)([ _])(\d+)$/.exec(clean);
  const stem = m ? m[1] : clean, sep = m ? m[2] : ' ';
  for (let n = m ? Number(m[3]) + 1 : 2; ; n++) {
    const suffix = `${sep}${n}`;
    const cand = stem.slice(0, MAX_NAME - suffix.length).trimEnd() + suffix;
    if (!taken.has(cand)) return cand;
  }
}

/**
 * `count` ledige navne af formen "<base>_<n>" (n = 1, 2, …; numre der allerede er brugt springes over).
 * Basen forkortes, så navnet med løbenummer holder sig inden for MAX_NAME tegn. `used`: navne der findes i forvejen.
 */
export function numberedNames(base, count, used) {
  const clean = String(base ?? '').replace(/\s+/g, ' ').trim() || 'Symbol';
  const taken = new Set(used);
  const out = [];
  for (let n = 1; out.length < count; n++) {
    const suffix = `_${n}`;
    const name = clean.slice(0, MAX_NAME - suffix.length).trimEnd() + suffix;
    if (taken.has(name)) continue;
    taken.add(name);
    out.push(name);
  }
  return out;
}

/**
 * Dublet-navne (v0.89.0): for navnene i tegningens rækkefølge — det første af hvert navn beholdes, de næste får det
 * næste ledige løbenummer ("Bøjning 90° 6" ×3 → 6, 7, 8 eller næste ledige). → nyt navn pr. plads, null = uændret.
 */
export function uniqueRenames(names) {
  const used = new Set(names);
  const seen = new Set();
  return names.map((name) => {
    if (!seen.has(name)) { seen.add(name); return null; }
    const next = nextFreeName(name, used);
    used.add(next);
    return next;
  });
}

/** Navne der bruges mere end én gang: [{ name, count }] i rækkefølgen de først optræder. */
export function duplicateNames(names) {
  const counts = new Map();
  for (const n of names) counts.set(n, (counts.get(n) ?? 0) + 1);
  return [...counts].filter(([, k]) => k > 1).map(([name, count]) => ({ name, count }));
}
