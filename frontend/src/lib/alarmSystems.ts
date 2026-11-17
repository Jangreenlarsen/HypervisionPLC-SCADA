// Alarmer pr. system (tegning): hvilke alarmer og hændelser hører til et valgt system.
export interface AlarmSystem { id: string; name: string; tags: string[] }
export interface AlarmLike { key: string; kind?: string; tag?: string }

/** Skal alarmen/hændelsen vises, når `system` er valgt (null = alle systemer)? Symbolalarmer hører til deres tegning, tag-alarmer til
 *  tegninger, der bruger tagget; SCADA- og PLC-forbindelsesalarmer og alt uden tag vises altid. */
export function inSystem(system: AlarmSystem | null, a: AlarmLike): boolean {
  if (!system) return true;
  if (a.key.startsWith('sym:')) return a.key.split(':')[1] === system.id;
  if (a.kind === 'sys' || a.kind === 'comm' || !a.tag) return true;
  return system.tags.includes(a.tag);
}
