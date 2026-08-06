# 0005 — Gmail API for transactional email

**Status:** Accepted, with a known ceiling
**Written:** 2026-08 (retrospectively)

## Context

The platform sends OTPs, password resets, receipts, renewal reminders and
notifications. OTP and password reset are **auth-critical**: if they do not arrive,
users cannot sign in.

Deliverability for a new domain is the hard part, not throughput.

## Decision

Gmail API as the primary sender, with SMTP and SendGrid as configured fallbacks.
Delivery is split by criticality (`dispatch_notification_email`):

- **critical** (OTP, password reset) — sent from the web process in a daemon
  thread, so delivery does not depend on Celery being healthy;
- **non-critical** — queued to the Celery `notifications` queue, with a synchronous
  fallback if the worker is down.

## Consequences

- OTP delivery survives a broker outage. This is the whole reason for the split: a
  dead Celery worker must not mean nobody can sign in.
- **A shared daily quota of roughly 500 messages is the real constraint**, and it is
  a security boundary as much as a capacity one. Any unthrottled endpoint that
  sends mail can exhaust it and take OTP delivery down with it — which is exactly
  the contact-form finding (Z2-6), and why a reserve is held back for auth mail.
- Sending from a personal-domain Gmail identity limits bulk sending. Marketing mail
  needs a separate identity before it grows.
- The daemon-thread path means a critical send is fire-and-forget: failures are
  logged, not surfaced to the caller. Deliberate — the password-reset response must
  not reveal whether an account exists (Z2-5).

## Alternatives rejected

- **SES / Postmark / dedicated ESP.** The right answer at volume and the likely next
  step. Rejected for now on setup cost and domain-warming time, not on merit.
- **SMTP only.** Deliverability from a fresh droplet IP is poor.
- **Everything through Celery.** Would make signing in depend on the broker.
