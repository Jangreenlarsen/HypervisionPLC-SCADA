// Spørgsmål til brugeren i en dialog på siden i stedet for browserens confirm()/prompt() (BUGS.md v0.63.2): Firefox kan
// blokere en sides dialoger ("Tillad ikke denne side at vise flere dialoger"), og så svarer confirm() straks "Annullér"
// uden at vise noget — handlingen gør da stille ingenting. AskDialog.svelte (sat ind én gang i App) viser køens første.
import { writable } from 'svelte/store';

export interface AskOptions {
  ok?: string;         // tekst på OK-knappen (standard "OK")
  cancel?: string;     // tekst på annullér-knappen (standard "Annullér")
  danger?: boolean;    // OK-knappen vises som en farlig handling (slet, overskriv)
}
export interface AskRequest extends Required<Omit<AskOptions, 'danger'>> {
  text: string;
  danger: boolean;
  input: null | { value: string; placeholder: string };   // null = ja/nej-spørgsmål
  resolve: (answer: string | null) => void;                // null = annulleret
}

/** Spørgsmål der venter på svar; dialogen viser det første. */
export const askQueue = writable<AskRequest[]>([]);

function enqueue(text: string, opts: AskOptions, input: AskRequest['input']): Promise<string | null> {
  return new Promise((resolve) => {
    const req: AskRequest = {
      text, input, ok: opts.ok ?? 'OK', cancel: opts.cancel ?? 'Annullér', danger: !!opts.danger,
      resolve: (answer) => {
        askQueue.update((q) => q.filter((r) => r !== req));
        resolve(answer);
      },
    };
    askQueue.update((q) => [...q, req]);
  });
}

/** Ja/nej-spørgsmål. → true ved OK. */
export async function ask(text: string, opts: AskOptions = {}): Promise<boolean> {
  return (await enqueue(text, opts, null)) !== null;
}

/**
 * Spørg efter en tekst. → teksten (trimmet), eller null ved Annullér eller tom tekst.
 * `allowEmpty`: tom tekst er et gyldigt svar ('') — kun Annullér giver null (fx "tomt navn = intet navn").
 */
export async function askText(text: string, opts: AskOptions & { value?: string; placeholder?: string; allowEmpty?: boolean } = {}): Promise<string | null> {
  const answer = await enqueue(text, opts, { value: opts.value ?? '', placeholder: opts.placeholder ?? '' });
  const t = answer?.trim() ?? '';
  if (opts.allowEmpty) return answer === null ? null : t;
  return t ? t : null;
}
