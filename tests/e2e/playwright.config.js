// @ts-check
const { defineConfig, devices } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SITE_URL = process.env.SITE_URL || 'http://localhost:5173';

module.exports = defineConfig({
  testDir: '.',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: [
    ['html'],
    ['junit', { outputFile: 'results.xml' }],
    process.env.CI ? ['github'] : ['list'],
  ],
  use: {
    baseURL: SITE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    extraHTTPHeaders: {
      'X-Forwarded-Proto': 'https',
    },
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    // Only run Firefox + mobile on full suite (not smoke)
    ...(process.env.FULL_SUITE ? [
      { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
      { name: 'mobile-chrome', use: { ...devices['Pixel 5'] } },
    ] : []),
  ],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  globalSetup: './fixtures/global-setup.js',
  globalTeardown: './fixtures/global-teardown.js',
  outputDir: 'playwright-results',
});
