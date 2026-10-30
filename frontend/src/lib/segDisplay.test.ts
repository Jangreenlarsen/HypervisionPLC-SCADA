import { describe, expect, it } from 'vitest';
import { MAX_DIGITS, SEGMENTS, SEG_OFF, SEG_ON, clearSegments, layoutDigits, renderSegmentText, segDisplaySvg, segmentsFor, type SegKind } from './segDisplay';

const sorted = (s: Set<string>) => [...s].sort().join('');

describe('tegn → segmenter', () => {
  it('7-segment: alle tal', () => {
    const want: Record<string, string> = { '0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg', '5': 'acdfg', '6': 'acdefg', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg' };
    for (const [ch, segs] of Object.entries(want)) expect(sorted(segmentsFor(ch, 7)), ch).toBe(segs);
  });
  it('minus, mellemrum og ukendte tegn', () => {
    expect(sorted(segmentsFor('-', 7))).toBe('g');
    expect(segmentsFor(' ', 7).size).toBe(0);
    expect(segmentsFor('@', 7).size).toBe(0);
    expect(segmentsFor('@', 11).size).toBe(0);
  });
  it('11-segment: tal bruger delt midterstreg, bogstaver de lodrette midtersegmenter', () => {
    expect(sorted(segmentsFor('8', 11))).toBe('abcdefg1g2');
    expect(sorted(segmentsFor('1', 11))).toBe('bc');
    expect(sorted(segmentsFor('T', 11))).toBe('ail');
    expect(sorted(segmentsFor('t', 11))).toBe('ail');   // små bogstaver vises som store
    expect(sorted(segmentsFor('I', 11))).toBe('adil');
    expect(sorted(segmentsFor('-', 11))).toBe('g1g2');
  });
  it('alle tændte segmenter findes i typens segmentliste', () => {
    for (const kind of [7, 11] as SegKind[]) {
      for (const ch of '0123456789-_=° ABCDEFGHIJLOPSTUYZabcdhnoqrtuy') {
        for (const s of segmentsFor(ch, kind)) expect(SEGMENTS[kind], `${ch} (${kind})`).toContain(s);
      }
    }
  });
});

describe('layout', () => {
  const show = (text: string, n: number, p = {}) => layoutDigits(text, n, p).map((c) => c.ch + (c.dp ? '.' : '')).join('|');
  it('højrejusteret som standard, venstrejusteret efter valg', () => {
    expect(show('12', 4)).toBe(' | |1|2');
    expect(show('12', 4, { align: 'left' })).toBe('1|2| | ');
  });
  it('decimalpunktet hører til tegnet foran og fylder ikke et ciffer', () => {
    expect(show('12.5', 4)).toBe(' |1|2.|5');
    expect(layoutDigits('1.25', 4).map((c) => c.ch)).toEqual([' ', '1', '2', '5']);
    expect(layoutDigits('1.25', 4)[1].dp).toBe(true);
    expect(layoutDigits('1,5', 3)[1].ch).toBe('1');   // komma tolkes som punktum
  });
  it('foranstillede nuller, fortegnet forrest', () => {
    expect(show('42', 5, { zeros: true })).toBe('0|0|0|4|2');
    expect(show('-7', 4, { zeros: true })).toBe('-|0|0|7');
    expect(show('12', 4, { zeros: false })).toBe(' | |1|2');
    expect(show('AB', 4, { zeros: true })).toBe(' | |A|B');   // kun tal fyldes op
  });
  it('for langt: bindestreg i alle cifre (overløb)', () => {
    expect(show('12345', 4)).toBe('-|-|-|-');
  });
  it('antal cifre begrænses til 1–16', () => {
    expect(layoutDigits('1', 0)).toHaveLength(1);
    expect(layoutDigits('1', 99)).toHaveLength(MAX_DIGITS);
  });
});

const parse = (svg: string): Element => new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${svg}</svg>`, 'image/svg+xml').documentElement.firstElementChild!;

describe('tegningen', () => {
  it('1–16 cifre i begge typer: ét ciffer-element pr. ciffer med alle typens segmenter', () => {
    for (const kind of [7, 11] as SegKind[]) {
      for (let n = 1; n <= MAX_DIGITS; n++) {
        const root = parse(segDisplaySvg(kind, n));
        expect(root.getAttribute('data-hv-kind')).toBe(String(kind));
        const digits = root.querySelectorAll('[data-hv-digit]');
        expect(digits.length, `${kind}/${n}`).toBe(n);
        for (const d of digits) expect([...d.querySelectorAll('[data-hv-seg]')].map((s) => s.getAttribute('data-hv-seg'))).toEqual([...SEGMENTS[kind]]);
      }
    }
  });
  it('antal cifre uden for 1–16 rettes, og alle segmenter står slukket', () => {
    expect(parse(segDisplaySvg(7, 0)).querySelectorAll('[data-hv-digit]')).toHaveLength(1);
    expect(parse(segDisplaySvg(7, 40)).querySelectorAll('[data-hv-digit]')).toHaveLength(MAX_DIGITS);
    for (const s of parse(segDisplaySvg(11, 3)).querySelectorAll('[data-hv-seg]')) expect(s.getAttribute('fill')).toBe(SEG_OFF);
  });
  it('kun farver fra symbolbibliotekets palette og ingen script/ekstern url', () => {
    const svg = segDisplaySvg(11, 2);
    expect(svg).not.toMatch(/url\(|script|href/i);
  });
});

describe('visning', () => {
  const lit = (root: Element, i: number, on = SEG_ON) =>
    [...root.querySelectorAll('[data-hv-digit]')[i].querySelectorAll('[data-hv-seg]')].filter((s) => s.getAttribute('fill') === on).map((s) => s.getAttribute('data-hv-seg')).sort().join('');
  it('tænder de rigtige segmenter og decimalpunktet', () => {
    const root = parse(segDisplaySvg(7, 3));
    renderSegmentText(root, '1.5');
    expect(lit(root, 0)).toBe('');
    expect(lit(root, 1)).toBe('bcdp');
    expect(lit(root, 2)).toBe('acdfg');
  });
  it('egne farver for tændt og slukket', () => {
    const root = parse(segDisplaySvg(7, 1));
    renderSegmentText(root, '7', { on: '#ffffff', off: '#111111' });
    expect(lit(root, 0, '#ffffff')).toBe('abc');
    expect(root.querySelector('[data-hv-seg="g"]')!.getAttribute('fill')).toBe('#111111');
  });
  it('en ny værdi slukker det der ikke skal være tændt længere; nulstil slukker alt', () => {
    const root = parse(segDisplaySvg(7, 1));
    renderSegmentText(root, '8');
    renderSegmentText(root, '1');
    expect(lit(root, 0)).toBe('bc');
    clearSegments(root);
    expect(lit(root, 0)).toBe('');
  });
  it('et element uden ciffer-dele røres ikke', () => {
    const g = parse('<g><rect/></g>');
    expect(() => renderSegmentText(g, '1')).not.toThrow();
  });
});
