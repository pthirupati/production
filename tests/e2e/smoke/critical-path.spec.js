// smoke/critical-path.spec.js
// Critical path smoke tests: health, public API, login, lab start, scenario completion
const { test, expect } = require('@playwright/test');
const { AuthPage } = require('../pages/AuthPage');
const { LabPage } = require('../pages/LabPage');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SITE_URL = process.env.SITE_URL || 'http://localhost:5173';

test.describe('Critical path smoke', () => {
  // ── Public endpoints ────────────────────────────────────────────────────
  test('GET /health returns 200', async ({ page }) => {
    // Public gateway exposes /health; /api/health/ is blocked from external IPs.
    const resp = await page.request.get(`${BASE_URL}/health`, {
      headers: { 'X-Forwarded-Proto': 'https' },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('status');
  });

  test('Public API endpoints return 200', async ({ page }) => {
    const endpoints = [
      '/api/stats/',
      '/api/technologies/',
      '/api/scenarios/',
      '/api/config/',
      '/api/leaderboard/',
      '/api/interviews/plans/',
    ];
    for (const path of endpoints) {
      const resp = await page.request.get(`${BASE_URL}${path}`, {
        headers: { 'X-Forwarded-Proto': 'https' },
      });
      expect(resp.status(), `${path} should be 200`).toBe(200);
    }
  });

  // ── SPA loads ──────────────────────────────────────────────────────────
  test('Homepage loads without JS error', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.goto(SITE_URL);
    await page.waitForLoadState('networkidle');
    expect(errors).toHaveLength(0);
  });

  test('Scenarios page loads', async ({ page }) => {
    await page.goto(`${SITE_URL}/scenarios`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toHaveText('500');
  });

  // ── Authentication flow ────────────────────────────────────────────────
  test('Admin login returns JWT', async ({ page }) => {
    const auth = new AuthPage(page);
    const { resp, access } = await auth.login({
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    });
    expect(resp.status()).toBe(200);
    expect(access).toBeTruthy();
    expect(access.split('.')).toHaveLength(3); // JWT format
  });

  // ── Scenario + lab flow ───────────────────────────────────────────────
  test('Can list technologies and scenarios', async ({ page }) => {
    const auth = new AuthPage(page);
    const { access } = await auth.login({
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    });

    const techResp = await auth.api('GET', '/api/technologies/', { token: access });
    expect(techResp.status()).toBe(200);
    const techs = await techResp.json();
    expect(Array.isArray(techs) || techs.results).toBeTruthy();

    const scenResp = await auth.api('GET', '/api/scenarios/', { token: access });
    expect(scenResp.status()).toBe(200);
  });

  test('Lab start returns session_id', async ({ page }) => {
    test.skip(process.env.E2E_SKIP_LAB === '1', 'Lab provisioning skipped');

    const auth = new AuthPage(page);
    const lab = new LabPage(page);

    const { access } = await auth.login({
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    });

    // Get first simulation scenario slug
    const scenResp = await auth.api('GET', '/api/scenarios/?type=simulation', { token: access });
    const scenBody = await scenResp.json();
    const scenarios = scenBody.results || scenBody;
    test.skip(!scenarios.length, 'No simulation scenarios available');

    const slug = scenarios[0].slug;
    const startResp = await lab.startLab(slug, access);
    expect([200, 201]).toContain(startResp.status());

    const startBody = await startResp.json();
    expect(startBody).toHaveProperty('session_id');
    expect(startBody.session_id).toBeTruthy();

    // Cleanup
    await lab.stopLab(startBody.session_id, access);
  });

  // ── Dashboard renders for authenticated user ───────────────────────────
  test('Dashboard page loads when authenticated', async ({ page }) => {
    const auth = new AuthPage(page);
    const { access } = await auth.login({
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    });

    // Set token in localStorage then navigate
    await page.goto(SITE_URL);
    await page.evaluate((token) => {
      localStorage.setItem('access_token', token);
    }, access);

    await page.goto(`${SITE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toHaveText('Error');
  });
});
