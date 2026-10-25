// Meddelelser på Overview (v1.10.0): fejl, advarsler og beskeder vises i en fast plads i værktøjslinjen (ikke som bannere over tegningen),
// så tegningen aldrig hopper op og ned, når en besked kommer og går. Rene funktioner — vises af MessageSlot.svelte.

export type MsgKind = 'error' | 'warn' | 'ok' | 'info';
export interface Msg {
  id: string;
  kind: MsgKind;
  text: string;
  /** Knap i beskeden, fx Kvittér / OK / vis igen */
  action?: { label: string; run: () => void; title?: string };
  link?: { href: string; label: string };
}

const RANK: Record<MsgKind, number> = { error: 0, warn: 1, ok: 2, info: 3 };

/** Alvorligste først (fejl, advarsel, bekræftelse, info); samme alvor beholder rækkefølgen. */
export const sortMessages = (messages: Msg[]): Msg[] =>
  messages.map((m, i) => ({ m, i })).sort((a, b) => RANK[a.m.kind] - RANK[b.m.kind] || a.i - b.i).map((x) => x.m);

/** Det der vises i den lukkede plads: den alvorligste besked og antallet af de øvrige (null = ingen beskeder). */
export function headline(messages: Msg[]): { first: Msg; more: number } | null {
  const sorted = sortMessages(messages);
  return sorted.length ? { first: sorted[0], more: sorted.length - 1 } : null;
}

/** Kort tekst til den lukkede plads: ét stykke, uden linjeskift. */
export const oneLine = (text: string): string => text.replace(/\s+/g, ' ').trim();
