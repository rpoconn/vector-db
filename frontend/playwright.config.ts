import { defineConfig, devices } from '@playwright/test'

/**
 * The e2e run starts its own backend (`backend/scripts/serve_e2e.py`: a synthetic catalog,
 * model-free search and an in-memory mailbox) and its own Vite server on separate ports,
 * so it never touches a dev server or the real catalog.
 */
const FRONTEND_PORT = process.env.E2E_FRONTEND_PORT ?? '5174'
const BACKEND_PORT = process.env.E2E_BACKEND_PORT ?? '8001'
const BASE_URL = `http://localhost:${FRONTEND_PORT}`
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `uv run --project ../backend python ../backend/scripts/serve_e2e.py --port ${BACKEND_PORT} --frontend-url ${BASE_URL}`,
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'bun run dev',
      url: BASE_URL,
      env: { PORT: FRONTEND_PORT, BACKEND_URL },
      reuseExistingServer: !process.env.CI,
    },
  ],
})
