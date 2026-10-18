// Genvejssymboler (v0.75.0): knapper i tegningen, der åbner Alarmer, Trends eller Energi. Symbolets rod har
// data-hv-nav="alarms|trends|energy"; kun disse mål godtages (en tegning kan ikke sende brugeren andre steder hen).

export const NAV_TARGETS = { alarms: 'Alarmer', trends: 'Trends', energy: 'Energi' } as const;
export type NavTarget = keyof typeof NAV_TARGETS;

/** Målet for et klik (elementet eller en af dets forfædre har data-hv-nav), eller null. */
export function navTarget(el: Element | null | undefined): NavTarget | null {
  const host = el?.closest?.('[data-hv-nav]');
  const v = host?.getAttribute('data-hv-nav') ?? '';
  return Object.prototype.hasOwnProperty.call(NAV_TARGETS, v) ? (v as NavTarget) : null;
}

/** Alarmknappens mærke: antal aktive alarmer; "unack" når der er ukvitterede (også ophørte), "none" = skjult. */
export function alarmBadge(s: { active: number; unacked: number } | null | undefined): { text: string; state: 'none' | 'active' | 'unack' } {
  const active = Math.max(0, s?.active ?? 0), unacked = Math.max(0, s?.unacked ?? 0);
  if (!active && !unacked) return { text: '', state: 'none' };
  const n = Math.max(active, unacked);
  return { text: n > 99 ? '99+' : String(n), state: unacked ? 'unack' : 'active' };
}

/** Gør genvejene klikbare (markør og hover) i en monteret tegning. */
export function markNavClickable(root: ParentNode | null | undefined): void {
  root?.querySelectorAll('[data-hv-nav]').forEach((el) => el.classList.add('hv-clickable'));
}

/** Sæt alarmknappernes mærke (delene "maerke" og "antal") ud fra alarmoversigten. */
export function applyAlarmBadges(root: ParentNode | null | undefined, s: { active: number; unacked: number } | null | undefined): void {
  const b = alarmBadge(s);
  root?.querySelectorAll('[data-hv-nav="alarms"]').forEach((btn) => {
    const mark = btn.querySelector('[data-hv-pid="maerke"]');
    const count = btn.querySelector('[data-hv-pid="antal"]');
    for (const el of [mark, count]) {
      if (!el) continue;
      el.classList.toggle('hv-nav-badge-active', b.state === 'active');
      el.classList.toggle('hv-nav-badge-unack', b.state === 'unack');
      (el as SVGElement).style.display = b.state === 'none' ? 'none' : '';
    }
    if (count) count.textContent = b.text;
  });
}
