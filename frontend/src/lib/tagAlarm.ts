// Alarmer i symbolguiden (v0.74.0): tag-alarmens opsætning som kort tekst, formularen til at rette den, og status.

export interface TagAlarm {
  alarm_hh: number | null; alarm_h: number | null; alarm_l: number | null; alarm_ll: number | null;
  alarm_deadband: number | null; alarm_delay_s: number | null; alarm_on: 'true' | 'false' | null;
}

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

export interface AlarmForm { hh: string; h: string; l: string; ll: string; deadband: string; delay: string; on: '' | 'true' | 'false' }

export function formFrom(t: Partial<TagAlarm>): AlarmForm {
  const s = (v: number | null | undefined) => (v == null ? '' : String(v));
  return { hh: s(t.alarm_hh), h: s(t.alarm_h), l: s(t.alarm_l), ll: s(t.alarm_ll), deadband: s(t.alarm_deadband || null), delay: s(t.alarm_delay_s || null), on: t.alarm_on ?? '' };
}

/** Tal fra et felt: tomt (også kun mellemrum) = null; komma eller punktum; ellers en fejl med feltets navn. */
function parse(v: string, label: string): number | null {
  const t = v.trim().replace(',', '.');
  if (!t) return null;
  const n = Number(t);
  if (!Number.isFinite(n)) throw new Error(`${label} skal være et tal`);
  return n;
}

/**
 * Formularen som PATCH-data til /api/tags/{navn}. Til/fra-tag: kun til/fra-alarm og forsinkelse (grænserne ryddes);
 * tal-tag: grænser, dødbånd og forsinkelse (til/fra-alarmen ryddes). Serveren kontrollerer rækkefølgen af grænserne.
 */
export function alarmPayload(f: AlarmForm, kind: 'bool' | 'num'): { data: Partial<TagAlarm> } | { error: string } {
  try {
    const delay = parse(f.delay, 'Forsinkelse') ?? 0;
    if (delay < 0) throw new Error('Forsinkelse kan ikke være negativ');
    if (kind === 'bool') {
      return { data: { alarm_on: f.on || null, alarm_hh: null, alarm_h: null, alarm_l: null, alarm_ll: null, alarm_delay_s: delay } };
    }
    const deadband = parse(f.deadband, 'Dødbånd') ?? 0;
    if (deadband < 0) throw new Error('Dødbånd kan ikke være negativt');
    return { data: { alarm_hh: parse(f.hh, 'HH'), alarm_h: parse(f.h, 'H'), alarm_l: parse(f.l, 'L'), alarm_ll: parse(f.ll, 'LL'),
      alarm_deadband: deadband, alarm_delay_s: delay, alarm_on: null } };
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
