// Alarmmarkeringen på Overview (v0.87.0): hvilke elementer der får den røde markering, når deres tag er i alarm.
// Kun dele der VISER tagget som en værdi (Værdi/tekst og Niveau) — ikke dele der blot bruger tagget til en animation
// (fx pumpens pil der vokser med flowet, eller en flamme der blafrer over en grænse).
import type { Binding } from './api';

export const ALARM_MARK_ANIMS: ReadonlySet<string> = new Set(['text', 'level']);

export type MarkState = 'unack' | 'ack';

/** Markering pr. element ud fra bindingerne og tagenes alarmtilstand; ukvitteret vinder over kvitteret. */
export function alarmMarks(bindings: Pick<Binding, 'element' | 'tag' | 'anim'>[], alarmTags: Map<string, MarkState>): Map<string, MarkState> {
  const out = new Map<string, MarkState>();
  for (const b of bindings) {
    if (!b.tag || !ALARM_MARK_ANIMS.has(b.anim)) continue;
    const st = alarmTags.get(b.tag);
    if (st && out.get(b.element) !== 'unack') out.set(b.element, st);
  }
  return out;
}
