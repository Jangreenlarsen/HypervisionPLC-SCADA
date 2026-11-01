// Scrape-token til /metrics (v3.16.0). Tokenet genereres her i browseren og sendes til serveren, som kun gemmer en
// kontrolsum — det kan derfor aldrig hentes igen og vises kun lige efter, det er oprettet.

/** 32 tilfældige bytes → URL-sikker tekst (43 tegn). `rng` kan udskiftes i test. */
export function generateToken(rng: (a: Uint8Array) => Uint8Array = (a) => crypto.getRandomValues(a)): string {
  const bytes = rng(new Uint8Array(32));
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Færdig scrape-konfiguration til prometheus.yml. */
export function scrapeConfig(host: string, token: string): string {
  return [
    'scrape_configs:',
    '  - job_name: hypervisionplc-scada',
    '    scheme: https',
    '    tls_config:',
    '      insecure_skip_verify: true   # selvsigneret certifikat — fjern, når der er et rigtigt',
    `    authorization:`,
    `      credentials: ${token}`,
    '    static_configs:',
    `      - targets: ['${host}']`,
  ].join('\n');
}
