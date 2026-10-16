// "Erstat med symbol": forslag til hvilket bibliotekssymbol en tegnet del ligner. Ren logik — testet i symbolSuggest.test.ts
// (med opbygningerne fra den rigtige "varme"-tegning). Forslagene er hjælp, ikke et facit: man kan altid søge i hele biblioteket.

/** Det host-API'et `describeSelection()` giver om det valgte element (tegningens enheder). */
export interface SelectionInfo {
  id: string;
  tag: string;                       // rect, g, path, ellipse, text …
  counts: Record<string, number>;    // antal figurer i elementet inkl. det selv: { path: 2, ellipse: 1 }
  children: number;
  w: number;
  h: number;
  angle: number;
  fill: string;
  stroke: string;
  strokeWidth: number;
  rx: number;
  name: string;
  symbolType: string;                // data-hv-type, hvis det allerede er et bibliotekssymbol
  ids: string[];
  texts: string[];                   // tekster inde i elementets boks
  apexAngle: number | null;          // retningen (grader) delens ene ligebenede trekant peger — null hvis ingen/flere
  similar: number;                   // antal andre elementer med samme opbygning og størrelse
  similarAny: number;                // … uanset størrelse (fx etiketter med forskellig tekstlængde)
  similarGroups: string[][];         // pr. lignende del: de id'er der forsvinder (til at springe bundne dele over)
}

export interface Suggestion { id: string; score: number; why: string }

const has = (c: Record<string, number>, tag: string, n?: number) => (n === undefined ? (c[tag] ?? 0) > 0 : (c[tag] ?? 0) === n);
const near = (v: number, lo: number, hi: number) => v >= lo && v <= hi;
const filled = (fill: string) => !!fill && fill !== 'none' && fill !== 'transparent';

/** Er elementet en indhyllet sammensætning (gruppe) — frem for en enkelt figur? */
const isGroup = (s: SelectionInfo) => s.tag === 'g';

/**
 * Forslag, bedst først (score 0–100). Reglerne er bygget ud fra opbygning, størrelse og farver:
 *  - afrundet, ufyldt rektangel i pille-størrelse → statusfelt
 *  - cirkel + trekant (pumpe), ventil med stilk, målepunkt (lille cirkel med streg), store fyldte rektangler (tank/kedel), tykke streger (rør)
 */
export function suggestSymbols(s: SelectionInfo): Suggestion[] {
  const out: Suggestion[] = [];
  const add = (id: string, score: number, why: string) => out.push({ id, score, why });
  const c = s.counts;
  const size = Math.max(s.w, s.h);
  const small = Math.max(s.w, s.h) <= 40;

  if (s.symbolType) return [];   // et symbol er allerede et symbol

  // ---- etiketter (afrundede, ufyldte rektangler af pillestørrelse)
  if (s.tag === 'rect' && s.rx >= 4 && !filled(s.fill) && s.h <= 45 && s.w >= 40) {
    add('statusfelt', 95, 'Afrundet rektangel i pillestørrelse — en statusetiket');
    add('vaerdi', 55, 'Kan også være et værdifelt');
    add('setpunkt', 35, 'Eller et setpunkt-felt');
  }

  // ---- etiketter tegnet som en sti (en afrundet kontur af pillestørrelse, ikke en tynd linje)
  if (s.tag === 'path' && !filled(s.fill) && s.strokeWidth > 0 && s.strokeWidth < 6 && s.h >= 15 && s.h <= 45 && s.w >= 40 && s.w / s.h >= 1.8 && s.w / s.h <= 9) {
    add('statusfelt', 80, 'Kontur i pillestørrelse — ligner en statusetiket');
    add('vaerdi', 45, 'Kan også være et værdifelt');
  }

  // ---- store fyldte rektangler: beholdere, kedler
  if (s.tag === 'rect' && filled(s.fill) && s.w >= 50 && s.h >= 50) {
    const tall = s.h >= s.w * 1.2;
    add('tank', tall ? 80 : 65, 'Stort fyldt rektangel — en tank');
    add('kedel', tall ? 50 : 70, 'Eller en kedel/fyr');
    add('ekspansion', size < 110 ? 60 : 30, 'Lille beholder: ekspansionsbeholder');
    add('varmeveksler', 30, 'Eller en varmeveksler');
  }

  // ---- grupper
  if (isGroup(s)) {
    const circle = has(c, 'ellipse') || has(c, 'circle');
    const paths = c.path ?? 0;
    const lines = c.line ?? 0;
    const pumpLike = circle && near(s.w, 40, 110) && near(s.h, 40, 110) && Math.abs(s.w - s.h) <= 0.25 * Math.max(s.w, s.h);
    if (pumpLike && paths === 1 && lines === 0) {
      add('pumpe', 90, 'Cirkel med trekant — en pumpe');
      add('ventilator', 45, 'Eller en ventilator');
      add('motor', 40, 'Eller en motor');
    } else if (pumpLike && lines >= 1 && paths === 0) {
      add('pumpe', 70, 'Cirkel med streger — ligner en pumpe');
      add('motor', 50, 'Eller en motor');
      add('ventilator', 40, 'Eller en ventilator');
    }
    if (circle && paths >= 2 && lines >= 1 && near(s.w, 40, 120) && near(s.h, 40, 120)) {
      add('motorventil', 75, 'Ventil med stilk og motor-cirkel — en motorventil');
      add('trevejs_motorventil', 60, 'Eller en 3-vejs motorventil');
      add('trevejs_motorventil_ab', 50, 'Eller en 3-vejs motorventil (AB i midten)');
      add('ventil', 45, 'Eller en manuel ventil');
      add('regventil', 40, 'Eller en reguleringsventil');
      add('sikkerhedsventil', 35, 'Eller en sikkerhedsventil');
    }
    if (circle && lines >= 1 && paths === 0 && small && s.w <= 30) {
      add('foeler', 45, 'Lille cirkel med streg — et målepunkt/en føler');
      add('forbindelse', 35, 'Eller et forbindelsespunkt');
      add('lampe', 30, 'Eller en lampe');
    }
    if (has(c, 'rect') && paths >= 2 && s.w >= 80 && s.h >= 100) {
      add('kedel', 85, 'Rektangel med flammer/rørsløjfer — en kedel/fyr');
      add('tank', 45, 'Eller en tank');
      add('varmeveksler', 35, 'Eller en varmeveksler');
    }
  }

  // ---- rør: tykke streger
  if ((s.tag === 'path' || s.tag === 'line' || s.tag === 'polyline') && s.strokeWidth >= 6) {
    const horizontal = s.w >= s.h * 3;
    const vertical = s.h >= s.w * 3;
    if (horizontal) add('roer_v', 90, 'Tyk, vandret streg — et vandret rør');
    else if (vertical) add('roer_l', 90, 'Tyk, lodret streg — et lodret rør');
    else {
      add('boejning90', 70, 'Tyk streg med et knæk — en bøjning');
      add('boejning45', 40, 'Eller en 45°-bøjning');
      add('t_stykke', 30, 'Eller et T-stykke');
    }
  }

  // ---- en lille udfyldt cirkel med tekst (M = motor)
  if ((s.tag === 'ellipse' || s.tag === 'circle') && filled(s.fill) && small) {
    add('motor', 55, 'Lille cirkel — en motor (M)');
    add('lampe', 45, 'Eller en lampe');
  }

  // sorter bedst først; samme symbol kun én gang (højeste score)
  const best = new Map<string, Suggestion>();
  for (const x of out) if (!best.has(x.id) || best.get(x.id)!.score < x.score) best.set(x.id, x);
  return [...best.values()].sort((a, b) => b.score - a.score);
}

/** Symboler hvis tegning har en del med id "tekst" — her kan en tegnet etikets tekst overtages. */
export const hasTextSlot = (svg: string): boolean => /id="tekst"/.test(svg);

/** Et forslag til symbolets navn: det nuværende navn, ellers en tekst inde i delen, ellers symbolets eget navn. */
export function nameHint(s: SelectionInfo, symbolLabel: string): string {
  if (s.name) return s.name;
  const text = s.texts.find((t) => t.length <= 30);
  if (text) return `${symbolLabel} ${text}`;
  return symbolLabel;
}

/** Symboler med en retning (deres trekant peger mod højre ved 0°) — her kan symbolet drejes efter den tegnede trekant. */
export const NATIVE_DIRECTION: Record<string, number> = { pumpe: 0 };

/** Skal symbolet strækkes til at fylde delens boks (rør) i stedet for at beholde sine proportioner? */
export const stretchesByDefault = (symbolId: string): boolean => ['roer_v', 'roer_l', 'ledning_v', 'ledning_l'].includes(symbolId);
