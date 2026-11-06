// Navneforslag til et element uden navn, når det skal sættes op med guiden (v3.36.0): "Rør 1", "Pumpe 2", "Linje 1" …

const TAG_BASE: Record<string, string> = {
  path: 'Linje', line: 'Linje', polyline: 'Linje', polygon: 'Figur', rect: 'Felt', circle: 'Cirkel', ellipse: 'Cirkel',
  text: 'Tekst', g: 'Gruppe', image: 'Billede', use: 'Figur',
};

/** Første ledige "<grundnavn> N" — rør hedder "Rør", et symbol sit eget navn, ellers efter elementtypen. */
export function suggestName(el: { tag: string; pipe?: boolean; label?: string }, used: Iterable<string>): string {
  const base = el.pipe ? 'Rør' : el.label?.trim() || TAG_BASE[el.tag] || 'Element';
  const taken = new Set(used);
  for (let n = 1; ; n++) if (!taken.has(`${base} ${n}`)) return `${base} ${n}`;
}
