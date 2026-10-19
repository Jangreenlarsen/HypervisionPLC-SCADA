// Tegningens størrelse i Tegn (v0.92.0): faste valg og kontrol af bredde/højde. Ren logik — testet i drawingSize.test.ts.

export const SIZE_MIN = 100;
export const SIZE_MAX = 10000;

export const SIZE_PRESETS: { label: string; w: number; h: number }[] = [
  { label: 'Standard (1200 × 700)', w: 1200, h: 700 },
  { label: 'Full HD-skærm (1920 × 1080)', w: 1920, h: 1080 },
  { label: 'Panel (1280 × 800)', w: 1280, h: 800 },
  { label: 'Lille panel (800 × 480)', w: 800, h: 480 },
  { label: 'Stor tegning (2560 × 1440)', w: 2560, h: 1440 },
  { label: 'A4 liggende (1123 × 794)', w: 1123, h: 794 },
];

/** Bredde og højde fra felterne: hele tal mellem SIZE_MIN og SIZE_MAX; ellers en fejl med feltets navn. */
export function parseSize(w: string, h: string): { w: number; h: number } | { error: string } {
  const one = (v: string, name: string): number | string => {
    const t = v.trim();
    if (!t) return `Skriv en ${name}`;
    const n = Number(t.replace(',', '.'));
    if (!Number.isFinite(n)) return `${name[0].toUpperCase()}${name.slice(1)} skal være et tal`;
    const r = Math.round(n);
    if (r < SIZE_MIN || r > SIZE_MAX) return `${name[0].toUpperCase()}${name.slice(1)} skal være mellem ${SIZE_MIN} og ${SIZE_MAX}`;
    return r;
  };
  const a = one(w, 'bredde'), b = one(h, 'højde');
  if (typeof a === 'string') return { error: a };
  if (typeof b === 'string') return { error: b };
  return { w: a, h: b };
}

/** "1920 × 1080" og det faste valg, størrelsen svarer til (eller null). */
export const sizeText = (w: number, h: number): string => `${Math.round(w)} × ${Math.round(h)}`;
export const presetFor = (w: number, h: number) => SIZE_PRESETS.find((p) => p.w === Math.round(w) && p.h === Math.round(h)) ?? null;
