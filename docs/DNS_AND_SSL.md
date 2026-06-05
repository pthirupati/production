# DNS and HTTPS for fixitlab.in

## Automatic DNS (GoDaddy)

When the production IP changes, run:

```bash
./scripts/update-godaddy-dns.sh 64.227.175.89
```

Or it runs automatically from **Production Deploy** (Create server) and `update-production-host.sh` if `GODADDY_API_KEY` + `GODADDY_API_SECRET` are in your env.

Updates:
- **A** `@` → server IP
- **CNAME** `www` → `fixitlab.in`

## Your GoDaddy DNS is correct

| Type  | Name | Value           | Notes                          |
|-------|------|-----------------|--------------------------------|
| A     | @    | 64.227.175.89     | Root domain → server IP        |
| CNAME | www  | fixitlab.in.    | www resolves via root A record |

Verify from your machine:

```bash
dig +short fixitlab.in
dig +short www.fixitlab.in
# Both should return 64.227.175.89
```

## Why the site “works on IP” but not on the domain

1. **HTTP works** — `http://fixitlab.in` and `http://64.227.175.89` both hit nginx on port 80.
2. **HTTPS was broken** — Browsers often upgrade to `https://fixitlab.in`. Port 443 was closed because the gateway ran HTTP-only bootstrap mode (no TLS listener) until Let's Encrypt certificates existed.

## Fix on the production server

After deploying the latest gateway changes:

```bash
ssh root@64.227.175.89
cd /opt/fixitlab
git pull   # or deploy via GitHub Actions Platform Start

# Rebuild gateway (bootstrap nginx + self-signed HTTPS on :443)
docker compose -f docker-compose.prod.yml build gateway
docker compose -f docker-compose.prod.yml up -d gateway

# Obtain trusted Let's Encrypt certificate
chmod +x scripts/ensure-ssl-certs.sh
./scripts/ensure-ssl-certs.sh

# Verify
curl -sI http://fixitlab.in/
curl -skI https://fixitlab.in/   # -k only needed before LE cert is issued
```

### Bootstrap vs production TLS

| Mode       | Port 80 | Port 443 | Certificate                          |
|------------|---------|----------|--------------------------------------|
| Bootstrap  | Site    | Site     | Self-signed (browser warning)        |
| Production | ACME    | Site     | Let's Encrypt (trusted)              |

Once `ensure-ssl-certs.sh` succeeds, the gateway automatically switches to `nginx.prod.conf` with trusted HTTPS.

## Firewall

Ensure ports 80 and 443 are open:

```bash
ufw allow 80/tcp
ufw allow 443/tcp
ufw status
```

## Environment variables

In `.env.production`:

```env
SITE_URL=https://fixitlab.in
SSL_DOMAIN=fixitlab.in
LETSENCRYPT_EMAIL=your@email.com
```

## Sync secrets from GitHub

App config (Jira, OAuth, etc.) should live in the GitHub `production` environment secret `PRODUCTION_ENV_B64`, not in git:

```bash
./scripts/upload-secrets-to-github.sh   # run locally once
# Then trigger Platform Start workflow
```

On the server, confirm Jira is loaded:

```bash
grep JIRA_ .env.production
docker compose -f docker-compose.prod.yml exec backend python -c "
from django.conf import settings
print(settings.JIRA_ENABLED, settings.JIRA_PROJECT_KEY, bool(settings.JIRA_API_TOKEN))
"
```
