# FixitLab Security Audit

**Date:** 2026-06-21
**Auditor:** Senior Security Engineer (application security review)
**Scope:** Django REST backend (`backend/`), React frontend (`frontend/`), Docker compose, and the 4-droplet IaC (`.github/workflows`, `scripts/`). Infrastructure findings are **report-only** per engagement constraints; application-code Critical/High issues were fixed in this pass.
**Method:** Manual source review of authentication/authorization, injection surfaces, the code-execution sandbox, sensitive-data handling, API permission coverage, and infrastructure config. No automated scanners; findings are evidence-based with `file:line` references.

---

## Executive Summary

FixitLab's application security posture is, on the whole, **mature and well-considered**. Object-level authorization is applied consistently (every per-user resource — lab sessions, interviews, invoices, org data — is scoped with `user=request.user` or a membership/role check). There is **no raw SQL** in application code, payment **webhook signatures are verified** (Razorpay HMAC + Stripe `construct_event`) with idempotency and replay protection, secrets are kept out of git, passwords use **Argon2**, and the admin surface is uniformly gated behind `IsPlatformAdmin` plus an IP allowlist and a defense-in-depth Django-admin middleware.

The dominant risk **was** the **free code-execution sandbox**. User-submitted Python/JavaScript was executed **synchronously inside the Django web container**, isolated only by POSIX `rlimits`, a scrubbed environment, and a wall-clock timeout — with **full outbound network access, full read access to the host filesystem (app source, JWT signing key, DB/Redis/RabbitMQ credentials), and unrestricted process spawning**. **This is now fixed (C-01):** the grader runs each submission in a throwaway, **network-less, read-only, non-root, capability-dropped, pids/memory/CPU-capped Docker container** on the dedicated labs engine, with the in-process `rlimit` grader kept as a fail-closed fallback for dev/CI (gated by `SANDBOX_DOCKER`). See the C-01 row and "What was FIXED" below.

The other notable gaps were: JWT delivered via **both** httpOnly cookie **and** JSON body with **no CSRF defense** on the cookie path (**now fixed, A-01** — the cookie path requires a custom JS header on state changes); OAuth login/link flows whose `state` parameter is **not** a CSRF nonce (still open, A-03); a password change that **did not rotate the session/JTI** (fixed, A-02); and a small number of endpoints returning raw exception strings (refund path fixed, D-02).

### Top Critical / High findings (one line each)

| Sev | Finding | Status |
|-----|---------|--------|
| **Critical** | Code-exec sandbox runs user code in the web process with host FS + network + secrets reachable (no container/namespace isolation) — `apps/labs/code_exec.py` | **FIXED** (C-01) — container backend `apps/labs/sandbox_runner.py` |
| **High** | Cookie-based JWT auth has no CSRF protection on state-changing endpoints (only `SameSite=Lax` mitigates) — `apps/auth_app/cookie_auth.py`, `config/settings.py` | **FIXED** (A-01) — custom-header requirement on cookie path |
| **High** | OAuth `state` is the literal intent string, not a signed/random CSRF nonce — login & account-link CSRF — `apps/accounts/oauth_urls.py`, `apps/accounts/views.py` | Open (A-03) — needs FE/BE coordination |
| **High (infra)** | `ADMIN_ALLOWED_IPS` empty ⇒ admin API open to all IPs; only a warning is emitted — `config/settings.py` | **FIXED, opt-in** (I-01) — `ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST` |
| **Medium→High** | `ChangePasswordView` does not invalidate existing sessions/tokens, and enforces only an 8-char minimum — `apps/accounts/views.py` | **FIXED** (A-02) |
| **Medium** | Sandbox: no `RLIMIT_NPROC` ⇒ fork-bomb DoS of the host | **FIXED** (C-02) — superseded by C-01 container `--pids-limit` |
| **Medium** | Several endpoints return raw `str(exception)` to clients (mostly admin; refund endpoint) — `apps/billing/views.py` | **FIXED** (refund, D-02); admin-only details retained |

### What was FIXED in this pass (application code only)

1. **C-01 — Containerised code-exec grader (the flagship fix).** A new module `apps/labs/sandbox_runner.py` runs each submission inside a throwaway Docker container on the dedicated labs engine (`settings.DOCKER_SOCKET`, which may be a remote `ssh://` engine) with **`--network none` + `network_disabled`** (no egress, no cloud-metadata), a **read-only root filesystem**, a **non-root user (`65534:65534`)**, **`cap_drop=ALL`**, **`no-new-privileges`**, a **`--pids-limit` (anti fork-bomb)**, and hard **memory/CPU/tmpfs** caps. The harness is streamed in via `put_archive` (no bind mounts of app code/secrets), so app source, the JWT signing key, and DB/Redis creds are unreachable from user code. `apps/labs/code_exec.py` selects this backend when `settings.SANDBOX_DOCKER` is on **and** the engine answers a ping; otherwise it falls back to the existing in-process `rlimit` subprocess (so dev/CI keep working) and **also** falls back if the engine errors mid-grade. The verdict format is identical across backends; a missing/failed engine, non-zero exit, timeout, or unparseable output still **fails closed** (never auto-passes). The public grading API and the `finalize_validated_session()` completion path are unchanged.
2. **C-02 — Sandbox fork-bomb / resource caps** (`apps/labs/code_exec.py`): the in-process fallback retains `RLIMIT_NPROC`, `RLIMIT_CORE=0`, `RLIMIT_NOFILE`, `umask(0o077)`; the container backend enforces `--pids-limit`, `--memory`, and `--cpus` at the kernel/cgroup layer. Superseded in production by C-01.
3. **A-01 — CSRF defense on the cookie JWT path** (`apps/auth_app/cookie_auth.py`, `config/settings.py`, `frontend/src/api/client.js`): `CookieJWTAuthentication` now requires a custom JS header (`X-Requested-With`) on the **cookie-authenticated** path for unsafe HTTP methods — a cross-site auto-submitting `<form>` cannot set it, so a stolen-cookie CSRF is rejected. Safe methods and the `Authorization: Bearer` path (the SPA's default for authenticated calls, immune to CSRF) are untouched. Gated by `COOKIE_AUTH_REQUIRE_CSRF_HEADER` (default `True`); the SPA sends the header on every request.
4. **I-01 — Admin IP allowlist can now fail closed** (`config/settings.py`, `common/middleware_security.py`): a new `ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST` flag makes production **default-deny** `/api/admin/` + `/django-admin/` when `ADMIN_ALLOWED_IPS` is empty. **Default `False`** so the existing deploy (whose live E2E hits admin endpoints from arbitrary CI IPs without an allowlist) is not broken; flip it on once the allowlist is populated. Dev (`DEBUG`) is always allowed.
5. **A-02 — Session invalidation on password change** (`apps/accounts/views.py`): `ChangePasswordView` invalidates all active JWT sessions (`SessionTracker.invalidate_all_sessions`) and runs Django's `validate_password` (full policy). (Verified present.)
6. **D-02 — Raw-exception leak** removed from the admin **refund** response (`apps/billing/views.py`) — generic message; detail stays in server logs. (Verified present.)

Items left open are either infrastructure (per constraints) or Medium/Low not trivially safe to change without product/UX decisions — see "Still open" at the end.

### Verification

* `DJANGO_SETTINGS_MODULE=config.test_settings .venv/bin/python manage.py check` → passes (0 issues); `makemigrations --check` → no changes.
* `tests/test_coding_ide.py` (37 tests incl. new `DockerSandboxBackendTests` proving the container lockdown flags, verdict round-trip, fail-closed wrong-code, and graceful fallback) → passes.
* `tests/test_sandbox_security.py` (new — A-01 cookie-CSRF matrix + I-01 admin fail-closed matrix) → passes.
* `tests/test_api_security.py`, `tests/test_production_security.py` → pass (env-gated cases skipped as before). Frontend `npx vite build` → succeeds.
* The known SQLite-only `test_interviews` question-engine failure is pre-existing and unrelated (CI runs on Postgres; no interview/question files were touched this pass).

---

## Findings

> Severity scale: **Critical** (remote compromise / mass data loss), **High** (account takeover / privilege escalation / secret exposure), **Medium** (meaningful weakening of a control), **Low** (hardening / defense-in-depth).

| ID | Area | Title | Severity | Location | Attack scenario | Fix |
|----|------|-------|----------|----------|-----------------|-----|
| **C-01** | Code-exec sandbox | User code executes in the web process with host FS, network, and secrets reachable | **Critical** → **FIXED** | `backend/apps/labs/code_exec.py` (`_execute` dispatch) + new `backend/apps/labs/sandbox_runner.py`; invoked from `apps/public_api/views.py` `CodeValidateView` and `apps/interviews/services/practical_lab.py` | A subscriber to any coding scenario submits Python/JS that reads `JWT_RSA_PRIVATE_KEY`/`POSTGRES_PASSWORD` from `/proc/1/environ` or the mounted env file, opens a socket to an attacker host and exfiltrates them, or curls `http://169.254.169.254/` for cloud metadata. `rlimits` cap CPU/memory but do **not** restrict network or filesystem. | **FIXED.** Grading now runs in a throwaway container via `sandbox_runner.run_in_container`: `network_mode="none"` + `network_disabled=True` (no egress / no metadata), `read_only=True` rootfs, `user="65534:65534"` (non-root), `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `pids_limit`, `mem_limit`/`memswap_limit`, `nano_cpus`, and a small writable `tmpfs` at `/work` as the ONLY writable path. The harness is streamed in with `put_archive` — **no bind mounts** of app code/secrets — and runs on the dedicated labs engine (`settings.DOCKER_SOCKET`, may be remote `ssh://`). Enabled by `settings.SANDBOX_DOCKER`; the in-process `rlimit` grader is a fail-closed fallback for dev/CI and for transient engine errors. Verdict format unchanged; fails closed on any error. Tests: `tests/test_coding_ide.py::DockerSandboxBackendTests`. **Residual (infra, report-only):** moving the call to a Celery worker (off the web request) and adding a custom seccomp profile remain nice-to-haves; the network/FS/privilege isolation is now enforced. |
| **C-02** | DoS | Sandbox fork bomb crashes the host | Medium→High → **FIXED** | `apps/labs/code_exec.py` `_posix_preexec`; container `pids_limit` | User submits `import os; while True: os.fork()` (Py) — without a process cap the host process table fills, taking down Daphne for all users. | **Fixed:** `RLIMIT_NPROC` in the in-process fallback preexec hook **and** a kernel-enforced `--pids-limit` on the C-01 container backend. |
| **A-01** | AuthZ / CSRF | Cookie JWT with no CSRF enforcement on mutating endpoints | **High** → **FIXED** | `apps/auth_app/cookie_auth.py`; cookies set in `apps/accounts/views.py` `set_auth_cookies`; `config/settings.py`; `frontend/src/api/client.js` | `CookieJWTAuthentication` extends DRF `JWTAuthentication`, which (unlike `SessionAuthentication`) never calls `enforce_csrf`. A logged-in user's browser auto-attaches the `access_token` cookie. With `SameSite=Lax`, a cross-site **top-level POST** (e.g. an auto-submitting form) could still ride the cookie to a state-changing endpoint. | **FIXED.** `CookieJWTAuthentication._enforce_cookie_csrf` now rejects cookie-authenticated unsafe-method requests (`POST/PUT/PATCH/DELETE`) that lack a custom header (`X-Requested-With` / `X-CSRF-Header`) — a cross-site `<form>` cannot set one. The `Authorization: Bearer` path (the SPA default, immune to CSRF) and safe methods are untouched, so no existing flow breaks. Gated by `COOKIE_AUTH_REQUIRE_CSRF_HEADER` (default `True`); the SPA's axios client sets `X-Requested-With` on every request. Tests: `tests/test_sandbox_security.py::CookieAuthCsrfTests`. (`SameSite=Lax` retained as defense-in-depth; `SameSite=Strict` remains an option for first-party-only flows.) |
| **A-02** | Session mgmt | Password change does not revoke existing tokens; weak min length | **Medium→High** | `apps/accounts/views.py:574` `ChangePasswordView` | After a credential-stuffing or shoulder-surf compromise, the victim changes their password but the attacker's still-valid 7-day refresh token / 15-min access JTI remains usable — defeating the purpose of the reset. Also accepts 8-char passwords while registration requires 10 + complexity validators (`config/settings.py:175`). | **Fixed:** invalidate all sessions via `SessionTracker.invalidate_all_sessions(user.id)` and run Django's `validate_password`; min length raised to match policy. (`ResetPasswordView` similarly should rotate — noted; lower priority since the reset token is single-use.) |
| **A-03** | AuthZ / CSRF | OAuth `state` is the intent string, not a random/signed nonce | **High** | `apps/accounts/oauth_urls.py:36,49` (`"state": intent`); callbacks `apps/accounts/views.py:786,954` never validate `state` | The OAuth `state` parameter is meant to be an unguessable, per-session value verified on callback to prevent login CSRF and authorization-code injection. Here it is the constant `"login"`/`"register"`/`"link"`, so an attacker can stitch a victim's browser to the attacker's authorization code (login CSRF) or, on the `link` flow, trick a logged-in user into linking the attacker's social identity. | Generate a random `state`, store it server-side (cache keyed to the browser/session) or as a signed value, and verify it in the callback before exchanging the code. For the `link` flow, additionally bind `state` to the authenticated user. Reported (FE/BE coordination). |
| **A-04** | AuthZ | OAuth auto-link/registration on possibly-unverified email | **Medium** | `apps/accounts/views.py:885` `_resolve_social_login`; GitHub email selection `:850-857` | GitHub path prefers a `verified` primary email but **falls back to `emails[0]`** if none is verified, then auto-links to an existing FixitLab account with that email (account takeover if an attacker controls an unverified GitHub email matching a victim's address). Google's `email_verified` claim is not checked. | Require a provider-verified email before linking to an existing local account; never link on an unverified address. Reported. |
| **D-01** | Data exposure | Public certificate verifier enables user enumeration + name/progress disclosure | **Low** | `apps/public_api/views.py:2160` `CertificateVerifyView` (`user_id` parsed from cert string) | An unauthenticated caller iterates `FIXIT-<tech>-<id>-<date>` and learns each user's display name and completion counts. This is inherent to a public credential verifier, but it is unauthenticated enumeration. | Acceptable for a verification feature; optionally rate-limit harder and only echo data when a real `UserCertificate` row exists (don't reconstruct from raw IDs). Reported. |
| **D-02** | Data exposure | Endpoints return raw exception strings to clients | **Medium** | `apps/billing/views.py:1551` (admin refund: `f"Refund failed: {str(e)}"`); admin health checks `apps/adminpanel/views.py:1401+`; `apps/community/views.py:326` | Raw `str(e)` can leak gateway internals, library versions, or partial config. Most occurrences are admin-only (lower exposure), but the refund path echoes Razorpay SDK errors to the admin UI. | **Fixed** the refund response to a generic message (detail stays in logs). Admin-only health-check details left as-is (admin context, useful for ops) but noted. |
| **A-05** | Rate limiting | OTP / login throttle scoping | **Low** | `config/settings.py:221-232`; `apps/accounts/views.py` (`AuthRateThrottle 20/min`, `LoginRateThrottle 5/min`, `OTPRateThrottle 3/min`) | Throttles are present and reasonable. Anon throttles are keyed on client IP derived from `X-Forwarded-For[0]` with `NUM_PROXIES=1` — correct only if exactly one trusted proxy sits in front; a misconfigured proxy chain would let a client spoof `XFF` to evade throttling. | Verified the throttle rates are sound. Ensure the edge proxy strips/normalizes inbound `X-Forwarded-For` (infra). Reported. |
| **I-01** | Infra / config | Admin IP allowlist fails open when unset | **High** → **FIXED (opt-in)** | `config/settings.py`; `common/middleware_security.py` `AdminIPRestrictionMiddleware` | If `ADMIN_ALLOWED_IPS` is empty in production, the middleware previously returned `None` (allow all) with only a `warnings.warn`. The entire `/api/admin/` + `/django-admin/` surface was reachable from any IP (still `is_staff`-gated, but a key network control was missing). | **FIXED, opt-in.** New `ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST` flag: when set and `not DEBUG` and the allowlist is empty, the middleware **default-denies** admin paths (403). **Default `False`** because the live production E2E currently hits `/api/admin/...` from arbitrary GitHub-runner IPs **without** setting `ADMIN_ALLOWED_IPS`; making it fail-closed by default would break the green pipeline. **Recommended production config:** set `ADMIN_ALLOWED_IPS` to the office/VPN ranges **and** `ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=1`, and (or alternatively) enforce the allowlist at the D1 nginx edge so CI E2E can be scoped/allowlisted. Tests: `tests/test_sandbox_security.py::AdminIpFailClosedTests`. |
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

1. **~~Isolate the code-exec grader (C-01).~~ DONE.** User code now runs in a throwaway container (`--network none`, `--read-only` rootfs + small `tmpfs` workdir, `--cap-drop ALL`, `--pids-limit`, `--memory`, `--user 65534:65534`, `no-new-privileges`, no app/secret bind mounts) via `apps/labs/sandbox_runner.py`, gated by `SANDBOX_DOCKER`. **Remaining nice-to-haves:** move the call into a Celery worker (off the web request) and ship a custom seccomp profile.
2. **~~Add CSRF defense for cookie auth (A-01).~~ DONE.** Cookie-authenticated mutations now require a custom JS header (`X-Requested-With`); the Bearer-header path is unaffected. `SameSite=Strict` remains an optional further hardening.
3. **Make OAuth `state` a real nonce (A-03).** Random per-attempt value, server-verified on callback; bind to the user on the `link` flow. **Still open** (needs coordinated FE/BE change to the OAuth redirect/callback).
4. **~~Fail closed on the admin IP allowlist in production (I-01).~~ DONE (opt-in).** `ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST` default-denies `/api/admin/` when the allowlist is empty in prod. **Action for ops:** populate `ADMIN_ALLOWED_IPS` + set the flag (kept off by default so the current CI E2E, which hits admin from arbitrary IPs, stays green).
5. **Verify provider-email is verified before social account linking (A-04). Still open.**
6. **Normalize `X-Forwarded-For` at the edge and pin trusted proxies (I-02/A-05)** so IP-based throttles/allowlists can't be spoofed.
7. **Consolidate the two Stripe webhook views (H-02)** to avoid protection drift.
8. **Tighten CSP** to nonce-based scripts; drop `'unsafe-inline'` (H-01).

---

## Production-grade hardening checklist

**Application**
- [x] Code grading runs in an isolated, network-less, read-only, non-root, pids-limited container (C-01) when `SANDBOX_DOCKER=1`; in-process `rlimit` fallback for dev/CI.
- [x] Sandbox (in-process fallback) sets `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE`, **`RLIMIT_NPROC`**, **`RLIMIT_CORE=0`**, **`RLIMIT_NOFILE`**, and `umask(077)`; container backend caps pids/memory/cpus at the kernel layer.
- [x] CSRF protection enforced on all cookie-authenticated state changes (A-01) via the required custom header.
- [ ] OAuth `state` is a verified random nonce (A-03); provider email verified before linking (A-04). **Still open.**
- [x] Password change invalidates all active sessions and enforces the full password policy (A-02).
- [x] No raw exception strings returned on the user-facing refund path (D-02).
- [ ] Single consolidated Stripe webhook view (H-02). **Still open (Low).**
- [x] All per-user resources scoped by owner; all admin views behind `IsPlatformAdmin`.
- [x] Webhook signatures verified (Stripe/Razorpay) with idempotency + replay window; amounts re-validated server-side.

**Configuration / secrets**
- [ ] `DEBUG=False` in production (default is `False`; confirm env never sets it true).
- [ ] `ALLOWED_HOSTS` set to the real domains (empty default in prod is fail-closed — confirm it's populated).
- [ ] `DJANGO_SECRET_KEY`, `JWT_RSA_*`, DB/Redis/RabbitMQ creds sourced from Vault/secret store; rotation cadence defined (I-03).
- [~] `ADMIN_ALLOWED_IPS` set; production fails closed when unset (I-01) — capability shipped (`ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST`), default off pending allowlist population + CI E2E scoping.
- [x] `.env*` and `*.pem` gitignored and untracked.
- [x] Argon2 password hashing; `SECURE_HSTS_*`, `SECURE_SSL_REDIRECT`, secure/httpOnly/SameSite cookies enabled.

**Infrastructure (verify; report-only here)**
- [ ] D2/D3/D4 (DB/Redis/RabbitMQ + workers) bind to the private VPC interface only; no public ports.
- [ ] Edge (D1) terminates TLS, strips/sets `X-Forwarded-For`, enforces the admin IP allowlist, and rate-limits.
- [ ] Vault unseal keys handled out-of-band; AppRole creds short-lived; credential email redacted in logs/notifications.
- [ ] Container images run as non-root; `cap_drop`, `read_only`, and `no-new-privileges` where possible.
- [ ] Centralized logging with the JSON formatter + PII masking; alert on `login_failed` spikes and admin-access-denied events.

---

---

## Still open (with recommendations)

Prioritised remaining items after the P9 hardening pass. None is Critical; the
Critical (C-01) and the two cookie/admin Highs (A-01, I-01) are closed.

| ID | Sev | Item | Recommendation | Why not done now |
|----|-----|------|----------------|------------------|
| **A-03** | High | OAuth `state` is the literal intent string, not a random/signed nonce (login & link CSRF) | Generate a random per-attempt `state`, persist it server-side (cache keyed to the browser/session), verify on callback before code exchange; bind to the user on the `link` flow | Requires a coordinated change to the FE OAuth redirect **and** BE callback; touching the live OAuth flow is riskier than the brief's "additive + safe" scope and is better done as its own change with an OAuth E2E. |
| **A-04** | Medium | Social login auto-links on a possibly-unverified provider email (GitHub `emails[0]` fallback; Google `email_verified` unchecked) | Require a provider-verified email before linking to an existing local account; never link on an unverified address | Same OAuth-flow blast radius as A-03; pairs naturally with it. |
| **I-01 (residual)** | — | Fail-closed flag defaults off | Set `ADMIN_ALLOWED_IPS` + `ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=1` in prod env; allowlist/scope the CI E2E runner, or enforce the allowlist at the D1 nginx edge | Turning it on by default would break the current green production E2E (hits `/api/admin/...` from arbitrary GitHub-runner IPs with no allowlist set) — an ops/config action, not a code change. |
| **I-02 / A-05** | Medium | `X-Forwarded-For` trust / `NUM_PROXIES=1` — IP-based throttle/allowlist spoofable if proxy depth differs | Pin trusted proxy IPs; have the D1 edge overwrite inbound XFF | Infra/edge config (report-only per engagement constraints). |
| **H-01** | Low | CSP allows `'unsafe-inline'` scripts | Move to nonce/hash-based scripts; drop `'unsafe-inline'`; tighten `connect-src`/`img-src` | Nonce wiring through the SPA's inline bootstrap is non-trivial and can break rendering; React already contains reflected-XSS surface. Defense-in-depth, not a live vuln. |
| **H-02** | Low | Duplicate Stripe webhook views (`billing/views.py` + `payment_controller.py`) | Consolidate on one; delete the unused handler | Both verify signatures (no vuln today); requires confirming which is wired before deleting — safe but out of this pass's scope. |
| **H-03** | Low | Logout doesn't invalidate the current access JTI (valid ≤15 min) | Optionally call `SessionTracker.invalidate_session` for the current JTI on logout | Accepted given the 15-min access lifetime; minor. |
| **D-01** | Low | Public certificate verifier enables enumeration | Only echo data when a real `UserCertificate` row exists; rate-limit harder | Inherent to a public verifier; acceptable. |
| **I-03** | Info | Firewall matrix, secret rotation, Vault unseal handling | Verify D2–D4 bind to the private VPC only; define JWT/DB secret rotation cadence; redact credential email | Infrastructure (report-only). |

**Recommended next change (its own PR):** A-03 + A-04 together — make OAuth `state` a verified nonce and require provider-verified email before linking, behind an OAuth E2E. These are the only remaining High-adjacent items and share the same code paths.

---

*End of report.*
