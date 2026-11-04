// System › Certifikater (v3.25.0). Private nøgler og adgangskoder sendes kun til serveren — de kommer aldrig tilbage.

export type KeyType = 'ec256' | 'rsa2048' | 'rsa4096';
export interface CertInfo {
  subject: string; cn: string; issuer: string; sans: string[]; not_before: number; not_after: number; fingerprint: string;
  self_signed: boolean; kind: 'selfsigned' | 'letsencrypt' | 'ca'; key: string;
}
export interface PendingCsr { subject: string; sans: string[]; created: number; pem: string }
export interface TlsStatus {
  cert: CertInfo | null; chain: number; has_prev: boolean; has_selfsigned: boolean; pending_csr: PendingCsr | null;
  last: { at: number; source: string; ok: boolean; message: string } | null; warnings?: string[]; message?: string;
}
export interface SubjectForm { cn: string; o: string; ou: string; l: string; st: string; c: string; email: string; sans: string; key_type: KeyType }

export const KEY_TYPES: { id: KeyType; label: string }[] = [
  { id: 'ec256', label: 'EC P-256 (anbefalet)' },
  { id: 'rsa2048', label: 'RSA 2048' },
  { id: 'rsa4096', label: 'RSA 4096' },
];

export const KIND_LABEL: Record<CertInfo['kind'], string> = { selfsigned: 'Selvsigneret', letsencrypt: "Let's Encrypt", ca: 'Udstedt af en CA' };

export const emptySubject = (host: string): SubjectForm => ({ cn: host, o: '', ou: '', l: '', st: '', c: 'DK', email: '', sans: host, key_type: 'ec256' });

/** Navnelisten (komma/linjeskift/mellemrum) → unikke, trimmede navne. */
export function parseSans(text: string): string[] {
  return [...new Set(text.split(/[\s,]+/).map((s) => s.trim().toLowerCase()).filter(Boolean))];
}

/** Kroppen til /selfsigned og /csr. Tomme felter udelades. */
export function subjectBody(f: SubjectForm, extra: Record<string, unknown> = {}): Record<string, unknown> {
  const b: Record<string, unknown> = { cn: f.cn.trim(), sans: parseSans(f.sans), key_type: f.key_type, ...extra };
  for (const k of ['o', 'ou', 'l', 'st', 'c', 'email'] as const) if (f[k].trim()) b[k] = f[k].trim();
  return b;
}

/** Dækker certifikatets navne den adresse, siden åbnes på? (inkl. *.domæne for ét niveau) */
export function hostCovered(host: string, sans: string[]): boolean {
  const h = host.toLowerCase().replace(/^\[|\]$/g, '');
  return sans.some((s) => {
    const n = s.toLowerCase();
    if (n === h) return true;
    if (n.startsWith('*.')) {
      const rest = h.slice(h.indexOf('.') + 1);
      return h.includes('.') && rest === n.slice(2);
    }
    return false;
  });
}

export const daysLeft = (notAfter: number, now = Date.now() / 1000): number => Math.floor((notAfter - now) / 86400);

export const fmtDate = (ts: number): string => new Date(ts * 1000).toLocaleString('da-DK', { dateStyle: 'medium', timeStyle: 'short' });

/** Fil → base64 (til PKCS#12, som er binær). */
export async function fileBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
