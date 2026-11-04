// System › Integrationer (v3.21.0): API-nøgler til Node-RED, Home Assistant og andre systemer. Nøglen genereres her i browseren og sendes
// til serveren, som kun gemmer en kontrolsum — værdien kan aldrig hentes igen og vises kun lige efter, den er oprettet.
import { generateToken } from './metricsToken';

export interface Scope { all: boolean; tags: string[]; prefixes: string[] }
export interface ApiKey {
  id: string; name: string; prefix: string; scope: Scope; ip_allow: string[]; expires_at: number | null; disabled: boolean;
  created_at: number; created_by: string; last_used_at: number | null; last_ip: string; expired: boolean;
  stats: { requests: number; errors: number; rate_limited: number };
}
export interface KeyForm {
  name: string; scopeMode: 'all' | 'selected'; tags: string; prefixes: string; ips: string; expires: string;   // expires: YYYY-MM-DD eller tom
}

/** `hv_` + 43 tilfældige URL-sikre tegn (256 bit). `rng` kan udskiftes i test. */
export function generateKey(rng?: (a: Uint8Array) => Uint8Array): string {
  return 'hv_' + generateToken(rng);
}

/** "a, b;c\nd" → liste uden tomme (komma, semikolon, mellemrum og linjeskift). */
export function parseList(text: string): string[] {
  return text.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean);
}

/** Slutningen af den valgte dag (lokal tid) som Unix-sekunder; tom tekst → null (udløber aldrig). */
export function expiryFromDate(date: string): number | null {
  if (!date.trim()) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date.trim());
  if (!m) throw new Error('Udløbsdatoen skal være på formen ÅÅÅÅ-MM-DD');
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 23, 59, 59).getTime() / 1000;
}

export function dateFromExpiry(ts: number | null): string {
  if (ts === null) return '';
  const d = new Date(ts * 1000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function scopeBody(f: KeyForm): Scope {
  return f.scopeMode === 'all' ? { all: true, tags: [], prefixes: [] } : { all: false, tags: parseList(f.tags), prefixes: parseList(f.prefixes) };
}

export function createBody(f: KeyForm, key: string): Record<string, unknown> {
  return { name: f.name.trim(), key, scope: scopeBody(f), ip_allow: parseList(f.ips), expires_at: expiryFromDate(f.expires) };
}

/** Kun de felter, der er ændret (ellers kan man ikke omdøbe en udløbet nøgle, og et slettet tag i afgrænsningen blokerer alt). */
export function patchBody(f: KeyForm, original: ApiKey): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (f.name.trim() !== original.name) body.name = f.name.trim();
  const scope = scopeBody(f);
  if (JSON.stringify(scope) !== JSON.stringify({ all: original.scope.all, tags: original.scope.tags, prefixes: original.scope.prefixes })) body.scope = scope;
  const ips = parseList(f.ips);
  if (JSON.stringify(ips) !== JSON.stringify(original.ip_allow)) body.ip_allow = ips;
  if (f.expires.trim() !== dateFromExpiry(original.expires_at)) body.expires_at = expiryFromDate(f.expires);
  return body;
}

export function formFrom(k: ApiKey): KeyForm {
  return { name: k.name, scopeMode: k.scope.all ? 'all' : 'selected', tags: k.scope.tags.join('\n'), prefixes: k.scope.prefixes.join('\n'),
           ips: k.ip_allow.join('\n'), expires: dateFromExpiry(k.expires_at) };
}

export const emptyForm = (): KeyForm => ({ name: '', scopeMode: 'selected', tags: '', prefixes: '', ips: '', expires: '' });

export function scopeText(s: Scope): string {
  if (s.all) return 'alle tags';
  const parts = [];
  if (s.tags.length) parts.push(`${s.tags.length} tag${s.tags.length === 1 ? '' : 's'}`);
  if (s.prefixes.length) parts.push(`præfiks ${s.prefixes.join(', ')}`);
  return parts.join(' + ') || 'ingen';
}

export type KeyStatus = 'aktiv' | 'deaktiveret' | 'udløbet';
export const keyStatus = (k: ApiKey): KeyStatus => (k.disabled ? 'deaktiveret' : k.expired ? 'udløbet' : 'aktiv');

/** Færdige eksempler med den netop oprettede nøgle (vises én gang). `base` = fx https://scada.laces.dk. */
export function examples(base: string, key: string): { curl: string; nodered: string; homeassistant: string } {
  return {
    curl: `curl -k -H "Authorization: Bearer ${key}" ${base}/api/v1/integration/values`,
    nodered:
      `Node-RED: node "http request"\n` +
      `  Metode: GET   URL: ${base}/api/v1/integration/values\n` +
      `  Returner: et parset JSON-objekt\n` +
      `  Headers: Authorization = Bearer ${key}\n` +
      `  (selvsigneret certifikat: slå "Verify server certificate" fra i TLS-opsætningen)`,
    homeassistant:
      `# configuration.yaml\n` +
      `sensor:\n` +
      `  - platform: rest\n` +
      `    name: Kedeltemperatur\n` +
      `    resource: ${base}/api/v1/integration/values?tags=kedel_temp\n` +
      `    headers:\n` +
      `      Authorization: Bearer ${key}\n` +
      `    verify_ssl: false\n` +
      `    value_template: "{{ value_json.values.kedel_temp.v }}"\n` +
      `    unit_of_measurement: "°C"\n` +
      `    scan_interval: 30`,
  };
}
