import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // The cross-stack suite needs a running backend and its own command
    // (`npm run test:live`), which is what CI's smoke job provides. Leaving it here
    // would either fail every offline run or turn into a skip nobody reads, and a
    // skipped test reports success without evidence.
    exclude: ['**/node_modules/**', 'src/lib/__tests__/liveApi.test.ts'],
  },
});
