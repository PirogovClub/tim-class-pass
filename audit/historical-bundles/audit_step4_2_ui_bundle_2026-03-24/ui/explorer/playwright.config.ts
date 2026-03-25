import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 90_000,
  workers: 1,
  reporter: 'html',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    navigationTimeout: 90_000,
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run preview',
    url: 'http://127.0.0.1:4173/search',
    reuseExistingServer: true,
    timeout: 60_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
