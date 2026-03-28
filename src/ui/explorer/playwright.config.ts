import { defineConfig, devices } from '@playwright/test'

/** Dedicated port so e2e does not fight `npm run preview` on 4173; always pairs with `baseURL`. */
const e2ePreviewPort = 5199
const e2eOrigin = `http://127.0.0.1:${e2ePreviewPort}`

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 90_000,
  workers: 1,
  reporter: 'html',
  use: {
    baseURL: e2eOrigin,
    navigationTimeout: 90_000,
    trace: 'on-first-retry',
  },
  webServer: {
    // Preview serves `dist/` only — build first so UI matches source (compare decision panel, etc.).
    command: `npm run build && npx vite preview --host 127.0.0.1 --port ${e2ePreviewPort}`,
    url: `${e2eOrigin}/search`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
