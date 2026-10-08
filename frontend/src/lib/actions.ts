// Klik-handlinger på Overview: find handlingen for et element og valider setpunkter.
// Backenden håndhæver det samme (rolle, skrivbar, min/max) — her gives hurtig, dansk feedback.
import type { Binding, LiveValue, TagMeta } from './api';
import { formatValue } from './animate';
import { parseNumber } from './bindingForm';

export function clickFor(bindings: Binding[], element: string): Binding | null {
  return bindings.find((b) => b.element === element && b.anim.startsWith('click:')) ?? null;
}

/** Parse og tjek et indtastet setpunkt i tekniske enheder. Kaster Error med dansk tekst. */
export function parseSetpoint(text: string, meta: TagMeta | undefined): number {
  const v = parseNumber(text, 'Værdien');
  // 0 er en gyldig grænse — sammenlign med null/undefined, ikke truthiness.
  if (meta?.min !== null && meta?.min !== undefined && v < meta.min) {
    throw new Error(`Værdien skal være mindst ${meta.min}${meta.unit ? ' ' + meta.unit : ''}`);
  }
  if (meta?.max !== null && meta?.max !== undefined && v > meta.max) {
    throw new Error(`Værdien må højst være ${meta.max}${meta.unit ? ' ' + meta.unit : ''}`);
  }
  return v;
}

export function rangeText(meta: TagMeta | undefined): string {
  const unit = meta?.unit ? ` ${meta.unit}` : '';
  const lo = meta?.min ?? null;
  const hi = meta?.max ?? null;
  if (lo !== null && hi !== null) return `${lo} – ${hi}${unit}`;
  if (lo !== null) return `mindst ${lo}${unit}`;
  if (hi !== null) return `højst ${hi}${unit}`;
  return 'ingen grænser';
}

export function toggleQuestion(tag: string, live: LiveValue | undefined, meta: TagMeta | undefined): string {
  const name = meta?.description || tag;
  const now = formatValue(live?.value, meta);
  const next = formatValue(typeof live?.value === 'boolean' ? !live.value : live?.value ? 0 : 1, meta);
  return `Skift "${name}" fra ${now} til ${next}?`;
}
