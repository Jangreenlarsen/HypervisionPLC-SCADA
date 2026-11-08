// Hjælper-panelets fælles tilstand: om hjælperen findes, om panelet er åbent, og en ventende anmodning fra en side
// (fx knappen *Forklar* ved en alarm). Panelet (AssistPanel.svelte) stiller selve spørgsmålene.
import { get } from './api';

export interface AssistRequest { question: string; label: string; alarm?: string; tags?: string[]; summary?: boolean }

export const assist = $state<{ available: boolean; canAsk: boolean; open: boolean; request: AssistRequest | null }>({
  available: false, canAsk: false, open: false, request: null,
});

/** Tjek om hjælperen er slået til (kaldes efter login og jævnligt). Fejl = ingen hjælper (resten af SCADA'en virker). */
export async function refreshAssist(): Promise<void> {
  try {
    const r = await get<{ available: boolean; can_ask: boolean }>('/api/assist/available');
    assist.available = r.available;
    assist.canAsk = r.can_ask;
  } catch {
    assist.available = false;
    assist.canAsk = false;
  }
}

export function resetAssist(): void {
  assist.available = false;
  assist.canAsk = false;
  assist.open = false;
  assist.request = null;
}

/** Åbn panelet og stil et spørgsmål med ekstra kontekst (fx en alarm). */
export function askAssist(req: AssistRequest): void {
  assist.open = true;
  assist.request = req;
}
