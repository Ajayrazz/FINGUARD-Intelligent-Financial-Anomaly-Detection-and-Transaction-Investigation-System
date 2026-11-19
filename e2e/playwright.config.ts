import { readFileSync } from 'node:fs'
import { defineConfig, devices } from '@playwright/test'

// The password for the seeded role users lives in e2e/.env.local (git-ignored); see README.md
try {
  for (const line of readFileSync(new URL('./.env.local', import.meta.url), 'utf8').split('\n')) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/)
    if (m && !(m[1]! in process.env)) process.env[m[1]!] = m[2]!
  }
} catch {
  /* run with E2E_PASSWORD in the environment instead */
}

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1, // one browser at a time: the stack is small and tests share seeded data
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
