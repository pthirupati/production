// global-teardown.js — clean up E2E test data
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

module.exports = async function globalTeardown() {
  if (process.env.E2E_SKIP_CLEANUP === '1') {
    console.log('[global-teardown] Skipping cleanup (E2E_SKIP_CLEANUP=1)');
    return;
  }

  const authFile = path.join(__dirname, '.auth', 'admin-tokens.json');
  if (!fs.existsSync(authFile)) return;

  const { access } = JSON.parse(fs.readFileSync(authFile, 'utf8'));

  await fetch(`${BASE_URL}/api/admin/e2e-cleanup/`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${access}`,
      'Content-Type': 'application/json',
      'X-Forwarded-Proto': 'https',
    },
  }).catch((err) => console.warn('[global-teardown] Cleanup request failed:', err.message));

  console.log('[global-teardown] E2E test data cleanup requested.');
};
