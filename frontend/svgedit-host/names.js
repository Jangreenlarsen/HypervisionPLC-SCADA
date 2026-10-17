// Navne til symboler i Tegn (v0.62.0): rene funktioner — testes i src/lib/names.test.ts.

export const MAX_NAME = 60;   // samme grænse som feltet Navn (data-hv-name)

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
