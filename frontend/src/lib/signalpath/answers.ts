// Signalveje: svar → betingelser til backend, og valg af start/slut ved klik. Del af signalPath.ts (v4.15.1).
// ---------------------------------------------------------------- svar → betingelser (backend: services/signal_paths.py)
/** `derived`: et beregnet signal (v5.10.0) — et symbols position eller en logikblok; `name` er dets id, `description` dets visningsnavn;
 *  `labels`: positionernes navne (værdien er positionens nummer). */
export interface TagInfo { name: string; is_bool: boolean; unit: string; description: string; derived?: boolean; group?: string; labels?: string[] }
export type Cmp = '' | 'ge' | 'le' | 'eq';
/** Svaret for ét symbol: ingen betingelse, eller et tag (til/fra, eller et tal sammenlignet med en grænse). */
export interface Answer { element: string; src: string; on: boolean; cmp: Cmp; value: number | null }
export interface Condition { element: string; src: string; neg: boolean; cmp: Cmp; value: number | null }

/** Forslag ud fra symbolets egne tags: helst et til/fra-tag (tilbagemelding), ellers ingen betingelse. */
export function suggestAnswer(element: string, own: TagInfo[]): Answer {
  const t = own.find((x) => x.is_bool) ?? own[0];
  if (!t) return { element, src: '', on: true, cmp: '', value: null };
  return t.is_bool ? { element, src: t.name, on: true, cmp: '', value: null } : { element, src: t.name, on: true, cmp: 'ge', value: 1 };
}

/** Svarene → betingelser til backend. Tomme svar (ingen betingelse) springes over. → { conditions, errors } */
export function conditionsFrom(answers: Answer[], tags: TagInfo[]): { conditions: Condition[]; errors: string[] } {
  const byName = new Map(tags.map((t) => [t.name, t]));
  const conditions: Condition[] = [];
  const errors: string[] = [];
  for (const a of answers) {
    if (!a.src) continue;
    const t = byName.get(a.src);
    if (!t) {
      errors.push(`Tagget '${a.src}' findes ikke`);
      continue;
    }
    if (t.is_bool) conditions.push({ element: a.element, src: a.src, neg: !a.on, cmp: '', value: null });
    else if (!a.cmp || a.value === null || !Number.isFinite(a.value)) errors.push(`${t.derived ? t.description : a.src}: vælg ≥, ≤ eller = og en grænseværdi`);
    else conditions.push({ element: a.element, src: a.src, neg: !!t.labels?.length && !a.on, cmp: a.cmp, value: a.value });   // position: "er ikke" (v5.12.0)
  }
  return { conditions, errors };
}

/** En gemt betingelse tilbage til et svar (når en signalvej rettes). */
export function answerFrom(c: Condition): Answer {
  return { element: c.element, src: c.src, on: !c.neg, cmp: c.cmp, value: c.value };
}

// ---------------------------------------------------------------- vælg start/slut ved klik i tegningen (v4.5.0)
/** Det element, der netop er valgt i tegningen, som start eller slut — eller en forklaring på, hvorfor det ikke kan bruges. */
export function pickNext(which: 'start' | 'end', selected: string[], allowed: Set<string>, start: string): { id?: string; error?: string } {
  const id = selected.find((s) => allowed.has(s));
  if (!id) return { error: 'Det valgte er et rør, en tekst eller en visning — klik på et anlægssymbol (fx kedel, pumpe, radiator)' };
  if (which === 'end' && id === start) return { error: 'Det er startsymbolet — klik på et andet symbol som slut' };
  return { id };
}
