// Symbolstandard på Overview: klik-regler, nøglelås og tilstandsmærker (rene funktioner — testet i symbolUi.test.ts).
// Reference: prototypens `clickSymbol`, `needsPin`, `GLYPH`, `STATE_TXT`. Serveren håndhæver det samme.

export interface SymbolView {
  op: 'positions' | 'pulse' | 'entry' | 'view';
  labels: string[];
  display: 'remote' | 'local';
  confirm: boolean;
  lock_positions: boolean[];
  lock_leave: boolean;
  has_pin: boolean;
  fault: string;
  pulse_ms?: number;
  tag?: string;
  pseudo?: { pos: string; remote: string; state: string; locked: string };
  /** Trendgraf (v0.91.0). */
  chart?: import('./chartGraphic').ChartCfg | null;
}

export type SymbolState = 'confirmed' | 'pending' | 'mismatch' | 'unknown';

export const STATE_TXT: Record<SymbolState, string> = { confirmed: 'Bekræftet', pending: 'Venter', mismatch: 'Afvigelse', unknown: 'Ukendt' };
export const GLYPH: Record<SymbolState, string> = { confirmed: '✓', pending: '…', mismatch: '!', unknown: '?' };

const isLocked = (s: SymbolView, j: number | null): boolean =>
  j !== null && j >= 0 && j < s.lock_positions.length && Boolean(s.lock_positions[j]);

/** Kræver skiftet koden? Låst mål, eller ("kode for at forlade") en låst vist position der forlades. */
export function needsPin(s: SymbolView, shown: number | null, to: number): boolean {
  return isLocked(s, to) || (s.lock_leave && isLocked(s, shown) && shown !== to);
}

export const lockedPosition = isLocked;

export type ClickAction =
  | { kind: 'none' }
  | { kind: 'pulse' }                       // send puls straks
  | { kind: 'operate'; to: number }         // skift straks
  | { kind: 'dialog'; pick: number | null }; // åbn dialogen (evt. med en position valgt, fx for at taste koden)

/**
 * Et klik på symbolet (prototypens `clickSymbol`):
 * - trykknap: dialog hvis bekræftelse, ellers puls straks; setpunkt: altid dialog (indtastning);
 * - 2 positioner uden bekræftelse: skift straks til den anden (dialog med koden hvis den kræves);
 * - ellers dialog med positionerne.
 */
export function clickAction(s: SymbolView, shown: number | null): ClickAction {
  if (s.op === 'view') return { kind: 'none' };
  if (s.op === 'pulse') return s.confirm ? { kind: 'dialog', pick: null } : { kind: 'pulse' };
  if (s.op === 'entry') return { kind: 'dialog', pick: null };
  if (!s.confirm && s.labels.length === 2) {
    const to = shown === 1 ? 0 : 1;
    return needsPin(s, shown, to) ? { kind: 'dialog', pick: to } : { kind: 'operate', to };
  }
  return { kind: 'dialog', pick: null };
}

/**
 * Et klik på en position i dialogen: uden bekræftelse skiftes straks (medmindre koden kræves);
 * med bekræftelse vælges positionen, og "Skift til …" udfører.
 */
export function pickAction(s: SymbolView, shown: number | null, to: number): 'operate' | 'pick' {
  return !s.confirm && !needsPin(s, shown, to) ? 'operate' : 'pick';
}

/** Teksten på dialogens knap. */
export function operateLabel(s: SymbolView, shown: number | null, to: number): string {
  return `${needsPin(s, shown, to) ? 'Lås op og skift' : 'Skift'} til ${s.labels[to] ?? ''}`;
}
