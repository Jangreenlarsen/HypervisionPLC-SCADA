// ISA-101-inspireret symbolbibliotek: grå i normaltilstand, ingen farver der konkurrerer med alarmer.
// Hvert symbol er ét <g>-element; id sættes ved indsættelse. Animationer bindes bagefter i "Bindinger".

export interface SymbolDef {
  id: string;
  label: string;
  hint: string;
  svg: string;
}

const LINE = '#555';
const FILL = '#9e9e9e';
const PANEL = '#eeeeee';

export const SYMBOLS: SymbolDef[] = [
  {
    id: 'pumpe',
    label: 'Pumpe',
    hint: 'Bind "Fyldfarve" til drift-signalet',
    svg: `<g><circle cx="40" cy="40" r="32" fill="${FILL}" stroke="${LINE}" stroke-width="3"/>` +
      `<path d="M28 22 L60 40 L28 58 Z" fill="${FILL}" stroke="#333" stroke-width="2"/></g>`,
  },
  {
    id: 'motor',
    label: 'Motor',
    hint: 'Bind "Fyldfarve" til drift-signalet',
    svg: `<g><circle cx="40" cy="40" r="32" fill="${FILL}" stroke="${LINE}" stroke-width="3"/>` +
      `<text x="40" y="49" font-size="26" font-weight="600" text-anchor="middle" fill="#333" font-family="Segoe UI, Arial">M</text></g>`,
  },
  {
    id: 'ventil',
    label: 'Ventil',
    hint: 'Bind "Fyldfarve" til åben/lukket',
    svg: `<g><path d="M8 20 L40 40 L8 60 Z M72 20 L40 40 L72 60 Z" fill="${FILL}" stroke="${LINE}" stroke-width="3" stroke-linejoin="round"/>` +
      `<line x1="40" y1="40" x2="40" y2="14" stroke="${LINE}" stroke-width="3"/>` +
      `<rect x="28" y="6" width="24" height="10" fill="${FILL}" stroke="${LINE}" stroke-width="2"/></g>`,
  },
  {
    id: 'tank',
    label: 'Tank',
    hint: 'Bind "Niveau" på det indre rektangel',
    svg: `<g><rect x="0" y="0" width="90" height="140" rx="8" fill="${PANEL}" stroke="${LINE}" stroke-width="3"/>` +
      `<rect id="fyld" x="3" y="3" width="84" height="134" rx="5" fill="#7aa7c7"/></g>`,
  },
  {
    id: 'vaerdi',
    label: 'Værdifelt',
    hint: 'Bind "Tekst" på teksten',
    svg: `<g><rect x="0" y="0" width="160" height="56" rx="4" fill="${PANEL}" stroke="#888"/>` +
      `<text id="titel" x="12" y="20" font-size="12" fill="#5c5c5c" font-family="Segoe UI, Arial">Måling</text>` +
      `<text id="vaerdi" x="12" y="45" font-size="20" font-weight="600" fill="#1f1f1f" font-family="Segoe UI, Arial">--</text></g>`,
  },
  {
    id: 'lampe',
    label: 'Lampe',
    hint: 'Bind "Fyldfarve" til signalet',
    svg: `<g><circle cx="16" cy="16" r="14" fill="${FILL}" stroke="${LINE}" stroke-width="2"/></g>`,
  },
  {
    id: 'knap',
    label: 'Knap',
    hint: 'Bind "Klik: til/fra" eller "Klik: puls"',
    svg: `<g><rect x="0" y="0" width="110" height="40" rx="6" fill="#e3e3e3" stroke="${LINE}" stroke-width="2"/>` +
      `<text x="55" y="26" font-size="15" text-anchor="middle" fill="#1f1f1f" font-family="Segoe UI, Arial">Start</text></g>`,
  },
  {
    id: 'roer_v',
    label: 'Rør (vandret)',
    hint: 'Træk i enderne for at forlænge',
    svg: `<g><rect x="0" y="0" width="160" height="10" fill="${LINE}"/></g>`,
  },
  {
    id: 'roer_l',
    label: 'Rør (lodret)',
    hint: 'Træk i enderne for at forlænge',
    svg: `<g><rect x="0" y="0" width="10" height="160" fill="${LINE}"/></g>`,
  },
];
