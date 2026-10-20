import { readFileSync } from 'node:fs';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vitest/config';

// Versionen bygges ind i siden, så en åben fane kan opdage, at serveren er opdateret (BUGS.md v0.63.0)
const VERSION = JSON.parse(readFileSync(new URL('../version.json', import.meta.url), 'utf-8')) as { version: string; build: string };

// Udvikling: Vite på :5173 videresender API og WebSocket til SCADA-serveren på :8000.
export default defineConfig({
  plugins: [svelte()],
  define: { __APP_VERSION__: JSON.stringify(VERSION.version), __APP_BUILD__: JSON.stringify(VERSION.build) },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
  // Komponenttests (jsdom) skal bruge Svelte-browserudgaven, ikke serverudgaven
  resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
  test: { environment: 'jsdom' },
});
