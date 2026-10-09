// Hvor et tag får sin værdi fra (samme grammatik som backendens tagsource.py).

export type SourceKind = 'intern' | 'rtu' | 'mbx';

export function sourceKind(source: string): SourceKind {
  const kind = source.split(':')[1]?.toLowerCase();
  return kind === 'rtu' ? 'rtu' : kind === 'mbx' ? 'mbx' : 'intern';
}

export const SOURCE_LABEL: Record<SourceKind, string> = {
  intern: 'Intern',
  rtu: 'Extern (RS485)',
  mbx: 'Expansion board',
};
