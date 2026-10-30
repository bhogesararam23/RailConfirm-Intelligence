import { defineConfig } from 'vitest/config';
import { resolve } from 'node:path';

// The live suite talks to a real server over a real socket, so it is kept out of
// `npm test` (which must pass with nothing running) and enabled by one command:
// `npm run test:live`, with RAILCONFIRM_LIVE_API_URL pointing at the backend.
//
// The check below is deliberate. A suite that skips itself when the environment is
// missing is indistinguishable from a suite that passes, and a check nobody notices
// is not a check.
const liveApiUrl = process.env.RAILCONFIRM_LIVE_API_URL;
if (!liveApiUrl) {
  throw new Error(
    'test:live requires RAILCONFIRM_LIVE_API_URL to name a running backend, ' +
      'for example http://127.0.0.1:8010. Use scripts/smoke_full_stack.py to start one.',
  );
}

export default defineConfig({
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  test: {
    // Node, not jsdom, and not because the client needs to be tested "like the
    // server". `src/lib/api.ts` wraps every request in an AbortController so a hung
    // backend cannot leave the form spinning. Under the jsdom environment that
    // controller comes from jsdom's realm while `fetch` is Node's, and Node's fetch
    // rejects a foreign AbortSignal with a TypeError that the client reports — quite
    // correctly from its own point of view — as a network failure. Every call then
    // fails for a reason no browser would produce, and the suite would be measuring
    // the test harness instead of the client. In Node both come from one realm, so
    // the request under test is the one the client really builds.
    environment: 'node',
    globals: true,
    // No jest-dom matchers and no React tree to clean up: this suite drives plain
    // functions over HTTP.
    setupFiles: [],
    include: ['src/lib/__tests__/liveApi.test.ts'],
  },
});
