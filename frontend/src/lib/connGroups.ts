// Forbindelsesgrupper (v6.1.0, backend services/connection_groups.py): hvordan tegningens forbindelser viser det beregnede flow.
// Rene typer og hjælpere — testet i connGroups.test.ts.

export type ConnAnimType = 'flow' | 'color' | 'blink' | 'fixed';
export interface Limit { value: number; color: string }
export interface ConnAnim {
  type: ConnAnimType;
  light?: string; base?: string; speed?: number; dash?: number; full?: number;
  off?: string; limits?: Limit[];
  at_least?: number | null; at_most?: number | null; rate?: 'slow' | 'normal' | 'fast';
  color?: string;
}
export interface ConnGroup { id: number; name: string; members: string[]; missing?: string[]; anims: ConnAnim[] }
export interface ConnList {
  default: { anims: ConnAnim[]; members: string[] };
  groups: ConnGroup[];
  connections: { id: string; name: string }[];
  flow?: { unbound: boolean; notes: string[]; stats: { nodes: number; edges: number; pumps: number; pumping: number } | null };
}

export const CONN_ANIM_TXT: Record<ConnAnimType, string> = {
  flow: 'Løbelys (retning og fart efter flowet)', color: 'Farve efter flow', blink: 'Blink ved et flow', fixed: 'Fast farve',
};
export const MAX_CONN_ANIMS = 4;

/** En ny animation med fornuftige standarder (som backend ConnAnim). */
export function newConnAnim(type: ConnAnimType): ConnAnim {
  switch (type) {
    case 'flow': return { type, light: '#8fc8ea', base: '#555555', speed: 60, dash: 12, full: 0 };
    case 'color': return { type, off: '#9e9e9e', limits: [{ value: 1, color: '#1e88e5' }] };
    case 'blink': return { type, at_most: 0, at_least: null, rate: 'normal' };
    default: return { type, color: '#1e88e5' };
  }
}

/** Kort beskrivelse til listen. */
export function describeConnAnims(anims: ConnAnim[]): string {
  if (!anims.length) return 'ingen animation';
  return anims.map((a) => {
    if (a.type === 'flow') return 'løbelys';
    if (a.type === 'color') return `farve (${(a.limits ?? []).map((l) => `≥ ${l.value}`).join(', ') || 'ingen grænser'})`;
    if (a.type === 'blink') return a.at_least != null ? `blink ved ≥ ${a.at_least} l/min` : `blink ved ≤ ${a.at_most ?? 0} l/min`;
    return 'fast farve';
  }).join(' + ');
}

/** De valgte elementer, der er forbindelser (rør og rørstykker) — kun de kan være i en gruppe. */
export const pickConnections = (selected: string[], all: { id: string }[]): string[] => {
  const ok = new Set(all.map((c) => c.id));
  return [...new Set(selected.filter((id) => ok.has(id)))];
};

/** Grænserne skal være stigende (som backend). → fejltekst eller null */
export function connAnimError(a: ConnAnim): string | null {
  if (a.type === 'color') {
    const v = (a.limits ?? []).map((l) => l.value);
    if (v.some((x, i) => i > 0 && x < v[i - 1])) return 'Grænserne skal være stigende';
  }
  if (a.type === 'blink' && a.at_least == null && a.at_most == null) return 'Blink kræver en grænse';
  if (a.type === 'flow' && ((a.speed ?? 0) < 5 || (a.speed ?? 0) > 500)) return 'Farten skal være 5–500';
  return null;
}
