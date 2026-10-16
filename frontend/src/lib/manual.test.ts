// Brugermanualen (v0.52.0): opbygning, rendering, søgning — og at alle menusider og symboler er omtalt.
import { describe, expect, it } from 'vitest';
import { buildChapters, highlight, renderMarkdown, searchChapters, slugify } from './manual';
import { NAV } from './nav';
import { SYMBOLS } from './symbols';

const files = import.meta.glob('../manual/*.md', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;
const chapters = buildChapters(files);
const all = chapters.map((c) => c.md).join('\n');

describe('slugify', () => {
  it('dansk tekst bliver til et kort anker', () => {
    expect(slugify('Hvad rammer det?')).toBe('hvad-rammer-det');
    expect(slugify('Ældre pakker på Øen')).toBe('aeldre-pakker-paa-oeen');
    expect(slugify('3-vejs ventil (AB → A)')).toBe('3-vejs-ventil-ab-a');
    expect(slugify('???')).toBe('afsnit');
  });
});

describe('buildChapters', () => {
  it('sorterer efter filnavn, tager titlen fra første overskrift og samler ## som afsnit', () => {
    const c = buildChapters({ '../manual/02-b.md': '# Bravo\n\n## Del 1\n\n## Del 1\n\n### Under', '../manual/01-a.md': '# Alfa\n\n## Æble' });
    expect(c.map((x) => x.slug)).toEqual(['a', 'b']);
    expect(c.map((x) => x.title)).toEqual(['Alfa', 'Bravo']);
    expect(c[0].headings).toEqual([{ id: 'm-aeble', text: 'Æble' }]);
    expect(c[1].headings.map((h) => h.id)).toEqual(['m-del-1', 'm-del-1-2']);     // samme overskrift to gange får forskellige anker
  });

  it('fjerner en generator-kommentar øverst', () => {
    expect(buildChapters({ '../manual/07-x.md': '<!-- GENERERET -->\n# Titel\n' })[0].md.startsWith('# Titel')).toBe(true);
  });
});

describe('renderMarkdown', () => {
  it('giver tabeller, fed skrift og anker på overskrifter (samme id som kapiteloversigten)', () => {
    const md = '# T\n\n## Første afsnit\n\n| a | b |\n| - | - |\n| **x** | `y` |\n';
    const html = renderMarkdown(md);
    expect(html).toContain('<table>');
    expect(html).toContain('<strong>x</strong>');
    expect(html).toContain('id="m-foerste-afsnit"');
    expect(buildChapters({ '../manual/01-t.md': md })[0].headings[0].id).toBe('m-foerste-afsnit');
  });

  it('renser farligt indhold (script, hændelser, javascript-links)', () => {
    const html = renderMarkdown('hej <script>alert(1)</script> <img src=x onerror="alert(2)"> [klik](javascript:alert(3))');
    expect(html).not.toMatch(/<script|onerror|javascript:/i);
  });
});

describe('søgning', () => {
  const c = buildChapters({ '../manual/01-a.md': '# A\n\nLogikblokke samler tags.\n\nIntet her.', '../manual/02-b.md': '# B\n\nEn logikblok har op til 4 indgange.\nOg en logikblok mere.' });
  it('finder kapitler og sorterer efter antal træf; uden hensyn til store/små bogstaver', () => {
    const hits = searchChapters(c, 'LOGIKBLOK');
    expect(hits.map((h) => [h.chapter.slug, h.count])).toEqual([['b', 2], ['a', 1]]);
    expect(hits[0].snippets.length).toBeGreaterThan(0);
  });
  it('for korte eller tomme søgninger giver ingenting', () => {
    expect(searchChapters(c, '')).toEqual([]);
    expect(searchChapters(c, 'l')).toEqual([]);
    expect(searchChapters(c, 'findes-ikke')).toEqual([]);
  });
  it('highlight fremhæver kun tekst, aldrig tags eller attributter', () => {
    const root = document.createElement('div');
    root.innerHTML = '<p class="blok">En blok og en <b>blok</b></p><a href="#blok">link</a>';
    expect(highlight(root, 'blok')).toBe(2);
    expect(root.querySelectorAll('mark').length).toBe(2);
    expect(root.querySelector('p')!.getAttribute('class')).toBe('blok');
    expect(root.querySelector('a')!.getAttribute('href')).toBe('#blok');
    expect(highlight(root, 'b')).toBe(0);
  });
});

describe('manualens indhold', () => {
  it('har kapitler i rækkefølge med unikke adresser og en overskrift hver', () => {
    expect(chapters.length).toBeGreaterThanOrEqual(10);
    expect(new Set(chapters.map((c) => c.slug)).size).toBe(chapters.length);
    for (const c of chapters) expect(c.md.startsWith('# '), c.slug).toBe(true);
  });

  it('alle sider i menuen er omtalt', () => {
    for (const p of NAV.flatMap((g) => g.pages)) expect(all, p.label).toContain(p.label);
  });

  it('alle bibliotekssymboler er omtalt (kapitlet genereres — se manualGen.test.ts)', () => {
    for (const s of SYMBOLS) expect(all, s.label).toContain(s.label);
  });

  it('nævner de vigtigste begreber', () => {
    for (const word of ['logikblok', 'Nøglelås', 'Løbelys', 'Beregning', 'Hurtig opsætning', 'Opdatering', 'Backup', 'Ugeprogram', 'Energi', 'Trends', 'Alarmer'])
      expect(all.toLowerCase(), word).toContain(word.toLowerCase());
  });

  it('alle kapitler kan gengives uden fejl', () => {
    for (const c of chapters) expect(renderMarkdown(c.md).length, c.slug).toBeGreaterThan(100);
  });
});
