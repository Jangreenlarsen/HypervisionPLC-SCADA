// Gennemgang: virker HVER animationstype for HVER art af tag (til/fra, tal, position) — og ændrer den noget synligt?
import { describe, expect, it } from 'vitest';
import type { AnimType, SrcKind } from './symbolConfig';
import { newAnim, newTag, retune, syncSim, tagRange, type SimTag } from './symbolSim';
import { segDisplaySvg } from './segDisplay';

const SVG = '<g><rect id="r" x="0" y="0" width="20" height="10" fill="#ccc" stroke="#000" stroke-width="2"/>' +
  '<path id="p" d="M0 20 H90" stroke="#000" stroke-width="10" fill="none"/><text id="t">x</text>' +
  segDisplaySvg(7, 3).replace('<g data-hv-kind', '<g id="d" data-hv-kind') + '</g>';
const host = () => {
  const h = document.createElement('div');
  h.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg">${SVG}</svg>`;
  return h.firstElementChild!;
};
const PART: Record<AnimType, string> = {
  fill: 'r', stroke: 'r', blink: 'r', visible: 'r', spin: 'r', flicker: 'r', level: 'r', opacity: 'r', text: 't', rotate: 'r', move: 'r', scale: 'r', flow: 'p', segments: 'd',
};
const ALL = Object.keys(PART) as AnimType[];
const KINDS: SrcKind[] = ['bool', 'num', 'pos'];

/** Det synlige aftryk af delen: attributter og style (uden data-hv-quality, som altid sættes). */
const look = (el: Element): string =>
  JSON.stringify([...el.attributes].filter((a) => a.name !== 'data-hv-quality').map((a) => [a.name, a.value]).sort()) + el.textContent + (el as SVGElement).style.cssText + (el.hasAttribute('data-hv-kind') ? el.innerHTML : '');   // displayet ændrer sine segmenter (børn)

function lowHigh(t: SimTag): [number, number] {
  const r = tagRange(t);
  return [r.min, r.max];
}

describe('alle animationer virker på alle arter af tags', () => {
  for (const anim of ALL) {
    for (const kind of KINDS) {
      it(`${anim} / ${kind}: lav og høj værdi giver forskelligt udseende`, () => {
        const h = host();
        const tag: SimTag = { ...newTag([], kind), count: 3, min: 0, max: 100 };
        const a = newAnim(tag, PART[anim], anim);
        retune([a], tag);
        const el = h.querySelector(`#${PART[anim]}`)!;
        const seen = new Set<string>();
        const [lo, hi] = lowHigh(tag);
        const applied = new Map();
        for (const v of [lo, hi, lo]) {
          tag.value = v;
          expect(syncSim(h, [a], [tag], applied)).toEqual([]);
          seen.add(look(el));
        }
        // flow kræver et tegnet rør (flowlag) — her kontrolleres kun at det kan anvendes uden fejl
        if (anim === 'flow') return;
        expect(seen.size, `${anim}/${kind} ændrer ikke noget`).toBeGreaterThan(1);
      });
    }
  }
});

describe('tekst', () => {
  it('til/fra-tekst bruges ved Til og Fra (værdien er et til/fra-tag)', () => {
    const h = host();
    const tag: SimTag = { ...newTag([], 'bool') };
    const a = newAnim(tag, 't', 'text');
    a.params = { true_text: 'pis!!!', false_text: 'lort!!' };
    const applied = new Map();
    tag.value = 0;
    syncSim(h, [a], [tag], applied);
    expect(h.querySelector('#t')!.textContent).toBe('lort!!');
    tag.value = 1;
    syncSim(h, [a], [tag], applied);
    expect(h.querySelector('#t')!.textContent).toBe('pis!!!');
  });
  it('uden egne tekster vises Til/Fra', () => {
    const h = host();
    const tag: SimTag = { ...newTag([], 'bool'), value: 1 };
    syncSim(h, [newAnim(tag, 't', 'text')], [tag], new Map());
    expect(h.querySelector('#t')!.textContent).toBe('Til');
  });
});

describe('til/fra på tal-animationer giver en tydelig forskel', () => {
  const run = (anim: AnimType, part: string, value: number) => {
    const h = host();
    const tag: SimTag = { ...newTag([], 'bool'), value };
    syncSim(h, [newAnim(tag, part, anim)], [tag], new Map());
    return h.querySelector(`#${part}`) as SVGElement;
  };
  it('størrelse: Fra er 50 % og Til er 150 %', () => {
    expect(run('scale', 'r', 0).getAttribute('transform')).toContain('scale(0.5)');
    expect(run('scale', 'r', 1).getAttribute('transform')).toContain('scale(1.5)');
  });
  it('gennemsigtighed: Fra er usynlig og Til er fuldt synlig', () => {
    expect(run('opacity', 'r', 0).style.opacity).toBe('0');
    expect(run('opacity', 'r', 1).style.opacity).toBe('1');
  });
  it('niveau: Fra er tom og Til er fuld', () => {
    expect(run('level', 'r', 0).getAttribute('height')).toBe('0');
    expect(run('level', 'r', 1).getAttribute('height')).toBe('10');
  });
  it('tal og positioner: området følger tagget, så hele skyderen virker', () => {
    const h = host();
    const num: SimTag = { ...newTag([], 'num'), min: 0, max: 40, value: 40 };
    syncSim(h, [newAnim(num, 'r', 'scale')], [num], new Map());
    expect((h.querySelector('#r') as SVGElement).getAttribute('transform')).toContain('scale(1.5)');
    const pos: SimTag = { ...newTag([], 'pos'), count: 3, value: 2 };
    syncSim(h, [newAnim(pos, 'r', 'opacity')], [pos], new Map());
    expect((h.querySelector('#r') as SVGElement).style.opacity).toBe('1');
    pos.value = 1;
    syncSim(h, [newAnim(pos, 'r', 'opacity')], [pos], new Map());
    expect((h.querySelector('#r') as SVGElement).style.opacity).toBe('0.5');
  });
});
