// Handlinger på ét bibliotekssymbol, fælles for Symboler-panelet og "Organisér bibliotek" (v6.11.0).
import { ApiError, post } from './api';

/**
 * Redigér grafikken (v4.7.1): en lille arbejdstegning med symbolet åbnes i Tegn (#draw/<tegning>/sym:<type>). Der rettes
 * grafikken og gemmes med "Gem i biblioteket" — et eget symbol som ny version, et indbygget som en kopi ("… (egen)").
 * Navnet er måske taget: så prøves med et nummer. Kaster ved fejl; går ellers til Tegn.
 */
export async function editGraphic(type: string, label: string): Promise<void> {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300"></svg>';
  let made: { drawing: { id: string } } | null = null;
  for (let n = 1; n <= 20 && !made; n++) {
    try {
      made = await post<{ drawing: { id: string } }>('/api/drawings', { name: `Symbol – ${label}${n > 1 ? ` ${n}` : ''}`, svg });
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 409) throw e;   // navnet er taget: prøv med et nummer
    }
  }
  if (!made) throw new Error('Kunne ikke oprette en arbejdstegning');
  location.hash = `#draw/${encodeURIComponent(made.drawing.id)}/sym:${encodeURIComponent(type)}`;
}

/** Egne symboler (u_…) kan omdøbes og slettes; indbyggede kan kun kopieres (via Redigér grafik). */
export const isOwnSymbol = (id: string): boolean => id.startsWith('u_');
