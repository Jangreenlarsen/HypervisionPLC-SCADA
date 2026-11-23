// Alarmens type (v6.18.0, B1): niveauet på dansk — adskilt fra prioriteten (Høj/Medium/Lav), som vises i sin egen kolonne.

const TYPE_TEXT: Record<string, string> = {
  HH: 'HH', H: 'H', L: 'L', LL: 'LL', ON: 'Til', COMM: 'Kommunikation', SYS: 'System', AFV: 'Afvigelse',
};
const PRIO_TEXT: Record<string, string> = { high: 'Høj', medium: 'Medium', low: 'Lav' };

/** Niveaukoden som tekst; ukendte koder vises som de er (en tom kode bliver en tankestreg). */
export function alarmTypeText(level: string | null | undefined): string {
  if (!level) return '—';
  return TYPE_TEXT[level] ?? level;
}

/** Prioriteten som tekst; ukendt vises som den er. */
export function alarmPriorityText(priority: string | null | undefined): string {
  if (!priority) return '—';
  return PRIO_TEXT[priority] ?? priority;
}
