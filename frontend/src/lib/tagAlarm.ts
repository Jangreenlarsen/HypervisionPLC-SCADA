// Alarmer i symbolguiden (v0.74.0): tag-alarmens opsætning som kort tekst, formularen til at rette den, og status.

export interface TagAlarm {
  alarm_hh: number | null; alarm_h: number | null; alarm_l: number | null; alarm_ll: number | null;
  alarm_deadband: number | null; alarm_delay_s: number | null; alarm_on: 'true' | 'false' | null;
  alarm_priority: AlarmPriority | null;
  // Rationalisering (v6.20.0, ISA-18.2): hvad alarmen betyder; alle valgfri (null/udeladt = ikke angivet)
  alarm_consequence?: string | null; alarm_action?: string | null; alarm_response_min?: number | null;
}

export const RATIONALE_MAX = 200;
/** Antal tegn som serveren tæller dem (kodepunkter). */
export const charCount = (v: string): number => [...v].length;

/** Fast prioritet pr. tag (v6.18.0); null = efter niveauet (HH/LL/Til høj, H/L medium). */
export type AlarmPriority = 'high' | 'medium' | 'low';

const LIMITS = [['alarm_hh', 'HH'], ['alarm_h', 'H'], ['alarm_l', 'L'], ['alarm_ll', 'LL']] as const;
const num = (v: number) => String(Math.round(v * 1000) / 1000);

export function hasAlarm(t: Partial<TagAlarm>): boolean {
  return t.alarm_on != null || LIMITS.some(([k]) => t[k] != null);
}

/** "HH 90 · H 80 bar · dødbånd 2 · 5 s forsinkelse", "når Til", eller "ingen alarm". */
export function alarmSummary(t: Partial<TagAlarm>, unit = ''): string {
  if (!hasAlarm(t)) return 'ingen alarm';
  const parts: string[] = [];
  if (t.alarm_on != null) parts.push(t.alarm_on === 'true' ? 'når Til' : 'når Fra');
  else parts.push(LIMITS.filter(([k]) => t[k] != null).map(([k, l]) => `${l} ${num(t[k] as number)}`).join(' · ') + (unit ? ` ${unit}` : ''));
  if (t.alarm_on == null && t.alarm_deadband) parts.push(`dødbånd ${num(t.alarm_deadband)}`);
  if (t.alarm_delay_s) parts.push(`${num(t.alarm_delay_s)} s forsinkelse`);
  return parts.join(' · ');
}

export interface AlarmForm { hh: string; h: string; l: string; ll: string; deadband: string; delay: string; on: '' | 'true' | 'false'; priority: '' | AlarmPriority; consequence: string; action: string; responseMin: string }

export function formFrom(t: Partial<TagAlarm>): AlarmForm {
  const s = (v: number | null | undefined) => (v == null ? '' : String(v));
  return { hh: s(t.alarm_hh), h: s(t.alarm_h), l: s(t.alarm_l), ll: s(t.alarm_ll), deadband: s(t.alarm_deadband || null), delay: s(t.alarm_delay_s || null), on: t.alarm_on ?? '', priority: t.alarm_priority ?? '',
    consequence: t.alarm_consequence ?? '', action: t.alarm_action ?? '', responseMin: s(t.alarm_response_min) };
}

/** Tal fra et felt: tomt (også kun mellemrum) = null; komma eller punktum; ellers en fejl med feltets navn. */
function parse(v: string, label: string): number | null {
  const t = v.trim().replace(',', '.');
  if (!t) return null;
  const n = Number(t);
  if (!Number.isFinite(n)) throw new Error(`${label} skal være et tal`);
  return n;
}

/** Konsekvens/handling/svartid som PATCH-felter: tomt = null; fejl med feltets navn. */
export function rationale(f: Pick<AlarmForm, 'consequence' | 'action' | 'responseMin'>): Pick<TagAlarm, 'alarm_consequence' | 'alarm_action' | 'alarm_response_min'> {
  const text = (v: string | undefined, label: string): string | null => {
    const t = (v ?? '').trim().replace(/ {2,}/g, ' ');
    if (charCount(t) > RATIONALE_MAX) throw new Error(`${label} må højst være ${RATIONALE_MAX} tegn`);
    return t || null;
  };
  const m = (f.responseMin ?? '').trim();
  let minutes: number | null = null;
  if (m) {
    minutes = /^\d+$/.test(m) ? Number(m) : NaN;
    if (!(minutes >= 0 && minutes <= 1440)) throw new Error('Svartid skal være et helt antal minutter fra 0 til 1440');
  }
  return { alarm_consequence: text(f.consequence, 'Konsekvens'), alarm_action: text(f.action, 'Handling'), alarm_response_min: minutes };
}

/** Dæmpede linjer under en aktiv alarm: handling, konsekvens og svartid — kun dem der er sat (0 min er sat). */
export function rationaleLines(a: { consequence?: string | null; action?: string | null; response_min?: number | null }): string[] {
  const out: string[] = [];
  if (a.action) out.push(`Handling: ${a.action}`);
  if (a.consequence) out.push(`Konsekvens: ${a.consequence}`);
  if (a.response_min !== null && a.response_min !== undefined) out.push(`Svar inden ${a.response_min} min`);
  return out;
}

/**
 * Formularen som PATCH-data til /api/tags/{navn}. Til/fra-tag: kun til/fra-alarm og forsinkelse (grænserne ryddes);
 * tal-tag: grænser, dødbånd og forsinkelse (til/fra-alarmen ryddes). Serveren kontrollerer rækkefølgen af grænserne.
 */
export function alarmPayload(f: AlarmForm, kind: 'bool' | 'num'): { data: Partial<TagAlarm> } | { error: string } {
  try {
    const why = rationale(f);
    const delay = parse(f.delay, 'Forsinkelse') ?? 0;
    if (delay < 0) throw new Error('Forsinkelse kan ikke være negativ');
    if (kind === 'bool') {
      return { data: { alarm_on: f.on || null, alarm_hh: null, alarm_h: null, alarm_l: null, alarm_ll: null, alarm_delay_s: delay, alarm_priority: f.priority || null, ...why } };
    }
    const deadband = parse(f.deadband, 'Dødbånd') ?? 0;
    if (deadband < 0) throw new Error('Dødbånd kan ikke være negativt');
    return { data: { alarm_hh: parse(f.hh, 'HH'), alarm_h: parse(f.h, 'H'), alarm_l: parse(f.l, 'L'), alarm_ll: parse(f.ll, 'LL'),
      alarm_deadband: deadband, alarm_delay_s: delay, alarm_on: null, alarm_priority: f.priority || null, ...why } };
  } catch (e) {
    return { error: (e as Error).message };
  }
}

/** Status ud fra alarm:<tag>:active / :unack. undefined = ukendt (fx ingen alarm på tagget). */
export function alarmStatus(active: unknown, unack: unknown): { text: string; level: 'none' | 'active' | 'unack' | 'unknown' } {
  if (active === undefined && unack === undefined) return { text: '—', level: 'unknown' };
  if (active === true && unack === true) return { text: 'Aktiv — ukvitteret', level: 'unack' };
  if (active === true) return { text: 'Aktiv — kvitteret', level: 'active' };
  if (unack === true) return { text: 'Ophørt — ukvitteret', level: 'unack' };
  return { text: 'Ingen alarm', level: 'none' };
}
