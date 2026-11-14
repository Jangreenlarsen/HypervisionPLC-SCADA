// Forbindelsesgrupper (v6.1.0, backend services/connection_groups.py): hvordan tegningens forbindelser viser det beregnede flow.
// Rene typer og hjælpere — testet i connGroups.test.ts.

export type ConnAnimType = 'flow' | 'color' | 'blink' | 'fixed';
export interface Limit { value: number; color: string }
export interface ConnAnim {
  type: ConnAnimType;
  light?: string; base?: string; speed?: number; dash?: number; full?: number; stopped?: string;
  off?: string; limits?: Limit[];
  at_least?: number | null; at_most?: number | null; rate?: 'slow' | 'normal' | 'fast';
  color?: string;
}
export interface ConnGroup { id: number; name: string; members: string[]; missing?: string[]; anims: ConnAnim[] }
export interface ConnList {
  default: { anims: ConnAnim[]; members: string[] };
  groups: ConnGroup[];
  connections: { id: string; name: string }[];
  flow?: { unbound: boolean; notes: string[]; stats: { nodes: number; edges: number; pumps: number; pumping: number } | null };
}

export const CONN_ANIM_TXT: Record<ConnAnimType, string> = {
  flow: 'Løbelys (retning og fart efter flowet)', color: 'Farve efter flow', blink: 'Blink ved et flow', fixed: 'Fast farve',
};
export const MAX_CONN_ANIMS = 4;

/** En ny animation med fornuftige standarder (som backend ConnAnim). */
export function newConnAnim(type: ConnAnimType): ConnAnim {
  switch (type) {
    case 'flow': return { type, light: '#8fc8ea', base: '#555555', speed: 60, dash: 12, full: 0 };
    case 'color': return { type, off: '#9e9e9e', limits: [{ value: 1, color: '#1e88e5' }] };
    case 'blink': return { type, at_most: 0, at_least: null, rate: 'normal' };
    default: return { type, color: '#1e88e5' };
  }
}

/** Kort beskrivelse til listen. */
export function describeConnAnims(anims: ConnAnim[]): string {
  if (!anims.length) return 'ingen animation';
  return anims.map((a) => {
    if (a.type === 'flow') return 'løbelys';
    if (a.type === 'color') return `farve (${(a.limits ?? []).map((l) => `≥ ${l.value}`).join(', ') || 'ingen grænser'})`;
    if (a.type === 'blink') return a.at_least != null ? `blink ved ≥ ${a.at_least} l/min` : `blink ved ≤ ${a.at_most ?? 0} l/min`;
    return 'fast farve';
  }).join(' + ');
}

/** De valgte elementer, der er forbindelser (rør og rørstykker) — kun de kan være i en gruppe. */
export const pickConnections = (selected: string[], all: { id: string }[]): string[] => {
  const ok = new Set(all.map((c) => c.id));
  return [...new Set(selected.filter((id) => ok.has(id)))];
};

// ---------------------------------------------------------------- Til og Fra (v6.12.0)
// Jan: "en general config af de animationer for on/off som forbindelser skal bruge". Til = der er flow, Fra = intet flow. Gemmes
// som de samme animationer som før (ingen migration); en liste, der ikke kan vises som Til/Fra, redigeres under *Avanceret*.

/** "Til" = mindst så meget flow (l/min; flowet afrundes til 0,1). */
export const ON_MIN = 0.1;
export type Rate = 'slow' | 'normal' | 'fast';
export interface OnOff {
  on: { show: 'flow' | 'color' | 'none'; light: string; base: string; speed: number; full: number; color: string; blink: boolean; rate: Rate };
  off: { color: string; blink: boolean; rate: Rate };     // color '' = som tegnet
}

export function defaultOnOff(): OnOff {
  const f = newConnAnim('flow');
  return {
    on: { show: 'flow', light: f.light!, base: f.base!, speed: f.speed!, full: f.full!, color: '#1e88e5', blink: false, rate: 'normal' },
    off: { color: '', blink: false, rate: 'normal' },
  };
}

/** Animationerne som Til/Fra — eller null, hvis de ikke kan vises sådan (fx flere farvegrænser, fast farve). */
export function toOnOff(anims: ConnAnim[]): OnOff | null {
  const m = defaultOnOff();
  m.on.show = 'none';
  let shown = false, blinked = false;
  for (const a of anims) {
    if (a.type === 'flow' || a.type === 'color') {
      if (shown) return null;
      shown = true;
      if (a.type === 'flow') {
        const f = { ...newConnAnim('flow'), ...a };
        Object.assign(m.on, { show: 'flow', light: f.light, base: f.base, speed: f.speed, full: f.full });
        m.off.color = f.stopped ?? '';
      } else {
        const lim = a.limits ?? [];
        if (lim.length !== 1 || lim[0].value > 1) return null;
        m.on.show = lim[0].color ? 'color' : 'none';
        if (lim[0].color) m.on.color = lim[0].color;
        m.off.color = a.off ?? '';
      }
    } else if (a.type === 'blink') {
      if (blinked) return null;
      blinked = true;
      const rate = a.rate ?? 'normal';
      if (a.at_least != null && a.at_least === 0) { m.on.blink = m.off.blink = true; m.on.rate = m.off.rate = rate; }
      else if (a.at_least != null && a.at_least <= 1) { m.on.blink = true; m.on.rate = rate; }
      else if (a.at_most === 0) { m.off.blink = true; m.off.rate = rate; }
      else return null;
    } else return null;
  }
  return m;
}

/** Til/Fra → animationerne, der gemmes. Blink i både Til og Fra er ét blink altid (Til-afsnittets fart). */
export function fromOnOff(m: OnOff): ConnAnim[] {
  const out: ConnAnim[] = [];
  if (m.on.show === 'flow') {
    out.push({ type: 'flow', light: m.on.light, base: m.on.base, speed: m.on.speed, dash: 12, full: m.on.full, stopped: m.off.color });
  } else if (m.on.show === 'color' || m.off.color) {
    out.push({ type: 'color', off: m.off.color, limits: [{ value: ON_MIN, color: m.on.show === 'color' ? m.on.color : '' }] });
  }
  if (m.on.blink && m.off.blink) out.push({ type: 'blink', at_least: 0, at_most: null, rate: m.on.rate });
  else if (m.on.blink) out.push({ type: 'blink', at_least: ON_MIN, at_most: null, rate: m.on.rate });
  else if (m.off.blink) out.push({ type: 'blink', at_most: 0, at_least: null, rate: m.off.rate });
  return out;
}

/** Kort Til/Fra-tekst til listen (falder tilbage til animationslisten). */
export function describeOnOff(anims: ConnAnim[]): string {
  const m = toOnOff(anims);
  if (!m) return `avanceret: ${describeConnAnims(anims)}`;
  const on = m.on.show === 'flow' ? 'løbelys' : m.on.show === 'color' ? 'farve' : 'som tegnet';
  const off = m.off.color ? 'farve' : 'som tegnet';
  return `Til: ${on}${m.on.blink ? ' + blink' : ''} · Fra: ${off}${m.off.blink ? ' + blink' : ''}`;
}

/** Grænserne skal være stigende (som backend). → fejltekst eller null */
export function connAnimError(a: ConnAnim): string | null {
  if (a.type === 'color') {
    const v = (a.limits ?? []).map((l) => l.value);
    if (v.some((x, i) => i > 0 && x < v[i - 1])) return 'Grænserne skal være stigende';
  }
  if (a.type === 'blink' && a.at_least == null && a.at_most == null) return 'Blink kræver en grænse';
  if (a.type === 'flow' && ((a.speed ?? 0) < 5 || (a.speed ?? 0) > 500)) return 'Farten skal være 5–500';
  return null;
}
