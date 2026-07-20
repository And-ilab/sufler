import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: '../tests/ui',
  snapshotPathTemplate: '../tests/ui/__snapshots__/{arg}{ext}',
  fullyParallel: false,
  retries: 0,
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'http://127.0.0.1:6006',
    colorScheme: 'light',
    reducedMotion: 'reduce',
    viewport: { width: 900, height: 700 },
  },
  webServer: {
    command: 'npm run storybook -- --ci --no-open',
    url: 'http://127.0.0.1:6006',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
