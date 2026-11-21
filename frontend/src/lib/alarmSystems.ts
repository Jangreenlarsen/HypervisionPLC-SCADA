// Alarmer pr. system (tegning): hvilke alarmer og hændelser hører til et valgt system.
export interface AlarmSystem { id: string; name: string; tags: string[] }
export interface AlarmLike { key: string; kind?: string; tag?: string }

/** Værdien i valget for alarmer, der ikke står på nogen tegning. */
export const NO_SYSTEM = '-';

/** Systemerne (tegningerne), alarmen hører til: symbolalarmer til deres tegning, tag-alarmer til tegninger, der bruger tagget.
 *  SCADA- og PLC-forbindelsesalarmer og alt uden tag hører ikke til et bestemt system (tom liste). */
export function systemsOf(systems: AlarmSystem[], a: AlarmLike): AlarmSystem[] {
  if (a.key.startsWith('sym:')) return systems.filter((s) => s.id === a.key.split(':')[1]);
  if (a.kind === 'sys' || a.kind === 'comm' || !a.tag) return [];
  return systems.filter((s) => s.tags.includes(a.tag as string));
}

/** Skal alarmen/hændelsen vises for det valgte system (null = alle, NO_SYSTEM = kun alarmer uden tegning)? SCADA- og PLC-forbindelsesalarmer
 *  og hændelser uden tag vises altid. */
export function inSystem(systems: AlarmSystem[], selected: string, a: AlarmLike): boolean {
  if (!selected) return true;
  const general = a.kind === 'sys' || a.kind === 'comm' || (!a.tag && !a.key.startsWith('sym:'));
  if (general) return true;
  const mine = systemsOf(systems, a);
  return selected === NO_SYSTEM ? mine.length === 0 : mine.some((s) => s.id === selected);
}

/** Det system, Alarmer åbner med: den tegning, man kom fra (hvis den findes), ellers alle. Står man på en tegning, ser man dens alarmer. */
export function defaultSystem(systems: AlarmSystem[], lastDrawingId: string | null): string {
  return lastDrawingId && systems.some((s) => s.id === lastDrawingId) ? lastDrawingId : '';
}
