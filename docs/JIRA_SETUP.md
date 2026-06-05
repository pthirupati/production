# Jira Cloud Setup for FixitLab

## 1. Create Jira Cloud project

1. Sign up at [atlassian.com/software/jira](https://www.atlassian.com/software/jira)
2. Create a **Team-managed** or **Company-managed** project
3. Note the project key (e.g. `FIXIT`)

## 2. API token

1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Create token → copy value
3. Set in `.env.production`:

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

1. User opens scenario → sees existing Jira ticket (if any)
2. User starts lab → ticket created or reset → **In Progress**
3. User clicks Jira link → reads full incident details in Atlassian
4. User fixes issue in terminal → validates → ticket → **Done**
5. User restarts same lab → ticket reset → **In Progress** again (run count increments)

## 6. Verify

```bash
docker compose exec backend python manage.py seed_scenarios
# Start a lab via UI — check Jira project for new FIXIT-xxx ticket
curl -X POST "http://localhost/api/jira/webhooks/?secret=YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"webhookEvent":"jira:issue_updated","issue":{"key":"FIXIT-1","fields":{"status":{"name":"Done"}}}}'
```
