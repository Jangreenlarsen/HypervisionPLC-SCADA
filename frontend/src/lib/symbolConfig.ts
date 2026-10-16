// Symbol-guiden (symbolstandarden): datamodel og ren logik — testet i symbolConfig.test.ts.
// Reference: prototypens `template`, `preset`, `structural`, `activeAt`, `typesFor`, `animDefaults`, `remotePos`.
// Valideringen er serverens (POST …/preview) — her er kun struktur og forslag.

export type Op = 'positions' | 'pulse' | 'entry' | 'view';
export type AnimType = 'fill' | 'stroke' | 'blink' | 'visible' | 'spin' | 'level' | 'opacity' | 'text' | 'rotate' | 'move' | 'flow';
export type SrcKind = 'pos' | 'bool' | 'num';

export interface Signal { id: string; tag: string; fb: string; write: 'set' | 'pulse'; ms: number; rest: number | null }
export interface Plane { signal: string; values: (number | null)[] }
export interface Anim { part: string; type: AnimType; src: string; params: Record<string, any>; only: boolean[] | null }
export type Cmp = '' | 'ge' | 'le' | 'eq';
/** Én indgang til en logikblok: et tag (til/fra, eller et tal sammenlignet med en grænse) eller en tidligere blok (`@L1`). */
export interface LogicInput { src: string; neg: boolean; cmp: Cmp; value: number | null }
/** En logikblok i et ANDET symbol på tegningen, som kan bruges som kilde: `@<symbol>:<blok>`. */
export interface PoolBlock { element: string; symbol: string; id: string; name: string }
export interface LogicBlock { id: string; name: string; op: 'and' | 'or'; inputs: LogicInput[]; invert: boolean }
export interface SymbolConfig {
  type: string; op: Op; positions: { label: string }[]; signals: Signal[]; planes: Plane[]; fault: string;
  display: 'remote' | 'local'; validate_s: number; alarm: '' | 'low' | 'medium' | 'high'; confirm: boolean; pulse_ms: number;
  lock: { positions: boolean[]; leave: boolean }; anims: Anim[]; logic: LogicBlock[];
}
export interface PartInfo { tag: string; line: boolean; pid?: string | null }
export interface SymbolInfo extends PartInfo { type: string; name: string | null; parts: Record<string, PartInfo> }

export const POS = '@pos';
export const MAX_POSITIONS = 8, MAX_PLANES = 8, MAX_ANIMS = 12, MAX_LOGIC = 8, MAX_LOGIC_INPUTS = 4;

export const STEPS = ['Symbol', 'Signaler', 'Kontakter', 'Visning', 'Betjening', 'Test og gem'];
export const OP_TXT: Record<Op, string> = { view: 'Kun visning', positions: 'Positioner', pulse: 'Trykknap (puls)', entry: 'Setpunkt (indtastning)' };
export const ALARM_TXT: Record<string, string> = { '': 'Nej', low: 'Ja — lav', medium: 'Ja — medium', high: 'Ja — høj' };
export const ANIM_TXT: Record<AnimType, string> = {
  fill: 'Farve', stroke: 'Stregfarve', blink: 'Blink', visible: 'Synlig', spin: 'Roterer', level: 'Niveau',
  opacity: 'Gennemsigtighed', text: 'Værdi', rotate: 'Drej', move: 'Flyt', flow: 'Løbelys',
};
export const BLINK_TXT: Record<string, string> = { slow: 'Langsom (0,5 Hz)', normal: 'Normal (1 Hz)', fast: 'Hurtig (2 Hz)' };

/** Danske navne på bibliotekets dele (data-hv-pid). Ukendte vises med deres eget navn. */
export const PART_LABEL: Record<string, string> = {
  greb: 'Greb', vippe: 'Vippe', spor: 'Spor', flade: 'Knap', tekst: 'Tekst', vaerdi: 'Værdi', status: 'Status',
  felt: 'Felt', port_a: 'Port A', port_b: 'Port B', port_ab: 'Port AB', motor: 'Motor',
  lampe: 'Lampe', fyld: 'Fyld', soejle: 'Søjle', rotor: 'Rotor', flamme: 'Flamme', viser: 'Viser', skive: 'Skive',
};

export function partLabel(id: string, info: SymbolInfo | null): string {
  if (id === 'all') return 'Hele symbolet';
  const pid = info?.parts[id]?.pid;
  if (pid) return PART_LABEL[pid] ?? pid;
  return id;
}

/**
 * Forslag til et nyt symbol ud fra biblioteket (kun når symbolet ikke er konfigureret og ikke kan konverteres).
 * 3-vejs motorventil: to positioner, AB → A og AB → B; AB er altid åben, og A eller B er åben efter positionen.
 * Statusfelt: farven følger et register (vælg tagget i trin 4).
 */
export function libraryDefault(symbol: SymbolInfo | null): { config: SymbolConfig; note: string } | null {
  if (!symbol) return null;
  const partOf = (pid: string) => Object.entries(symbol.parts).find(([, p]) => p.pid === pid)?.[0];
  const cfg = emptyConfig(symbol.type);
  if (symbol.type === 'trevejs_motorventil' || symbol.type === 'trevejs_motorventil_ab') {
    cfg.positions = [{ label: 'AB → A' }, { label: 'AB → B' }];
    setOp(cfg, 'positions');
    cfg.display = 'remote';
    const OPEN = '#7cc47f', CLOSED = '#ffffff';
    const colors: [string, string[]][] = [['port_a', [OPEN, CLOSED]], ['port_b', [CLOSED, OPEN]], ['port_ab', [OPEN, OPEN]]];
    for (const [pid, cols] of colors) {
      const part = partOf(pid);
      if (part) cfg.anims.push({ part, type: 'fill', src: POS, params: { colors: cols }, only: null });
    }
    return { config: cfg, note: 'Forslag fra symbolbiblioteket: to positioner (AB → A og AB → B) med farver pr. port. Vælg tag under trin 2.' };
  }
  if (symbol.type === 'statusfelt') {
    const part = partOf('felt');
    if (!part) return null;
    cfg.anims.push({ part, type: 'fill', src: '', params: { ...animDefaults('fill', 'num', 0), off: '#e4e4e4' }, only: null });
    return { config: cfg, note: 'Forslag fra symbolbiblioteket: feltets farve følger et register. Vælg registeret og grænserne under trin 4.' };
  }
  return null;
}

/** Til/fra, tal eller ukendt (ST-variabler kendes først fra live-værdien) ud fra tagets kilde `plc:type:adr[:datatype]`. */
export function tagKind(source: string | undefined): 'bool' | 'num' | 'unknown' {
  if (!source) return 'unknown';
  const parts = source.split(':');
  const kind = parts[1];
  if (kind === 'coil' || kind === 'di') return 'bool';
  if (kind === 'logic' || kind === 'global') return 'unknown';
  return parts[parts.length - 1] === 'bool' ? 'bool' : 'num';
}

export function emptyConfig(type = 'custom'): SymbolConfig {
  return {
    type, op: 'view', positions: [], signals: [], planes: [], fault: '', display: 'remote', validate_s: 5, alarm: 'medium',
    confirm: true, pulse_ms: 500, lock: { positions: [], leave: false }, anims: [], logic: [],
  };
}

export function newSignal(cfg: SymbolConfig, tag = '', fb = ''): Signal {
  let i = 1;
  while (cfg.signals.some((s) => s.id === `S${i}`)) i++;
  return { id: `S${i}`, tag, fb, write: 'set', ms: 500, rest: null };
}

export const CMP_TXT: Record<string, string> = { ge: '≥', le: '≤', eq: '=' };

/** `@L1` — animationens kilde er en logikblok (`@pos` er positionen). */
export const isLogicRef = (src: string): boolean => src.startsWith('@') && src !== POS;

export function newBlock(cfg: SymbolConfig): LogicBlock {
  let i = 1;
  while (cfg.logic.some((b) => b.id === `L${i}`)) i++;
  return { id: `L${i}`, name: '', op: 'and', inputs: [{ src: '', neg: false, cmp: '', value: null }, { src: '', neg: false, cmp: '', value: null }], invert: false };
}

/** Fjern en blok; indgange og animationer der brugte den bliver tomme (serveren melder dem som manglende valg). */
export function removeBlock(cfg: SymbolConfig, id: string): void {
  cfg.logic = cfg.logic.filter((b) => b.id !== id);
  for (const b of cfg.logic) for (const i of b.inputs) if (i.src === `@${id}`) i.src = '';
  for (const a of cfg.anims) if (a.src === `@${id}`) a.src = '';
}

/** Blokkens formel som tekst, fx `Pumpe AND NOT Alarm` — til oversigt og test. */
export function describeBlock(b: LogicBlock): string {
  const parts = b.inputs.map((i) => {
    const what = !i.src ? '?' : isLogicRef(i.src) ? i.src.slice(1) : i.cmp ? `${i.src} ${CMP_TXT[i.cmp]} ${i.value ?? '?'}` : i.src;
    return i.neg ? `NOT ${what}` : what;
  });
  const body = parts.join(b.op === 'or' ? ' OR ' : ' AND ');
  return b.invert ? `NOT (${body})` : body;
}

/**
 * Logikblokkene ud fra live-værdier (som serverens `evaluate_logic`): tre-værdi-logik — en afgørende indgang vinder
 * (AND med en Fra = Fra, OR med en Til = Til), ellers er resultatet ukendt (null). `valueOf` giver undefined/null for ukendt.
 */
export function evalLogic(
  blocks: LogicBlock[], valueOf: (tag: string) => unknown, foreign: (ref: string) => boolean | null = () => null,
): Record<string, boolean | null> {
  const out: Record<string, boolean | null> = {};
  for (const b of blocks) {
    const vals = b.inputs.map((i): boolean | null => {
      let v: boolean | null;
      if (isLogicRef(i.src)) v = i.src.includes(':') ? foreign(i.src) : out[i.src.slice(1)] ?? null;   // @symbol:L1 = blok i et andet symbol
      else {
        const raw = valueOf(i.src);
        if (typeof raw === 'boolean') v = raw;
        else if (typeof raw !== 'number' || !Number.isFinite(raw)) v = null;
        else if (!i.cmp || i.value === null) v = raw !== 0;
        else v = i.cmp === 'ge' ? raw >= i.value : i.cmp === 'le' ? raw <= i.value : Math.abs(raw - i.value) <= 1e-9 * Math.max(1, Math.abs(i.value));
      }
      return v === null ? null : i.neg ? !v : v;
    });
    let r: boolean | null;
    if (!vals.length) r = null;
    else if (b.op === 'or') r = vals.some((v) => v === true) ? true : vals.every((v) => v === false) ? false : null;
    else r = vals.some((v) => v === false) ? false : vals.every((v) => v === true) ? true : null;
    out[b.id] = r !== null && b.invert ? !r : r;
  }
  return out;
}

/** Hvilke animationer en del kan have — efter delens geometri (samme regel som serveren). */
export function typesFor(part: PartInfo | undefined): AnimType[] {
  const t: AnimType[] = ['fill', 'stroke', 'blink', 'visible', 'spin', 'rotate', 'move', 'opacity'];
  if (part?.tag === 'rect') t.push('level');
  if (part?.tag === 'text' || part?.tag === 'tspan') t.push('text');
  if (part?.line) t.push('flow');
  return t;
}

/** Standardparametre for en animation ud fra kilden (prototypens animDefaults). */
export function animDefaults(type: AnimType, kind: SrcKind, n: number): Record<string, any> {
  const spread = (lo: number, hi: number) => Array.from({ length: n }, (_, j) => (n > 1 ? Math.round(lo + ((hi - lo) * j) / (n - 1)) : 0));
  switch (type) {
    case 'fill':
    case 'stroke':
      if (kind === 'pos') return { colors: n === 2 ? ['#d6d6d6', '#7cc47f'] : Array.from({ length: n }, () => '#e4e4e4') };
      if (kind === 'bool') return { on: '#2e7d32', off: '#9e9e9e' };
      return { off: '#9e9e9e', thresholds: [{ value: 50, color: '#b26a00' }, { value: 80, color: '#c62828' }] };
    case 'blink':
    case 'visible':
    case 'spin': {
      const base = kind === 'pos' ? { set: Array.from({ length: n }, (_, j) => j > 0) } : kind === 'num' ? { at_least: 50 } : { invert: false };
      return type === 'blink' ? { ...base, speed: 'normal' } : base;
    }
    case 'level':
      return { min: 0, max: 100, direction: 'up' };
    case 'opacity':
      return { min: 0, max: 100 };
    case 'text':
      return {};
    case 'rotate':
      if (kind === 'pos') return { angles: spread(-45, 45) };
      return kind === 'bool' ? { min: 0, max: 1, angle_min: 0, angle_max: 90 } : { min: 0, max: 100, angle_min: -120, angle_max: 120 };
    case 'move':
      if (kind === 'pos') return { dxs: Array.from({ length: n }, (_, j) => j * 20), dys: Array.from({ length: n }, () => 0) };
      return kind === 'bool' ? { min: 0, max: 1, dx: 20, dy: 0 } : { min: 0, max: 100, dx: 40, dy: 0 };
    case 'flow': {
      const base = { mode: kind === 'num' ? 'code' : 'onoff', reverse: false, base: '#555555', light: '#8fc8ea', speed: 40, dash: 12,
        arm: '', arm_flow: 'in', dir_tag: '' };
      return kind === 'pos' ? { ...base, dirs: Array.from({ length: n }, (_, j) => (j === 0 ? 0 : 1)) } : base;
    }
  }
}

/**
 * Positionerne er ændret (antal): alle arrays følger med (prototypens `structural`) — planernes celler (nye: Fra for
 * til/fra-signaler, "røres ikke" for registre), låste positioner, "gælder i positionerne" og værdier pr. position.
 */
export function resize(cfg: SymbolConfig, kindOf: (signalId: string) => 'bool' | 'num' | 'unknown'): void {
  const n = cfg.positions.length;
  const fit = <T>(list: T[], fill: (j: number) => T): T[] => Array.from({ length: n }, (_, j) => (j < list.length ? list[j] : fill(j)));
  for (const p of cfg.planes) p.values = fit(p.values, () => (kindOf(p.signal) === 'bool' ? 0 : null));
  cfg.lock.positions = fit(cfg.lock.positions, () => false);
  for (const a of cfg.anims) {
    if (a.only) a.only = fit(a.only, () => true);
    const p = a.params;
    if (Array.isArray(p.colors)) p.colors = fit(p.colors, () => '#e4e4e4');
    if (Array.isArray(p.set)) p.set = fit(p.set, () => false);
    for (const k of ['angles', 'dxs', 'dys', 'dirs']) if (Array.isArray(p[k])) p[k] = fit(p[k], () => 0);
  }
}

/** Skabeloner for kontaktplanerne (prototypens `template`). Signalerne beholdes hvor de passer; tags vælges bagefter. */
export function template(cfg: SymbolConfig, t: 'A' | 'B' | 'C' | 'D'): void {
  const n = cfg.positions.length;
  const ensure = (count: number): Signal[] => {
    while (cfg.signals.length < count) cfg.signals.push(newSignal(cfg));
    return cfg.signals.slice(0, count);
  };
  if (t === 'A') cfg.planes = [{ signal: ensure(1)[0].id, values: cfg.positions.map((_, j) => j) }];
  if (t === 'C') cfg.planes = [{ signal: ensure(1)[0].id, values: cfg.positions.map((_, j) => 1 << j) }];
  if (t === 'B') {
    const sigs = ensure(n);
    cfg.planes = sigs.map((s, i) => ({ signal: s.id, values: cfg.positions.map((_, j) => (i === j ? 1 : 0)) }));
  }
  if (t === 'D') {
    const off = cfg.positions[0]?.label.trim() === '0' ? 0 : 1;   // står første position for 0, tælles fra 0
    const bits = Math.max(1, Math.ceil(Math.log2(n - 1 + off + 1)));
    const sigs = ensure(bits);
    cfg.planes = sigs.map((s, b) => ({ signal: s.id, values: cfg.positions.map((_, j) => ((j + off) >> b) & 1) }));
  }
  for (const s of cfg.signals) if (s.write === 'pulse' && t !== 'A') s.write = 'set';
}

/** Eksemplet "7-trins vælger, dec → bin": 7 positioner, 3 signaler, 3 kontaktplaner (prototypens `preset`). */
export function preset(cfg: SymbolConfig): void {
  cfg.op = 'positions';
  cfg.positions = Array.from({ length: 7 }, (_, j) => ({ label: String(j + 1) }));
  cfg.signals = [];
  template(cfg, 'D');
  cfg.lock = { positions: Array(7).fill(false), leave: false };
  cfg.anims = cfg.anims.filter((a) => a.src !== POS);
}

/** Det position j sætter (prototypens `activeAt`): til/fra-signaler der er Til, og registre med deres værdi. */
export function activeAt(cfg: SymbolConfig, j: number, kindOf: (signalId: string) => 'bool' | 'num' | 'unknown'): string[] {
  const out: string[] = [];
  for (const p of cfg.planes) {
    const v = p.values[j];
    if (v === null || v === undefined || !cfg.signals.some((s) => s.id === p.signal)) continue;
    if (kindOf(p.signal) === 'bool') {
      if (Number(v) === 1) out.push(p.signal);
    } else out.push(`${p.signal}=${v}`);
  }
  return out;
}

/** Kontaktdiagrammets celle for et til/fra-signal: Til → Fra → røres ikke → Til. */
export const cycleCell = (v: number | null): number | null => (v === 1 ? 0 : v === 0 ? null : 1);

/** Fundet position ud fra live-værdier (som serverens `remote_position`) — til guidens trin 6. */
export function foundPosition(cfg: SymbolConfig, valueOf: (tag: string) => unknown): number | null {
  const sigs = new Map(cfg.signals.map((s) => [s.id, s]));
  const hits: number[] = [];
  for (let j = 0; j < cfg.positions.length; j++) {
    let ok = true, used = 0;
    for (const p of cfg.planes) {
      const s = sigs.get(p.signal);
      const cell = p.values[j];
      if (!s || !s.tag || s.write === 'pulse' || cell === null || cell === undefined) continue;
      used++;
      const v = valueOf(s.fb || s.tag);
      const n = typeof v === 'boolean' ? (v ? 1 : 0) : typeof v === 'number' ? v : NaN;
      if (Math.abs(n - Number(cell)) > 1e-6) ok = false;
    }
    if (ok && used) hits.push(j);
  }
  return hits.length === 1 ? hits[0] : null;
}

/** Skift betjeningsform (prototypens `setOp`): nulstil det der ikke giver mening for den nye form. */
export function setOp(cfg: SymbolConfig, op: Op): void {
  cfg.op = op;
  if (op === 'positions') {
    if (cfg.positions.length < 2) cfg.positions = [{ label: 'Fra' }, { label: 'Til' }];
    if (!cfg.signals.length) cfg.signals = [newSignal(cfg)];
    if (!cfg.planes.length) cfg.planes = [{ signal: cfg.signals[0].id, values: cfg.positions.map((_, j) => (j === 0 ? 0 : 1)) }];
    cfg.lock.positions = cfg.positions.map((_, j) => cfg.lock.positions[j] ?? false);
  } else {
    cfg.positions = [];
    cfg.planes = [];
    cfg.lock = { positions: [], leave: false };
    cfg.signals = op === 'view' ? [] : [cfg.signals[0] ?? newSignal(cfg)].map((s) => ({ ...s, fb: '', write: 'set', rest: null }));
    cfg.anims = cfg.anims.filter((a) => a.src !== POS).map((a) => ({ ...a, only: null }));
  }
}
