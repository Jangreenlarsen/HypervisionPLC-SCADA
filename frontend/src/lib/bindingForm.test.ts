import { describe, expect, it } from 'vitest';
import { emptyForm, flatten, fromForm, groupIds, nextBinding, toDrafts, parseNumber, pickElement, toForm, toHex } from './bindingForm';

describe('parseNumber', () => {
  it('accepterer decimalkomma og 0', () => {
    expect(parseNumber('2,5', 'X')).toBe(2.5);
    expect(parseNumber('0', 'X')).toBe(0);
  });
  it('tom og ugyldig giver dansk fejl', () => {
    expect(() => parseNumber('  ', 'Min')).toThrow('Min skal udfyldes');
    expect(() => parseNumber('abc', 'Max')).toThrow('Max skal være et tal');
  });
});

describe('fromForm', () => {
  it('kræver tag', () => expect(() => fromForm(emptyForm('', 'text'))).toThrow('Vælg et tag'));

  it('move: dx/dy med decimalkomma; begge 0 afvises; læses tilbage', () => {
    const p = fromForm({ ...emptyForm('T', 'move'), dx: '-12,5', dy: '30' }).params;
    expect(p).toEqual({ min: 0, max: 100, dx: -12.5, dy: 30 });
    expect(() => fromForm({ ...emptyForm('T', 'move'), dx: '0', dy: '0' })).toThrow('begge være 0');
    expect(toForm({ tag: 'T', anim: 'move', params: p })).toMatchObject({ dx: '-12.5', dy: '30' });
  });

  it('text: tomme decimaler udelades, 0 bevares', () => {
    expect(fromForm(emptyForm('T', 'text')).params).not.toHaveProperty('decimals');
    expect(fromForm({ ...emptyForm('T', 'text'), decimals: '0' }).params.decimals).toBe(0);
    expect(() => fromForm({ ...emptyForm('T', 'text'), decimals: '1.5' })).toThrow('heltal');
  });

  it('text: tekst før/efter gemmes som skrevet og læses tilbage', () => {
    const b = fromForm({ ...emptyForm('T', 'text'), prefix: 'Tank : ', suffix: ' liter' });
    expect(b.params).toMatchObject({ prefix: 'Tank : ', suffix: ' liter' });
    expect(fromForm(emptyForm('T', 'text')).params).not.toHaveProperty('prefix');
    const f = toForm({ tag: 'T', anim: 'text', params: b.params });
    expect([f.prefix, f.suffix]).toEqual(['Tank : ', ' liter']);
  });

  it('level: min skal være mindre end max', () => {
    expect(fromForm({ ...emptyForm('T', 'level'), min: '0', max: '50' }).params).toEqual({ min: 0, max: 50, direction: 'up' });
    expect(() => fromForm({ ...emptyForm('T', 'level'), min: '5', max: '5' })).toThrow('mindre end max');
  });

  it('fill: tærskler parses og skal være stigende', () => {
    const f = { ...emptyForm('T', 'fill'), thresholds: [{ value: '0', color: 'blue' }, { value: '10,5', color: 'red' }] };
    expect(fromForm(f).params.thresholds).toEqual([{ value: 0, color: 'blue' }, { value: 10.5, color: 'red' }]);
    expect(() => fromForm({ ...f, thresholds: [...f.thresholds].reverse() })).toThrow('stigende');
  });

  it('toForm → fromForm er tabsfri for rotate', () => {
    const b = { tag: 'Fan', anim: 'rotate' as const, params: { min: 0, max: 1500, angle_min: -90, angle_max: 90 } };
    expect(fromForm(toForm(b))).toEqual({ tag: 'Fan', anim: 'rotate', params: b.params });
  });
});

describe('pickElement', () => {
  it('finder nærmeste forfader med id, men ikke selve svg-roden', () => {
    document.body.innerHTML = '<div id="c"><svg id="rod"><g id="Pumpe"><circle></circle></g><rect></rect></svg></div>';
    const svg = document.querySelector('svg')!;
    expect(pickElement(document.querySelector('circle'), svg)?.id).toBe('Pumpe');
    expect(pickElement(document.querySelector('rect'), svg)).toBeNull();
  });
});

describe('toHex', () => {
  it('normaliserer korte hex og navne', () => {
    expect(toHex('#abc')).toBe('#aabbcc');
    expect(toHex('#2e7d32')).toBe('#2e7d32');
    expect(toHex('red')).toBe('#000000');
  });
});

describe('nextBinding', () => {
  it('første binding: tekst på tekst-element, fyldfarve på figur, intet tag', () => {
    expect(nextBinding([], true)).toMatchObject({ tag: '', anim: 'text' });
    expect(nextBinding([], false)).toMatchObject({ tag: '', anim: 'fill' });
  });
  it('kombinér: samme tag, og en animation der ikke allerede er brugt (tekst → blink)', () => {
    const b = nextBinding([emptyForm('test01', 'text')], true);
    expect(b).toMatchObject({ tag: 'test01', anim: 'blink' });
    expect(nextBinding([emptyForm('test01', 'text'), b], true).anim).toBe('fill');
  });
  it('arver seneste tag med et tag (ikke gå-til-tegning)', () => {
    expect(nextBinding([emptyForm('A', 'fill'), emptyForm('B', 'blink'), emptyForm('', 'click:goto')], false).tag).toBe('B');
  });
});

describe('toDrafts / flatten', () => {
  it('samme tag = én binding med flere animationer; gå-til-tegning og tomt tag står for sig', () => {
    const d = toDrafts([emptyForm('A', 'text'), emptyForm('B', 'fill'), emptyForm('A', 'blink'),
      emptyForm('', 'click:goto'), emptyForm('', 'text')]);
    expect(d.map((x) => x.gid)).toEqual([0, 1, 0, 2, 3]);
    expect(groupIds(d)).toEqual([0, 1, 2, 3]);
    expect(flatten(d).map((x) => `${x.tag}:${x.anim}`)).toEqual(['A:text', 'A:blink', 'B:fill', ':click:goto', ':text']);
  });
  it('nye gid kan starte efter de eksisterende', () => expect(toDrafts([emptyForm('A', 'text')], 7)[0].gid).toBe(7));
});
