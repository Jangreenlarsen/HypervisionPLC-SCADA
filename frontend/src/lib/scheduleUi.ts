// Ugeprogrammer i brugerfladen: formular ↔ API og visning (rene funktioner — testet i scheduleUi.test.ts).
// Selve beregningen (hvad gælder hvornår) ligger på serveren — forhåndsvisningen spørger den.

export const DAYS = ['Ma', 'Ti', 'On', 'To', 'Fr', 'Lø', 'Sø'];
export const PRESETS: { label: string; days: number[] }[] = [
  { label: 'Hverdage', days: [1, 2, 3, 4, 5] },
  { label: 'Weekend', days: [6, 7] },
  { label: 'Alle', days: [1, 2, 3, 4, 5, 6, 7] },
];

export interface EntryForm { days: number[]; start: string; end: string; value: string }
export interface ExceptionForm { date_from: string; date_to: string; value: string; note: string }
export interface ScheduleForm {
  name: string; tag: string; enabled: boolean; default_value: string;
  entries: EntryForm[]; exceptions: ExceptionForm[];
}

/** '' = ingen værdi (null); til/fra-tags bruger '1'/'0'. Decimalkomma accepteres. */
export function parseValue(text: string): number | null {
  const t = text.trim().replace(',', '.');
  if (t === '') return null;
  const n = Number(t);
  if (!Number.isFinite(n)) throw new Error(`"${text}" er ikke et tal`);
  return n;
}

export function toPayload(f: ScheduleForm, isBool: boolean): Record<string, unknown> {
  const val = (v: string, where: string) => {
    try {
      const n = parseValue(v);
      return isBool && n !== null ? n === 1 : n;
    } catch (e) {
      throw new Error(`${where}: ${(e as Error).message}`);
    }
  };
  return {
    name: f.name.trim(), tag: f.tag, enabled: f.enabled, default_value: val(f.default_value, 'Standardværdi'),
    entries: f.entries.map((e, i) => {
      const v = val(e.value, `Periode ${i + 1}`);
      if (v === null) throw new Error(`Periode ${i + 1}: angiv en værdi`);
      return { days: [...e.days].sort(), start: e.start.trim(), end: e.end.trim(), value: v };
    }),
    exceptions: f.exceptions.map((x, i) => ({
      date_from: x.date_from, date_to: x.date_to || x.date_from, value: val(x.value, `Undtagelse ${i + 1}`), note: x.note.trim(),
    })),
  };
}

const str = (v: number | null | undefined, isBool: boolean) =>
  v === null || v === undefined ? '' : isBool ? (v ? '1' : '0') : String(v).replace('.', ',');

export function toForm(s: {
  name: string; tag: string; enabled: boolean; default_value: number | null;
  entries: { days: number[]; start: string; end: string; value: number }[];
  exceptions: { date_from: string; date_to: string; value: number | null; note?: string }[];
}, isBool: boolean): ScheduleForm {
  return {
    name: s.name, tag: s.tag, enabled: s.enabled, default_value: str(s.default_value, isBool),
    entries: s.entries.map((e) => ({ days: [...e.days], start: e.start, end: e.end, value: str(e.value, isBool) })),
    exceptions: s.exceptions.map((x) => ({ date_from: x.date_from, date_to: x.date_to, value: str(x.value, isBool), note: x.note ?? '' })),
  };
}

export function fmtValue(v: number | null | undefined, isBool: boolean, unit = ''): string {
  if (v === null || v === undefined) return 'ingen';
  if (isBool) return v ? 'Til' : 'Fra';
  return v.toLocaleString('da-DK', { maximumFractionDigits: 2 }) + (unit ? ` ${unit}` : '');
}

/** Farve pr. værdi i ugeoversigten: til/fra grøn/grå; tal fra lys til mørk blå efter størrelse. */
export function valueColor(v: number | null, isBool: boolean, all: (number | null)[]): string {
  if (v === null || v === undefined) return 'transparent';
  if (isBool) return v ? '#7cc47f' : '#d6d6d6';
  const vals = [...new Set(all.filter((x): x is number => x !== null && x !== undefined))].sort((a, b) => a - b);
  const ramp = ['#cfe1f5', '#a6c8eb', '#7aaede', '#4f90cc', '#2f72b4', '#1f5f99'];
  if (vals.length <= 1) return ramp[3];
  const i = vals.indexOf(v);
  return ramp[Math.round((i / (vals.length - 1)) * (ramp.length - 1))];
}

/** Tekstfarve oven på en segmentfarve. */
export const textOn = (bg: string) => (['#2f72b4', '#1f5f99', '#4f90cc'].includes(bg) ? '#fff' : '#1f1f1f');
