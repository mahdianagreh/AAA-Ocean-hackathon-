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
  },

  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
