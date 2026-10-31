// Panelet til højre i Tegn (v3.5.0): foldbare sektioner. Åbnes en sektion, foldes de andre sammen — undtagen dem, der
// er fastgjort (📌), som altid står åbne. Tilstanden huskes i browseren.

export interface PanelState { open: string[]; pinned: string[] }

export const PANEL_IDS = ['valgt', 'egenskaber', 'objekter', 'symboler'] as const;
export const DEFAULT_PANELS: PanelState = { open: ['valgt', 'egenskaber', 'symboler'], pinned: ['valgt', 'egenskaber'] };
const KEY = 'draw.panels';

const uniq = (xs: string[]) => [...new Set(xs)];

/** Fold ud/ind. Ud: de andre ikke-fastgjorte foldes sammen. Ind: en fastgjort sektion løsnes også. */
export function togglePanel(s: PanelState, id: string): PanelState {
  if (s.open.includes(id)) return { open: s.open.filter((x) => x !== id), pinned: s.pinned.filter((x) => x !== id) };
  return { open: uniq([...s.open.filter((x) => s.pinned.includes(x)), id]), pinned: s.pinned };
}

/** Fastgør/løsn. Fastgjort står altid åben; løsnes den, forbliver den åben, til en anden sektion åbnes. */
export function togglePin(s: PanelState, id: string): PanelState {
  if (s.pinned.includes(id)) return { open: s.open, pinned: s.pinned.filter((x) => x !== id) };
  return { open: uniq([...s.open, id]), pinned: uniq([...s.pinned, id]) };
}

/** Læs gemt tilstand; ukendte sektioner og ødelagte data giver standarden. */
export function parsePanels(raw: string | null): PanelState {
  try {
    const v = JSON.parse(raw ?? '');
    const ok = (xs: unknown): string[] => (Array.isArray(xs) ? xs.filter((x): x is string => (PANEL_IDS as readonly string[]).includes(x as string)) : []);
    if (!v || typeof v !== 'object') return DEFAULT_PANELS;
    const pinned = uniq(ok(v.pinned));
    return { open: uniq([...ok(v.open), ...pinned]), pinned };
  } catch {
    return DEFAULT_PANELS;
  }
}

export function loadPanels(): PanelState {
  try {
    return parsePanels(localStorage.getItem(KEY));
  } catch {
    return DEFAULT_PANELS;   // localStorage blokeret
  }
}

export function savePanels(s: PanelState): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    // blokeret localStorage: panelet virker stadig, det huskes bare ikke
  }
}
