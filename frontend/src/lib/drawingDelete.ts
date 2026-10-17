// Slet en tegning — fælles for siderne Tegninger og Tegn: hent hvad sletningen rammer, bekræft, slet.
import { ask as askUser } from './ask';
import { api, get } from './api';

export interface DrawingUsage {
  id: string; name: string; versions: number; bindings: number;
  goto_from: string[]; start: boolean; users: string[];
}

/** Bekræftelsesteksten — nævner kun det der faktisk rammes, så vigtige advarsler ikke drukner. */
export function deleteWarning(u: DrawingUsage): string {
  const lines = [`Slet tegningen "${u.name}"?`, '',
    `Det fjerner alle ${u.versions} version${u.versions === 1 ? '' : 'er'} og ${u.bindings} binding${u.bindings === 1 ? '' : 'er'} og kan ikke fortrydes.`];
  if (u.goto_from.length) lines.push('', `⚠ Disse tegninger har en "gå til"-knap hertil, som holder op med at virke: ${u.goto_from.join(', ')}.`);
  if (u.start) lines.push('', 'Tegningen er start-tegning — Overview åbner derefter med den første tegning i stedet.');
  if (u.users.length) lines.push('', `Brugere med adgang til tegningen: ${u.users.join(', ')} (de mister adgangen til den).`);
  return lines.join('\n');
}

/** Spørg, slet og returnér true hvis tegningen blev slettet. Kaster Error med serverens fejltekst. */
export async function deleteDrawingFlow(id: string, ask: (text: string) => boolean | Promise<boolean> = (t) => askUser(t, { ok: 'Slet', danger: true })): Promise<boolean> {
  const usage = await get<DrawingUsage>(`/api/drawings/${encodeURIComponent(id)}/usage`);
  if (!(await ask(deleteWarning(usage)))) return false;
  await api('DELETE', `/api/drawings/${encodeURIComponent(id)}`);
  return true;
}
