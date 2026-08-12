/**
 * Anonymous read-only API load profile for `.github/workflows/performance.yml`.
 *
 * Audit Z5-20: this deliberately does NOT start labs, open WebSockets, or exercise
 * UnifiedSimulationEngine. It cannot detect Z5-1…Z5-7 (sim registry leak, snapshot
 * write amplification, capacity races). Those need an authenticated lab/WS profile
 * with staging credentials — track separately.
 *
 * What it *does* catch: anonymous catalog/health regressions under ~20 VUs, and
 * whether `/api/health/ready/` stays up (includes sim_sessions / lab_capacity gauges).
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

const ENDPOINTS = [
  '/api/health/',
  '/api/health/ready/',
  '/api/stats/',
  '/api/technologies/',
  '/api/scenarios/',
  '/api/leaderboard/',
  '/api/config/',
];

export default function () {
  for (const path of ENDPOINTS) {
    const res = http.get(`${BASE}${path}`);
    check(res, {
      [`${path} status 200`]: (r) => r.status === 200,
    });
  }
  sleep(1);
}
