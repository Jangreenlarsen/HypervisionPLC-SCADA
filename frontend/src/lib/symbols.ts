// ISA-101-inspireret symbolbibliotek: grå i normaltilstand, ingen farver der konkurrerer med alarmer.
// Hvert symbol er ét <g>-element; id sættes ved indsættelse. Animationer bindes bagefter i "Bindinger".
// Rør har tykkelse 10 og centerlinje i y=45 / x=45, så fittings og rør passer sammen. Brug
// SVG-Edits rotation (eller spejling) for at vende en bøjning/T-stykke den rigtige vej.

export type SymbolCategory = 'betjening' | 'proces' | 'vvs' | 'el' | 'sol';

export interface SymbolDef {
  id: string;
  label: string;
  hint: string;
  category: SymbolCategory;
  svg: string;
}

export const CATEGORIES: { id: SymbolCategory; label: string }[] = [
  { id: 'betjening', label: 'Betjening (skriver til PLC)' },
  { id: 'proces', label: 'Proces og visning' },
  { id: 'vvs', label: 'Rør og VVS' },
  { id: 'el', label: 'Elektrisk' },
  { id: 'sol', label: 'Solcelleanlæg' },
];

const LINE = '#555';
const FILL = '#9e9e9e';
const PANEL = '#eeeeee';
const DARK = '#333';
const FONT = 'font-family="Segoe UI, Arial"';

/** Rør-/fitting-sti: tykkelse 10 som de lige rør. */
const pipe = (d: string, join = 'miter') =>
  `<path d="${d}" fill="none" stroke="${LINE}" stroke-width="10" stroke-linejoin="${join}"/>`;
/** Tynd elektrisk streg. */
const wire = (d: string, extra = '') => `<path d="${d}" fill="none" stroke="${DARK}" stroke-width="2.5" stroke-linecap="round"${extra}/>`;
/** Ventilhus (sommerfugl) med centrum i (40,45) — rørenden flugter med rørets centerlinje. */
const VALVE_BODY = `<path d="M8 27 L40 45 L8 63 Z M72 27 L40 45 L72 63 Z" fill="${FILL}" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>`;
const STEM = `<line x1="40" y1="45" x2="40" y2="20" stroke="${LINE}" stroke-width="3"/>`;
const text = (x: number, y: number, s: string, size = 14, attrs = '', anchor = 'middle') =>
  `<text x="${x}" y="${y}" font-size="${size}" text-anchor="${anchor}" fill="${DARK}" ${FONT} ${attrs}>${s}</text>`;
/** ISA-instrumentboble: bogstaverne kan rettes i Tegn; værdien vises bedst i et værdifelt ved siden af. */
const bubble = (letters: string) =>
  `<g><line x1="30" y1="54" x2="30" y2="80" stroke="${LINE}" stroke-width="2" stroke-dasharray="4 3"/>` +
  `<circle cx="30" cy="30" r="24" fill="${PANEL}" stroke="${LINE}" stroke-width="2.5"/>` +
  text(30, 36, letters, 16, 'font-weight="600" id="tekst"') + '</g>';

/**
 * Betjeningssymboler beskriver selv deres bindinger: `data-hv-auto` på roden (klik-handlingen) og
 * `data-hv-part` på de dele der viser tilstanden. Vælges et tag i Tegn (id = tag-navn), danner serveren
 * bindingerne — klik-handlinger kun hvis tagget er skrivbart.
 */
const auto = (items: object[]) => `data-hv-auto='${JSON.stringify(items)}'`;
const part = (item: object) => `data-hv-part='${JSON.stringify(item)}'`;
const ON = '#7cc47f';   // tændt/aktiv i betjeningssymboler (lys, så sort tekst kan læses)
const OFF = '#d6d6d6';

/** Rør og fittings vises i samme målestok i symbolpaletten, så rørtykkelsen (10) ser ens ud (v0.28.1). */
export const PIPE_IDS = new Set(['roer_v', 'roer_l', 'boejning90', 'boejning45', 't_stykke', 'kryds', 'reduktion', 'prop', 'flange', 'flowpil']);
/** Rør-symbolernes fælles vindue i paletten: plads til 90 + rørets halve tykkelse på hver side + lidt luft. */
export const PIPE_PREVIEW = 104;

/**
 * viewBox til et symbols forhåndsvisning ud fra dets getBBox (som ikke medregner stregbredden).
 * Rør og fittings: fast målestok centreret om symbolet. Andre: tilpasset symbolets egen størrelse.
 */
export function previewViewBox(b: { x: number; y: number; width: number; height: number }, pipe: boolean): string {
  if (pipe) {
    const size = Math.max(PIPE_PREVIEW, b.width + 14, b.height + 14);
    const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
    return `${cx - size / 2} ${cy - size / 2} ${size} ${size}`;
  }
  const pad = 4 + Math.max(b.width, b.height) * 0.04;
  return `${b.x - pad} ${b.y - pad} ${b.width + 2 * pad} ${b.height + 2 * pad}`;
}

export const SYMBOLS: SymbolDef[] = [
  // ---------------------------------------------------------------- Betjening
  {
    id: 'trykknap_puls', label: 'Trykknap (puls)', category: 'betjening',
    hint: 'Sender en kort puls (500 ms) — fx start, stop, kvittér. Vælg et skrivbart tag',
    svg: `<g ${auto([{ anim: 'click:pulse', params: { ms: 500, confirm: false } }])}>` +
      // Tavlemonteret trykknap set forfra: frontplade, metalkrave, rund knap med glans og et skilt under (v0.28.0)
      `<rect x="0" y="0" width="76" height="76" rx="8" fill="${PANEL}" stroke="${LINE}" stroke-width="2"/>` +
      `<circle cx="38" cy="38" r="30" fill="#c8c8c8" stroke="${DARK}" stroke-width="2"/>` +
      `<circle cx="38" cy="38" r="25" fill="none" stroke="#f5f5f5" stroke-width="1.5"/>` +
      `<circle id="flade" cx="38" cy="38" r="21" fill="${OFF}" stroke="${LINE}" stroke-width="2" ${part({ anim: 'fill', params: { on: ON, off: OFF } })}/>` +
      `<path d="M24 32 A15 15 0 0 1 44 22" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".8"/>` +
      `<rect x="6" y="84" width="64" height="22" rx="2" fill="#fff" stroke="${LINE}" stroke-width="1.5"/>` +
      text(38, 100, 'Start', 14, 'font-weight="600" id="tekst"') + '</g>',
  },
  {
    id: 'startstop', label: 'Start/stop (til/fra)', category: 'betjening',
    hint: 'Skifter tagget til/fra med bekræftelse; lampen og teksten viser tilstanden',
    svg: `<g ${auto([{ anim: 'click:toggle', params: { confirm: true } }])}>` +
      `<rect x="0" y="0" width="130" height="50" rx="6" fill="#e3e3e3" stroke="${LINE}" stroke-width="2"/>` +
      `<circle id="lampe" cx="24" cy="25" r="11" fill="${FILL}" stroke="${DARK}" stroke-width="1.5" ${part({ anim: 'fill', params: { on: ON, off: FILL } })}/>` +
      `<text id="status" x="44" y="31" font-size="15" fill="${DARK}" ${FONT} ${part({ anim: 'text', params: { true_text: 'Kører', false_text: 'Stoppet' } })}>Stoppet</text></g>`,
  },
  {
    id: 'vippekontakt', label: 'Vippekontakt', category: 'betjening',
    hint: 'Til/fra uden bekræftelse — vippen flytter sig og skifter farve',
    svg: `<g ${auto([{ anim: 'click:toggle', params: { confirm: false } }])}>` +
      `<rect id="spor" x="0" y="0" width="64" height="32" rx="16" fill="${OFF}" stroke="${LINE}" stroke-width="2" ${part({ anim: 'fill', params: { on: ON, off: OFF } })}/>` +
      `<circle id="vippe" cx="16" cy="16" r="12" fill="#fff" stroke="${LINE}" stroke-width="2" ${part({ anim: 'move', params: { min: 0, max: 1, dx: 32, dy: 0 } })}/>` +
      `<text id="tekst" x="32" y="50" font-size="13" text-anchor="middle" fill="${DARK}" ${FONT} ${part({ anim: 'text', params: { true_text: 'TIL', false_text: 'FRA' } })}>FRA</text></g>`,
  },
  {
    id: 'omskifter3', label: 'Omskifter Hånd/0/Auto', category: 'betjening',
    hint: 'Vælg position i en dialog (værdi 0/1/2). Andre positioner: brug "Omskifter med egne positioner" nedenfor',
    get svg() { return selectorSymbol(['Hånd', '0', 'Auto']); },
  },
  {
    id: 'drejeomskifter', label: 'Drejeomskifter 0/1', category: 'betjening',
    hint: 'Til/fra med bekræftelse — grebet drejer mellem 0 og 1',
    svg: `<g ${auto([{ anim: 'click:toggle', params: { confirm: true } }])}>` +
      `<circle cx="40" cy="46" r="30" fill="#e3e3e3" stroke="${LINE}" stroke-width="2.5"/>` +
      text(14, 12, '0', 14, 'font-weight="600"') + text(66, 12, '1', 14, 'font-weight="600"') +
      // Grebet er symmetrisk om drejepunktet (40,46), så "Rotation" drejer det om centrum
      `<g id="greb" ${part({ anim: 'rotate', params: { min: 0, max: 1, angle_min: -45, angle_max: 45 } })}>` +
      `<rect x="34" y="18" width="12" height="56" rx="4" fill="${FILL}" stroke="${DARK}" stroke-width="1.5"/>` +
      `<rect x="37" y="20" width="6" height="14" rx="2" fill="${DARK}"/></g></g>`,
  },
  {
    id: 'automanuel', label: 'Auto/Manuel', category: 'betjening',
    hint: 'Skifter driftsform (til = AUTO) med bekræftelse',
    svg: `<g ${auto([{ anim: 'click:toggle', params: { confirm: true } }])}>` +
      `<rect id="flade" x="0" y="0" width="120" height="40" rx="6" fill="${PANEL}" stroke="${LINE}" stroke-width="2" ${part({ anim: 'fill', params: { on: '#bcd6ee', off: PANEL } })}/>` +
      `<text id="tekst" x="60" y="26" font-size="15" font-weight="600" text-anchor="middle" fill="${DARK}" ${FONT} ${part({ anim: 'text', params: { true_text: 'AUTO', false_text: 'MANUEL' } })}>MANUEL</text></g>`,
  },
  {
    id: 'setpunkt', label: 'Setpunkt-felt', category: 'betjening',
    hint: 'Klik for at indtaste en ny værdi (min/max fra tagget) — viser den aktuelle værdi',
    svg: `<g ${auto([{ anim: 'click:write' }])}>` +
      `<rect x="0" y="0" width="150" height="40" rx="4" fill="#fff" stroke="${LINE}" stroke-width="2"/>` +
      `<text id="vaerdi" x="12" y="26" font-size="17" font-weight="600" fill="#1f1f1f" ${FONT} ${part({ anim: 'text' })}>--</text>` +
      `<path d="M126 28 L130 16 L140 12 L136 22 Z M126 28 L132 26" fill="${FILL}" stroke="${DARK}" stroke-width="1.5" stroke-linejoin="round"/></g>`,
  },

  // ---------------------------------------------------------------- Proces og visning
  {
    id: 'statusfelt', label: 'Statusfelt', category: 'proces', hint: 'Knyt til et register: farven følger værdien (Fyldfarve) — ret teksten i Tegn',
    svg: `<g><rect id="felt" x="2" y="2" width="76" height="26" rx="13" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>` +
      text(40, 21, 'STF', 15, 'font-weight="700" id="tekst"') + '</g>',
  },
  {
    id: 'pumpe', label: 'Pumpe', category: 'proces', hint: 'Bind "Fyldfarve" til drift-signalet',
    svg: `<g><circle cx="40" cy="40" r="32" fill="${FILL}" stroke="${LINE}" stroke-width="3"/>` +
      `<path d="M28 22 L60 40 L28 58 Z" fill="${FILL}" stroke="${DARK}" stroke-width="2"/></g>`,
  },
  {
    id: 'motor', label: 'Motor', category: 'proces', hint: 'Bind "Fyldfarve" til drift-signalet',
    svg: `<g><circle cx="40" cy="40" r="32" fill="${FILL}" stroke="${LINE}" stroke-width="3"/>` +
      text(40, 49, 'M', 26, 'font-weight="600"') + '</g>',
  },
  {
    id: 'tank', label: 'Tank', category: 'proces', hint: 'Bind "Niveau" på det indre rektangel',
    svg: `<g><rect x="0" y="0" width="90" height="140" rx="8" fill="${PANEL}" stroke="${LINE}" stroke-width="3"/>` +
      `<rect id="fyld" x="3" y="3" width="84" height="134" rx="5" fill="#7aa7c7"/></g>`,
  },
  {
    id: 'vaerdi', label: 'Værdifelt', category: 'proces', hint: 'Bind "Tekst" på teksten',
    svg: `<g><rect x="0" y="0" width="160" height="56" rx="4" fill="${PANEL}" stroke="#888"/>` +
      `<text id="titel" x="12" y="20" font-size="12" fill="#5c5c5c" ${FONT}>Måling</text>` +
      `<text id="vaerdi" x="12" y="45" font-size="20" font-weight="600" fill="#1f1f1f" ${FONT}>--</text></g>`,
  },
  {
    id: 'lampe', label: 'Lampe', category: 'proces', hint: 'Bind "Fyldfarve" til signalet',
    svg: `<g><circle cx="16" cy="16" r="14" fill="${FILL}" stroke="${LINE}" stroke-width="2"/></g>`,
  },
  {
    id: 'knap', label: 'Knap', category: 'proces', hint: 'Bind "Klik: til/fra" eller "Klik: puls"',
    svg: `<g><rect x="0" y="0" width="110" height="40" rx="6" fill="#e3e3e3" stroke="${LINE}" stroke-width="2"/>` +
      text(55, 26, 'Start', 15) + '</g>',
  },

  // ---------------------------------------------------------------- Rør og fittings
  {
    id: 'roer_v', label: 'Rør (vandret)', category: 'vvs', hint: 'Træk i enderne for at forlænge',
    svg: `<g><rect x="0" y="0" width="90" height="10" fill="${LINE}"/></g>`,
  },
  {
    id: 'roer_l', label: 'Rør (lodret)', category: 'vvs', hint: 'Træk i enderne for at forlænge',
    svg: `<g><rect x="0" y="0" width="10" height="90" fill="${LINE}"/></g>`,
  },
  {
    id: 'boejning90', label: 'Bøjning 90°', category: 'vvs', hint: 'Rotér/spejl i Tegn for at vende den',
    svg: `<g>${pipe('M0 45 H25 A20 20 0 0 0 45 25 V0')}</g>`,
  },
  {
    id: 'boejning45', label: 'Bøjning 45°', category: 'vvs', hint: 'Rotér/spejl i Tegn for at vende den',
    // Rund bøjning med samme radius (20 i centerlinjen) som Bøjning 90°. Knækpunktet er (45,45), og begge ben er 45
    // lange som på de andre fittings (v0.28.2)
    svg: `<g>${pipe('M0 45 H36.72 A20 20 0 0 0 50.86 39.14 L76.82 13.18')}</g>`,
  },
  {
    id: 't_stykke', label: 'T-stykke', category: 'vvs', hint: 'Rotér i Tegn for at vende afgreningen',
    svg: `<g>${pipe('M0 45 H90 M45 45 V0')}</g>`,
  },
  {
    id: 'kryds', label: 'Kryds', category: 'vvs', hint: 'Fire rør mødes',
    svg: `<g>${pipe('M0 45 H90 M45 0 V90')}</g>`,
  },
  {
    id: 'reduktion', label: 'Reduktion', category: 'vvs', hint: 'Overgang fra stort til lille rør',
    svg: `<g><path d="M0 38 H28 L52 41 H80 V49 H52 L28 52 H0 Z" fill="${LINE}"/></g>`,
  },
  {
    id: 'prop', label: 'Prop/endedæksel', category: 'vvs', hint: 'Afslutning af et rør',
    svg: `<g><rect x="0" y="40" width="30" height="10" fill="${LINE}"/><rect x="30" y="32" width="7" height="26" fill="${LINE}"/></g>`,
  },
  {
    id: 'flange', label: 'Flangesamling', category: 'vvs', hint: 'Samling mellem to rør',
    svg: `<g><rect x="0" y="40" width="30" height="10" fill="${LINE}"/><rect x="30" y="31" width="5" height="28" fill="${LINE}"/>` +
      `<rect x="38" y="31" width="5" height="28" fill="${LINE}"/><rect x="43" y="40" width="30" height="10" fill="${LINE}"/></g>`,
  },
  {
    id: 'flowpil', label: 'Strømningsretning', category: 'vvs', hint: 'Læg på et rør; bind evt. "Synlighed" til pumpedrift',
    svg: `<g><path d="M0 45 H40" stroke="${LINE}" stroke-width="10"/><path d="M36 31 L64 45 L36 59 Z" fill="${LINE}"/></g>`,
  },

  // ---------------------------------------------------------------- Ventiler
  {
    id: 'ventil', label: 'Ventil (manuel)', category: 'vvs', hint: 'Bind "Fyldfarve" til åben/lukket',
    svg: `<g>${VALVE_BODY}${STEM}<rect x="28" y="11" width="24" height="10" fill="${FILL}" stroke="${LINE}" stroke-width="2"/></g>`,
  },
  {
    id: 'kugleventil', label: 'Kugleventil', category: 'vvs', hint: 'Bind "Fyldfarve" til åben/lukket',
    svg: `<g>${VALVE_BODY}<circle cx="40" cy="45" r="9" fill="${DARK}"/>` +
      `<line x1="40" y1="36" x2="40" y2="18" stroke="${LINE}" stroke-width="3"/><line x1="40" y1="18" x2="62" y2="18" stroke="${LINE}" stroke-width="4"/></g>`,
  },
  {
    id: 'kontraventil', label: 'Kontraventil', category: 'vvs', hint: 'Tillader kun strømning i pilens retning',
    svg: `<g><path d="M8 27 L40 45 L8 63 Z" fill="${DARK}" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `<path d="M72 27 L40 45 L72 63 Z" fill="${FILL}" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `<path d="M24 14 H52 M46 9 L54 14 L46 19" fill="none" stroke="${LINE}" stroke-width="2"/></g>`,
  },
  {
    id: 'trevejsventil', label: '3-vejs ventil', category: 'vvs', hint: 'Bind "Fyldfarve" pr. port eller på hele ventilen',
    svg: `<g><path d="M8 27 L40 45 L8 63 Z M72 27 L40 45 L72 63 Z M22 77 L40 45 L58 77 Z" fill="${FILL}" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `${STEM}<circle cx="40" cy="45" r="4" fill="${DARK}"/></g>`,
  },
  {
    id: 'trevejs_motorventil', label: '3-vejs motorventil', category: 'vvs',
    hint: 'Portene A, B og AB farves hver for sig (fx AB → A eller AB → B) — opsæt med guiden',
    svg: `<g><path id="port_a" d="M8 27 L40 45 L8 63 Z" fill="#222222" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `<path id="port_b" d="M22 13 L58 13 L40 45 Z" fill="#222222" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `<path id="port_ab" d="M72 27 L40 45 L72 63 Z" fill="#ffffff" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `<line x1="40" y1="45" x2="40" y2="66" stroke="${LINE}" stroke-width="3"/><circle cx="40" cy="45" r="4" fill="${DARK}"/>` +
      `<circle id="motor" cx="40" cy="78" r="12" fill="${PANEL}" stroke="${LINE}" stroke-width="2.5"/>` +
      text(40, 83, 'M', 14, 'font-weight="600"') + text(8, 86, 'A', 13) + text(66, 20, 'B', 13) + text(76, 86, 'AB', 13) + '</g>',
  },
  {
    id: 'motorventil', label: 'Motorventil', category: 'vvs', hint: 'Bind "Fyldfarve" til åben/lukket',
    svg: `<g>${VALVE_BODY}${STEM}<circle cx="40" cy="12" r="12" fill="${PANEL}" stroke="${LINE}" stroke-width="2.5"/>` +
      text(40, 17, 'M', 14, 'font-weight="600"') + '</g>',
  },
  {
    id: 'magnetventil', label: 'Magnetventil', category: 'vvs', hint: 'Bind "Fyldfarve" til spolen',
    svg: `<g>${VALVE_BODY}${STEM}<rect x="28" y="0" width="24" height="20" fill="${PANEL}" stroke="${LINE}" stroke-width="2.5"/>` +
      text(40, 15, 'S', 14, 'font-weight="600"') + '</g>',
  },
  {
    id: 'regventil', label: 'Reguleringsventil', category: 'vvs', hint: 'Bind "Tekst" (åbning %) i et værdifelt ved siden af',
    svg: `<g>${VALVE_BODY}${STEM}<path d="M22 20 A18 18 0 0 1 58 20 Z" fill="${PANEL}" stroke="${LINE}" stroke-width="2.5"/></g>`,
  },
  {
    id: 'sikkerhedsventil', label: 'Sikkerhedsventil', category: 'vvs', hint: 'Indløb nedefra, afgang til højre',
    svg: `<g><path d="M22 77 L40 45 L58 77 Z M72 27 L40 45 L72 63 Z" fill="${FILL}" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `<path d="M40 45 V36 L30 32 L50 26 L30 20 L50 14 L40 10 V4" fill="none" stroke="${LINE}" stroke-width="2.5" stroke-linejoin="round"/></g>`,
  },

  // ---------------------------------------------------------------- Komponenter
  {
    id: 'varmeveksler', label: 'Varmeveksler', category: 'vvs', hint: 'Bind "Fyldfarve" til drift',
    svg: `<g><circle cx="40" cy="40" r="32" fill="${PANEL}" stroke="${LINE}" stroke-width="3"/>` +
      `<path d="M8 40 H18 L26 24 L36 56 L46 24 L56 56 L62 40 H72" fill="none" stroke="${DARK}" stroke-width="2.5" stroke-linejoin="round"/></g>`,
  },
  {
    id: 'filter', label: 'Filter/snavssamler', category: 'vvs', hint: 'Bind "Fyldfarve" til f.eks. tilstoppet-alarm',
    svg: `<g><path d="M40 5 L75 40 L40 75 L5 40 Z" fill="${PANEL}" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `<line x1="22" y1="22" x2="58" y2="58" stroke="${LINE}" stroke-width="2.5" stroke-dasharray="5 4"/></g>`,
  },
  {
    id: 'ekspansion', label: 'Ekspansionsbeholder', category: 'vvs', hint: 'Bind "Tekst" (tryk) i et værdifelt ved siden af',
    svg: `<g><rect x="10" y="0" width="60" height="90" rx="30" fill="${PANEL}" stroke="${LINE}" stroke-width="3"/>` +
      `<path d="M12 45 Q40 35 68 45" fill="none" stroke="${LINE}" stroke-width="2.5"/>` +
      `<rect x="35" y="90" width="10" height="25" fill="${LINE}"/></g>`,
  },
  {
    id: 'radiator', label: 'Radiator', category: 'vvs', hint: 'Bind "Fyldfarve" til varme til/fra',
    svg: `<g><rect x="0" y="0" width="110" height="60" rx="4" fill="${PANEL}" stroke="${LINE}" stroke-width="3"/>` +
      `<path d="M15 8 V52 M30 8 V52 M45 8 V52 M60 8 V52 M75 8 V52 M90 8 V52" stroke="${LINE}" stroke-width="3"/></g>`,
  },
  {
    id: 'ventilator', label: 'Ventilator/blæser', category: 'vvs', hint: 'Bind "Fyldfarve" til drift, evt. "Rotation" på rotoren',
    svg: `<g><circle cx="40" cy="40" r="32" fill="${FILL}" stroke="${LINE}" stroke-width="3"/>` +
      `<g id="rotor"><path d="M40 40 C30 30 32 14 40 12 C48 14 50 30 40 40 C50 50 48 66 40 68 C32 66 30 50 40 40 Z" fill="${PANEL}" stroke="${DARK}" stroke-width="2"/>` +
      `<circle cx="40" cy="40" r="4" fill="${DARK}"/></g></g>`,
  },
  {
    id: 'kedel', label: 'Kedel/fyr', category: 'vvs', hint: 'Bind "Fyldfarve" på flammen til brænderdrift',
    svg: `<g><rect x="0" y="0" width="90" height="120" rx="6" fill="${PANEL}" stroke="${LINE}" stroke-width="3"/>` +
      `<path id="flamme" d="M45 98 C28 96 26 78 36 66 C36 76 42 78 42 78 C38 64 46 52 52 46 C52 60 64 66 62 82 C60 92 54 98 45 98 Z" fill="${FILL}" stroke="${DARK}" stroke-width="2"/></g>`,
  },

  // ---------------------------------------------------------------- Måleinstrumenter
  { id: 'tt', label: 'Temperatur (TT)', category: 'vvs', hint: 'ISA-boble; værdien vises i et værdifelt', svg: bubble('TT') },
  { id: 'pt', label: 'Tryk (PT)', category: 'vvs', hint: 'ISA-boble; værdien vises i et værdifelt', svg: bubble('PT') },
  { id: 'ft', label: 'Flow (FT)', category: 'vvs', hint: 'ISA-boble; værdien vises i et værdifelt', svg: bubble('FT') },
  { id: 'lt', label: 'Niveau (LT)', category: 'vvs', hint: 'ISA-boble; værdien vises i et værdifelt', svg: bubble('LT') },
  {
    id: 'manometer', label: 'Manometer', category: 'vvs', hint: 'Bind "Rotation" på viseren (fx min -120°, max 120°)',
    svg: `<g><circle cx="40" cy="40" r="32" fill="${PANEL}" stroke="${LINE}" stroke-width="3"/>` +
      `<path d="M17 63 A32 32 0 1 1 63 63" fill="none" stroke="#bbb" stroke-width="2"/>` +
      // Viseren er symmetrisk om midten (usynlig cirkel), så "Rotation" drejer den om centrum
      `<g id="viser"><circle cx="40" cy="40" r="26" fill="none"/><path d="M40 40 L37 37 L40 16 L43 37 Z" fill="${DARK}"/>` +
      `<circle cx="40" cy="40" r="4" fill="${DARK}"/></g>` +
      `<rect x="35" y="72" width="10" height="20" fill="${LINE}"/></g>`,
  },
  {
    id: 'termometer', label: 'Termometer', category: 'vvs', hint: 'Bind "Niveau" på søjlen (min/max = måleområdet)',
    svg: `<g><rect x="10" y="0" width="20" height="100" rx="10" fill="${PANEL}" stroke="${LINE}" stroke-width="2.5"/>` +
      `<circle cx="20" cy="108" r="14" fill="${FILL}" stroke="${LINE}" stroke-width="2.5"/>` +
      `<rect id="soejle" x="16" y="10" width="8" height="92" fill="${FILL}"/></g>`,
  },

  // ---------------------------------------------------------------- Elektrisk
  {
    id: 'ledning_v', label: 'Ledning (vandret)', category: 'el', hint: 'Træk i enderne for at forlænge; bind "Stregfarve" til spænding',
    svg: `<g>${wire('M0 10 H120')}</g>`,
  },
  {
    id: 'ledning_l', label: 'Ledning (lodret)', category: 'el', hint: 'Træk i enderne for at forlænge; bind "Stregfarve" til spænding',
    svg: `<g>${wire('M10 0 V120')}</g>`,
  },
  {
    id: 'forbindelse', label: 'Forbindelsespunkt', category: 'el', hint: 'Hvor ledninger er forbundet',
    svg: `<g><circle cx="8" cy="8" r="5" fill="${DARK}"/></g>`,
  },
  {
    id: 'klemme', label: 'Klemme', category: 'el', hint: 'Klemmerække/tilslutning — ret nummeret i Tegn',
    svg: `<g><circle cx="20" cy="20" r="7" fill="#fff" stroke="${DARK}" stroke-width="2.5"/>${text(20, 46, 'X1', 12)}</g>`,
  },
  {
    id: 'kontakt_no', label: 'Sluttekontakt (NO)', category: 'el', hint: 'Bind "Stregfarve" til kontaktens tilstand',
    svg: `<g>${wire('M0 40 H22 L50 24 M48 40 H70')}</g>`,
  },
  {
    id: 'kontakt_nc', label: 'Brydekontakt (NC)', category: 'el', hint: 'Bind "Stregfarve" til kontaktens tilstand',
    svg: `<g>${wire('M0 40 H22 L52 34 M48 40 H70 M48 40 V28')}</g>`,
  },
  {
    id: 'trykknap', label: 'Trykknap (NO)', category: 'el', hint: 'Bind "Klik: puls" for at betjene fra SCADA',
    svg: `<g>${wire('M0 50 H22 L50 34 M48 50 H70')}${wire('M36 42 V14', ' stroke-dasharray="4 3"')}${wire('M26 14 H46 M26 14 V8 M46 14 V8')}</g>`,
  },
  {
    id: 'noedstop', label: 'Nødstop', category: 'el', hint: 'Bind "Fyldfarve"/"Blink" til aktiveret nødstop',
    svg: `<g>${wire('M0 60 H22 L52 54 M48 60 H70 M48 60 V48')}${wire('M37 57 V26', ' stroke-dasharray="4 3"')}` +
      `<path d="M17 26 A20 18 0 0 1 57 26 Z" fill="${FILL}" stroke="${DARK}" stroke-width="2.5"/></g>`,
  },
  {
    id: 'kontaktor', label: 'Kontaktor 3-polet', category: 'el', hint: 'Bind "Stregfarve" til kontaktorens tilbagemelding',
    svg: `<g>${wire('M10 0 V20 L26 46 M10 52 V72 M40 0 V20 L56 46 M40 52 V72 M70 0 V20 L86 46 M70 52 V72')}` +
      `${wire('M14 33 H76', ' stroke-dasharray="4 3"')}${text(98, 40, 'K1', 13, '', 'start')}</g>`,
  },
  {
    id: 'spole', label: 'Relæ-/kontaktorspole', category: 'el', hint: 'Bind "Fyldfarve" til spolen er aktiv',
    svg: `<g>${wire('M30 0 V14 M30 46 V60')}<rect x="10" y="14" width="40" height="32" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>` +
      `${text(30, 35, 'K1', 14)}</g>`,
  },
  {
    id: 'sikring', label: 'Sikring', category: 'el', hint: 'Bind "Stregfarve"/"Blink" til sikring sprunget',
    svg: `<g>${wire('M20 0 V80')}<rect x="11" y="18" width="18" height="44" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>${wire('M20 18 V62')}</g>`,
  },
  {
    id: 'automatsikring', label: 'Automatsikring', category: 'el', hint: 'Bind "Stregfarve" til slået fra',
    svg: `<g>${wire('M20 0 V24 L36 52 M20 58 V80')}${wire('M15 19 L25 29 M25 19 L15 29')}` +
      `<rect x="36" y="32" width="12" height="10" fill="none" stroke="${DARK}" stroke-width="2"/></g>`,
  },
  {
    id: 'motorvaern', label: 'Motorværn', category: 'el', hint: 'Bind "Blink" til udløst motorværn',
    svg: `<g>${wire('M30 0 V16 M30 64 V80')}<rect x="6" y="16" width="48" height="48" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>` +
      `${wire('M14 48 H24 V32 H36 V48 H46')}</g>`,
  },
  {
    id: 'motor3', label: 'Motor 3~', category: 'el', hint: 'Bind "Fyldfarve" til drift',
    svg: `<g>${wire('M40 0 V8')}<circle cx="40" cy="40" r="32" fill="${FILL}" stroke="${LINE}" stroke-width="3"/>` +
      text(40, 40, 'M', 24, 'font-weight="600"') + text(40, 60, '3~', 14) + '</g>',
  },
  {
    id: 'frekvensomformer', label: 'Frekvensomformer', category: 'el', hint: 'Bind "Tekst" (Hz) i et værdifelt ved siden af',
    svg: `<g><rect x="0" y="0" width="70" height="70" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>${wire('M0 70 L70 0')}` +
      `${text(18, 24, '~', 20)}${text(50, 60, '~', 20)}${text(35, 88, 'VFD', 12)}</g>`,
  },
  {
    id: 'transformer', label: 'Transformer', category: 'el', hint: 'Fx 400/24 V',
    svg: `<g>${wire('M30 0 V12 M30 84 V96')}<circle cx="30" cy="36" r="22" fill="none" stroke="${DARK}" stroke-width="2.5"/>` +
      `<circle cx="30" cy="60" r="22" fill="none" stroke="${DARK}" stroke-width="2.5"/></g>`,
  },
  {
    id: 'stroemforsyning', label: 'Strømforsyning', category: 'el', hint: 'AC/DC, fx 230 V~ → 24 V=',
    svg: `<g><rect x="0" y="0" width="70" height="70" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>${wire('M0 70 L70 0')}` +
      `${text(18, 24, '~', 20)}${text(50, 62, '=', 20)}</g>`,
  },
  {
    id: 'jord', label: 'Jord', category: 'el', hint: 'Beskyttelsesjord',
    svg: `<g>${wire('M25 0 V22 M5 22 H45 M12 30 H38 M19 38 H31')}</g>`,
  },
  {
    id: 'signallampe', label: 'Signallampe', category: 'el', hint: 'Bind "Fyldfarve" til lampen',
    svg: `<g>${wire('M25 0 V8 M25 42 V50')}<circle cx="25" cy="25" r="17" fill="${FILL}" stroke="${DARK}" stroke-width="2.5"/>` +
      `${wire('M13 13 L37 37 M37 13 L13 37')}</g>`,
  },
  {
    id: 'modstand', label: 'Modstand', category: 'el', hint: 'Fx varmelegeme — bind "Fyldfarve" til til/fra',
    svg: `<g>${wire('M0 15 H15 M65 15 H80')}<rect x="15" y="5" width="50" height="20" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/></g>`,
  },
  {
    id: 'foeler', label: 'Føler (nærhed)', category: 'el', hint: 'Bind "Fyldfarve" til føler aktiv',
    svg: `<g>${wire('M30 0 V10')}<path d="M30 10 L50 30 L30 50 L10 30 Z" fill="${FILL}" stroke="${DARK}" stroke-width="2.5" stroke-linejoin="round"/>` +
      `${wire('M22 30 H38 M24 36 H36')}</g>`,
  },
  {
    id: 'hovedafbryder', label: 'Hovedafbryder', category: 'el', hint: 'Bind "Stregfarve" til slået til/fra',
    svg: `<g>${wire('M20 0 V24 L38 52 M20 58 V80')}${wire('M29 38 H52', ' stroke-dasharray="4 3"')}` +
      `<circle cx="58" cy="38" r="7" fill="${FILL}" stroke="${DARK}" stroke-width="2"/></g>`,
  },
  {
    id: 'plc', label: 'PLC', category: 'el', hint: 'Bind "Fyldfarve" på feltet til PLC-forbindelse ok',
    svg: `<g><rect x="0" y="0" width="110" height="70" rx="4" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>` +
      `${text(55, 42, 'PLC', 18, 'font-weight="600"')}` +
      `${wire('M15 70 V82 M35 70 V82 M55 70 V82 M75 70 V82 M95 70 V82')}</g>`,
  },

  // ---------------------------------------------------------------- Solcelleanlæg
  {
    id: 'solpanel', label: 'Solcellepanel', category: 'sol', hint: 'Bind "Fyldfarve" til produktion, eller vis effekten i et værdifelt',
    svg: `<g><rect x="0" y="0" width="80" height="110" rx="3" fill="#5f7d95" stroke="${LINE}" stroke-width="3"/>` +
      `<path d="M27 3 V107 M53 3 V107 M3 28 H77 M3 55 H77 M3 82 H77" stroke="#c9d6e0" stroke-width="2"/></g>`,
  },
  {
    id: 'solstreng', label: 'Solcellestreng', category: 'sol', hint: 'Flere paneler i serie — kopiér for flere strenge',
    svg: `<g>${[0, 1, 2].map((i) => `<rect x="${i * 54}" y="0" width="48" height="66" rx="2" fill="#5f7d95" stroke="${LINE}" stroke-width="2.5"/>` +
      `<path d="M${i * 54 + 16} 2 V64 M${i * 54 + 32} 2 V64 M${i * 54 + 2} 22 H${i * 54 + 46} M${i * 54 + 2} 44 H${i * 54 + 46}" stroke="#c9d6e0" stroke-width="1.5"/>`).join('')}` +
      `${wire('M24 66 V80 H132 V66')}</g>`,
  },
  {
    id: 'sol', label: 'Sol/indstråling', category: 'sol', hint: 'Bind "Gennemsigtighed" til indstråling (W/m²)',
    svg: `<g><circle cx="40" cy="40" r="16" fill="${FILL}" stroke="${LINE}" stroke-width="2.5"/>` +
      `${wire('M40 4 V16 M40 64 V76 M4 40 H16 M64 40 H76 M14 14 L23 23 M57 57 L66 66 M66 14 L57 23 M23 57 L14 66')}</g>`,
  },
  {
    id: 'inverter', label: 'Inverter', category: 'sol', hint: 'DC → AC; bind "Fyldfarve" til drift/fejl',
    svg: `<g>${wire('M0 25 H14 M94 55 H108')}<rect x="14" y="0" width="80" height="80" rx="3" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>` +
      `${wire('M14 80 L94 0')}${text(36, 30, '=', 22)}${text(72, 68, '~', 22)}</g>`,
  },
  {
    id: 'hybridinverter', label: 'Hybridinverter', category: 'sol', hint: 'PV + batteri + net i én enhed',
    svg: `<g>${text(20, 10, 'PV', 10)}${text(50, 10, 'BAT', 10)}${wire('M20 14 V26 M50 14 V26 M100 86 H114')}` +
      `<rect x="0" y="26" width="100" height="90" rx="3" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>` +
      `${text(50, 52, 'HYBRID', 13, 'font-weight="600"')}${text(24, 86, '=', 20)}${text(76, 86, '~', 22)}${wire('M50 64 V104')}</g>`,
  },
  {
    id: 'mppt', label: 'MPPT-regulator', category: 'sol', hint: 'Laderegulator mellem paneler og batteri',
    svg: `<g><rect x="0" y="0" width="80" height="60" rx="3" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>` +
      `${text(40, 26, 'MPPT', 14, 'font-weight="600"')}${text(40, 48, '= / =', 14)}</g>`,
  },
  {
    id: 'batteri', label: 'Batteri', category: 'sol', hint: 'Bind "Niveau" på det indre felt til ladetilstand (SOC %)',
    svg: `<g><rect x="0" y="10" width="70" height="110" rx="5" fill="${PANEL}" stroke="${LINE}" stroke-width="3"/>` +
      `<rect x="22" y="0" width="26" height="10" rx="2" fill="${LINE}"/>` +
      `<rect id="fyld" x="5" y="15" width="60" height="100" rx="3" fill="#8fbf8f"/></g>`,
  },
  {
    id: 'batteribank', label: 'Batteribank', category: 'sol', hint: 'Flere battericeller i serie (elektrisk symbol)',
    svg: `<g>${wire('M0 30 H14 M66 30 H80')}${[0, 1, 2].map((i) => `<path d="M${14 + i * 22} 12 V48" stroke="${DARK}" stroke-width="3"/><path d="M${22 + i * 22} 20 V40" stroke="${DARK}" stroke-width="5"/>`).join('')}` +
      `${wire('M22 30 H36 M44 30 H58')}${text(8, 20, '+', 14)}${text(74, 20, '−', 14)}</g>`,
  },
  {
    id: 'dc_afbryder', label: 'DC-afbryder', category: 'sol', hint: 'Bind "Stregfarve" til slået til/fra',
    svg: `<g>${wire('M20 0 V24 L38 52 M20 58 V80')}${text(44, 24, '=', 18, '', 'start')}</g>`,
  },
  {
    id: 'ac_afbryder', label: 'AC-afbryder', category: 'sol', hint: 'Bind "Stregfarve" til slået til/fra',
    svg: `<g>${wire('M20 0 V24 L38 52 M20 58 V80')}${text(44, 26, '~', 20, '', 'start')}</g>`,
  },
  {
    id: 'spd', label: 'Overspændingsbeskyttelse', category: 'sol', hint: 'SPD/afleder mod jord',
    svg: `<g>${wire('M25 0 V16 M25 64 V76 M8 76 H42 M14 83 H36 M20 90 H30')}` +
      `<rect x="13" y="16" width="24" height="48" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>${wire('M28 22 L20 40 H30 L22 58', ' stroke-linejoin="round"')}</g>`,
  },
  {
    id: 'elmaaler', label: 'Elmåler (kWh)', category: 'sol', hint: 'Bind "Tekst" på tallet til energi/effekt',
    // Displayet har plads til 5 cifre + decimal + enhed, fx "12345.6 kWh" (v0.27.1)
    svg: `<g><rect x="0" y="0" width="130" height="70" rx="4" fill="${PANEL}" stroke="${DARK}" stroke-width="2.5"/>` +
      `<rect x="10" y="12" width="110" height="26" fill="#fff" stroke="${LINE}" stroke-width="1.5"/>` +
      `<text id="vaerdi" x="114" y="31" font-size="15" text-anchor="end" fill="${DARK}" ${FONT}>0</text>${text(65, 58, 'kWh', 13)}</g>`,
  },
  {
    id: 'elnet', label: 'Elnet', category: 'sol', hint: 'Forsyningsnettet; bind "Stregfarve" til import/eksport',
    svg: `<g><path d="M40 0 L22 100 M40 0 L58 100 M10 18 H70 M14 34 H66 M31 50 L49 76 M49 50 L31 76 M28 52 H52 M25 76 H55" fill="none" stroke="${DARK}" stroke-width="3" stroke-linejoin="round"/>` +
      `<circle cx="10" cy="18" r="3" fill="${DARK}"/><circle cx="70" cy="18" r="3" fill="${DARK}"/><circle cx="14" cy="34" r="3" fill="${DARK}"/><circle cx="66" cy="34" r="3" fill="${DARK}"/></g>`,
  },
  {
    id: 'forbrug', label: 'Forbrug/hus', category: 'sol', hint: 'Husstandens forbrug — vis effekten i et værdifelt',
    svg: `<g><path d="M5 45 L45 8 L85 45" fill="none" stroke="${LINE}" stroke-width="4" stroke-linejoin="round"/>` +
      `<rect x="15" y="42" width="60" height="50" fill="${FILL}" stroke="${LINE}" stroke-width="3"/>` +
      `<rect x="38" y="62" width="16" height="30" fill="${PANEL}" stroke="${LINE}" stroke-width="2"/></g>`,
  },
  {
    id: 'elbillader', label: 'Elbillader', category: 'sol', hint: 'Bind "Fyldfarve" til ladning i gang',
    svg: `<g><rect x="0" y="0" width="50" height="90" rx="6" fill="${FILL}" stroke="${LINE}" stroke-width="3"/>` +
      `<rect x="9" y="10" width="32" height="22" rx="2" fill="${PANEL}" stroke="${LINE}" stroke-width="1.5"/>` +
      `<path d="M28 40 L18 58 H27 L22 76 L34 54 H25 Z" fill="${PANEL}" stroke="${DARK}" stroke-width="1.5" stroke-linejoin="round"/>` +
      `${wire('M50 60 C70 60 70 90 86 90')}</g>`,
  },
  {
    id: 'energipil', label: 'Energiflow-pil', category: 'sol', hint: 'Bind "Synlighed" (fx kun ved eksport) eller "Fyldfarve"',
    svg: `<g><path d="M0 18 H70 V4 L100 30 L70 56 V42 H0 Z" fill="${FILL}" stroke="${LINE}" stroke-width="2.5" stroke-linejoin="round"/></g>`,
  },
];

/** Vinkler (grader, 0 = op, med uret) for n positioner — fordelt symmetrisk om lodret. */
export function selectorAngles(n: number): number[] {
  const span = Math.max(60, Math.min(270, 45 * (n - 1)));
  return Array.from({ length: n }, (_, i) => (n === 1 ? 0 : -span / 2 + (i * span) / (n - 1)));
}

/**
 * Omskifter med 2-8 positioner (navnene i rækkefølge, fx ["Hånd", "0", "Auto"]). Positionernes værdier er
 * 0, 1, 2 … (kan rettes under Bindinger). Klik → dialog med én knap pr. position; grebet drejer til den
 * aktive position. Navnene står rundt om grebet.
 */
export function selectorSymbol(labels: string[]): string {
  const names = labels.map((l) => l.trim()).filter(Boolean).slice(0, 8);
  if (names.length < 2) throw new Error('Angiv mindst 2 positioner, adskilt med komma (fx Hånd, 0, Auto)');
  if (names.some((l) => l.length > 20)) throw new Error('Et positionsnavn må højst være 20 tegn');
  const n = names.length;
  const angles = selectorAngles(n);
  const cx = 70, cy = 70, R = 52;
  const esc = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const labelSvg = names.map((l, i) => {
    const a = (angles[i] * Math.PI) / 180;
    const x = Math.round(cx + R * Math.sin(a)), y = Math.round(cy - R * Math.cos(a) + 5);
    return `<text x="${x}" y="${y}" font-size="13" font-weight="600" text-anchor="middle" fill="${DARK}" ${FONT}>${esc(l)}</text>`;
  }).join('');
  const ticks = angles.map((deg) => {
    const a = (deg * Math.PI) / 180;
    return `<line x1="${Math.round(cx + 33 * Math.sin(a))}" y1="${Math.round(cy - 33 * Math.cos(a))}" x2="${Math.round(cx + 38 * Math.sin(a))}" y2="${Math.round(cy - 38 * Math.cos(a))}" stroke="${DARK}" stroke-width="2"/>`;
  }).join('');
  const params = { positions: names.map((label, value) => ({ value, label })), confirm: true };
  return `<g ${auto([{ anim: 'click:select', params }])}>` +
    `<circle cx="${cx}" cy="${cy}" r="30" fill="#e3e3e3" stroke="${LINE}" stroke-width="2.5"/>${ticks}${labelSvg}` +
    // Grebet er symmetrisk om drejepunktet, så "Rotation" drejer det om centrum
    `<g id="greb" ${part({ anim: 'rotate', params: { min: 0, max: n - 1, angle_min: angles[0], angle_max: angles[n - 1] } })}>` +
    `<rect x="${cx - 6}" y="${cy - 26}" width="12" height="52" rx="4" fill="${FILL}" stroke="${DARK}" stroke-width="1.5"/>` +
    `<rect x="${cx - 3}" y="${cy - 24}" width="6" height="14" rx="2" fill="${DARK}"/></g></g>`;
}

/** Giv symbolets rod-<g> et navn (data-hv-name), så det kan kendes i Bindinger og Overview. */
export function withName(svg: string, name: string): string {
  const esc = name.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;').slice(0, 60);
  return svg.replace(/^<g(?=[\s>])/, `<g data-hv-name="${esc}"`);
}
