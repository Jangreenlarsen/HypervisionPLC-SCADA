// Symbol-oversigten i Tegn (v5.5.0): alle symboler på tegningen som et træ. Rene funktioner — testet i symbolTree.test.ts.
//   Niveau 1: Grundsymboler · Grupper
//   Niveau 2: en gruppes medlemmer

export interface SymbolRow { element: string; name: string | null; type: string; configured: boolean }
export interface GroupRow { id: number; name: string; kind: 'function' | 'selection'; members: string[] }

export type TreeKind = 'section' | 'symbol' | 'group';
export interface TreeNode {
  key: string;
  kind: TreeKind;
  label: string;
  sub: string;                       // lille tekst ved siden af navnet (type, antal)
  ids: string[];                     // elementer i tegningen, et klik vælger
  guide: { id: string; name: string } | null;     // symbol-guiden åbnes for dette id
  group: number | null;              // gruppens id (animationer for gruppen)
  configured: boolean | null;        // null = kan ikke opsættes (sektion, gruppe)
  children: TreeNode[];
}

export const nodeLabel = (r: Pick<SymbolRow, 'element' | 'name'>): string => r.name?.trim() || r.element;

const symbolNode = (r: SymbolRow, key: string): TreeNode => ({
  key, kind: 'symbol', label: nodeLabel(r), sub: r.type === 'custom' ? '' : r.type, ids: [r.element],
  guide: { id: r.element, name: nodeLabel(r) }, group: null, configured: r.configured, children: [],
});

/** Træet: to sektioner (tomme sektioner udelades). Et symbol må stå flere steder (som medlem af flere grupper). */
export function buildTree(symbols: SymbolRow[], groups: GroupRow[]): TreeNode[] {
  const byId = new Map(symbols.map((s) => [s.element, s]));
  const child = (id: string, key: string): TreeNode => {
    const r = byId.get(id);
    // et medlem uden navn/bibliotekstype (fx et rør) kan vælges, men har ingen guide
    return r ? symbolNode(r, key)
      : { key, kind: 'symbol', label: id, sub: '', ids: [id], guide: null, group: null, configured: null, children: [] };
  };
  const out: TreeNode[] = [];
  const section = (key: string, label: string, children: TreeNode[]) => {
    if (children.length) out.push({ key, kind: 'section', label, sub: String(children.length), ids: [], guide: null, group: null, configured: null, children });
  };
  section('s:symbols', 'Grundsymboler', symbols.map((s) => symbolNode(s, `sym:${s.element}`)));
  section('s:groups', 'Grupper', groups.map((g) => ({
    key: `group:${g.id}`, kind: 'group' as const, label: g.name, sub: `${g.members.length} · ${g.kind === 'function' ? 'funktion' : 'udvalg'}`,
    ids: g.members, guide: null, group: g.id, configured: null, children: g.members.map((m) => child(m, `group:${g.id}:${m}`)),
  })));
  return out;
}

/** Søgning og "kun ikke-opsatte": en række vises, hvis den selv eller et barn passer; træffer et barn, foldes forælderen ud. */
export function filterTree(nodes: TreeNode[], query: string, onlyOpen: boolean): TreeNode[] {
  const q = query.trim().toLowerCase();
  if (!q && !onlyOpen) return nodes;
  const fits = (n: TreeNode) =>
    (!q || n.label.toLowerCase().includes(q) || n.ids.some((i) => i.toLowerCase().includes(q)) || n.sub.toLowerCase().includes(q))
    && (!onlyOpen || n.configured === false);
  const walk = (n: TreeNode): TreeNode | null => {
    const kids = n.children.map(walk).filter((x): x is TreeNode => x !== null);
    return kids.length || (n.kind !== 'section' && fits(n)) ? { ...n, children: kids.length ? kids : [] } : null;
  };
  return nodes.map(walk).filter((x): x is TreeNode => x !== null);
}

/** Antal rækker med/uden opsætning (hvert grundsymbol tælles én gang, uanset hvor mange steder det står). */
export function countSymbols(symbols: SymbolRow[]): { total: number; configured: number } {
  return { total: symbols.length, configured: symbols.filter((s) => s.configured).length };
}
