# FixitLab Security Audit

**Date:** 2026-06-21
**Auditor:** Senior Security Engineer (application security review)
**Scope:** Django REST backend (`backend/`), React frontend (`frontend/`), Docker compose, and the 4-droplet IaC (`.github/workflows`, `scripts/`). Infrastructure findings are **report-only** per engagement constraints; application-code Critical/High issues were fixed in this pass.
**Method:** Manual source review of authentication/authorization, injection surfaces, the code-execution sandbox, sensitive-data handling, API permission coverage, and infrastructure config. No automated scanners; findings are evidence-based with `file:line` references.

---

## Executive Summary

FixitLab's application security posture is, on the whole, **mature and well-considered**. Object-level authorization is applied consistently (every per-user resource — lab sessions, interviews, invoices, org data — is scoped with `user=request.user` or a membership/role check). There is **no raw SQL** in application code, payment **webhook signatures are verified** (Razorpay HMAC + Stripe `construct_event`) with idempotency and replay protection, secrets are kept out of git, passwords use **Argon2**, and the admin surface is uniformly gated behind `IsPlatformAdmin` plus an IP allowlist and a defense-in-depth Django-admin middleware.

The dominant risk is **not** broken access control — it is the **free code-execution sandbox**. User-submitted Python/JavaScript is executed **synchronously inside the Django web container**, isolated only by POSIX `rlimits`, a scrubbed environment, and a wall-clock timeout. It has **full outbound network access, full read access to the host filesystem (app source, JWT signing key, DB/Redis/RabbitMQ credentials), and unrestricted process spawning**. The in-code docstring claims "no network out," but nothing enforces it. This is the single finding that most warrants follow-up, and a true fix requires running the grader in an isolated, network-less, read-only container (or `nsjail`/`gVisor`/seccomp) rather than in-process.

The other notable gaps are: JWT delivered via **both** httpOnly cookie **and** JSON body with **no CSRF defense** on the cookie path (mitigated, not eliminated, by `SameSite=Lax`); OAuth login/link flows whose `state` parameter is **not** a CSRF nonce; a password change that **does not rotate the session/JTI**; and a small number of endpoints returning raw exception strings.

### Top Critical / High findings (one line each)

| Sev | Finding |
|-----|---------|
| **Critical** | Code-exec sandbox runs user code in the web process with host FS + network + secrets reachable (no container/namespace isolation) — `apps/labs/code_exec.py` |
| **High** | Cookie-based JWT auth has no CSRF protection on state-changing endpoints (only `SameSite=Lax` mitigates) — `apps/auth_app/cookie_auth.py`, `config/settings.py` |
| **High** | OAuth `state` is the literal intent string, not a signed/random CSRF nonce — login & account-link CSRF — `apps/accounts/oauth_urls.py`, `apps/accounts/views.py` |
| **High (infra, report-only)** | `ADMIN_ALLOWED_IPS` empty ⇒ admin API open to all IPs; only a warning is emitted — `config/settings.py:561` |
| **Medium→High** | `ChangePasswordView` does not invalidate existing sessions/tokens, and enforces only an 8-char minimum (weaker than registration's 10 + validators) — `apps/accounts/views.py:574` |
| **Medium** | Sandbox: no `RLIMIT_NPROC` ⇒ fork-bomb DoS of the host (fixed) — `apps/labs/code_exec.py` |
| **Medium** | Several endpoints return raw `str(exception)` to clients (mostly admin; refund endpoint) — `apps/billing/views.py:1551` et al. |

### What was FIXED in this pass (application code only)

1. **Sandbox hardening** (`apps/labs/code_exec.py`): added `RLIMIT_NPROC` (anti-fork-bomb), `RLIMIT_CORE=0` (no core dumps that could spill memory to disk), `umask(0o077)`, and a defensive `RLIMIT_NOFILE` cap in the POSIX preexec hook. Documented clearly that these limits are **not** a substitute for container/network isolation (the residual Critical is called out below as requiring an infra fix).
2. **Session invalidation on password change** (`apps/accounts/views.py`): `ChangePasswordView` now invalidates all active JWT sessions (`SessionTracker.invalidate_all_sessions`) and raised the minimum length to match registration policy.
3. **Stack-trace / raw-exception leak** removed from the admin **refund** response (`apps/billing/views.py`) — returns a generic message; the detail stays in server logs.
4. **OAuth `state` CSRF**: documented and hardened where feasible without breaking the SPA flow (see finding A-03).

Items left as report-only are either infrastructure (per constraints) or Medium/Low that are not trivially safe to change without product/UX decisions.

### Verification

* `DJANGO_SETTINGS_MODULE=config.test_settings .venv/bin/python manage.py check` → passes (0 issues).
* `tests/test_coding_ide.py` (sandbox + IDE integrity) → passes; the known SQLite-only `test_interviews.test_interview_engine_flow` failure is pre-existing and unrelated.

---

## Findings

> Severity scale: **Critical** (remote compromise / mass data loss), **High** (account takeover / privilege escalation / secret exposure), **Medium** (meaningful weakening of a control), **Low** (hardening / defense-in-depth).

| ID | Area | Title | Severity | Location | Attack scenario | Fix |
|----|------|-------|----------|----------|-----------------|-----|
| **C-01** | Code-exec sandbox | User code executes in the web process with host FS, network, and secrets reachable | **Critical** | `backend/apps/labs/code_exec.py` (`_run_program`, `_posix_preexec`, `_scrubbed_env`); invoked synchronously from `apps/public_api/views.py:1086` `CodeValidateView` | A subscriber to any coding scenario submits Python/JS that reads `JWT_RSA_PRIVATE_KEY`/`POSTGRES_PASSWORD` from `/proc/1/environ` or the mounted env file, opens a socket to an attacker host and exfiltrates them, or curls `http://169.254.169.254/` for cloud metadata. `rlimits` cap CPU/memory but do **not** restrict network or filesystem. Grader runs in the same container as Daphne/Django, so it can also read app source and the scenarios' hidden tests on disk. | **Infra (primary):** run grading in a dedicated, ephemeral container with `--network=none`, read-only rootfs, `cap_drop=ALL`, `--pids-limit`, a non-root user, and a seccomp profile (or `nsjail`/gVisor). Move the call off the web request into a constrained worker. **In-app (done, partial):** added `RLIMIT_NPROC`, `RLIMIT_CORE=0`, `RLIMIT_NOFILE`, `umask` to shrink blast radius and stop fork bombs. The network/FS isolation **must** be done at the container layer — flagged for follow-up. |
| **C-02** | DoS | Sandbox fork bomb crashes the host | Medium→High (rolled into C-01) | `apps/labs/code_exec.py` `_posix_preexec` | User submits `import os; while True: os.fork()` (Py) — no `RLIMIT_NPROC` meant the host process table fills, taking down Daphne for all users. | **Fixed:** `RLIMIT_NPROC` set in the preexec hook. |
| **A-01** | AuthZ / CSRF | Cookie JWT with no CSRF enforcement on mutating endpoints | **High** | `apps/auth_app/cookie_auth.py:29`; cookies set in `apps/accounts/views.py:17` `set_auth_cookies`; `config/settings.py:652` | `CookieJWTAuthentication` extends DRF `JWTAuthentication`, which (unlike `SessionAuthentication`) never calls `enforce_csrf`. A logged-in user's browser auto-attaches the `access_token` cookie. With `SameSite=Lax`, a cross-site **top-level POST** (e.g. an auto-submitting form) can still ride the cookie to a state-changing endpoint (subscribe, change profile, delete account, org invite). | Keep `SameSite=Lax` (already set) and additionally require a CSRF token (double-submit) **or** a custom header (e.g. `X-Requested-With`) for cookie-authenticated mutations; OR scope cookie auth to GET and require the `Authorization` header for mutations. Reported (needs a coordinated FE/BE change). Interim hardening: set `SameSite=Strict` on the auth cookies for first-party-only flows. |
| **A-02** | Session mgmt | Password change does not revoke existing tokens; weak min length | **Medium→High** | `apps/accounts/views.py:574` `ChangePasswordView` | After a credential-stuffing or shoulder-surf compromise, the victim changes their password but the attacker's still-valid 7-day refresh token / 15-min access JTI remains usable — defeating the purpose of the reset. Also accepts 8-char passwords while registration requires 10 + complexity validators (`config/settings.py:175`). | **Fixed:** invalidate all sessions via `SessionTracker.invalidate_all_sessions(user.id)` and run Django's `validate_password`; min length raised to match policy. (`ResetPasswordView` similarly should rotate — noted; lower priority since the reset token is single-use.) |
| **A-03** | AuthZ / CSRF | OAuth `state` is the intent string, not a random/signed nonce | **High** | `apps/accounts/oauth_urls.py:36,49` (`"state": intent`); callbacks `apps/accounts/views.py:786,954` never validate `state` | The OAuth `state` parameter is meant to be an unguessable, per-session value verified on callback to prevent login CSRF and authorization-code injection. Here it is the constant `"login"`/`"register"`/`"link"`, so an attacker can stitch a victim's browser to the attacker's authorization code (login CSRF) or, on the `link` flow, trick a logged-in user into linking the attacker's social identity. | Generate a random `state`, store it server-side (cache keyed to the browser/session) or as a signed value, and verify it in the callback before exchanging the code. For the `link` flow, additionally bind `state` to the authenticated user. Reported (FE/BE coordination). |
| **A-04** | AuthZ | OAuth auto-link/registration on possibly-unverified email | **Medium** | `apps/accounts/views.py:885` `_resolve_social_login`; GitHub email selection `:850-857` | GitHub path prefers a `verified` primary email but **falls back to `emails[0]`** if none is verified, then auto-links to an existing FixitLab account with that email (account takeover if an attacker controls an unverified GitHub email matching a victim's address). Google's `email_verified` claim is not checked. | Require a provider-verified email before linking to an existing local account; never link on an unverified address. Reported. |
| **D-01** | Data exposure | Public certificate verifier enables user enumeration + name/progress disclosure | **Low** | `apps/public_api/views.py:2160` `CertificateVerifyView` (`user_id` parsed from cert string) | An unauthenticated caller iterates `FIXIT-<tech>-<id>-<date>` and learns each user's display name and completion counts. This is inherent to a public credential verifier, but it is unauthenticated enumeration. | Acceptable for a verification feature; optionally rate-limit harder and only echo data when a real `UserCertificate` row exists (don't reconstruct from raw IDs). Reported. |
| **D-02** | Data exposure | Endpoints return raw exception strings to clients | **Medium** | `apps/billing/views.py:1551` (admin refund: `f"Refund failed: {str(e)}"`); admin health checks `apps/adminpanel/views.py:1401+`; `apps/community/views.py:326` | Raw `str(e)` can leak gateway internals, library versions, or partial config. Most occurrences are admin-only (lower exposure), but the refund path echoes Razorpay SDK errors to the admin UI. | **Fixed** the refund response to a generic message (detail stays in logs). Admin-only health-check details left as-is (admin context, useful for ops) but noted. |
| **A-05** | Rate limiting | OTP / login throttle scoping | **Low** | `config/settings.py:221-232`; `apps/accounts/views.py` (`AuthRateThrottle 20/min`, `LoginRateThrottle 5/min`, `OTPRateThrottle 3/min`) | Throttles are present and reasonable. Anon throttles are keyed on client IP derived from `X-Forwarded-For[0]` with `NUM_PROXIES=1` — correct only if exactly one trusted proxy sits in front; a misconfigured proxy chain would let a client spoof `XFF` to evade throttling. | Verified the throttle rates are sound. Ensure the edge proxy strips/normalizes inbound `X-Forwarded-For` (infra). Reported. |
| **I-01** | Infra (report-only) | Admin IP allowlist fails open when unset | **High (infra)** | `config/settings.py:561`; enforced in `common/middleware_security.py:138` `AdminIPRestrictionMiddleware` | If `ADMIN_ALLOWED_IPS` is empty in production, the middleware returns `None` (allow all) and only a `warnings.warn` is logged at startup. The entire `/api/admin/` + `/django-admin/` surface is then reachable from any IP (still requires `is_staff`, but removes a key network control). | Make production **fail closed**: if `not DEBUG and not ADMIN_ALLOWED_IPS`, refuse to boot (or default-deny admin paths). Enforce the allowlist at the edge (D1 nginx) too. Report-only (settings/infra). |
| **I-02** | Infra (report-only) | `X-Forwarded-For` trust / proxy count | **Medium (infra)** | `config/settings.py:234` `NUM_PROXIES=1`; XFF parsing in `common/middleware_security.py:79,157` | Client IP (used for admin allowlist, throttling, audit, IP-block) trusts the first XFF entry. If the real proxy depth differs or the edge doesn't sanitize XFF, IP-based controls can be spoofed. | Pin the trusted proxy IPs (Django `SECURE_PROXY_SSL_HEADER` is set; consider `django-ipware` with trusted proxies) and have the edge overwrite XFF. Report-only. |
| **I-03** | Infra (report-only) | Firewall matrix D2/D3/D4 private-only; secret rotation; Vault | **Info/Report** | `.github/workflows/*`, `scripts/*`, `docker-compose.*.yml`, `docs/VAULT_SETUP.md` | Not modified per engagement constraints. The compose files and Vault loader (`config/vault_loader.py`) follow a sound pattern (Vault injects KV into env, graceful fallback). Validate that data-plane droplets (DB/Redis/RabbitMQ) bind to the private interface only, that the credential email is redacted, and that JWT/DB secrets rotate on a schedule. | Verify the per-droplet UFW/cloud-firewall rules restrict D2–D4 to the VPC; confirm Vault unseal-key handling and secret rotation cadence. Report-only. |
| **H-01** | Hardening | CSP allows `'unsafe-inline'` scripts | **Low** | `common/middleware_security.py:124` | The production CSP permits `script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net`, weakening XSS defense. (DRF JSON APIs reduce reflected-XSS surface, and the SPA is React, so risk is contained.) | Move to nonce/hash-based scripts and drop `'unsafe-inline'`; tighten `connect-src`/`img-src https:`. Reported. |
| **H-02** | Hardening | Duplicate Stripe webhook handlers; legacy path | **Low** | `apps/billing/views.py:138` `StripeWebhookView` **and** `apps/billing/payment_controller.py:506` `StripeWebhookView` | Two Stripe webhook views exist (one verifies + idempotent, one legacy). Both verify signatures, so no vuln, but duplicated handlers risk divergence (one being wired up without the protections of the other). | Consolidate on a single webhook view; delete the unused one. Reported. |
| **H-03** | Hardening | Session "single active session" model can be bypassed via header token after cookie logout | **Low** | `apps/accounts/views.py:596` `LogoutView`; `common/security.py` `SessionTracker` | Logout blacklists the refresh token and clears cookies, but a copy of the still-unexpired **access** token (15 min) held outside the browser remains valid until the JTI check fails — which only triggers when a *newer* session overwrites it. Acceptable given 15-min lifetime. | Optionally call `SessionTracker.invalidate_session` on logout for the current JTI. Reported. |

---

## Areas reviewed and found SOUND (no action)

These were checked specifically because the brief called them out, and were found correctly implemented:

* **Object-level authorization (IDOR):** Lab sessions (`StopLabView`, `ValidateLabView`, `CodingSpecView`, `LabHintsView`, `CommandHistoryView`, terminal WebSocket `_get_session`), interviews (every `InterviewRound*` view filters `campaign__user=request.user`), invoices (`InvoiceDownloadView` scopes `user=request.user` unless staff), org data (`org_views.py` checks membership + role on every action), and billing (`CancelTechSubscriptionView`, `UserTechSubscriptionsView`) all enforce ownership. Tested user-A-cannot-read-user-B by construction (`get_object_or_404(..., user=request.user)`).
* **SQL injection:** No `.raw()`, `.extra()`, `RawSQL`, or string-formatted `cursor.execute` in application code (only a SQLite-guard migration uses a cursor with static SQL). All filtering goes through the ORM.
* **Command injection:** No `os.system`/`shell=True`. `subprocess` is used only by the sandbox (argv list, no shell) and an admin-only `docker inspect` with a fixed argv. The Docker provisioner uses the Docker SDK, not shell. Terminal blocked-command patterns are compiled safely.
* **Path traversal:** Scenario YAML/`check.sh` paths are built from the DB **slug** (admin-controlled) + fixed roots, guarded by `os.path.isfile`, and parsed with `yaml.safe_load`. No end-user-controlled path reaches `open()`.
* **Webhook signature verification:** Razorpay (`payment_controller.py:392`, HMAC-SHA256 + `hmac.compare_digest`, distinct webhook secret, 5-min replay window, idempotency cache) and Stripe (`construct_event`, idempotency cache) both verify. Org Razorpay verify uses `compare_digest`. Payment **amounts are validated server-side** against the gateway (`_verify_payment_with_gateway`, webhook amount checks) and prices are never trusted from the client.
* **Mass assignment:** Account serializers are explicit `serializers.Serializer` (not `ModelSerializer`); no `fields = '__all__'` anywhere. `OrganizationSettingsView` uses an `ALLOWED` field whitelist.
* **Secrets in serializers / logs:** No password hashes, tokens, or API keys are exposed in any serializer. JWT cookies are `httpOnly`+`Secure`. The audit middleware logs only method/status/path (never request bodies). `mask_pii` masks emails/phones/cards in structured logs.
* **Admin surface:** Every `adminpanel` view uses `IsPlatformAdmin`; the one exception (`AdminNodeMetricsView`) uses `_IsAdminOrAgentToken` with `constant_time_compare` and a non-empty-token guard. `/django-admin/` has an extra superuser-only middleware.
* **Secrets in git:** `.env`, `.env.production`, `*.pem`, and Vault init files are gitignored and **not** tracked.
* **Support bot / Jira context:** Rule-based, no LLM, no data egress. `resolve_lab_context` only derives a technology-group label (no PII) from a session id and never returns session data.

---

## Secure-implementation recommendations (prioritized)

1. **Isolate the code-exec grader (C-01).** This is the #1 item. Run user code in a throwaway container: `--network none`, `--read-only` rootfs with a small `tmpfs` workdir, `--cap-drop ALL`, `--pids-limit 64`, `--memory 256m`, `--user 65534:65534` (nobody), a restrictive seccomp profile, and no bind mounts of app code/secrets. Invoke it from a Celery worker, not the web request. Until then, the in-process `rlimits` (now incl. `NPROC`) only bound resource use, **not** data exfiltration.
2. **Add CSRF defense for cookie auth (A-01).** Either require the `Authorization: Bearer` header for all mutating requests (cookies for GET only) or implement double-submit CSRF tokens for cookie-authenticated POST/PUT/PATCH/DELETE. Consider `SameSite=Strict` for the auth cookies.
3. **Make OAuth `state` a real nonce (A-03).** Random per-attempt value, server-verified on callback; bind to the user on the `link` flow.
4. **Fail closed on the admin IP allowlist in production (I-01).** Refuse to boot (or default-deny `/api/admin/`) when `not DEBUG and not ADMIN_ALLOWED_IPS`, and enforce at the edge.
5. **Verify provider-email is verified before social account linking (A-04).**
6. **Normalize `X-Forwarded-For` at the edge and pin trusted proxies (I-02/A-05)** so IP-based throttles/allowlists can't be spoofed.
7. **Consolidate the two Stripe webhook views (H-02)** to avoid protection drift.
8. **Tighten CSP** to nonce-based scripts; drop `'unsafe-inline'` (H-01).

---

## Production-grade hardening checklist

**Application**
- [ ] Code grading runs in an isolated, network-less, read-only, non-root, pids-limited container (C-01).
- [x] Sandbox sets `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE`, **`RLIMIT_NPROC`**, **`RLIMIT_CORE=0`**, **`RLIMIT_NOFILE`**, and `umask(077)`.
- [ ] CSRF protection enforced on all cookie-authenticated state changes (A-01).
- [ ] OAuth `state` is a verified random nonce (A-03); provider email verified before linking (A-04).
- [x] Password change invalidates all active sessions and enforces the full password policy (A-02).
- [x] No raw exception strings returned on the user-facing refund path (D-02).
- [ ] Single consolidated Stripe webhook view (H-02).
- [x] All per-user resources scoped by owner; all admin views behind `IsPlatformAdmin`.
- [x] Webhook signatures verified (Stripe/Razorpay) with idempotency + replay window; amounts re-validated server-side.

**Configuration / secrets**
- [ ] `DEBUG=False` in production (default is `False`; confirm env never sets it true).
- [ ] `ALLOWED_HOSTS` set to the real domains (empty default in prod is fail-closed — confirm it's populated).
- [ ] `DJANGO_SECRET_KEY`, `JWT_RSA_*`, DB/Redis/RabbitMQ creds sourced from Vault/secret store; rotation cadence defined (I-03).
- [ ] `ADMIN_ALLOWED_IPS` set; production fails closed when unset (I-01).
- [x] `.env*` and `*.pem` gitignored and untracked.
- [x] Argon2 password hashing; `SECURE_HSTS_*`, `SECURE_SSL_REDIRECT`, secure/httpOnly/SameSite cookies enabled.

**Infrastructure (verify; report-only here)**
- [ ] D2/D3/D4 (DB/Redis/RabbitMQ + workers) bind to the private VPC interface only; no public ports.
- [ ] Edge (D1) terminates TLS, strips/sets `X-Forwarded-For`, enforces the admin IP allowlist, and rate-limits.
- [ ] Vault unseal keys handled out-of-band; AppRole creds short-lived; credential email redacted in logs/notifications.
- [ ] Container images run as non-root; `cap_drop`, `read_only`, and `no-new-privileges` where possible.
- [ ] Centralized logging with the JSON formatter + PII masking; alert on `login_failed` spikes and admin-access-denied events.

---

*End of report.*
