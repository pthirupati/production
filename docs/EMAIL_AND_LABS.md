# Email on FixitLab (production)

## Quick checklist (production)

1. Set `GMAIL_OAUTH_*` in `.env.production` on the **backend** and ensure the same file is loaded by **celery_worker**.
2. Admin → Settings → **Send test email** (or `POST /api/admin/email/test/`).
3. Admin → Security → confirm **Gmail API: Connected** and no 15-minute delivery alert.
4. After each deploy, scenarios sync automatically via `platform-start.sh` (`seed_scenarios`). Manual: Admin → Scenarios → **Sync from repo**.

## Why Gmail SMTP in `.env` does not work on your server

| What you configured | What happens |
|---------------------|--------------|
| `EMAIL_HOST=smtp.gmail.com` + app password | **Blocked** — DigitalOcean blocks outbound SMTP ports 587 and 465 |
| MailHog container | **Dev only** — in `docker-compose.yml`, not production. It catches mail locally; it never delivers to real inboxes |

There is no mail container in `docker-compose.prod.yml` because catching mail locally does not help production users receive OTPs.

**Gmail app passwords only work over SMTP.** They cannot bypass a blocked port.

## What actually works (free, using your Gmail)

### Option A: Gmail API over HTTPS (recommended — uses your Gmail)

Uses port **443** (not blocked). Same Google account; ~**500 emails/day** on free Gmail (not unlimited — Google’s limit).

**One-time setup on your laptop:**

1. [Google Cloud Console](https://console.cloud.google.com) → your project (or create one)
2. Enable **Gmail API**
3. OAuth consent screen → External → add scope `https://www.googleapis.com/auth/gmail.send`
4. Add your sender Gmail under **Test users** (while app is in Testing)
5. Credentials → Create OAuth client ID → **Desktop app**
6. Run locally:

```bash
cd fixitlab
pip install google-auth-oauthlib google-api-python-client
export GMAIL_OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com
export GMAIL_OAUTH_CLIENT_SECRET=xxx
python scripts/setup-gmail-oauth.py
```

7. Add to `.env.production` on the server:

```env
EMAIL_HOST_USER=your-sender@gmail.com
GMAIL_OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com
GMAIL_OAUTH_CLIENT_SECRET=xxx
GMAIL_OAUTH_REFRESH_TOKEN=1//xxx
DEFAULT_FROM_EMAIL=FixitLab <your-sender@gmail.com>
```

You can reuse the same `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` already in `.env` if the OAuth client is the same project.

8. Rebuild and restart:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production build backend
docker compose -f docker-compose.prod.yml --env-file .env.production up -d backend celery_worker
```

**Delivery order in code:** Gmail API → SendGrid (if set) → SMTP (local dev only).

### Option B: SendGrid (optional, 100/day free)

```env
SENDGRID_API_KEY=SG.xxxx
EMAIL_HOST_USER=verified-sender@fixitlab.in
```

## Verify sending

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c "
from apps.notifications.email import send_email
send_email('FixitLab test', 'YOUR_EMAIL@gmail.com', 'emails/otp_verification.html',
           {'otp_code': '123456', 'expires_minutes': 10})
"
```

Check logs:

```bash
docker compose logs celery_worker --tail 20 | grep -i email
docker compose logs backend --tail 50 | grep -i email
```

## Refresh token runbook (when Gmail stops sending)

Symptoms: Admin Security shows **Gmail API: Error**, EmailLog has failures, OTP emails not arriving.

1. On your laptop (not the blocked SMTP VPS):

```bash
cd fixitlab
pip install google-auth-oauthlib google-api-python-client
export GMAIL_OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com
export GMAIL_OAUTH_CLIENT_SECRET=xxx
python scripts/setup-gmail-oauth.py
```

2. Copy the new `GMAIL_OAUTH_REFRESH_TOKEN` into `.env.production` on the server.
3. Restart **both** services:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d backend celery_worker
```

4. Send admin test email and register a test user to confirm OTP delivery.

**Note:** Refresh tokens can expire if revoked in Google Account → Security, or if OAuth consent app is deleted.

## Delivery alerts (15-minute window)

Admin Security and `/api/admin/health/` expose `email_delivery_alert` when:

- Any failures with zero successes in the last 15 minutes, or
- Failure rate ≥ 50% with at least 3 attempts.

Fix Gmail OAuth on workers before scaling user traffic.

## Limits (honest expectations)

| Method | Free tier limit |
|--------|-----------------|
| Gmail (personal) | ~500 recipients/day |
| Gmail (Workspace) | Higher (plan-dependent) |
| SendGrid free | 100/day forever |
| SMTP from VPS | Blocked on DigitalOcean |

There is no truly **unlimited free** email from a personal Gmail account on a VPS.

## Lab scenario images

Labs need Docker images built on the server:

```bash
./scripts/build-scenario-images.sh
```
