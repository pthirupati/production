import { useParams, Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Clock, ArrowLeft, Tag, User, Calendar, ChevronRight } from 'lucide-react'
import DOMPurify from 'dompurify'
import api from '../api/client'
import { getCategoryClass } from '../data/blogFallback'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import { usePageTitle } from '../hooks/usePageTitle'

const blogContent = {
  'why-hands-on-learning-works': {
    title: 'Why Hands-On Learning Works Better Than Reading Docs',
    category: 'Education',
    author: 'Thirupathi P.',
    date: 'March 28, 2026',
    readTime: '5 min read',
    color: 'accent-cyan',
    content: `
## The Problem with Passive Learning

Most engineers learn new technologies by reading documentation. While docs are essential references, studies consistently show that passive reading has a retention rate of only **5–10%** after 24 hours. Lectures barely improve this — roughly 20%.

So why does the industry still default to "read the docs" as the primary learning path?

## The Case for Active Practice

Edgar Dale's **Cone of Experience** and more recent cognitive science research shows that retention skyrockets when learners *do* the thing they're trying to learn:

- **Reading:** 10% retention
- **Audio/Visual:** 20–30% retention
- **Demonstration:** 30% retention
- **Practice by doing:** 75% retention
- **Teaching others:** 90% retention

When you SSH into a broken server and actually fix the Nginx config yourself, your brain encodes that experience across multiple pathways — motor memory (typing commands), visual memory (seeing log output), and problem-solving pathways.

## How FixitLab Applies This

Every FixitLab scenario drops you into a **real, broken environment**. There's no multiple-choice quiz. No "click the right answer." You open a terminal, investigate, and fix.

### The Learning Loop

1. **Encounter** — You see the symptoms (502 error, service won't start, DNS failures)
2. **Investigate** — You run real commands: \`journalctl\`, \`nginx -t\`, \`dig\`, \`ss -tlnp\`
3. **Hypothesize** — Based on output, you form a theory
4. **Fix** — You edit configs, restart services, verify
5. **Validate** — FixitLab automatically checks your fix and scores it

This cycle mirrors real incident response — the #1 skill SREs and DevOps engineers need.

## The Science Behind Spaced Repetition

FixitLab's difficulty progression (Easy → Medium → Hard) and varied scenario types ensure you encounter concepts multiple times in different contexts. This **spaced repetition** effect cements knowledge into long-term memory.

A junior engineer who solves 20 hands-on scenarios will outperform one who read 200 pages of documentation — not because docs are bad, but because **doing is remembering**.

## Start Practicing

The best time to start hands-on learning was yesterday. The second best time is now. Pick a technology, choose a scenario, and break something (safely).
    `,
  },
  'debugging-nginx-like-a-pro': {
    title: 'Debugging Nginx Like a Pro: A Step-by-Step Guide',
    category: 'Linux',
    author: 'Platform Team',
    date: 'March 25, 2026',
    readTime: '8 min read',
    color: 'accent-green',
    content: `
## Introduction

Nginx powers over 30% of all websites on the internet. When it breaks, you need a systematic approach — not frantic googling. This guide walks through the exact debugging methodology that experienced SREs use.

## Step 1: Check the Service Status

Always start here:

\`\`\`bash
systemctl status nginx
journalctl -u nginx --no-pager -n 50
\`\`\`

The status output tells you:
- Is the service **active** or **failed**?
- What's the **PID** (or why it couldn't start)?
- Recent log entries that often contain the smoking gun

## Step 2: Test the Configuration

\`\`\`bash
nginx -t
\`\`\`

This is the single most useful Nginx debugging command. It validates all config files and reports the exact line number and file where syntax errors occur.

**Common errors you'll see:**
- \`unknown directive\` — typo or missing module
- \`conflicting server name\` — duplicate server blocks
- \`host not found in upstream\` — backend server unreachable

## Step 3: Check the Error Log

\`\`\`bash
tail -f /var/log/nginx/error.log
\`\`\`

Key patterns to look for:
- **\`connect() failed (111: Connection refused)\`** — upstream is down
- **\`permission denied\`** — SELinux or file permission issue
- **\`too many open files\`** — worker_connections limit hit

## Step 4: Verify Port Binding

\`\`\`bash
ss -tlnp | grep -E ':80|:443'
\`\`\`

If nothing is listening on port 80/443, Nginx isn't running. If something else is (Apache, Caddy), you have a port conflict.

## Step 5: Test with curl

\`\`\`bash
curl -I http://localhost
curl -v http://localhost 2>&1 | head -20
\`\`\`

The headers reveal whether Nginx is responding, what status code it returns, and which server block matched.

## Step 6: Check Upstream Connectivity

If Nginx is a reverse proxy:

\`\`\`bash
curl -I http://127.0.0.1:8000  # Test backend directly
\`\`\`

If the backend responds but Nginx returns 502/504, the issue is in the proxy_pass configuration.

## Common Fixes Cheat Sheet

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 502 Bad Gateway | Backend down or wrong port | Check upstream, restart backend |
| 403 Forbidden | File permissions or missing index | \`chmod\`/ check \`root\` directive |
| 404 Not Found | Wrong \`root\` or \`location\` | Verify paths in config |
| Connection refused | Nginx not running | \`systemctl start nginx\` |
| SSL handshake failed | Cert expired or wrong path | Check \`ssl_certificate\` paths |

## Practice on FixitLab

Our **Broken Nginx** scenario gives you a server with 3 intentional misconfigurations. Can you find and fix all of them in under 15 minutes?
    `,
  },
  'docker-vs-cloud-labs': {
    title: 'Docker vs Cloud Labs: When to Use Each for Training',
    category: 'Architecture',
    author: 'Platform Team',
    date: 'March 22, 2026',
    readTime: '6 min read',
    color: 'accent-purple',
    content: `
## The Lab Provider Decision

FixitLab supports three lab providers: **Docker**, **AWS EC2**, and **DigitalOcean Droplets**. Each has trade-offs that affect cost, realism, and startup time.

## Docker Labs (Default)

**Startup time:** 2–5 seconds
**Cost:** Near zero (runs on existing infrastructure)
**Realism:** High for single-service scenarios

Docker labs are perfect for most Linux troubleshooting scenarios. When a user clicks "Start Lab," we:

1. Pull the pre-built scenario image (\`fixitlab/scenario-broken-nginx\`)
2. Create a container with resource limits (512MB RAM, 1 CPU)
3. Attach user's terminal via WebSocket
4. Set a timer based on scenario difficulty

**Pros:**
- Instant provisioning — labs start in seconds
- Cheap — hundreds of concurrent labs on one server
- Isolated — each user gets their own container
- Reproducible — Docker images guarantee identical environments

**Cons:**
- Can't model multi-host networking
- Limited to Linux (no Windows labs)
- No real cloud provider interaction

## AWS EC2 Labs

**Startup time:** 45–90 seconds
**Cost:** ~$0.01 per lab session
**Realism:** Full VM with real networking

EC2 labs are used for scenarios that need:
- Multiple networked hosts
- Real systemd (not PID 1 hacks)
- Cloud-specific debugging (security groups, VPCs)
- Kubernetes clusters (multi-node)

## DigitalOcean Droplet Labs

**Startup time:** 30–60 seconds
**Cost:** ~$0.007 per lab session
**Realism:** Full VM, simpler networking

DO droplets are our middle ground — cheaper than EC2, more realistic than Docker, with faster provisioning.

## How We Choose

| Scenario Type | Provider | Reason |
|--------------|----------|--------|
| Single-service fix (Nginx, cron) | Docker | Speed + cost |
| Multi-service (DB + App + LB) | EC2 or DO | Need real networking |
| Kubernetes | EC2 | Need k3s/kind with real resources |
| Security/CTF | Docker | Isolation is critical |
| DNS/Networking | DO | Need real resolver chain |

## Architecture Deep Dive

The \`LabProvisioner\` factory pattern makes this transparent:

\`\`\`python
provisioner = get_provisioner(scenario.provider)  # "docker" | "aws_ec2" | "digitalocean"
session = provisioner.provision(scenario, user)
\`\`\`

Each provisioner implements the same interface: \`provision()\`, \`terminate()\`, \`get_status()\`, and \`cleanup_expired()\`.

## What's Next

We're exploring **Firecracker microVMs** for the best of both worlds: VM-level isolation with container-speed provisioning. Stay tuned.
    `,
  },
  'top-5-linux-troubleshooting-commands': {
    title: 'Top 5 Linux Commands Every SRE Should Master',
    category: 'Linux',
    author: 'Content Team',
    date: 'March 18, 2026',
    readTime: '7 min read',
    color: 'accent-amber',
    content: `
## The SRE Toolkit

When production is on fire at 3 AM, you don't have time to read man pages. These 5 commands should be muscle memory.

## 1. journalctl — Read System Logs

\`\`\`bash
# Last 100 lines from a specific service
journalctl -u nginx --no-pager -n 100

# Logs since last boot
journalctl -b

# Follow logs in real-time
journalctl -f -u myapp

# Logs from a specific time range
journalctl --since "2026-03-18 02:00" --until "2026-03-18 03:00"
\`\`\`

**Why it matters:** 90% of debugging starts with "what do the logs say?" \`journalctl\` is the unified log interface for all systemd services.

## 2. ss — Socket Statistics

\`\`\`bash
# All listening TCP ports with process info
ss -tlnp

# All established connections
ss -tn state established

# Connections to a specific port
ss -tn dport = :443

# Count connections by state
ss -s
\`\`\`

**Why it matters:** \`ss\` replaced \`netstat\` and is significantly faster. It answers: "Is the service listening?" "How many connections are open?" "Who's connected?"

## 3. strace — System Call Tracer

\`\`\`bash
# Trace a running process
strace -p <PID> -e trace=open,read,write

# Trace a command from start
strace -f -e trace=network curl https://example.com

# Count system calls (summary)
strace -c -p <PID>
\`\`\`

**Why it matters:** When logs tell you nothing, \`strace\` shows you exactly what a process is doing at the kernel level. It's the ultimate debugging tool for "it works on my machine" problems.

## 4. lsof — List Open Files

\`\`\`bash
# What files does a process have open?
lsof -p <PID>

# What process is using port 80?
lsof -i :80

# All network connections for a user
lsof -i -u nginx

# Find deleted files still held open (disk space mystery)
lsof +L1
\`\`\`

**Why it matters:** On Linux, "everything is a file" — sockets, pipes, devices. \`lsof\` reveals the invisible connections between processes and resources.

## 5. dmesg — Kernel Messages

\`\`\`bash
# Last 50 kernel messages
dmesg | tail -50

# Watch for OOM kills
dmesg | grep -i "oom\\|killed"

# Hardware errors
dmesg | grep -i "error\\|fail"

# Follow in real-time
dmesg -w
\`\`\`

**Why it matters:** When processes mysteriously die, it's often the OOM killer. When disks fail, \`dmesg\` has the first report. It's the kernel's voice.

## Bonus: Combining Them

Real debugging chains these together:

\`\`\`bash
# 1. Check if service is running and listening
systemctl status myapp && ss -tlnp | grep 8080

# 2. If not listening, check logs
journalctl -u myapp --no-pager -n 50

# 3. If logs are unhelpful, trace the process
strace -p $(pgrep myapp) -e trace=network

# 4. Check for resource issues
dmesg | tail -20 && lsof -p $(pgrep myapp) | wc -l
\`\`\`

Practice these commands daily on FixitLab scenarios and they'll become second nature.
    `,
  },
  'building-fixitlab-architecture': {
    title: 'How We Built FixitLab: Architecture Deep Dive',
    category: 'Engineering',
    author: 'Thirupathi P.',
    date: 'March 15, 2026',
    readTime: '12 min read',
    color: 'accent-cyan',
    content: `
## The Challenge

FixitLab needs to:
1. Provision isolated, broken Linux environments in seconds
2. Give users a real terminal (not a fake shell)
3. Automatically validate whether the user fixed the problem
4. Handle 1,000+ concurrent labs safely
5. Keep costs under control

Let's walk through how each piece works.

## Architecture Overview

\`\`\`
                    ┌─────────────┐
                    │   Nginx     │
                    │  (Gateway)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴────┐ ┌────┴─────┐
        │  Frontend  │ │ Django │ │ WebSocket│
        │  (React)   │ │  API   │ │ (Daphne) │
        └───────────┘ └───┬────┘ └────┬─────┘
                          │            │
              ┌───────────┼────────────┼──────┐
              │           │            │      │
        ┌─────┴─┐   ┌────┴───┐  ┌────┴──┐  ┌┴──────┐
        │Postgres│   │ Redis  │  │Celery │  │Docker │
        │       │   │        │  │Beat   │  │Engine │
        └───────┘   └────────┘  └───────┘  └───────┘
\`\`\`

## Backend: Django + DRF

We chose Django for several reasons:
- **ORM** — Complex queries across scenarios, progress, billing, and leaderboards
- **DRF** — Mature, well-documented REST API framework
- **Admin panel** — Instant CRUD UI for content management
- **Ecosystem** — django-channels, celery integration, JWT auth

The backend runs via **Daphne** (ASGI) so we can handle both HTTP and WebSocket connections on the same server.

## Real-Time Terminal: WebSockets + Docker Exec

When a user starts a lab:

1. Backend creates a Docker container from the scenario image
2. Frontend opens a WebSocket connection to \`/ws/terminal/{session_id}/\`
3. Backend runs \`docker exec -it {container} /bin/bash\` and pipes stdin/stdout over the WebSocket
4. User types commands in xterm.js → backend sends to container → output streams back

This gives users a **real** terminal, not a fake shell. They can run any command, install packages, edit files with vim.

## Scenario Validation

Each scenario defines validation checks in its metadata:

\`\`\`python
validation_checks = [
    {"type": "command", "command": "systemctl is-active nginx", "expected": "active"},
    {"type": "http", "url": "http://localhost", "expected_status": 200},
    {"type": "file_contains", "path": "/etc/nginx/nginx.conf", "contains": "proxy_pass"},
]
\`\`\`

When the user clicks "Validate," we run each check inside the container and calculate a score based on how many pass.

## Celery: Background Tasks

- **Lab cleanup** — Every 5 minutes, find expired sessions and terminate containers
- **Leaderboard** — Recalculated hourly from progress data
- **Notifications** — Email and in-app via async tasks
- **Container orphan cleanup** — Safety net for leaked resources

## Frontend: React + Zustand

The frontend is a React SPA with:
- **Zustand** for state management (auth, theme)
- **TailwindCSS** for styling (custom dark theme)
- **xterm.js** for the terminal emulator
- **React Router v6** with lazy loading for code splitting

## Scaling to 10,000+ Users

- **PostgreSQL** with connection pooling (CONN_MAX_AGE)
- **Redis** caching on hot endpoints (stats, technologies)
- **Kubernetes** deployment with HPA for autoscaling
- **Per-session Docker networks** for lab isolation
- **Rate limiting** on lab starts (5/min per user)

## What We Learned

1. **Docker socket access is powerful but dangerous** — We run the backend in a privileged container, which is a security concern. Firecracker microVMs are the future.
2. **WebSocket connections are expensive** — Each active terminal holds an open connection. We cap concurrent labs per user.
3. **Validation is the hardest part** — Checking if a user "fixed" something requires understanding what "fixed" means for each scenario.
4. **Content is king** — The platform is only as good as its scenarios. We invest heavily in realistic, well-tested challenges.
    `,
  },
  'dns-troubleshooting-guide': {
    title: 'DNS Resolution Failures: A Complete Troubleshooting Playbook',
    category: 'Networking',
    author: 'Content Team',
    date: 'March 10, 2026',
    readTime: '9 min read',
    color: 'accent-green',
    content: `
## DNS: The #1 Cause of Outages

"It's always DNS." This meme exists for a reason. DNS failures cause more outages than any other single component because *everything* depends on name resolution.

## The Resolution Chain

When your app tries to connect to \`api.example.com\`:

1. **Application** calls \`getaddrinfo()\`
2. **libc** checks \`/etc/nsswitch.conf\` for resolution order
3. **Local resolver** checks \`/etc/hosts\` first (if configured)
4. **Stub resolver** reads \`/etc/resolv.conf\` for nameserver IPs
5. **Recursive resolver** (e.g., 8.8.8.8) queries the DNS hierarchy
6. **Authoritative nameserver** returns the final answer

A failure anywhere in this chain = "DNS is broken."

## Step 1: Check /etc/resolv.conf

\`\`\`bash
cat /etc/resolv.conf
\`\`\`

Look for:
- **Missing \`nameserver\`** — No resolver configured
- **Wrong IP** — Pointing to a non-existent server
- **\`search\` domain issues** — Wrong domain appended to short names

**Common fix:**
\`\`\`bash
echo "nameserver 8.8.8.8" > /etc/resolv.conf
\`\`\`

## Step 2: Test with dig

\`\`\`bash
# Query default resolver
dig example.com

# Query a specific resolver
dig @8.8.8.8 example.com

# Get just the answer
dig +short example.com

# Trace the full resolution path
dig +trace example.com
\`\`\`

If \`dig @8.8.8.8\` works but \`dig\` alone doesn't, your local resolver is misconfigured.

## Step 3: Check /etc/nsswitch.conf

\`\`\`bash
grep hosts /etc/nsswitch.conf
\`\`\`

Expected: \`hosts: files dns\`

If \`dns\` is missing, the system won't use DNS at all — only \`/etc/hosts\`.

## Step 4: Test Connectivity to Resolver

\`\`\`bash
# Can you reach the DNS server?
ping -c 3 8.8.8.8

# Is port 53 open?
nc -zv 8.8.8.8 53

# Is it a firewall issue?
iptables -L -n | grep 53
\`\`\`

## Step 5: Check for systemd-resolved

Modern Ubuntu uses a local resolver stub:

\`\`\`bash
systemctl status systemd-resolved
resolvectl status
\`\`\`

If \`/etc/resolv.conf\` points to \`127.0.0.53\`, that's the systemd-resolved stub. Check its upstream configuration.

## Common DNS Failures & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| \`NXDOMAIN\` | Domain doesn't exist | Check spelling, check if domain expired |
| \`SERVFAIL\` | Resolver can't reach authoritative NS | Check firewall, try different resolver |
| \`connection timed out\` | Can't reach resolver | Check /etc/resolv.conf nameserver |
| \`Temporary failure\` | nsswitch misconfigured | Add \`dns\` to nsswitch.conf hosts line |
| Works with IP, fails with name | DNS broken, network is fine | Focus on resolver chain |

## The Docker DNS Trap

Inside Docker containers, DNS is configured differently:
- Docker sets \`/etc/resolv.conf\` to point to Docker's embedded DNS (127.0.0.11)
- Container-to-container resolution uses Docker's internal DNS
- External resolution is forwarded to the host's DNS

If DNS fails inside a container, check both Docker's DNS and the host's DNS.

## Practice

Our **DNS Resolution Broken** scenario gives you a server where DNS is broken in three different ways. Can you restore full name resolution in under 10 minutes?
    `,
  },
  'kubernetes-crashloop-debugging': {
    title: 'Kubernetes CrashLoopBackOff: A Practical Debug Checklist',
    category: 'Kubernetes',
    author: 'Platform Team',
    date: 'March 20, 2026',
    readTime: '7 min read',
    color: 'accent-purple',
    content: `
## What CrashLoopBackOff Actually Means

\`CrashLoopBackOff\` is not an error in itself — it's Kubernetes telling you that a container **started, exited, and is being restarted repeatedly**, with an increasing back-off delay (10s, 20s, 40s … capped at 5 minutes). The real failure happened *inside* the container. Your job is to find it.

## Step 1: Describe the Pod

\`\`\`bash
kubectl describe pod <pod-name>
\`\`\`

Scroll to the **Events** section and the **Last State** of the container:

- \`Exit Code 0\` — the process finished and didn't stay running (wrong command / one-shot script)
- \`Exit Code 1\` — generic application error (check logs)
- \`Exit Code 137\` — **OOMKilled** (out of memory) or SIGKILL
- \`Exit Code 139\` — segfault (SIGSEGV)
- \`Reason: Error\` with no logs — often a bad image entrypoint

## Step 2: Read the Logs (Including the Previous Container)

\`\`\`bash
kubectl logs <pod-name>
kubectl logs <pod-name> --previous   # the crashed instance, not the restarting one
\`\`\`

The \`--previous\` flag is the single most-missed trick. The *current* container may be too young to log anything useful; the *previous* one holds the stack trace.

## Step 3: Work the Usual Suspects

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Exit 137, terse logs | Memory limit too low | Raise \`resources.limits.memory\` |
| "connection refused" to a dependency | DB / service not ready | Add readiness probe or init container |
| "no such file or directory" | Wrong \`command\`/\`args\` or missing binary | Fix the entrypoint or image |
| Config / secret key errors | Missing env var, ConfigMap, or Secret | Mount it; check \`envFrom\` |
| Permission denied on a path | Wrong \`securityContext\` / read-only FS | Set \`runAsUser\` / fix volume perms |

## Step 4: Probes That Kill Healthy Pods

A liveness probe that is too aggressive will restart a perfectly fine container before it finishes booting:

\`\`\`yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30   # give slow apps time to start
  periodSeconds: 10
  failureThreshold: 3
\`\`\`

If your app needs 25 seconds to warm up but \`initialDelaySeconds\` is 5, Kubernetes "helpfully" kills it forever. Use a **startupProbe** for slow starters.

## Step 5: Inspect Inside the Container

If logs are empty, override the entrypoint and look around:

\`\`\`bash
kubectl run debug --rm -it --image=<same-image> --command -- sh
kubectl debug <pod-name> -it --image=busybox --target=<container>
\`\`\`

## The Fast Triage Loop

1. \`kubectl get pods\` — confirm the state and restart count
2. \`kubectl describe pod\` — read Events + Last State exit code
3. \`kubectl logs --previous\` — get the real error
4. Form a hypothesis (memory, config, dependency, probe)
5. Patch the manifest, \`kubectl apply\`, watch \`kubectl get pods -w\`

## Practice

Our **CrashLoopBackOff** scenario drops you into a cluster with a pod that won't stay up. Use the checklist above and get it to \`Running\` before the timer expires.
    `,
  },
  'teams-coupons-and-security': {
    title: "Teams, Coupons, and Platform Security — What's New",
    category: 'Product',
    author: 'Platform Team',
    date: 'June 5, 2026',
    readTime: '4 min read',
    color: 'accent-green',
    content: `
## A Bigger Release Than Usual

This update rounds out FixitLab for **teams and organizations** while tightening platform security across the board. Here is everything that shipped.

## Teams & Enterprise Seats

Organizations can now manage learning at scale from the **Team dashboard**:

- **Email invites** with pending-invite tracking and one-click member removal
- **Per-member analytics** — scenarios attempted, completion rate, and time spent in labs
- **Seat-based billing** so you only pay for active members
- Org-level visibility into progress across Linux, Docker, Kubernetes, cloud, and more

Hiring managers can assign scenarios for interview prep and review completion data without leaving the platform.

## Coupon Codes at Checkout

Both **technology subscriptions** and **AI Interview Studio** plans now accept promo codes:

- Apply a coupon directly in the cart before paying
- Live discount preview shows your savings before you confirm
- Admins create and manage codes (percentage or fixed amount, with expiry and usage caps) from the admin panel

## Admin Security Dashboards

Operators get production-grade tooling:

- **Audit logs** for sensitive actions (subscription grants, role changes, content edits)
- **Rate limiting** on auth and API endpoints to blunt abuse and credential stuffing
- A **security dashboard** summarizing recent events, failed logins, and gateway status

## Community Threads with Screenshots

The community got more useful for real troubleshooting:

- **Attach screenshots** of error output and terminal state to any thread
- Upvote solutions and react to helpful answers
- Threads stay tied to the scenario and technology they belong to, so context travels with the discussion

## Smaller Improvements

- Clearer billing and Jira notifications in the in-app notification center
- Safe fallbacks across public pages so marketing and docs always render, even during maintenance
- Polish across light and dark themes

## Try It

Invite your team from the Team page, grab a coupon, and start assigning labs. As always — break things, fix them, get hired.
    `,
  },
}

export default function BlogPost() {
  const { slug } = useParams()
  const [post, setPost] = useState(blogContent[slug] || null)
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(true)

  usePageTitle(
    post?.title,
    post?.excerpt || post?.subtitle,
    post ? { canonical: `${typeof window !== 'undefined' ? window.location.origin : ''}/blog/${slug}` } : undefined,
  )

  useEffect(() => {
    setLoading(true)
    api.get(`/blog/${slug}/`, { silentError: true })
      .then(res => {
        const apiPost = res.data
        const rich = blogContent[slug]
        setPost({
          ...apiPost,
          content: (rich?.content && (!apiPost.content || apiPost.content.length < 200))
            ? rich.content
            : (apiPost.content || rich?.content || ''),
          color: rich?.color || 'accent-cyan',
        })
      })
      .catch(() => setPost(blogContent[slug] || null))
      .finally(() => setLoading(false))
  }, [slug])

  useEffect(() => {
    api.get('/blog/', { silentError: true })
      .then(res => {
        const list = (res.data || []).filter(p => p.slug !== slug).slice(0, 3)
        setRelated(list)
      })
      .catch(() => {
        setRelated(
          Object.entries(blogContent)
            .filter(([s]) => s !== slug)
            .slice(0, 3)
            .map(([s, p]) => ({ slug: s, title: p.title, category: p.category, readTime: p.readTime }))
        )
      })
  }, [slug])

  if (loading) {
    return (
      <MarketingPageShell narrow>
        <div className="flex items-center justify-center py-24">
          <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
        </div>
      </MarketingPageShell>
    )
  }

  if (!post) {
    return (
      <MarketingPageShell narrow>
        <div className="py-12 text-center">
          <h1 className="text-3xl font-bold text-white mb-4">Post Not Found</h1>
          <p className="text-surface-400 mb-6">The blog post you&apos;re looking for doesn&apos;t exist.</p>
          <Link to="/blog" className="btn-primary px-6 py-2 inline-flex items-center gap-2">
            <ArrowLeft size={16} /> Back to Blog
          </Link>
        </div>
      </MarketingPageShell>
    )
  }

  // Simple markdown-like rendering
  const renderContent = (text) => {
    const lines = text.trim().split('\n')
    const elements = []
    let inCodeBlock = false
    let codeLines = []
    let codeLang = ''
    let inTable = false
    let tableRows = []

    const processInline = (text) => {
      // Bold
      text = text.replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      // Italic
      text = text.replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Inline code
      text = text.replace(/`([^`]+)`/g, '<code class="bg-surface-800 text-accent-cyan px-1.5 py-0.5 rounded text-sm font-mono">$1</code>')

      return DOMPurify.sanitize(text, {
        ALLOWED_TAGS: ['strong', 'em', 'code', 'br', 'span'],
        ALLOWED_ATTR: ['class'],
        ALLOW_DATA_ATTR: false,
        FORCE_BODY: true,
      })
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]

      // Code blocks
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          elements.push(
            <div key={`code-${i}`} className="my-4">
              <pre className="bg-surface-900 border border-surface-700/50 rounded-lg p-4 overflow-x-auto">
                <code className="text-sm text-surface-300 font-mono whitespace-pre">
                  {codeLines.join('\n')}
                </code>
              </pre>
            </div>
          )
          codeLines = []
          inCodeBlock = false
        } else {
          codeLang = line.slice(3)
          inCodeBlock = true
        }
        continue
      }

      if (inCodeBlock) {
        codeLines.push(line)
        continue
      }

      // Table rows
      if (line.startsWith('|')) {
        if (!inTable) inTable = true
        // Skip separator rows
        if (line.match(/^\|[\s-|]+\|$/)) continue
        const cells = line.split('|').filter(c => c.trim()).map(c => c.trim())
        tableRows.push(cells)
        continue
      } else if (inTable) {
        // End table
        elements.push(
          <div key={`table-${i}`} className="my-4 overflow-x-auto">
            <table className="w-full text-sm border border-surface-700/50 rounded-lg overflow-hidden">
              <thead>
                <tr className="bg-surface-800/50">
                  {tableRows[0]?.map((cell, ci) => (
                    <th key={ci} className="px-3 py-2 text-left text-surface-300 font-medium border-b border-surface-700/50">{cell}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.slice(1).map((row, ri) => (
                  <tr key={ri} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-2 text-surface-400" dangerouslySetInnerHTML={{ __html: processInline(cell) }} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
        tableRows = []
        inTable = false
      }

      // Empty line
      if (line.trim() === '') continue

      // Headings
      if (line.startsWith('## ')) {
        elements.push(
          <h2 key={`h2-${i}`} className="text-xl font-bold text-white mt-8 mb-3">
            {line.slice(3)}
          </h2>
        )
        continue
      }
      if (line.startsWith('### ')) {
        elements.push(
          <h3 key={`h3-${i}`} className="text-lg font-semibold text-white mt-6 mb-2">
            {line.slice(4)}
          </h3>
        )
        continue
      }

      // List items
      if (line.startsWith('- ')) {
        elements.push(
          <li key={`li-${i}`} className="flex items-start gap-2 text-surface-300 ml-4 mb-1.5">
            <ChevronRight size={14} className="text-accent-cyan mt-0.5 shrink-0" />
            <span dangerouslySetInnerHTML={{ __html: processInline(line.slice(2)) }} />
          </li>
        )
        continue
      }
      // Numbered lists
      if (line.match(/^\d+\.\s/)) {
        const content = line.replace(/^\d+\.\s/, '')
        elements.push(
          <li key={`ol-${i}`} className="flex items-start gap-2 text-surface-300 ml-4 mb-1.5">
            <span className="text-accent-cyan font-bold text-sm mt-0.5 shrink-0">{line.match(/^(\d+)/)[1]}.</span>
            <span dangerouslySetInnerHTML={{ __html: processInline(content) }} />
          </li>
        )
        continue
      }

      // Regular paragraph
      elements.push(
        <p key={`p-${i}`} className="text-surface-300 leading-relaxed mb-3" dangerouslySetInnerHTML={{ __html: processInline(line) }} />
      )
    }

    // Flush remaining table
    if (inTable && tableRows.length > 0) {
      elements.push(
        <div key="table-end" className="my-4 overflow-x-auto">
          <table className="w-full text-sm border border-surface-700/50 rounded-lg overflow-hidden">
            <thead>
              <tr className="bg-surface-800/50">
                {tableRows[0]?.map((cell, ci) => (
                  <th key={ci} className="px-3 py-2 text-left text-surface-300 font-medium border-b border-surface-700/50">{cell}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(1).map((row, ri) => (
                <tr key={ri} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-3 py-2 text-surface-400" dangerouslySetInnerHTML={{ __html: processInline(cell) }} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    return elements
  }

  // Find related posts from API (fallback: static catalog)
  const relatedPosts = related

  return (
    <MarketingPageShell narrow>
      <article>
        <Link to="/blog" className="inline-flex items-center gap-2 text-sm text-surface-400 hover:text-white transition-colors mb-8">
          <ArrowLeft size={14} /> Back to Blog
        </Link>

        <header className="mb-8">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <span className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded border ${getCategoryClass(post.category)}`}>
              <Tag size={10} className="inline mr-1" />{post.category}
            </span>
            <span className="text-xs text-surface-500 flex items-center gap-1"><Clock size={10} />{post.readTime}</span>
          </div>
          <h1 className="text-3xl lg:text-4xl font-extrabold text-white mb-4 leading-tight">
            {post.title}
          </h1>
          <div className="flex items-center gap-4 text-sm text-surface-400">
            <span className="flex items-center gap-1.5"><User size={14} /> {post.author}</span>
            <span className="flex items-center gap-1.5"><Calendar size={14} /> {post.date}</span>
          </div>
        </header>

        <FixitPanel padding="p-6 md:p-8" className="mb-8">
          <div className="prose-dark">
            {renderContent(post.content)}
          </div>
        </FixitPanel>

        <FixitPanel hero padding="p-8" className="text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 to-accent-purple/5" />
          <div className="relative">
            <h3 className="text-xl font-bold text-white mb-2">Ready to Practice?</h3>
            <p className="text-surface-400 text-sm mb-4">Stop reading, start doing. Real environments, real challenges.</p>
            <Link to="/register" className="btn-primary px-8 py-3 text-sm inline-block">Start Free &rarr;</Link>
          </div>
        </FixitPanel>

        {relatedPosts.length > 0 && (
          <div className="mt-12">
            <h3 className="text-lg font-semibold text-white mb-4">More Articles</h3>
            <div className="grid sm:grid-cols-3 gap-4">
              {relatedPosts.map(p => (
                <Link key={p.slug} to={`/blog/${p.slug}`} className="group">
                  <FixitPanel padding="p-4" className="h-full hover:border-accent-cyan/25 transition-colors">
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${getCategoryClass(p.category)}`}>
                      {p.category}
                    </span>
                    <h4 className="text-sm font-medium text-white mt-2 group-hover:text-accent-cyan transition-colors leading-snug">
                      {p.title}
                    </h4>
                    <span className="text-xs text-surface-500 mt-2 block">{p.readTime}</span>
                  </FixitPanel>
                </Link>
              ))}
            </div>
          </div>
        )}
      </article>
    </MarketingPageShell>
  )
}
