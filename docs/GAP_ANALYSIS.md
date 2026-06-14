# FixitLab Gap Analysis

Last updated: June 2026 (Phase 2+ completion)

## Recently implemented (Phase 2+)

- **Unified billing:** `GET /api/billing/unified/` — plan, tech subs, orgs, gateway status for Profile/Pricing
- **Stripe tech checkout:** `POST /api/billing/stripe/tech-checkout/` + webhook fulfillment for international USD/INR
- **Org seat billing:** `POST /api/billing/org/<slug>/checkout/` + `POST /api/org/<slug>/verify-payment/`
- **Org analytics:** `GET /api/org/<slug>/analytics/` + Team page dashboard
- **Invite-before-register:** `PendingOrgInvite` model; auto-accept on `RegisterView`
- **Blog CMS:** `BlogPost` model, admin CRUD, public `/api/blog/`, frontend fetch with static fallback
- **Learning path progress:** `LearningPathProgress` model + progress on Technologies page
- **Interview mode:** Standard hints blocked; AI coaching hints at `/api/labs/<id>/ai-hint/`
- **OpenAPI:** Swagger UI at `/api/docs/`, schema at `/api/schema/` (drf-spectacular)
- **Changelog modal:** In-app modal from PlatformSettings changelog JSON

## Previously shipped (Phase 1)

- Email dispatch thread, OAuth register/link, simulation validation, certificate email, community reports, platform stats, sync_scenarios, admin teams/security

---

## Critical (production blockers)

| Item | Status | Notes |
|------|--------|-------|
| Email delivery in production | **Verify** | Run admin test email in prod |
| Full E2E on every deploy | **Partial** | `RUN_FULL_E2E=1` optional |
| Celery `notifications` queue health | **Monitor** | Critical mail bypasses queue |

---

## High priority (remaining)

| Item | Status | Action |
|------|--------|--------|
| Frontend Playwright CI | **Open** | Smoke tests for login, register OTP, lab start |
| Stripe org checkout (USD) | **Open** | Razorpay org seats done; Stripe for orgs optional |
| Admin blog editor UI | **Partial** | API CRUD exists; dedicated admin React page optional |

---

## Medium priority

| Item | Status | Action |
|------|--------|--------|
| `ScenarioVersion` model | **Orphan** | Integrate or remove |
| Admin payment failure dashboard | **Partial** | Security metrics exist |
| SSO / SAML / OIDC | **Open** | Enterprise SAML — contact sales workflow |
| 2FA (TOTP) | **Open** | Optional enterprise add-on |

---

## Nice-to-have

- Mobile-optimized lab terminal
- Technology ratings moderation in admin
- Real AWS/K8s production scenarios (provisioners exist)
- Frontend i18n

---

## Feature inventory

**Auth:** OTP register, OAuth login/register/link, pending org invites on signup

**Labs:** Docker, simulation, AWS/DO, interview mode + AI hints, WebSocket terminal

**Billing:** Razorpay + Stripe per-technology, unified billing API, org seat checkout, coupons, invoices, certificates

**Admin:** Overview, scenarios, users, labs, blog CMS API, teams, security, changelog, test email

**Community:** Threads, replies, votes, attachments, reports

platform-start.sh runs `seed_scenarios` on deploy. Resync: Admin → Scenarios → **Sync from repo** or `python manage.py sync_scenarios`.
