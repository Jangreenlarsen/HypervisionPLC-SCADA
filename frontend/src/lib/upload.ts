// Upload af store filer med fremdrift (fetch kan ikke vise upload-fremdrift) — fx LLM-pakken på flere GB (v3.37.0).
import { notifyUnauthorized } from './api';

export interface UploadResult { ok: boolean; status: number; body: unknown }

/** Send `file` uændret (application/octet-stream). `onProgress` får 0–1. Afvises aldrig — se `ok`/`status`. */
export function uploadWithProgress(url: string, file: Blob, onProgress: (p: number) => void): Promise<UploadResult> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.upload.onprogress = (e) => { if (e.lengthComputable && e.total) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      let body: unknown = xhr.responseText;
      try { body = xhr.responseText ? JSON.parse(xhr.responseText) : null; } catch { /* ikke-JSON (fx en proxy-fejlside) vises som tekst */ }
      if (xhr.status === 401) notifyUnauthorized();
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, body });
    };
    xhr.onerror = () => resolve({ ok: false, status: 0, body: 'Ingen forbindelse til SCADA-serveren under upload' });
    xhr.send(file);
  });
}

/** 2740937888 → "2,7 GB" */
export function formatBytes(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1).replace('.', ',')} GB`;
  if (n >= 1e6) return `${Math.round(n / 1e6)} MB`;
  if (n >= 1e3) return `${Math.round(n / 1e3)} kB`;
  return `${n} B`;
}
