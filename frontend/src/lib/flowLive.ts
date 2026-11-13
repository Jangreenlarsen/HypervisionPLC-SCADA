// Flowet live i Tegn (v6.3.0, PLAN.md › Flow-model runde 2): typer og hjælpere til preview-kaldet og simuleringen.

export interface PreviewPump { id: string; name: string; configured: boolean; capacity: number }
export interface PreviewValve { id: string; name: string; labels: string[]; pos: number | null }
export interface PreviewSymbol { id: string; name: string; restrict: number }
export interface Preview {
  flows: Record<string, number>;
  ports: Record<string, Record<string, number>>;
  notes: string[];
  stats: { pumps?: number; pumping?: number; edges?: number };
  pumps: PreviewPump[];
  valves: PreviewValve[];
  symbols: PreviewSymbol[];
  linked: boolean;
  ms: number;
  simulated: boolean;
  pieces: string[];
}

export interface Sim {
  rates: Record<string, number>;       // pumpe → 0,00–1,00 (kun de pumper, brugeren har rørt)
  positions: Record<string, number>;   // ventil → position
  restricts: Record<string, number>;   // symbol → 0,00–1,00
}

export const emptySim = (): Sim => ({ rates: {}, positions: {}, restricts: {} });

/** Kroppen til POST /flow/preview: live = kun tegningen; simuleret = med de værdier, brugeren har sat. */
export function previewBody(svg: string, sim: Sim | null): Record<string, unknown> {
  if (!sim) return { svg };
  const clamp = (o: Record<string, number>) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Math.round(Math.min(1, Math.max(0, v)) * 100) / 100]));
  return { svg, rates: clamp(sim.rates), positions: { ...sim.positions }, restricts: clamp(sim.restricts) };
}

/** Det overlayet i Tegn behøver (scada-core setFlowOverlay). */
export function overlayData(p: Preview, unit = 'l/min'): Record<string, unknown> {
  const max = Math.max(1, ...p.pumps.map((x) => x.capacity), ...Object.values(p.flows).map((v) => Math.abs(v)));
  return { flows: p.flows, ports: p.ports, unit, max, pieces: p.pieces };
}

/** 0,25 → "0,25" */
export const fmt2 = (v: number): string => v.toFixed(2).replace('.', ',');
