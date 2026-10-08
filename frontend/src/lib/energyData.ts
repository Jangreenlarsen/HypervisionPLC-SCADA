// Hjælpefunktioner til energirapporten (rene funktioner — testet i energyData.test.ts).

/** "Pæne" trin på y-aksen (1, 2, 2,5, 5 × 10^n) fra 0 til mindst `max`. */
export function niceTicks(max: number, count = 5): number[] {
  if (!(max > 0) || !Number.isFinite(max)) return [0, 1];
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw)!;
  const ticks: number[] = [];
  for (let v = 0; v < max + step * 0.999; v += step) ticks.push(Math.round(v * 1e9) / 1e9);
  return ticks;
}

/** Akse-etiket: samme antal decimaler på alle trin (ud fra trinstørrelsen). */
export function fmtTick(v: number, step: number): string {
  const dec = step >= 1 ? 0 : step >= 0.1 ? 1 : step >= 0.01 ? 2 : 3;
  return v.toLocaleString('da-DK', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

/** kWh med fornuftige decimaler og dansk tal-format; null = ingen data. */
export function fmtKwh(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  const abs = Math.abs(v);
  const dec = abs >= 100 ? 0 : abs >= 10 ? 1 : abs >= 1 ? 2 : 3;
  return v.toLocaleString('da-DK', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}
