// OTA-opdatering (System › Opdatering): ren logik til siden — testet i updateUi.test.ts.

export interface Version { version: string; build: string }
export type Relation = 'newer' | 'same' | 'older' | 'unknown';
export type UpdateState = 'idle' | 'queued' | 'applying' | 'done' | 'failed' | 'rolled_back' | 'stalled';

export interface Staged extends Version {
  sha256: string; size: number; files: number; relation: Relation; uploaded_by: string; uploaded_at: number;
}
export interface LastRun { state: string; message: string; from: string; to: string; by: string; ts: number; backup?: string }
export interface UpdateStatus {
  enabled: boolean; current: Version; staged: Staged | null; state: UpdateState; last: LastRun | null; busy: boolean; log: string[];
}

export const RELATION_TEXT: Record<Relation, string> = {
  newer: 'Nyere end den installerede', same: 'Samme version som den installerede', older: 'Ældre end den installerede', unknown: 'Kan ikke sammenlignes',
};

/** Kan pakken installeres? Ældre versioner afvises (databasen kan være opgraderet); samme version kræver en ekstra bekræftelse. */
export function canInstall(s: UpdateStatus | null, reinstallConfirmed: boolean): boolean {
  if (!s || !s.enabled || s.busy || !s.staged) return false;
  if (s.staged.relation === 'older') return false;
  if (s.staged.relation === 'same') return reinstallConfirmed;
  return true;
}

/** Teksten under overskriften for den seneste kørsel — og om den er en succes, en tilbagerulning eller en fejl. */
export function resultOf(last: LastRun | null): { kind: 'ok' | 'warn' | 'error'; text: string } | null {
  if (!last) return null;
  const route = `${last.from} → ${last.to}`;
  switch (last.state) {
    case 'done': return { kind: 'ok', text: `Opdateret ${route}. ${last.message}` };
    case 'rolled_back': return { kind: 'warn', text: `Opdateringen ${route} blev rullet tilbage: ${last.message}` };
    case 'failed': return { kind: 'error', text: `Opdateringen ${route} mislykkedes: ${last.message}` };
    default: return null;
  }
}

/** Fremdrift mens en opdatering kører: serveren genstarter undervejs, så fejlede kald er en del af forløbet. */
export function progressText(s: UpdateStatus | null, unreachable: boolean): string {
  if (unreachable) return 'Serveren genstarter … (siden prøver igen automatisk)';
  if (!s) return 'Henter status …';
  if (s.state === 'stalled') return 'Opdateringen ser ud til at være gået i stå — se loggen nedenfor';
  if (s.busy) return s.last?.message || 'Opdateringen er sat i gang …';
  return '';
}

/** Er forløbet slut? Slut = en endelig tilstand fra hjælperen, efter at vi selv har startet den. */
export function isFinished(s: UpdateStatus | null, startedAt: number): boolean {
  if (!s || s.busy) return false;
  const last = s.last;
  return !!last && ['done', 'failed', 'rolled_back'].includes(last.state) && last.ts >= startedAt - 5;
}

export const fmtSize = (bytes: number): string => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} kB`);
