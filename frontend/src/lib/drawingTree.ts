// Tegningshierarki (ISA-101: overblik → område → detalje, v6.22.0). Ren logik uden DOM/netværk.
// Reglerne er de samme som i backend (services/drawing_tree.py), som er den der håndhæver dem: ikke sig selv, ingen cirkel,
// højst MAX_DEPTH niveauer (rod = niveau 1, også for hele undertræet under den flyttede tegning).
// Alle gennemløb er sikret mod cirkulære data: et medlem af en cirkel behandles som rod i stedet for at hænge.

export const MAX_DEPTH = 4;

export interface TreeItem { id: string; name: string; parent_id?: string | null }
export interface TreeNode<T extends TreeItem> { item: T; children: TreeNode<T>[] }
export interface FlatItem<T extends TreeItem> { item: T; indent: number }

const byName = (a: TreeItem, b: TreeItem): number => a.name.localeCompare(b.name, 'da') || a.id.localeCompare(b.id);

/** Effektiv forælder pr. tegning: kun en forælder der findes i listen (ukendt/utilgængelig = ingen), ikke sig selv, og
 *  medlemmer af en cirkel får ingen (så alle gennemløb ender). */
function parentMap<T extends TreeItem>(list: readonly T[]): Map<string, string | null> {
  const ids = new Set(list.map((d) => d.id));
  const raw = new Map<string, string | null>();
  for (const d of list) {
    const p = typeof d.parent_id === 'string' ? d.parent_id.trim() : '';
    raw.set(d.id, p && p !== d.id && ids.has(p) ? p : null);
  }
  const eff = new Map<string, string | null>();
  for (const d of list) {
    let cur = raw.get(d.id) ?? null;
    let steps = 0;
    let looped = false;
    while (cur !== null && steps <= list.length) {
      if (cur === d.id) { looped = true; break; }
      cur = raw.get(cur) ?? null;
      steps += 1;
    }
    // (hænger tegningen blot under en cirkel uden selv at være med i den, beholder den sin forælder: cirklens medlemmer er rødder)
    eff.set(d.id, looped ? null : raw.get(d.id) ?? null);
  }
  return eff;
}

function kidsMap<T extends TreeItem>(list: readonly T[]): Map<string | null, T[]> {
  const eff = parentMap(list);
  const kids = new Map<string | null, T[]>();
  for (const d of list) {
    const p = eff.get(d.id) ?? null;
    const arr = kids.get(p);
    if (arr) arr.push(d); else kids.set(p, [d]);
  }
  for (const arr of kids.values()) arr.sort(byName);
  return kids;
}

/** Hele hierarkiet som træ (rødder og børn sorteret efter navn). Tegninger med ukendt forælder bliver rødder. */
export function buildTree<T extends TreeItem>(list: readonly T[]): TreeNode<T>[] {
  const kids = kidsMap(list);
  const make = (d: T): TreeNode<T> => ({ item: d, children: (kids.get(d.id) ?? []).map(make) });
  return (kids.get(null) ?? []).map(make);
}

/** Direkte undertegninger (sorteret efter navn). */
export function childrenOf<T extends TreeItem>(list: readonly T[], id: string): T[] {
  return kidsMap(list).get(id) ?? [];
}

/** Alle efterkommere (børn, børnebørn …) — uden tegningen selv. */
export function descendantsOf<T extends TreeItem>(list: readonly T[], id: string): T[] {
  const kids = kidsMap(list);
  const out: T[] = [];
  const seen = new Set<string>([id]);
  const stack = [...(kids.get(id) ?? [])];
  while (stack.length) {
    const d = stack.shift() as T;
    if (seen.has(d.id)) continue;
    seen.add(d.id);
    out.push(d);
    stack.push(...(kids.get(d.id) ?? []));
  }
  return out;
}

/** Stien fra roden til tegningen (begge med). Ukendt tegning = []. En ukendt/utilgængelig forælder afkorter stien: den
 *  starter ved det øverste led man kender. */
export function breadcrumb<T extends TreeItem>(list: readonly T[], id: string | null | undefined): T[] {
  if (!id) return [];
  const byId = new Map(list.map((d) => [d.id, d] as const));
  const eff = parentMap(list);
  let cur = byId.get(id);
  const out: T[] = [];
  while (cur && out.length <= list.length) {
    out.unshift(cur);
    const p = eff.get(cur.id) ?? null;
    cur = p ? byId.get(p) : undefined;
  }
  return out;
}

/** Niveau: rod = 1. Ukendt tegning = 0. */
export function depthOf<T extends TreeItem>(list: readonly T[], id: string): number {
  return breadcrumb(list, id).length;
}

/** Antal niveauer i undertræet med tegningen som rod (uden børn = 1; ukendt = 0). */
export function heightOf<T extends TreeItem>(list: readonly T[], id: string): number {
  if (!list.some((d) => d.id === id)) return 0;
  const kids = kidsMap(list);
  let level: T[] = kids.get(id) ?? [];
  const seen = new Set<string>([id]);
  let h = 1;
  while (level.length) {
    h += 1;
    const next: T[] = [];
    for (const d of level) {
      if (seen.has(d.id)) continue;
      seen.add(d.id);
      next.push(...(kids.get(d.id) ?? []));
    }
    level = next;
  }
  return h;
}

/** Hvorfor `parentId` ikke må være forælder til `id` (dansk tekst) — eller null hvis det er tilladt. null/'' = ingen forælder. */
export function parentProblem<T extends TreeItem>(list: readonly T[], id: string, parentId: string | null | undefined): string | null {
  const p = (parentId ?? '').trim();
  if (!p) return null;
  const me = list.find((d) => d.id === id);
  if (!me) return `Tegningen '${id}' findes ikke`;
  if (p === id) return `Tegningen '${me.name}' kan ikke være sin egen overordnede tegning`;
  const parent = list.find((d) => d.id === p);
  if (!parent) return `Den overordnede tegning '${p}' findes ikke`;
  if (descendantsOf(list, id).some((d) => d.id === p)) return `'${parent.name}' ligger under '${me.name}' — det ville give en cirkel i hierarkiet`;
  const total = depthOf(list, p) + heightOf(list, id);
  if (total > MAX_DEPTH) return `Hierarkiet må højst have ${MAX_DEPTH} niveauer — '${me.name}' (med undertegninger) under '${parent.name}' ville give ${total}`;
  return null;
}

export function canSetParent<T extends TreeItem>(list: readonly T[], id: string, parentId: string | null | undefined): boolean {
  return parentProblem(list, id, parentId) === null;
}

/** Tegningerne `id` må have som overordnet (uden sig selv, efterkommere og valg der giver for stor dybde), i hierarki-rækkefølge. */
export function allowedParents<T extends TreeItem>(list: readonly T[], id: string): FlatItem<T>[] {
  return flatOrder(list).filter((f) => f.item.id !== id && canSetParent(list, id, f.item.id));
}

/** Tilladte forældre for ALLE tegninger på én gang (id → valg i hierarki-rækkefølge) — samme resultat som `allowedParents`
 *  pr. tegning, men beregnet i ét gennemløb: dybde fra indrykningen, højde og undertræ-størrelse i én omvendt præordens-
 *  runde, og "ligger under mig" som et interval i præordens-rækkefølgen (O(n²) i alt i stedet for O(n³ log n)). */
export function allowedParentsMap<T extends TreeItem>(list: readonly T[]): Map<string, FlatItem<T>[]> {
  const flat = flatOrder(list);
  const eff = parentMap(list);
  const index = new Map<string, number>();
  flat.forEach((f, i) => index.set(f.item.id, i));
  const size: number[] = flat.map(() => 1);
  const height: number[] = flat.map(() => 1);
  for (let i = flat.length - 1; i >= 0; i--) {          // børn har højere indeks end forælderen i præorden
    const p = eff.get(flat[i].item.id);
    const pi = p ? index.get(p) : undefined;
    if (pi === undefined) continue;
    size[pi] += size[i];
    height[pi] = Math.max(height[pi], height[i] + 1);
  }
  const out = new Map<string, FlatItem<T>[]>();
  flat.forEach((me, a) => {
    out.set(me.item.id, flat.filter((c, j) => j !== a && !(j > a && j < a + size[a]) && c.indent + 1 + height[a] <= MAX_DEPTH));
  });
  return out;
}

/** Alle tegninger i hierarki-rækkefølge (forælder før børn, dybde først) med indrykning (rod = 0) — til indrykket liste/select. */
export function flatOrder<T extends TreeItem>(list: readonly T[]): FlatItem<T>[] {
  const out: FlatItem<T>[] = [];
  const walk = (nodes: TreeNode<T>[], indent: number): void => {
    for (const n of nodes) {
      out.push({ item: n.item, indent });
      walk(n.children, indent + 1);
    }
  };
  walk(buildTree(list), 0);
  return out;
}

/** Navn med indrykning til en select: '— ' pr. niveau. */
export function indentedName(name: string, indent: number): string {
  return '— '.repeat(Math.max(0, indent)) + name;
}
