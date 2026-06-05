# Jira Cloud Setup for FixitLab

## 1. Create Jira Cloud project

1. Sign up at [atlassian.com/software/jira](https://www.atlassian.com/software/jira)
2. Create a **Team-managed** or **Company-managed** project
3. Note the project key (e.g. `FIXIT`)

## 2. API token

1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Create token → copy value
3. Set in `.env.production` (or `deploy/production.env` → upload via `./scripts/upload-secrets-to-github.sh`):

See [GITHUB_SECRETS.md](GITHUB_SECRETS.md) for how env reaches the server.

```env
JIRA_ENABLED=true
JIRA_BASE_URL=https://fixitlab.atlassian.net
JIRA_EMAIL=your-atlassian-account@email.com
JIRA_API_TOKEN=your-token
JIRA_PROJECT_KEY=KAN
JIRA_WEBHOOK_SECRET=generate-a-long-random-string
SITE_URL=https://fixitlab.in
```

**Important:** `JIRA_BASE_URL` must be your site root only (`https://YOURORG.atlassian.net`), **not** a board URL like `/jira/software/projects/KAN/boards/2`.

**Project key:** In Jira → Project settings → Details → **Key** (e.g. `KAN`, not the project display name).

## 3. Workflow transitions

Ensure your Jira workflow includes these status names (or update env vars):

| Env var | Default |
|---------|---------|
| `JIRA_TRANSITION_TODO` | To Do |
| `JIRA_TRANSITION_IN_PROGRESS` | In Progress |
| `JIRA_TRANSITION_DONE` | Done |

## 4. Webhook (bidirectional sync)

In Jira: **Settings → System → Webhooks → Create**

| Field | Value |
|-------|-------|
| URL | `https://fixitlab.in/api/jira/webhooks/?secret=YOUR_JIRA_WEBHOOK_SECRET` |
| Events | Issue updated, Comment created |

When a manager updates a ticket in Jira, FixitLab:

- Updates ticket status on the user's dashboard
- Sends an in-app notification
- Logs the event in `JiraWebhookEvent`

## 5. User flow

1. User opens scenario → FixitLab creates **their own** Jira ticket (e.g. `KAN-12`)
2. User sees ticket **inside FixitLab** (key, status, activity) — **no Jira login required**
3. User starts lab → ticket → **In Progress**
4. User completes lab → ticket → **Done**
5. User retries → same ticket reset, run count increments

**Staff only:** Admins with `is_staff` see an "Open in Jira ↗" link to Atlassian.

## 6. Multi-user model (important)

| Question | Answer |
|----------|--------|
| Same ticket for all users? | **No** — one ticket per **user + scenario** |
| User A vs User B on "Broken Nginx" | User A → `KAN-12`, User B → `KAN-13` (separate issues) |
| Can users see each other's comments? | **No** — API filters by logged-in user; each ticket is private in Jira |
| Who logs into Jira? | **Only the server bot** (`JIRA_EMAIL` + API token). Learners never need Atlassian accounts |
| Why did Jira ask for a password? | The old UI linked to `atlassian.net` — that site requires login. Use the in-app ticket panel instead |

Database: `UserScenarioJiraTicket` with `unique_together (user, scenario)`.

## 7. Verify

```bash
docker compose exec backend python manage.py seed_scenarios
# Start a lab via UI — check Jira project for new FIXIT-xxx ticket
curl -X POST "http://localhost/api/jira/webhooks/?secret=YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"webhookEvent":"jira:issue_updated","issue":{"key":"FIXIT-1","fields":{"status":{"name":"Done"}}}}'
```
