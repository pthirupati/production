// global-setup.js — authenticate admin once, save storage state for all tests
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SITE_URL = process.env.SITE_URL || 'http://localhost:5173';

module.exports = async function globalSetup() {
  // Ensure auth state directory exists
  const authDir = path.join(__dirname, '.auth');
  if (!fs.existsSync(authDir)) fs.mkdirSync(authDir, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({ baseURL: SITE_URL });
  const page = await context.newPage();

  // Obtain JWT via API (faster than UI login)
  const resp = await page.request.post(`${BASE_URL}/api/auth/login/`, {
    data: {
      email: process.env.SUPERUSER_EMAIL,
      password: process.env.SUPERUSER_PASSWORD,
    },
  });

  if (!resp.ok()) {
    throw new Error(`Admin login failed: ${resp.status()} ${await resp.text()}`);
  }

  const { access, refresh } = await resp.json();

  // Store tokens for use in tests
  fs.writeFileSync(
    path.join(authDir, 'admin-tokens.json'),
    JSON.stringify({ access, refresh })
  );

  await context.storageState({ path: path.join(authDir, 'admin.json') });
  await browser.close();

  console.log('[global-setup] Admin auth state saved.');
};
