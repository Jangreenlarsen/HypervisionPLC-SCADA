import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, errorText } from './api';

describe('errorText', () => {
  it('bruger serverens error-felt', () =>
    expect(errorText(400, { error: 'Adgangskoden må ikke være tom' }, 'Bad')).toBe('Adgangskoden må ikke være tom'));
  it('flader FastAPI-liste ud', () => expect(errorText(422, { detail: [{ msg: 'a' }, { msg: 'b' }] }, '')).toBe('a; b'));
  it('blank error falder igennem til fallback', () => expect(errorText(500, { error: '  ' }, 'Server Error')).toBe('Server Error'));
  it('ikke-JSON tekst', () => expect(errorText(502, '<h1>Bad gateway</h1>', '')).toBe('<h1>Bad gateway</h1>'));
  it('intet giver HTTP-status', () => expect(errorText(503, null, '')).toBe('HTTP 503'));
});

describe('api()', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('kaster ApiError med serverens tekst', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'Tag findes allerede' }), { status: 409 })));
    await expect(api('POST', '/api/tags', {})).rejects.toMatchObject({ status: 409, message: 'Tag findes allerede' });
  });

  it('netværksfejl giver forståelig besked', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    }));
    await expect(api('GET', '/api/tags')).rejects.toThrow('Ingen forbindelse til SCADA-serveren');
  });

  it('204 giver undefined', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })));
    await expect(api('DELETE', '/api/tags/x')).resolves.toBeUndefined();
  });
});
