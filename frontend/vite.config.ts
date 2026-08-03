// defineConfig comes from vitest/config, not vite — it is the same function
// widened to accept the `test` block, which vite's own types reject.
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],

  server: {
    // Not optional in the container: Vite binds 127.0.0.1 by default, which is
    // unreachable from the host even with 5173:5173 published in compose.
    host: true,
    port: 5173,
    strictPort: true,
    // macOS bind mounts drop filesystem events, so the container needs polling.
    // Opt in rather than always paying for it — polling costs CPU continuously.
    watch: process.env.VITE_POLL ? { usePolling: true, interval: 300 } : undefined,
  },

  build: {
    // Vite 8 minifies CSS with lightningcss. Keep the target modern or it will
    // downlevel oklch() into an rgb() fallback and ship colours the palette
    // validator never blessed for gamut, contrast or CVD separation. The Phase 0
    // audit greps the built CSS for `oklch(` to prove this held.
    target: 'es2022',
    cssTarget: 'chrome120',

    // MapLibre is ~250 kB gzipped on its own and is non-negotiable — the map is
    // the product. Splitting it into its own chunk does not make the first paint
    // faster (it is needed immediately), but it keeps app-code changes from
    // invalidating it, which matters for the repeat loads a rehearsal does.
    rolldownOptions: {
      output: {
        advancedChunks: {
          groups: [{ name: 'maplibre', test: /node_modules\/maplibre-gl/ }],
        },
      },
    },
    // Raised deliberately: the warning fires on the maplibre chunk, which we have
    // already decided to ship whole. The budget that actually matters is app JS,
    // measured separately in the phase audit.
    chunkSizeWarningLimit: 1200,
  },

  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
