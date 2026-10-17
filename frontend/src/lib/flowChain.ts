// Sammenhængende løbelys (v0.64.0): løbelys-dele (et rør, en bøjning, et ben i et T-stykke), hvis ender rører hinanden,
// danner et FORLØB. Langs forløbet tælles én fælles koordinat g (i tegningens enheder), og hver del får sin stiplings-
// forskydning ud fra den — så lys og mørke fortsætter hen over samlingerne. Retningen ensrettes inden for forløbet, så et
// rør der er tegnet "baglæns" ikke kører imod sine naboer. Rene beregninger — målingen i tegningen sker i animate.ts.

export type Pt = [number, number];

export interface Piece {
  key: string;
  /** Start- og slutpunkt langs delens egen tegneretning (tegningens koordinater). */
  a: Pt;
  b: Pt;
  /** Længde i tegningens enheder (målt langs stregen; for en bue længere end afstanden a–b). */
  len: number;
  /** Kun dele i samme gruppe (samme tag og samme løbelys-indstillinger) kan danne forløb. */
  group: string;
  /** Den indstillede retning langs delens tegneretning: 1 = frem, -1 = "Vend retning", 0 = fast (fx et ben i et T-stykke). */
  dir: 1 | -1 | 0;
  /** Delens indstillede lyslængde og fart (tegningens enheder) — forløbet bruger den, flest dele har. */
  dash: number;
  speed: number;
}

export interface Phase {
  /** Forløbets koordinat i delens startpunkt. */
  g0: number;
  /** 1: g vokser langs delens tegneretning; -1: g falder. */
  orient: 1 | -1;
  /** true: delen skal køre modsat sin indstilling for at følge forløbets retning. */
  flip: boolean;
  /** Forløbets fælles lyslængde og fart (flertallet; uafgjort → den første del). */
  dash: number;
  speed: number;
}

const dist = (p: Pt, q: Pt) => Math.hypot(p[0] - q[0], p[1] - q[1]);

/**
 * Forløb og koordinater for alle dele. `tol`: hvor tæt to ender skal være for at hænge sammen. Dele uden nabo får
 * g0 = 0 / orient 1 / flip false (som før). Rækkefølgen af `pieces` bestemmer, hvilken del der er udgangspunkt (stabilt).
 */
export function chainPhases(pieces: Piece[], tol: number): Map<string, Phase> {
  const out = new Map<string, Phase>();
  const usable = pieces.filter((p) => p.len > 0 && [...p.a, ...p.b].every(Number.isFinite));
  // Naboer: (anden del, mit endepunkt 'a'|'b', dens endepunkt 'a'|'b')
  type Link = { j: number; mine: 'a' | 'b'; theirs: 'a' | 'b' };
  const links: Link[][] = usable.map(() => []);
  // En ende kobles kun til de NÆRMESTE ender inden for tolerancen (fx et kort rør mellem et T-stykke og en bøjning: T-stykket
  // og bøjningen er inden for tolerancen af hinanden, men hver har det korte rør tættere på). Flere ender i samme punkt
  // (et kryds) kobles alle.
  const SLACK = 1;
  const near: { i: number; mine: 'a' | 'b'; j: number; theirs: 'a' | 'b'; d: number }[] = [];
  const best = new Map<string, number>();
  const bump = (k: string, d: number) => best.set(k, Math.min(best.get(k) ?? Infinity, d));
  for (let i = 0; i < usable.length; i++) {
    for (let j = i + 1; j < usable.length; j++) {
      if (usable[i].group !== usable[j].group) continue;
      for (const mine of ['a', 'b'] as const) {
        for (const theirs of ['a', 'b'] as const) {
          const d = dist(usable[i][mine], usable[j][theirs]);
          if (d > tol) continue;
          near.push({ i, mine, j, theirs, d });
          bump(`${i}${mine}`, d);
          bump(`${j}${theirs}`, d);
        }
      }
    }
  }
  for (const { i, mine, j, theirs, d } of near) {
    if (d > best.get(`${i}${mine}`)! + SLACK || d > best.get(`${j}${theirs}`)! + SLACK) continue;
    links[i].push({ j, mine, theirs });
    links[j].push({ j: i, mine: theirs, theirs: mine });
  }
  const seen = new Array<boolean>(usable.length).fill(false);
  for (let root = 0; root < usable.length; root++) {
    if (seen[root]) continue;
    // Bredde-først gennem forløbet: delens interval på g og dens orientering
    const lo = new Map<number, number>(), orient = new Map<number, 1 | -1>();
    const order: number[] = [];
    seen[root] = true;
    lo.set(root, 0);
    orient.set(root, 1);
    const queue = [root];
    while (queue.length) {
      const i = queue.shift()!;
      order.push(i);
      const L = usable[i].len, o = orient.get(i)!, g0 = lo.get(i)!;
      const gAt = (end: 'a' | 'b') => (end === 'a') === (o === 1) ? g0 : g0 + L;   // g i delens ende
      const isHigh = (end: 'a' | 'b') => (end === 'b') === (o === 1);               // ligger enden i intervallets top?
      for (const { j, mine, theirs } of links[i]) {
        if (seen[j]) continue;
        seen[j] = true;
        const gE = gAt(mine), Lj = usable[j].len;
        // Naboen fortsætter på den anden side af samlingen: opad hvis samlingen er min top, ellers nedad
        const up = isHigh(mine);
        const oj: 1 | -1 = (theirs === 'a') === up ? 1 : -1;
        orient.set(j, oj);
        lo.set(j, up ? gE : gE - Lj);
        queue.push(j);
      }
    }
    // Retning: flertallet af de indstillede retninger (målt på g) bestemmer; uafgjort → den første del med en retning
    let vote = 0, first = 0;
    for (const i of order) {
      const v = usable[i].dir * orient.get(i)!;
      vote += v;
      if (!first && v) first = v;
    }
    const D = vote > 0 ? 1 : vote < 0 ? -1 : first;
    // Én lyslængde og fart i hele forløbet — ellers kan mønstret ikke fortsætte over samlingerne
    const common = majority(order.map((i) => `${usable[i].dash}|${usable[i].speed}`));
    const [dash, speed] = common.split('|').map(Number);
    for (const i of order) {
      const o = orient.get(i)!, d = usable[i].dir;
      const g0 = o === 1 ? lo.get(i)! : lo.get(i)! + usable[i].len;   // g i delens START (a)
      out.set(usable[i].key, { g0, orient: o, flip: d !== 0 && D !== 0 && d * o !== D, dash, speed });
    }
  }
  for (const p of pieces) if (!out.has(p.key)) out.set(p.key, { g0: 0, orient: 1, flip: false, dash: p.dash, speed: p.speed });
  return out;
}

/** Den hyppigste værdi; uafgjort → den der kom først. */
function majority(values: string[]): string {
  const n = new Map<string, number>();
  for (const v of values) n.set(v, (n.get(v) ?? 0) + 1);
  let best = values[0], most = 0;
  for (const v of values) if (n.get(v)! > most) [best, most] = [v, n.get(v)!];
  return best;
}

/**
 * Del en SVG-sti i dens delstier, hver som en selvstændig sti der starter med et ABSOLUT M (fx et T-stykke "M0 45 H90 M45 45 V0"
 * → gennemløb og afgrening), så hver delsti kan få sin egen plads i et forløb. Relative kommandoer i en delsti er relative
 * til dens eget startpunkt og kan derfor stå uændret. → null hvis stien ikke kan læses.
 */
export function splitSubpaths(d: string): string[] | null {
  const toks = d.match(/[a-zA-Z]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/g) ?? [];
  const ARGS: Record<string, number> = { M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7, Z: 0 };
  const out: string[] = [];
  let cur: string[] = [];
  let x = 0, y = 0, sx = 0, sy = 0, i = 0, cmd = '';
  while (i < toks.length) {
    if (/[a-zA-Z]/.test(toks[i])) cmd = toks[i++];
    const C = cmd.toUpperCase(), rel = cmd !== C, n = ARGS[C];
    if (n === undefined) return null;
    const args = toks.slice(i, i + n).map(Number);
    if (args.length < n || args.some((v) => !Number.isFinite(v))) return null;
    i += n;
    if (C === 'M') {
      x = (rel ? x : 0) + args[0];
      y = (rel ? y : 0) + args[1];
      sx = x; sy = y;
      if (cur.length) out.push(cur.join(' '));
      cur = [`M${x} ${y}`];
      cmd = rel ? 'l' : 'L';   // efterfølgende talpar er linjer (SVG-reglen)
      continue;
    }
    if (!cur.length) return null;   // stien skal starte med M
    cur.push(`${cmd}${args.join(' ')}`);
    if (C === 'Z') { x = sx; y = sy; continue; }
    if (C === 'H') x = (rel ? x : 0) + args[0];
    else if (C === 'V') y = (rel ? y : 0) + args[0];
    else { x = (rel ? x : 0) + args[n - 2]; y = (rel ? y : 0) + args[n - 1]; }
  }
  if (cur.length) out.push(cur.join(' '));
  return out;
}

/**
 * Stiplingens forskydning (tegningens enheder) for en del, så mønstret "lys i [0, dash), mørk i [dash, 2·dash)" langs g
 * fortsætter hen over delen: frem langs g → g0; baglæns → dash − g0 (mønstret er symmetrisk med en halv periodes skift).
 */
export function dashOffset(phase: Pick<Phase, 'g0' | 'orient'>, dash: number): number {
  const period = 2 * dash;
  const raw = phase.orient === 1 ? phase.g0 : dash - phase.g0;
  return ((raw % period) + period) % period;
}

type XY = [number, number];
/** Delstiens kommandoer med absolutte punkter (fra splitSubpaths: starter med et absolut M). null = kan ikke læses. */
function walk(d: string): { start: XY; cmds: { raw: string; from: XY; to: XY; straight: boolean }[] } | null {
  const toks = d.match(/[a-zA-Z]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/g) ?? [];
  const ARGS: Record<string, number> = { M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7, Z: 0 };
  if (toks[0] !== 'M') return null;
  const cmds: { raw: string; from: XY; to: XY; straight: boolean }[] = [];
  let x = Number(toks[1]), y = Number(toks[2]), i = 3, cmd = 'L';
  const start: XY = [x, y];
  while (i < toks.length) {
    if (/[a-zA-Z]/.test(toks[i])) cmd = toks[i++];
    const C = cmd.toUpperCase(), rel = cmd !== C, n = ARGS[C];
    if (n === undefined || C === 'M') return null;
    const a = toks.slice(i, i + n).map(Number);
    if (a.length < n || a.some((v) => !Number.isFinite(v))) return null;
    i += n;
    const from: XY = [x, y];
    if (C === 'Z') [x, y] = start;
    else if (C === 'H') x = (rel ? x : 0) + a[0];
    else if (C === 'V') y = (rel ? y : 0) + a[0];
    else { x = (rel ? x : 0) + a[n - 2]; y = (rel ? y : 0) + a[n - 1]; }
    cmds.push({ raw: `${cmd}${a.join(' ')}`, from, to: [x, y], straight: 'LHVZ'.includes(C) });
  }
  return { start, cmds };
}

/** Ligger punktet inde på et lige stykke (ikke ved dets ender)? */
function inside(p: XY, a: XY, b: XY, margin: number): boolean {
  const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
  if (L <= 2 * margin) return false;
  const t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L);
  const cross = Math.abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / L;
  return cross < 0.5 && t * L > margin && (1 - t) * L > margin;
}

/**
 * Lyset i et T-stykkes afgrening skal starte ved gennemløbets KANT, ikke i dets midterlinje (v0.65.0): en delsti der
 * starter eller slutter inde på en anden delsti (lige stykke), forkortes med `width / 2` langs sit første/sidste lige
 * stykke. Kryds (hvor ingen ende ligger inde på en anden) og buer røres ikke. Stierne kommer fra splitSubpaths.
 */
export function trimInnerEnds(subpaths: string[], width: number): string[] {
  const half = width / 2;
  const walked = subpaths.map(walk);
  if (!(half > 0) || walked.some((w) => !w)) return subpaths;
  const segs = walked.map((w) => w!.cmds.filter((c) => c.straight).map((c) => [c.from, c.to] as [XY, XY]));
  const onOther = (k: number, p: XY) => segs.some((list, j) => j !== k && list.some(([a, b]) => inside(p, a, b, half)));
  return walked.map((w, k) => {
    const { start, cmds } = w!;
    if (!cmds.length) return subpaths[k];
    const first = cmds[0], last = cmds[cmds.length - 1];
    let s0: XY = start, out = cmds.map((c) => c.raw);
    const fmt = (v: number) => String(Math.round(v * 1000) / 1000);
    const len = (a: XY, b: XY) => Math.hypot(b[0] - a[0], b[1] - a[1]);
    // start inde i en anden delsti: flyt startpunktet en halv bredde frem ad det første lige stykke
    if (first.straight && onOther(k, start) && len(first.from, first.to) > half) {
      const L = len(first.from, first.to);
      s0 = [start[0] + (first.to[0] - start[0]) * half / L, start[1] + (first.to[1] - start[1]) * half / L];
      out[0] = `L${fmt(first.to[0])} ${fmt(first.to[1])}`;
    }
    // slut inde i en anden delsti: træk slutpunktet en halv bredde tilbage ad det sidste lige stykke
    const end = last.to;
    if (last.straight && onOther(k, end) && len(last.from, last.to) > half && !(cmds.length === 1 && s0 !== start && len(s0, end) <= half)) {
      const from = cmds.length === 1 ? s0 : last.from;
      const L = len(from, end);
      const e: XY = [end[0] - (end[0] - from[0]) * half / L, end[1] - (end[1] - from[1]) * half / L];
      out[out.length - 1] = `L${fmt(e[0])} ${fmt(e[1])}`;
    }
    return s0 === start && out.every((r, i) => r === cmds[i].raw) ? subpaths[k] : [`M${fmt(s0[0])} ${fmt(s0[1])}`, ...out].join(' ');
  });
}
