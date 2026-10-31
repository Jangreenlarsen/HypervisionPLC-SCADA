// Foldbare sektioner i Tegns højre panel (panels.ts).
import { describe, expect, it } from 'vitest';
import { DEFAULT_PANELS, parsePanels, togglePanel, togglePin } from './panels';

describe('togglePanel', () => {
  it('åbner én og folder de ikke-fastgjorte sammen', () => {
    const s = togglePanel({ open: ['valgt', 'symboler'], pinned: ['valgt'] }, 'objekter');
    expect(s.open.sort()).toEqual(['objekter', 'valgt']);
  });
  it('lukker en åben — en fastgjort løsnes samtidig', () => {
    expect(togglePanel({ open: ['valgt'], pinned: ['valgt'] }, 'valgt')).toEqual({ open: [], pinned: [] });
  });
});

describe('togglePin', () => {
  it('fastgør åbner sektionen', () => {
    expect(togglePin({ open: [], pinned: [] }, 'objekter')).toEqual({ open: ['objekter'], pinned: ['objekter'] });
  });
  it('løsn holder den åben, til en anden åbnes', () => {
    const s = togglePin({ open: ['objekter'], pinned: ['objekter'] }, 'objekter');
    expect(s).toEqual({ open: ['objekter'], pinned: [] });
    expect(togglePanel(s, 'symboler').open).toEqual(['symboler']);
  });
});

describe('parsePanels', () => {
  it('ødelagte eller manglende data giver standarden', () => {
    expect(parsePanels(null)).toEqual(DEFAULT_PANELS);
    expect(parsePanels('{x')).toEqual(DEFAULT_PANELS);
  });
  it('ukendte sektioner fjernes; fastgjorte er altid åbne', () => {
    expect(parsePanels(JSON.stringify({ open: ['symboler', 'hmm'], pinned: ['objekter'] }))).toEqual({ open: ['symboler', 'objekter'], pinned: ['objekter'] });
  });
});
