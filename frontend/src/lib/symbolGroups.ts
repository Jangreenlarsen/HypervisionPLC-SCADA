// Navngivne symbolgrupper (v0.130.0): udvalg af elementer på en tegning. Samme element må være med i flere grupper.
import { del, get, post, put } from './api';

export type GroupKind = 'function' | 'selection';
export interface SymbolGroup { id: number; name: string; kind: GroupKind; members: string[] }

export const KIND_TXT: Record<GroupKind, string> = { function: 'Funktionsgrupper', selection: 'Udvalg' };
export const KIND_HINT: Record<GroupKind, string> = {
  function: 'En del af anlægget med en funktion, fx "Fyr uden akku-tank"',
  selection: 'Et frit udvalg af symboler, fx 3-vejs ventil, rør og akkutank',
};

const base = (drawingId: string) => `/api/drawings/${encodeURIComponent(drawingId)}/groups`;
export const listGroups = (drawingId: string) => get<SymbolGroup[]>(base(drawingId));
export const createGroup = (drawingId: string, name: string, kind: GroupKind, members: string[]) =>
  post<SymbolGroup>(base(drawingId), { name, kind, members });
export const updateGroup = (drawingId: string, g: { id: number; name: string; kind: GroupKind }, members?: string[]) =>
  put<SymbolGroup>(`${base(drawingId)}/${g.id}`, { name: g.name, kind: g.kind, ...(members ? { members } : {}) });
export const deleteGroup = (drawingId: string, id: number) => del(`${base(drawingId)}/${id}`);

/** Tilføj/fjern enkelte medlemmer på serveren — rører ikke de andre, så en forældet skærm ikke overskriver en kollegas ændringer. */
export const changeMembers = (drawingId: string, groupId: number, add: string[], remove: string[]) =>
  post<SymbolGroup>(`${base(drawingId)}/${groupId}/members`, { add, remove });
/** Flyt et forsvundet medlem (og dets gruppe-animationer) til det element, der har fået dets plads. */
export const moveMember = (drawingId: string, groupId: number, old: string, to: string) =>
  post<SymbolGroup & { dropped: string[]; discarded: number }>(`${base(drawingId)}/${groupId}/members/move`, { old, new: to });
/** Gruppernes rækkefølge (afgør hvem der vinder ved overlap). */
export const reorderGroups = (drawingId: string, ids: number[]) => post<SymbolGroup[]>(`${base(drawingId)}/order`, { ids });
/** Byt en gruppe med sin nabo af samme art; giver den nye samlede rækkefølge af id'er (eller null hvis den ikke kan flyttes). */
export function movedOrder(groups: SymbolGroup[], id: number, dir: -1 | 1): number[] | null {
  const i = groups.findIndex((g) => g.id === id);
  if (i < 0) return null;
  let j = i + dir;
  while (j >= 0 && j < groups.length && groups[j].kind !== groups[i].kind) j += dir;
  if (j < 0 || j >= groups.length) return null;
  const ids = groups.map((g) => g.id);
  [ids[i], ids[j]] = [ids[j], ids[i]];
  return ids;
}

/** Tilføj ids (uden dubletter, rækkefølgen bevares). */
export const withMembers = (members: string[], add: string[]): string[] => [...new Set([...members, ...add])];
/** Fjern ids. */
export const withoutMembers = (members: string[], remove: string[]): string[] => members.filter((m) => !remove.includes(m));
/** Grupperne et element er med i (til oversigt over overlap). */
export const groupsOf = (groups: SymbolGroup[], element: string): SymbolGroup[] => groups.filter((g) => g.members.includes(element));
export const ofKind = (groups: SymbolGroup[], kind: GroupKind): SymbolGroup[] => groups.filter((g) => g.kind === kind);

// ---- Animationer ejet af en gruppe (v0.131.0)
export interface GroupOwner { group_id: number; group_name: string; kind: GroupKind; anims: GroupAnim[] }
export interface GroupAnim { part: string; type: string; when?: boolean; src: string; params: Record<string, any>; only?: boolean[] | null }

/** En ejers animationer på et symbol i oversigten: symbolets egne (color null) eller en gruppes. */
export interface OwnerBlock { key: string; label: string; color: string | null; anims: GroupAnim[] }

export const getGroupAnims = (drawingId: string, groupId: number) =>
  get<Record<string, GroupAnim[]>>(`${base(drawingId)}/${groupId}/anims`);
export const putGroupAnims = (drawingId: string, groupId: number, element: string, anims: GroupAnim[]) =>
  put<{ element: string; anims: GroupAnim[]; warnings: string[] }>(`${base(drawingId)}/${groupId}/anims/${encodeURIComponent(element)}`, { anims });
/** Alle gruppers animationer på ét element (til oversigten over, hvem der ejer hvad). */
export const groupAnimsOn = (drawingId: string, element: string) =>
  get<GroupOwner[]>(`/api/drawings/${encodeURIComponent(drawingId)}/symbols/${encodeURIComponent(element)}/group-anims`);

/** Gruppernes farver i oversigter og guide: symbolets egne er neutrale, hver gruppe får sin egen. */
export const GROUP_COLORS = ['#1f77b4', '#d95f02', '#7b3fa0', '#1b9e77', '#c2185b', '#8d6e00'];
export const groupColor = (groupId: number): string => GROUP_COLORS[Math.abs(groupId) % GROUP_COLORS.length];
