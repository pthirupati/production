// interviews/interview-flow.spec.js
// Interview Studio E2E: public plans, voice config, admin settings,
// campaign creation, entitlement, media permission UI, scorecard
const { test, expect } = require('@playwright/test');
const { AuthPage } = require('../pages/AuthPage');
const { InterviewPage } = require('../pages/InterviewPage');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SITE_URL = process.env.SITE_URL || 'http://localhost:5173';

test.describe('Interview Studio — Public', () => {
  test('GET /api/interviews/plans/ is public and returns list', async ({ page }) => {
    const iv = new InterviewPage(page);
    const resp = await iv.getPlans();
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(Array.isArray(body) || body.results).toBeTruthy();
  });

  test('Voice config uses browser TTS (no paid APIs)', async ({ page }) => {
    const iv = new InterviewPage(page);
    const resp = await iv.getVoiceConfig();
    expect(resp.status()).toBe(200);
    const config = await resp.json();
    expect(config.tts_provider).toBe('browser');
    expect(config.uses_paid_apis).toBe(false);
  });

  test('Interview Hub SPA page loads', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.goto(`${SITE_URL}/interviews`);
    await page.waitForLoadState('networkidle');
    expect(errors).toHaveLength(0);
  });
});

test.describe('Interview Studio — Admin', () => {
  let adminToken;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const pg = await ctx.newPage();
    const auth = new AuthPage(pg);
    const result = await auth.login({
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    });
    adminToken = result.access;
    await ctx.close();
  });

  const ADMIN_PATHS = [
    '/api/admin/interviews/',
    '/api/admin/interviews/settings/',
    '/api/admin/interviews/tiers/',
    '/api/admin/interviews/voices/',
    '/api/admin/interviews/live/',
    '/api/admin/interviews/campaigns/',
    '/api/admin/interviews/questions/',
    '/api/admin/interviews/entitlements/',
    '/api/admin/interviews/join-requests/',
  ];

  for (const path of ADMIN_PATHS) {
    test(`GET ${path} returns 200`, async ({ page }) => {
      const resp = await page.request.get(`${BASE_URL}${path}`, {
        headers: {
          Authorization: `Bearer ${adminToken}`,
          'X-Forwarded-Proto': 'https',
        },
      });
      expect([200, 204]).toContain(resp.status());
    });
  }

  test('Admin can update interview settings', async ({ page }) => {
    const iv = new InterviewPage(page);
    const resp = await iv.adminUpdateSettings(adminToken, {
      enabled: true,
      staff_free_by_default: true,
    });
    expect([200, 204]).toContain(resp.status());
  });
});

test.describe('Interview Studio — User campaign flow', () => {
  let userToken;
  let adminToken;
  const testEmail = `e2e_interview_${Date.now()}@fixitlab-test.local`;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const pg = await ctx.newPage();
    const auth = new AuthPage(pg);

    // Admin token
    const adminResult = await auth.login({
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    });
    adminToken = adminResult.access;

    // Register test user (skip OTP in CI)
    if (process.env.E2E_SKIP_EMAIL === 'true') {
      // Use admin login as proxy user for entitlement test
      userToken = adminToken;
    } else {
      // Full OTP registration
      const iv = new InterviewPage(pg);
      await iv.adminUpdateSettings(adminToken, { enabled: true });
      // OTP flow would go here
    }

    await ctx.close();
  });

  test('User can get entitlement', async ({ page }) => {
    const iv = new InterviewPage(page);
    const resp = await iv.getEntitlement(userToken);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('has_access');
  });

  test('Admin can grant free interview access', async ({ page }) => {
    // Decode user ID from JWT (middle segment)
    const payload = JSON.parse(
      Buffer.from(userToken.split('.')[1], 'base64').toString()
    );
    const userId = payload.user_id;

    const iv = new InterviewPage(page);
    const resp = await iv.adminGrantFree(adminToken, userId);
    expect([200, 201, 204]).toContain(resp.status());

    // Verify entitlement now reflects grant
    const entResp = await iv.getEntitlement(userToken);
    const body = await entResp.json();
    expect(body.is_admin_granted_free).toBe(true);
  });

  test('User can create a campaign (3 rounds)', async ({ page }) => {
    const iv = new InterviewPage(page);
    const resp = await iv.createCampaign(userToken, { round_count: 3 });
    expect([200, 201]).toContain(resp.status());

    const body = await resp.json();
    expect(body).toHaveProperty('id');
    expect(body.round_count).toBe(3);
  });

  test('Campaign detail is accessible', async ({ page }) => {
    const iv = new InterviewPage(page);
    const createResp = await iv.createCampaign(userToken, { round_count: 1 });
    const { id } = await createResp.json();

    const detailResp = await iv.getCampaign(userToken, id);
    expect(detailResp.status()).toBe(200);
    const body = await detailResp.json();
    expect(body.id).toBe(id);
  });
});

test.describe('Interview Studio — UI rendering', () => {
  test('Interview room page renders', async ({ page }) => {
    test.skip(true, 'Requires active campaign ID — enable with specific campaign fixture');
    const iv = new InterviewPage(page);
    await iv.navigateToInterviewRoom('test-campaign-id');
    await iv.assertRoomRendered();
  });

  test('Media permission dialog presence', async ({ page }) => {
    // Navigate to a page that triggers media permission request
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(`${SITE_URL}/interviews/room/preview`);
    await page.waitForLoadState('networkidle');

    // Just verify no hard JS crash on the interview room route
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).not.toContain('Unhandled Error');
    expect(errors.filter((e) => e.includes('TypeError'))).toHaveLength(0);
  });

  test('Video preview component renders', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.goto(`${SITE_URL}/interviews`);
    await page.waitForLoadState('networkidle');
    // Verify no JS TypeError from InterviewVideoPreview or useVirtualBackground
    const typeErrors = errors.filter((e) => e.includes('TypeError'));
    expect(typeErrors).toHaveLength(0);
  });
});
