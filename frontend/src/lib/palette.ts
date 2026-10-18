// "Mine symboler" i Tegn (v0.78.0): brugerens egen sektion øverst i symbolbiblioteket (gemt pr. bruger på serveren).

/** Læg symbolet i Mine symboler (bagerst) — eller tag det ud, hvis det er der. */
export function toggleFavorite(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

/** Flyt et symbol én plads frem (-1) eller tilbage (1); ved kanten sker intet. */
export function moveFavorite(list: string[], id: string, dir: -1 | 1): string[] {
  const i = list.indexOf(id), j = i + dir;
  if (i < 0 || j < 0 || j >= list.length) return list;
  const out = [...list];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

/** Kun symboler der findes i biblioteket (et symbol kan være fjernet i en ny version), i brugerens rækkefølge, uden dubletter. */
export function knownFavorites(list: string[], known: Set<string>): string[] {
  return list.filter((id, i) => known.has(id) && list.indexOf(id) === i);
}
