// Elementlisten i Bindinger som træ: et symbol (eller en gruppe) med flere elementer vises med delene
// indrykket under sig. Rene funktioner — testet i elementTree.test.ts.

export interface ElementInfo {
  id: string;
  type: string;
  label: string | null;        // inkscape:label
  name: string | null;         // data-hv-name — symbolets navn (sat i Tegn)
  short: string | null;        // en dels korte navn under et symbol ("tekst" for "vippekontakt_tekst")
  desc: string | null;         // data-hv-desc — forklaring (sat i Tegn)
  parent: string | null;       // nærmeste forfader med id
  depth: number;
  children: number;            // antal direkte børn med id
  symbol: boolean;             // betjeningssymbol eller element med eget navn
  spec: boolean;               // betjeningssymbol med færdige bindinger (data-hv-auto)
  writes: boolean;             // symbolets klik-handling skriver til PLC'en (tagget skal være skrivbart)
}

export interface Row extends ElementInfo {
  context: boolean;            // vises kun fordi et barn matcher søgningen
}

const text = (v: string | null | undefined) => (v && v.trim() ? v.trim() : null);

function specWrites(raw: string | null): boolean {
  try {
    const items = JSON.parse(raw ?? 'null');
    return (Array.isArray(items) ? items : [items]).some((i) => ['click:write', 'click:toggle', 'click:pulse', 'click:select'].includes(i?.anim));
  } catch {
    return false; // ugyldig beskrivelse — serveren afviser/ignorerer den
  }
}

/** Alle elementer med id, i dokumentets rækkefølge, med forælder og dybde. */
export function buildElements(root: Element): ElementInfo[] {
  const out: ElementInfo[] = [];
  const index = new Map<Element, ElementInfo>();
  for (const el of Array.from(root.querySelectorAll('[id]'))) {
    let anc = el.parentElement;
    while (anc && anc !== root && !index.has(anc)) anc = anc.parentElement;
    const parent = anc && anc !== root ? index.get(anc)! : null;
    const name = text(el.getAttribute('data-hv-name'));
    // Symbolernes dele hedder "<symbol>_<del>" (Tegn giver dem symbolets id som præfiks) — vis blot delen
    const short = parent?.symbol && el.id.includes('_') && !el.id.endsWith('_') ? el.id.slice(el.id.lastIndexOf('_') + 1) : null;
    const info: ElementInfo = {
      id: el.id, type: el.tagName.toLowerCase(), label: text(el.getAttribute('inkscape:label')),
      name, short, desc: text(el.getAttribute('data-hv-desc')),
      parent: parent?.id ?? null, depth: parent ? parent.depth + 1 : 0, children: 0,
      symbol: name !== null || el.hasAttribute('data-hv-auto'),
      spec: el.hasAttribute('data-hv-auto'),
      writes: specWrites(el.getAttribute('data-hv-auto')),
    };
    if (parent) parent.children++;
    index.set(el, info);
    out.push(info);
  }
  return out;
}

/** Det der vises som elementets navn: symbolets navn, inkscape-label, delens korte navn, ellers id. */
export const displayName = (e: Pick<ElementInfo, 'id' | 'name' | 'label'> & { short?: string | null }) =>
  e.name ?? e.label ?? e.short ?? e.id;

/** Er id'et en sekundær oplysning ved siden af navnet (fordi navnet ikke selv er id'et)? */
export const showsId = (e: Pick<ElementInfo, 'id' | 'name' | 'label'> & { short?: string | null }) => displayName(e) !== e.id;

/** Standard: rene grupper er foldet ud (ellers skjuler de hele tegningen), symboler er foldet sammen. */
export function defaultExpanded(elements: ElementInfo[]): Set<string> {
  return new Set(elements.filter((e) => e.children > 0 && !e.symbol).map((e) => e.id));
}

/** Forfædre (nærmeste først) til et element. */
export function ancestorsOf(elements: ElementInfo[], id: string): string[] {
  const byId = new Map(elements.map((e) => [e.id, e]));
  const out: string[] = [];
  for (let p = byId.get(id)?.parent; p; p = byId.get(p)?.parent ?? null) out.push(p);
  return out;
}

/**
 * Rækkerne der vises. Uden søgning: kun elementer hvis forfædre alle er foldet ud. Med søgning: alle der
 * matcher (id, label, navn, forklaring) samt deres forfædre, så man ser hvor de hører til.
 */
export function visibleRows(elements: ElementInfo[], expanded: Set<string>, filter: string): Row[] {
  const q = filter.trim().toLowerCase();
  if (!q) {
    const byId = new Map(elements.map((e) => [e.id, e]));
    return elements
      .filter((e) => {
        for (let p = e.parent; p; p = byId.get(p)?.parent ?? null) if (!expanded.has(p)) return false;
        return true;
      })
      .map((e) => ({ ...e, context: false }));
  }
  const matches = new Set(elements.filter((e) =>
    [e.id, e.label, e.name, e.desc].some((v) => v?.toLowerCase().includes(q))).map((e) => e.id));
  const keep = new Set(matches);
  for (const id of matches) for (const a of ancestorsOf(elements, id)) keep.add(a);
  return elements.filter((e) => keep.has(e.id)).map((e) => ({ ...e, context: !matches.has(e.id) }));
}

/** Antal elementer under et element (alle niveauer) — vises ved et sammenfoldet symbol. */
export function descendantCount(elements: ElementInfo[], id: string): number {
  const kids = new Map<string, string[]>();
  for (const e of elements) if (e.parent) kids.set(e.parent, [...(kids.get(e.parent) ?? []), e.id]);
  const walk = (i: string): number => (kids.get(i) ?? []).reduce((n, k) => n + 1 + walk(k), 0);
  return walk(id);
}

/**
 * Det relevante under Bindinger: navngivne elementer (symboler), elementer med bindinger og alt under et symbol
 * (dets dele), plus forfædre så strukturen kan ses. `direct` er dem der er relevante i sig selv — resten er kun
 * med for at vise hvor de hører til. Børnetal tælles om, så et sammenfoldet træ ikke viser tomme pile.
 */
export function relevantElements(elements: ElementInfo[], bound: Set<string>): { elements: ElementInfo[]; direct: Set<string> } {
  const byId = new Map(elements.map((e) => [e.id, e]));
  const direct = new Set<string>();
  for (const e of elements) {
    let inSymbol = false;
    for (let p = e.parent; p; p = byId.get(p)?.parent ?? null) if (byId.get(p)?.symbol) inSymbol = true;
    if (e.symbol || bound.has(e.id) || inSymbol) direct.add(e.id);
  }
  const keep = new Set(direct);
  for (const id of direct) for (const a of ancestorsOf(elements, id)) keep.add(a);
  const kept = elements.filter((e) => keep.has(e.id));
  const kids = new Map<string, number>();
  for (const e of kept) if (e.parent) kids.set(e.parent, (kids.get(e.parent) ?? 0) + 1);
  return { elements: kept.map((e) => ({ ...e, children: kids.get(e.id) ?? 0 })), direct };
}
