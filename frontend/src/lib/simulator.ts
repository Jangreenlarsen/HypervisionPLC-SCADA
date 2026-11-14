// Simulatoren (v6.5.0, PLAN.md › Simulator): typer og rene hjælpere til siden Simulator. Serveren finder tegningens variabler
// (GET /simulator) og regner de afledte værdier med de indskudte (POST /simulate); siden tegner med Overview-motoren.

import type { LiveValue } from './api';

export interface SimLive { value: unknown; quality: string }
export interface SimTag {
  name: string; kind: 'bool' | 'num'; unit: string; min: number | null; max: number | null; decimals: number | null;
  description: string; plc: string; used: string[]; elements: string[]; live: SimLive;
}
export interface SimPosition { element: string; name: string; labels: string[]; states?: (string | null)[]; display: string; live: number | null }
export interface SimAlarm { name: string; tag: string; kind: string; used: string[]; elements: string[]; live: SimLive }
/** orphaned (v6.8.3): opsætninger på elementer, der ikke findes i tegningen — vises ikke som variabler */
export interface SimVariables { tags: SimTag[]; positions: SimPosition[]; alarms: SimAlarm[]; orphaned?: string[] }
export interface SimState { values: Record<string, unknown>; positions: Record<string, number> }
export interface SimScenario extends SimState { id: number; name: string; updated_at: number; updated_by: string }
export interface SimResult { values: Record<string, SimLive>; notes: string[]; ms: number; simulated: number }

export const emptyState = (): SimState => ({ values: {}, positions: {} });

/** Er variablen simuleret (ellers følger den PLC'en)? null-værdi = simuleret komm.fejl. */
export const isSimulated = (s: SimState, name: string): boolean => Object.prototype.hasOwnProperty.call(s.values, name);

/** Startværdien, når en variabel skiftes fra Live til Simuleret: den live værdi, ellers et fornuftigt nul. */
export function startValue(t: Pick<SimTag, 'kind' | 'min' | 'live'>): unknown {
  const v = t.live?.value;
  if (t.kind === 'bool') return typeof v === 'boolean' ? v : Boolean(v);
  return typeof v === 'number' ? v : t.min ?? 0;
}

const hasLive = (t: { live?: { quality?: string; value?: unknown } | null }): boolean =>
  t.live?.quality === 'good' && t.live.value !== null && t.live.value !== undefined;

/**
 * "Frys på live-værdier" (før "Start fra live", v6.11.2): alle tags og alarmer med en god live værdi bliver simulerede med den
 * værdi lige nu. Det, brugeren allerede har sat (`keep`), bevares — før blev det overskrevet uden et ord.
 */
export function fromLive(vars: SimVariables, keep: SimState = emptyState()): SimState {
  const values: Record<string, unknown> = {};
  for (const t of [...vars.tags, ...vars.alarms]) if (hasLive(t)) values[t.name] = t.live!.value;
  const positions: Record<string, number> = {};
  for (const p of vars.positions) if (p.live !== null) positions[p.element] = p.live;
  return { values: { ...values, ...keep.values }, positions: { ...positions, ...keep.positions } };
}

/** Hvor mange variabler har en god live værdi lige nu (0 = PLC'en svarer ikke, så der er intet at fryse). */
export function liveCount(vars: SimVariables): number {
  return [...vars.tags, ...vars.alarms].filter(hasLive).length + vars.positions.filter((p) => p.live !== null).length;
}

/** Hvor mange variabler "Frys" ville tilføje (de, der endnu ikke er simulerede og har en god live værdi). */
export function freezable(vars: SimVariables, sim: SimState): number {
  return [...vars.tags, ...vars.alarms].filter((t) => hasLive(t) && !isSimulated(sim, t.name)).length
    + vars.positions.filter((p) => p.live !== null && !(p.element in sim.positions)).length;
}

/** Svaret som Overview-motorens værditabel. */
export function toLive(r: SimResult): Record<string, LiveValue> {
  const out: Record<string, LiveValue> = {};
  for (const [k, v] of Object.entries(r.values)) out[k] = { value: v.value as LiveValue['value'], quality: v.quality as LiveValue['quality'], ts: 0, error: null };
  return out;
}

/** Søg/filtrér panelet: navn, beskrivelse eller hvor den bruges; `onlySim` = kun de simulerede. */
export function matches(t: { name: string; description?: string; used: string[] }, q: string, simulated: boolean, onlySim: boolean): boolean {
  if (onlySim && !simulated) return false;
  const s = q.trim().toLowerCase();
  return !s || t.name.toLowerCase().includes(s) || (t.description ?? '').toLowerCase().includes(s) || t.used.some((u) => u.toLowerCase().includes(s));
}

/** Skyderens trin efter tagets interval (ca. 100 trin; heltal ved decimaler 0). */
export function stepFor(t: Pick<SimTag, 'min' | 'max' | 'decimals'>): number {
  if (t.decimals === 0) return 1;
  if (t.min === null || t.max === null || !(t.max > t.min)) return 0.1;
  const raw = (t.max - t.min) / 100;
  const p = 10 ** Math.floor(Math.log10(raw));
  return Number((Math.round(raw / p) * p).toPrecision(2));
}

/** Kort visning af en live værdi i panelet. */
export function liveText(l: SimLive | undefined, unit = ''): string {
  if (!l || l.quality !== 'good' || l.value === null || l.value === undefined) return l?.quality === 'comm_error' ? 'komm.fejl' : '—';
  if (typeof l.value === 'boolean') return l.value ? 'Til' : 'Fra';
  return `${typeof l.value === 'number' ? Math.round(l.value * 1000) / 1000 : String(l.value)}${unit ? ` ${unit}` : ''}`;
}

/** Hvad en variabel bruges til, kort (v6.8.3): "Pumpe · opsætning", "Pumpe · Farve" → "Pumpe (opsætning, Farve)"; højst 3 symboler. */
export function usedText(used: string[], max = 3): string {
  const by = new Map<string, string[]>();
  for (const u of used) {
    const i = u.lastIndexOf(' · ');
    const who = i >= 0 ? u.slice(0, i) : u;
    const what = i >= 0 ? u.slice(i + 3) : '';
    const list = by.get(who) ?? [];
    if (what && !list.includes(what)) list.push(what);
    by.set(who, list);
  }
  const parts = [...by].map(([who, what]) => (what.length ? `${who} (${what.join(', ')})` : who));
  return parts.length > max ? `${parts.slice(0, max).join(', ')} +${parts.length - max}` : parts.join(', ');
}
