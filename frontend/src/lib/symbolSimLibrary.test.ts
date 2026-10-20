// Hele biblioteket gennem Symboltestens motor: hver del × hver animation delen kan have × til/fra, tal og position.
// Fanger fx dele hvor en animation ingen synlig virkning har, eller kaster en fejl.
import { describe, expect, it } from 'vitest';
import { SYMBOLS } from './symbols';
import { testParts } from './symbolTest';
import type { AnimType, SrcKind } from './symbolConfig';
import { newAnim, newTag, syncSim, tagRange, type SimTag } from './symbolSim';

const KINDS: SrcKind[] = ['bool', 'num', 'pos'];
const look = (el: Element): string =>
  JSON.stringify([...el.attributes].filter((a) => a.name !== 'data-hv-quality').map((a) => [a.name, a.value]).sort())
  + el.textContent + (el as SVGElement).style.cssText + [...el.querySelectorAll('*')].map((c) => (c as SVGElement).style?.cssText ?? '').join('|');

describe('hele biblioteket', () => {
  const problems: string[] = [];
  for (const s of SYMBOLS) {
    it(`${s.id}: alle dele og animationer kan anvendes, og lav/høj værdi ser forskellig ud`, () => {
      const h = document.createElement('div');
      h.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg">${s.svg}</svg>`;
      const host = h.firstElementChild!;
      for (const part of testParts(s.svg, s.id)) {
        for (const anim of part.types) {
          if (anim === 'flow') continue;   // løbelys kræver tegnet geometri (set i browseren)
          for (const kind of KINDS) {
            const tag: SimTag = { ...newTag([], kind), count: 3, min: 0, max: 100 };
            const a = newAnim(tag, part.id, anim as AnimType);
            const el = part.id === 'all' ? host.firstElementChild! : host.querySelector(`[id="${CSS.escape(part.id)}"]`)!;
            const r = tagRange(tag);
            const seen = new Set<string>();
            const applied = new Map();
            for (const v of [r.min, r.max, r.min]) {
              tag.value = v;
              const missing = syncSim(host, [a], [tag], applied);
              if (missing.length) problems.push(`${s.id}/${part.id}/${anim}/${kind}: del findes ikke`);
              seen.add(look(el));
            }
            // level virker kun på rect, og tekst kun på tekstdele (typesFor sørger for det) — resten skal ændre noget
            if (seen.size < 2) problems.push(`${s.id}/${part.id}/${anim}/${kind}: ingen synlig ændring`);
          }
        }
      }
    });
  }
  it('ingen problemer i biblioteket', () => {
    expect(problems).toEqual([]);
  });
});
