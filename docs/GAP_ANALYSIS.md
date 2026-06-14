# FixitLab Gap Analysis

Last updated: June 2026 (post gap-closure batch)

## Recently implemented

- **Email delivery:** Critical OTP sends in-process via daemon thread; admin test email endpoint (`POST /api/admin/email/test/`)
- **OAuth:** Register + login flows; **Profile → Link GitHub/Google** for OTP users (`/api/auth/social/link/*`)
- **Simulation validation:** Stub `check.sh` files resolved via slug-aware canonical scripts (nginx, mysql, k8s, docker, gpu, ansible, grub, etc.)
- **Certificate email:** Dedicated `emails/certificate_issued.html` template
- **Community:** Thread report flow (`POST /api/community/threads/{id}/report/`)
- **Platform stats:** Live counts on Home via `/api/stats/` and `/api/config/` `platform_stats`
- **Scenario sync:** `python manage.py sync_scenarios` (wraps `seed_scenarios`)
- **Technologies:** `learning_path` JSON on Technology model; UI on Technologies page
- **Scenarios:** `interview_mode` flag; global success rate on scenario cards
- **Admin:** Changelog JSON on PlatformSettings; promo banner delete; AWS/DO lab modes; expanded Teams/Security

---

## Critical (production blockers)

| Item | Status | Notes |
|------|--------|-------|
| Email delivery in production | **Verify** | Code path improved; confirm Gmail OAuth on workers + run admin test email in prod |
| Full E2E on every deploy | **Partial** | OTP/concurrent pass; scenario E2E gates deploy. `RUN_FULL_E2E=1` optional |
| Celery `notifications` queue health | **Monitor** | Critical mail bypasses queue; bulk mail still uses Celery |

---

## High priority (remaining)

| Item | Status | Action |
|------|--------|--------|
| Org-level Stripe/Razorpay checkout | **Open** | Team billing portal for seat-based orgs |
| Frontend Playwright CI | **Open** | Smoke tests for login, register OTP, lab start |
| Coupon + community API tests | **Open** | Dedicated pytest coverage |
| Blog CMS | **Static** | Posts still in `Blog.jsx`; wire to admin or headless CMS |

---

## Medium priority

| Item | Status | Action |
|------|--------|--------|
| `ScenarioVersion` model | **Orphan** | Integrate or remove |
| OpenAPI/Swagger | **Missing** | Document public API |
| Admin payment failure dashboard | **Partial** | Security metrics exist; dedicated payment retry UI |
| SSO / 2FA for enterprises | **Open** | SAML/OIDC + TOTP |

---

## Nice-to-have

- Mobile-optimized lab terminal
- Technology ratings moderation in admin
- Real AWS/K8s production scenarios (provisioners exist)
- Frontend i18n

---

## Feature inventory (what exists today)

**Auth:** OTP register (2 min), login, forgot/reset password, GitHub/Google login + register + profile link, profile

**Labs:** Docker, simulation (unified engine + real validation), AWS/DO provisioners, WebSocket terminal, hints, validation, replay, dual terminal, 15 min auto-expiry

**Billing:** Razorpay per-technology, coupons, invoices, certificates, demo mode (dev only)

**Admin:** Overview, scenarios, users, labs, monitoring, coupons, analytics, teams, security, test email, changelog

**Community:** Threads, replies, votes, reactions, attachments, reports

platform-start.sh already runs `seed_scenarios` on deploy. Manual resync: Admin → Scenarios → **Sync from repo** or `python manage.py sync_scenarios`.
