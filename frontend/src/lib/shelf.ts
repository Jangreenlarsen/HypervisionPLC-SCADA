// Udsæt alarm (v6.19.0, B5): varighedsvalg, begrundelsens regler og resttid. Rene funktioner, så grænserne kan testes.

export const REASON_MIN = 3;
export const REASON_MAX = 200;
export const DEFAULT_SHELVE_MINUTES = 60;

/** Varighederne i dialogen (backend tillader 5-1440 minutter). */
export const SHELVE_OPTIONS: { minutes: number; label: string }[] = [
  { minutes: 15, label: '15 min' },
  { minutes: 60, label: '1 time' },
  { minutes: 240, label: '4 timer' },
  { minutes: 480, label: '8 timer' },
  { minutes: 1440, label: '24 timer' },
];

/** Kommunikations- og systemalarmer må ikke udsættes, og en ophørt alarm skal kvitteres i stedet. */
export function canShelve(a: { kind: string; state: string }): boolean {
  return a.kind !== 'comm' && a.kind !== 'sys' && a.state !== 'rtn_unack';
}

/** Kontrol- (Cc: linjeskift, tabulator …) og formattegn (Cf: usynlige, retningsstyrende) afvises, som i backend. */
const FORBIDDEN = /[\p{Cc}\p{Cf}]/u;

/** Begrundelsen som backend gemmer den: whitespace kollapset til ét mellemrum og trimmet. */
export function normalizeReason(text: string): string {
  return text.split(/\s+/u).filter(Boolean).join(' ');
}

/** Antal tegn som backend tæller dem: kodepunkter (ikke UTF-16-enheder, så en emoji er ét tegn). */
export function reasonLength(text: string): number {
  return [...normalizeReason(text)].length;
}

/** Tom streng hvis begrundelsen er gyldig (efter normalisering), ellers fejlteksten. */
export function reasonError(text: string): string {
  if (FORBIDDEN.test(text)) return 'Begrundelsen må ikke indeholde linjeskift, kontroltegn eller usynlige tegn.';
  const n = reasonLength(text);
  if (n < REASON_MIN) return `Begrundelsen skal være mindst ${REASON_MIN} tegn.`;
  if (n > REASON_MAX) return `Begrundelsen må højst være ${REASON_MAX} tegn.`;
  return '';
}

/** Resttiden i sekunder nu: svaret fra serveren minus den tid, der er gået, siden det blev hentet (uafhængig af klientens ur). */
export function remainingNow(remainingS: number, fetchedAtMs: number, nowMs: number): number {
  return remainingS - Math.max(0, nowMs - fetchedAtMs) / 1000;
}

/** Resttid som tekst: '12 min', '1 t 5 min', '2 t', 'udløber nu' (højst nul sekunder tilbage). Minutter rundes op. */
export function remainingText(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return 'udløber nu';
  const m = Math.ceil(seconds / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h} t ${rest} min` : `${h} t`;
}
