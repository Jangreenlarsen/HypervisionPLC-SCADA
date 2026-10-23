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

/** Tilføj ids (uden dubletter, rækkefølgen bevares). */
export const withMembers = (members: string[], add: string[]): string[] => [...new Set([...members, ...add])];
/** Fjern ids. */
export const withoutMembers = (members: string[], remove: string[]): string[] => members.filter((m) => !remove.includes(m));
/** Grupperne et element er med i (til oversigt over overlap). */
export const groupsOf = (groups: SymbolGroup[], element: string): SymbolGroup[] => groups.filter((g) => g.members.includes(element));
export const ofKind = (groups: SymbolGroup[], kind: GroupKind): SymbolGroup[] => groups.filter((g) => g.kind === kind);
