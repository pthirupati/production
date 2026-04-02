# FixitLab — Scalability Architecture (10 Lakh+ Users)

## Overview

This document details how FixitLab scales to support **10 lakh (1,000,000+) registered users** with tens of thousands of concurrent lab sessions.

---

## Architecture Summary

```
Users → CloudFront CDN → ALB (Ingress)
                            ├── Frontend Pods (3-30 replicas)
                            ├── Backend Pods (5-200 replicas, Daphne ASGI)
                            │     ├── REST API (HTTP)
                            │     └── WebSocket Terminal (/ws/)
                            ├── Celery Workers (3-100 replicas)
                            └── Celery Beat (1 replica)
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
  Aurora PostgreSQL           ElastiCache Redis           RabbitMQ Cluster
  (2+ instances,              (2 nodes, failover)        (3 nodes, quorum)
   read replicas)
        │
        ▼
  Lab Runner Nodes (5-200 m5.2xlarge SPOT)
  Each node runs ~60 Docker containers (512MB each)
  Per-session network isolation
```

---

## Tier Breakdown

### Tier 1: Static Assets (Frontend)
- **CloudFront CDN** serves all static assets (JS, CSS, images)
- React SPA is built at deploy time → pure static files
- **Cache hit ratio**: >99% for all /assets/**
- **Zero backend load** for page loads

### Tier 2: API Layer (Backend)
| Metric | Development | Production (10L users) |
|--------|-------------|----------------------|
| Backend replicas | 1 | 5-200 (HPA) |
| Celery workers | 1 | 3-100 (HPA) |
| Requests/sec | <10 | 50,000+ |
| WebSocket connections | <50 | 50,000+ |

**Key optimizations implemented:**
1. **Redis caching** — Technologies, categories, tags, leaderboard, platform stats cached (60s-300s TTL)
2. **Connection pooling** — Django 5.1 native pool + `CONN_MAX_AGE=60` + `CONN_HEALTH_CHECKS=True`
3. **Rate throttling** — lab_start: 5/min, auth: 10/min, user: 1000/hr, anon: 100/hr
4. **Race condition protection** — `select_for_update()` on lab session creation
5. **HPA with rapid scale-up** — 10 pods added per 60s when CPU >60%

### Tier 3: Database
- **Aurora PostgreSQL** — 2 instances + auto-scaling read replicas
- **Connection pooling** — Django native pool reduces connection overhead
- **Key indexes** on: user_id, scenario_id, session status, timestamps
- **Estimated capacity**: 100K+ concurrent connections with pgbouncer

### Tier 4: Lab Infrastructure (Docker Containers)
This is the most resource-intensive tier.

| Metric | Per Container | Per Node (m5.2xlarge) | Cluster (200 nodes) |
|--------|---------------|----------------------|---------------------|
| RAM | 512MB | 32GB → ~60 containers | 12,000 containers |
| CPU | 1 core | 8 cores → ~8 containers | 1,600 containers |
| Effective limit | - | **~8 containers**/node | **~1,600 containers** |

**Realistic capacity**: With CPU as bottleneck (not RAM), 200 nodes support ~1,600 concurrent labs. For 10L registered users at 1% concurrent = 10,000 labs → requires ~1,250 lab runner nodes.

**Scaling strategies:**
1. **Right-size containers** — Reduce CPU limit to 0.5 for simple scenarios → 16 containers/node
2. **Spot instances** — Lab runners use SPOT for 60-70% cost reduction
3. **Auto-scaling** — Kubernetes Cluster Autoscaler provisions new nodes in 2-3 minutes
4. **Session timeouts** — Labs auto-terminate after time_limit (default 30-60 min)
5. **Queuing** — When at capacity, queue lab requests with estimated wait time

---

## Network Isolation Architecture

### Per-Session Networks (Implemented)
Every lab session creates its own Docker bridge network:

```
Session A: fixitlab_net_{uuid_a}  →  Container A (192.168.x.2)
Session B: fixitlab_net_{uuid_b}  →  Container B (192.168.y.2)
```

- Containers on different networks **cannot communicate**
- `internal=True` — no external internet access from labs
- Networks labeled with session_id for cleanup
- Cleanup: network removed with container on stop/expire

### Security Hardening
- `cap_drop=ALL` + selective `cap_add` (NET_BIND_SERVICE, SYS_PTRACE, DAC_OVERRIDE)
- Memory limit: 512MB
- CPU limit: 1 core
- PID limit: 256
- Non-privileged mode
- Auto-remove on stop

---

## WebSocket Scaling

Terminal sessions use WebSocket connections (`/ws/terminal/{session_id}/`).

### Challenges at Scale
1. **Sticky sessions required** — WebSocket must route to same backend pod
2. **Connection limits** — Each Daphne worker handles ~1000 concurrent WebSockets
3. **Memory per connection** — ~5KB per idle WebSocket, ~50KB active

### Solutions (Implemented)
- **Cookie-based session affinity** in K8s Ingress (`fixitlab-affinity` cookie)
- **Redis channel layer** for Django Channels (pub/sub for cross-pod messaging)
- **HPA scales backend pods** — at 200 pods × 1000 WS = 200K concurrent terminals

---

## Caching Strategy

| Cache Key | TTL | Purpose |
|-----------|-----|---------|
| `technologies_list` | 300s | Technology catalog (rarely changes) |
| `categories_list` | 300s | Scenario categories |
| `tags_list` | 300s | Tags with counts |
| `platform_stats` | 120s | Landing page stats (expensive aggregation) |
| `leaderboard_{tech_id}` | 60s | Leaderboard results |

**Cache invalidation**: Automatic via TTL expiry. Admin changes to scenarios/technologies reflect within 5 minutes.

---

## Cost Estimation (AWS, us-east-1)

| Component | Instance | Count | Monthly Cost |
|-----------|----------|-------|-------------|
| EKS Control Plane | - | 1 | $73 |
| App nodes (m5.xlarge) | ON_DEMAND | 5-50 | $350-$3,500 |
| Lab runners (m5.2xlarge) | SPOT (~30%) | 10-200 | $300-$6,000 |
| Aurora PostgreSQL (r6g.large) | - | 2 | $420 |
| ElastiCache Redis (r6g.large) | - | 2 | $340 |
| CloudFront | - | - | $100-$500 |
| ALB | - | 1 | $25 + data |
| **Total (steady state)** | | | **~$1,600-$11,000/mo** |

---

## Monitoring & Alerts

### Key Metrics to Watch
1. **Lab provisioning time** — P99 should be <10s
2. **WebSocket connection count** — Alert at 80% capacity
3. **Database connection pool** — Alert when pool exhausted
4. **Container density per node** — Alert when >80% RAM used
5. **Error rate** — Alert on >1% 5xx responses
6. **Lab queue depth** — Alert when users are waiting

### Recommended Stack
- **Prometheus + Grafana** — Metrics and dashboards
- **Loki** — Log aggregation
- **Jaeger** — Distributed tracing for API latency
- **PagerDuty/OpsGenie** — Alert routing

---

## Deployment Checklist for 10L Scale

- [ ] Deploy Aurora PostgreSQL with at least 2 read replicas
- [ ] Configure ElastiCache Redis cluster mode (3 shards × 2 replicas)
- [ ] Set up RabbitMQ cluster (3 nodes, quorum queues)
- [ ] Enable Cluster Autoscaler for EKS
- [ ] Configure Karpenter for faster node provisioning (30s vs 3min)
- [ ] Set up PodDisruptionBudgets for zero-downtime deployments
- [ ] Enable connection pooling (pgbouncer in sidecar mode)
- [ ] Pre-pull scenario images on lab runner nodes (DaemonSet)
- [ ] Set up CloudFront with S3 origin for static assets
- [ ] Configure WAF rules for DDoS protection
- [ ] Load test with k6/Locust before launch
- [ ] Set up Prometheus + Grafana monitoring
- [ ] Configure PagerDuty alerts for key metrics
