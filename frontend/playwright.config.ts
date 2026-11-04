import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

function resolvePython(): string {
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN;
  const candidates = [
    path.resolve(__dirname, '../.venv/Scripts/python.exe'),
    path.resolve(__dirname, '../.venv/bin/python'),
    path.resolve(__dirname, '../backend/.venv/Scripts/python.exe'),
    path.resolve(__dirname, '../backend/.venv/bin/python'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return 'python';
}

const BACKEND_PORT = process.env.BACKEND_PORT || '8010';
const FRONTEND_PORT = process.env.FRONTEND_PORT || '3010';
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  expect: {
    timeout: 7000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: FRONTEND_URL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: `"${resolvePython()}" -m uvicorn railconfirm.api.app:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      url: `${BACKEND_URL}/v1/health`,
      cwd: path.resolve(__dirname, '../backend'),
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
      env: {
        RAILCONFIRM_HISTORY_ENABLED: 'true',
        RAILCONFIRM_PERSIST_PREDICTIONS: 'true',
        RAILCONFIRM_CORS_ALLOWED_ORIGINS: JSON.stringify([
          'http://localhost:3000',
          'http://127.0.0.1:3000',
          'http://localhost:3010',
          'http://127.0.0.1:3010',
        ]),
      },
    },
    {
      command: `npx next dev -p ${FRONTEND_PORT}`,
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 45000,
      env: {
        NEXT_PUBLIC_API_URL: BACKEND_URL,
      },
    },
  ],
});

