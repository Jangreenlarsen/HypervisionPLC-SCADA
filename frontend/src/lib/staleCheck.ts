// Åben fane efter en opdatering (v0.63.1): siden kender sin egen version (bygget ind) og sammenligner med serverens.

export interface AppVersion { version: string; build: string }

/** Den version siden blev bygget som. */
export const BUNDLE: AppVersion = { version: __APP_VERSION__, build: __APP_BUILD__ };

/** Kører siden en anden version end serveren? Ukendt serverversion (fx under genstart) tæller ikke som forældet. */
export function isStale(bundle: AppVersion, server: Partial<AppVersion> | null | undefined): boolean {
  const v = server?.version?.trim(), b = server?.build?.trim();
  if (!v || !b) return false;
  return v !== bundle.version || b !== bundle.build;
}
