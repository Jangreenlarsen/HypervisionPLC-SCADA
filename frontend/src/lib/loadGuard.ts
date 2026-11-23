// Kapløb ved hurtige tegningsskift (brødkrumme, undertegninger, tilbage-knap): kun den NYESTE indlæsning må sætte visning,
// valgt tegning og adresse. Ren logik uden DOM/netværk, så reglen kan testes.

export interface LoadGuard {
  /** Start en indlæsning af `id`; returnerer dens løbenummer. Alle tidligere indlæsninger er hermed forældede. */
  begin(id: string): number;
  /** Er denne indlæsning stadig den nyeste? (tjekkes efter hver `await`) */
  isLatest(token: number): boolean;
  /** Indlæsningen er færdig (også ved fejl) — er den stadig den nyeste, er intet længere i gang. */
  finish(token: number): void;
  /** Tegningen den nyeste, endnu uafsluttede indlæsning henter — ellers null. */
  readonly inFlight: string | null;
}

export function createLoadGuard(): LoadGuard {
  let seq = 0;
  let pending: string | null = null;
  return {
    begin(id) {
      seq += 1;
      pending = id;
      return seq;
    },
    isLatest: (token) => token === seq,
    finish(token) {
      if (token === seq) pending = null;
    },
    get inFlight() {
      return pending;
    },
  };
}

/** Skal en adresseændring til `id` udløse en indlæsning? Er en indlæsning i gang, afgør den (samme id = dobbelt indlæsning,
 *  andet id = nyt skifte); ellers kun hvis `id` ikke allerede vises. */
export function shouldLoadFromHash(id: string, selected: string, inFlight: string | null): boolean {
  return inFlight !== null ? id !== inFlight : id !== selected;
}
