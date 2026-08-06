# Changelog

Notable changes to FixitLab, newest first.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions
here are **product milestones, not git tags** — the repo carries no semver tags
(audit Z6-15), and pretending otherwise would make this file lie on day one.

> This file was created in August 2026 by moving the release history out of
> `frontend/src/pages/Changelog.jsx`, where it lived as a hardcoded
> `FALLBACK_RELEASES` array. The page had markdown-parsing support but nothing to
> parse, so the fallback was always what shipped. Entries before v2.5 are that
> history, preserved as written.

## [Unreleased]

### Added
- Feature-flag layer (`settings.FEATURES` + `config.features.feature_enabled`),
  so a risky change can ship dark and be switched off with a `FEATURE_*`
  environment variable instead of a redeploy. Flags are re-read on every call —
  reading them at import time caches the value for the worker's life and makes
  flipping a flag look like it did nothing.
- Rollback drill mode: `rollback.yml` now takes `dry_run` (defaulting to **on**)
  that reports which commit would be restored and, critically, which migrations
  it added. The rollback scripts do not reverse migrations, so rolling back
  across a forward-incompatible one leaves the code and schema disagreeing.

### Changed
- Third-party GitHub Actions that receive credentials (`action-doctl`,
  `build-push-action`, `github-script`) are pinned to commit SHAs rather than
  mutable tags. `digitalocean/action-doctl@v2` was a *branch*, so upstream could
  change what CI ran against our DigitalOcean token without a commit here.
- Dependency scanning fails on CRITICAL findings instead of being advisory-only.
  Severity now comes from the OSV API: pip-audit's JSON carries no severity
  field at all, and grepping the description text produced a false positive on a
  advisory whose remediation prose contained the phrase "for critical
  deployments".
- Mid-deploy metadata pushes retry with a rebase instead of `|| true`. A
  swallowed push meant the next run read a stale droplet IP and could target the
  wrong host.

### Known gaps
- Still no semver tags and no version surfaced in the app, so entries here
  cannot yet be tied to a release. Still no error budgets. (audit Z6-15)

- Two-factor authentication (TOTP, RFC 6238). Mandatory for staff accounts,
  recommended for accounts holding resume or interview data, optional otherwise.
  Recovery codes, replay protection, and enforcement on social sign-in too.
- Activation funnel in the admin panel, derived from first-party data — signup →
  lab started → first command → completion → purchase, with per-technology
  conversion and time-to-activation.
- Browser crash reporting routed into the existing server-side error pipeline.
- Installable web app: manifest, maskable icons, apple-touch-icon.
- Structured data (`Course`, `Organization`, `BreadcrumbList`) for search results.
- Cookie and local-storage disclosure in the privacy policy; terms and privacy
  acceptance now recorded against a version.
- Small-screen warning before starting a lab, so a phone user is told what a lab
  needs before a daily slot is spent.
- GST place of supply, export zero-rating, and a gapless per-financial-year tax
  invoice series.
- Python linting (ruff) and a missing-migration gate in CI.

### Changed
- Subscriptions now cancel at period end instead of revoking access immediately.
- Password reset no longer reveals whether an account exists.
- Ratings require completing the lab, and averages are suppressed below three
  ratings.
- Blog content moved to the database; the bundled copy is now an offline fallback
  only.
- PostgreSQL retuned for the 8 GB data node.

### Fixed
- Deleting an account no longer destroys other people's replies in threads they
  started.
- Ten React labs described LLM context windows instead of React Context, caused by
  a duplicate key in the copy generator.
- Cache invalidation targeted a key the API had stopped writing, so catalog edits
  were invisible for the full TTL.
- Terminal output is now bounded server-side; a runaway command could previously
  saturate a worker.
- "Perfect Score" was awarded to essentially every completion.

## [v2.4] — June 2026 — Teams, coupons & security
- Enterprise seat licensing with org invites and per-member analytics
- Coupon codes at checkout for technology and interview plans
- Admin security dashboards, audit logs, and rate limiting
- Community threads now support screenshot attachments

## [v2.3] — May 2026 — AI Interview Studio
- Multi-round voice interviews (technical, manager, HR, leadership)
- Resume-aware questions with adaptive STAR scoring and reports
- FIXIT-INT certificates with public verification
- Pro and Premium interview plans, separate from lab subscriptions

## [v2.2] — April 2026 — Jira incident workflow
- Personal Jira ticket per learner per scenario with status timeline
- Bot account creates and transitions issues via the Jira REST API
- Bidirectional webhook sync of status and comments
- Built-in AI-powered mode when Jira is not configured

## [v2.1] — March 2026 — Cloud labs & faster spin-up
- AWS EC2 and DigitalOcean lab modes for cloud-native scenarios
- Instant AI-powered RHEL environments — ready in seconds
- Dual-pane terminals and SSH-client scenarios for networking
- Per-scenario blocked-command guardrails and session recording

## [v2.0] — February 2026 — Browser terminal labs
- Full xterm.js shell over WebSocket — real commands in any browser
- Auto-validation checks your fix inside the environment
- Global and per-technology leaderboards with timed scoring
- Bookmarks, achievements, and downloadable completion certificates
