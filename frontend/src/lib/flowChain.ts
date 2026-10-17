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
}

export interface Phase {
  /** Forløbets koordinat i delens startpunkt. */
  g0: number;
  /** 1: g vokser langs delens tegneretning; -1: g falder. */
  orient: 1 | -1;
  /** true: delen skal køre modsat sin indstilling for at følge forløbets retning. */
  flip: boolean;
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
  for (let i = 0; i < usable.length; i++) {
    for (let j = i + 1; j < usable.length; j++) {
      if (usable[i].group !== usable[j].group) continue;
      for (const mine of ['a', 'b'] as const) {
        for (const theirs of ['a', 'b'] as const) {
          if (dist(usable[i][mine], usable[j][theirs]) <= tol) {
            links[i].push({ j, mine, theirs });
            links[j].push({ j: i, mine: theirs, theirs: mine });
          }
        }
      }
    }
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
    for (const i of order) {
      const o = orient.get(i)!, d = usable[i].dir;
      const g0 = o === 1 ? lo.get(i)! : lo.get(i)! + usable[i].len;   // g i delens START (a)
      out.set(usable[i].key, { g0, orient: o, flip: d !== 0 && D !== 0 && d * o !== D });
    }
  }
  for (const p of pieces) if (!out.has(p.key)) out.set(p.key, { g0: 0, orient: 1, flip: false });
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
