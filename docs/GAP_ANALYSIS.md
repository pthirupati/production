# FixitLab Gap Analysis

Last updated: June 2026 (post OAuth, email prefs, org UI, simulation Jira)

## Recently implemented

- OAuth login-only: GitHub/Google login existing accounts; new users must register via OTP first
- Simulation-only Jira in production (`JIRA_SIMULATION_MODE=True`)
- Notification email preferences wired for subscription, lab completed/expired, achievements
- Lab completed/expired email templates connected
- Team self-service: `/team` page + `/api/org/` for members and owner/admin invites
- `/support` redirects to `/contact`
- Home page uses DB `coming_soon` flag for technologies
- Payment error email links fixed

---

## Critical (production blockers)

| Item | Status | Notes |
|------|--------|-------|
| Email delivery in production | **Open** | EmailLog showed 0 sent / 3700+ failed. Fix Gmail OAuth on `celery_worker`, verify `GMAIL_OAUTH_*` in `.env.production` |
| Full E2E on every deploy | **Partial** | OTP/concurrent pass; scenario E2E still gates deploy. Run with `RUN_FULL_E2E=1` |
| Celery `notifications` queue health | **Open** | Monitor worker logs; add alert when EmailLog failure rate > 0 |

---

## High priority

| Item | Status | Action |
|------|--------|--------|
| Unified billing UX | **Open** | Profile still shows legacy Plan + tech subscriptions. Consolidate to technology subscriptions only |
| Org billing / invoices for teams | **Open** | Org model exists; no org-level checkout or billing portal |
| Stripe pro/enterprise UI | **Open** | Backend supports Stripe; no frontend checkout |
| Frontend automated tests | **Open** | No Playwright in CI; add smoke tests for login, register OTP, lab start |
| Coupon test coverage | **Open** | Validate + redeem flows need dedicated tests |
| Community API tests | **Open** | Threads/replies untested in CI |
| Certificate email template | **Open** | Reuses subscription template; needs dedicated design |

---

## Medium priority

| Item | Status | Action |
|------|--------|--------|
| `ScenarioVersion` model | **Orphan** | Integrate versioning in admin + lab routing, or remove app |
| `email_marketing` preference | **Unused** | No sender uses it; wire or remove toggle |
| Blog CMS | **Static** | Hardcoded posts in `Blog.jsx`; admin-managed content |
| API documentation | **Missing** | OpenAPI/Swagger for integrators |
| Dev/prod RabbitMQ parity | **Open** | Dev compose lacks RabbitMQ auth defaults |
| Documentation index drift | **Open** | `DOCUMENTATION_INDEX.txt` references missing Jira docs |
| Admin payment transaction UI | **Partial** | Security metrics only; no failed payment dashboard |
| Register → link OAuth after signup | **Nice** | After OTP register, offer "Link GitHub/Google" on profile |

---

## Nice-to-have

- OAuth on register page (currently login-only by design)
- Mobile-optimized lab terminal
- Technology-level ratings moderation in admin
- Session replay polish and sharing
- Real AWS/K8s lab scenarios in production (provisioners exist; env optional)
- Marketing stats on Home/Register (hardcoded numbers)
- Remove duplicate `question_bank` admin API vs `/api/admin/*`
- Frontend i18n / multi-language

---

## Feature inventory (what exists today)

**Auth:** OTP register (2 min), login, forgot/reset password, GitHub/Google login (existing accounts only), profile

**Labs:** Docker, simulation (unified engine), AWS/DO provisioners, WebSocket terminal, hints, validation, replay, dual terminal

**Billing:** Razorpay per-technology, coupons, invoices, certificates, demo mode (dev only)

**Admin:** 16 pages including scenarios, users, labs, monitoring, coupons, analytics, teams, security

**Jira:** Simulation-only (`KAN-*` tickets), ticket UI, auto ticket on lab start

**Community:** Threads, replies, votes, attachments

**Engagement:** Achievements, leaderboard, bookmarks, ratings, notifications (in-app + email)

**Enterprise:** Org models, admin team management, member `/team` portal, technology grants

---

## Recommended next PRs (ordered)

1. Fix production Gmail OAuth + EmailLog monitoring
2. Unify Profile/Pricing billing UX (deprecate legacy Plan display)
3. Playwright smoke tests in CI
4. Org-level billing and invite-by-email before registration (optional pre-register invite queue)
5. Certificate + marketing email templates
6. Full scenario E2E stabilization
