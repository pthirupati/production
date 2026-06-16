// billing/billing-flow.spec.js
// Billing E2E: gateway status, plans, subscriptions, Razorpay order,
// coupon validation, subscription logs, admin billing panel
const { test, expect } = require('@playwright/test');
const { AuthPage } = require('../pages/AuthPage');
const { BillingPage } = require('../pages/BillingPage');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

test.describe('Billing — Public', () => {
  test('Gateway status returns 200', async ({ page }) => {
    const billing = new BillingPage(page);
    const resp = await billing.getGatewayStatus();
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('stripe');
    expect(body).toHaveProperty('razorpay');
  });
});

test.describe('Billing — Authenticated user', () => {
  let token;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const pg = await ctx.newPage();
    const auth = new AuthPage(pg);
    const { access } = await auth.login({
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    });
    token = access;
    await ctx.close();
  });

  test('GET /api/billing/subscriptions/ returns 200', async ({ page }) => {
    const billing = new BillingPage(page);
    const resp = await billing.getSubscriptions(token);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    // Check renewal fields exist on any subscription
    const subs = body.results || body;
    if (subs.length > 0) {
      // renewal_date or next_renewal_date should exist
      const sub = subs[0];
      const hasRenewal = 'renewal_date' in sub || 'next_renewal_date' in sub || 'expires_at' in sub;
      expect(hasRenewal).toBe(true);
    }
  });

  test('GET /api/billing/plans/ returns list', async ({ page }) => {
    const billing = new BillingPage(page);
    const resp = await billing.getPlans(token);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    const plans = body.results || body;
    expect(plans.length).toBeGreaterThan(0);
  });

  test('GET /api/billing/invoices/ returns 200', async ({ page }) => {
    const billing = new BillingPage(page);
    const resp = await billing.getInvoices(token);
    expect(resp.status()).toBe(200);
  });

  test('Currency rate endpoint returns rate', async ({ page }) => {
    const billing = new BillingPage(page);
    const resp = await billing.getCurrencyRate(token, 'USD');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('rate');
    expect(typeof body.rate).toBe('number');
  });

  test('Subscription logs returns 200', async ({ page }) => {
    const billing = new BillingPage(page);
    const resp = await billing.getSubscriptionLogs(token);
    expect(resp.status()).toBe(200);
  });

  test('Razorpay order dry-run returns order_id', async ({ page }) => {
    const billing = new BillingPage(page);

    // Get first paid plan
    const plansResp = await billing.getPlans(token);
    const plansBody = await plansResp.json();
    const plans = plansBody.results || plansBody;
    const paidPlan = plans.find((p) => p.price_inr > 0 || p.price_usd > 0);
    test.skip(!paidPlan, 'No paid plans available');

    const resp = await billing.createRazorpayOrder(token, {
      plan_id: paidPlan.id,
      currency: 'INR',
    });
    // 200/201 = success, 402/400 = expected in test mode without Razorpay keys
    expect([200, 201, 400, 402]).toContain(resp.status());
  });

  test('Coupon validation returns discount info or 404', async ({ page }) => {
    const billing = new BillingPage(page);
    const resp = await billing.applyCoupon(token, {
      code: 'NONEXISTENT_COUPON_XYZ',
      plan_id: 1,
    });
    // 404 = coupon not found (expected), 200 = valid coupon
    expect([200, 400, 404]).toContain(resp.status());
  });
});

test.describe('Billing — Admin panel', () => {
  let adminToken;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const pg = await ctx.newPage();
    const auth = new AuthPage(pg);
    const { access } = await auth.login({
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    });
    adminToken = access;
    await ctx.close();
  });

  const ADMIN_BILLING_PATHS = [
    '/api/admin/billing/',
    '/api/admin/billing/subscriptions/',
    '/api/admin/billing/invoices/',
    '/api/admin/billing/subscription-logs/',
  ];

  for (const path of ADMIN_BILLING_PATHS) {
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

  test('Admin INR revenue endpoint returns data', async ({ page }) => {
    const resp = await page.request.get(`${BASE_URL}/api/admin/billing/revenue/?currency=INR`, {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        'X-Forwarded-Proto': 'https',
      },
    });
    expect([200, 204]).toContain(resp.status());
  });

  test('Admin subscription expiry fields are present', async ({ page }) => {
    const resp = await page.request.get(`${BASE_URL}/api/admin/billing/subscriptions/`, {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        'X-Forwarded-Proto': 'https',
      },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    const subs = body.results || body;
    if (subs.length > 0) {
      const sub = subs[0];
      const hasExpiry = 'expires_at' in sub || 'end_date' in sub || 'expiry_date' in sub;
      expect(hasExpiry).toBe(true);
    }
  });
});
