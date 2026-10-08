// ISA-101-inspireret symbolbibliotek: grå i normaltilstand, ingen farver der konkurrerer med alarmer.
// Hvert symbol er ét <g>-element; id sættes ved indsættelse. Animationer bindes bagefter i "Bindinger".
// Rør har tykkelse 10 og centerlinje i y=45 / x=45, så fittings og rør passer sammen. Brug
// SVG-Edits rotation (eller spejling) for at vende en bøjning/T-stykke den rigtige vej.

export type SymbolCategory = 'proces' | 'vvs' | 'el';

export interface SymbolDef {
  id: string;
  label: string;
  hint: string;
  category: SymbolCategory;
  svg: string;
}

export const CATEGORIES: { id: SymbolCategory; label: string }[] = [
  { id: 'proces', label: 'Proces og visning' },
  { id: 'vvs', label: 'Rør og VVS' },
  { id: 'el', label: 'Elektrisk' },
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

export const SYMBOLS: SymbolDef[] = [
  // ---------------------------------------------------------------- Proces og visning
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
    svg: `<g><rect x="0" y="0" width="160" height="10" fill="${LINE}"/></g>`,
  },
  {
    id: 'roer_l', label: 'Rør (lodret)', category: 'vvs', hint: 'Træk i enderne for at forlænge',
    svg: `<g><rect x="0" y="0" width="10" height="160" fill="${LINE}"/></g>`,
  },
  {
    id: 'boejning90', label: 'Bøjning 90°', category: 'vvs', hint: 'Rotér/spejl i Tegn for at vende den',
    svg: `<g>${pipe('M0 45 H25 A20 20 0 0 0 45 25 V0')}</g>`,
  },
  {
    id: 'boejning45', label: 'Bøjning 45°', category: 'vvs', hint: 'Rotér/spejl i Tegn for at vende den',
    svg: `<g>${pipe('M0 45 H30 L60 15', 'round')}</g>`,
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
];
