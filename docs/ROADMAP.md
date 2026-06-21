# FixitLab — Master Roadmap (phased, nothing-missed)

Single source of truth for everything requested. FREE-only constraint applies to all
AI/voice/interview features (no paid/OpenAI APIs — browser-native or local/rule-based).
Everything ships via git + GitHub Actions (no manual server edits).

Legend: ✅ done · 🟡 partial · ⬜ not started

---
## DONE this program (deployed / in the live 4-droplet cluster)
- ✅ 4-droplet cluster deploy end-to-end (create→bootstrap→vault→deploy→health→email→cleanup green)
- ✅ Public pages populate (pricing/blog/about/contact/FAQ) — `useRevealOnScroll`
- ✅ Admin: 4-server monitoring, all 12 system containers, Vault health network-aware
- ✅ Login throttle → per-(IP+email), failures-only (no false lockouts)  *(E2E still red — see P1)*
- ✅ Unit-test memory: 4GB swap on all nodes + run tests in one-off container *(E2E still red — see P1)*
- ✅ VMware console: login-by-default (boot only on real reboot); stateful `yum`→`rpm`/`dpkg`; SSH opens full console-style terminal (min/max)
- ✅ Lab: coding IDE renders; terminal backspace + CRLF output; full-screen toggle + restore; complete→same technology; in-technology scenario nav
- ✅ Interviews "Server error" 500s fixed (free engine); "Ask AI" works in all labs (`/api/labs/<id>/ai-hint/`)
- ✅ Teams: self-service create + invite with subscription gating
- ✅ Django secret-key charset (no `$`) — fixed compose `eg6` warnings/corruption
- ✅ seed_admin_demo IntegrityError; slug max_length 50→255

---
## PHASE 1 — Stabilize CI to fully green  (in progress)
- ⬜ **Unit tests (D2)**: now runs `run --rm --no-deps` (no OOM) but exits 1 — capture the real failure (actual test failure vs `run` needing image). Fix root cause.
- ⬜ **E2E-API login** ("Interview admin login", "Concurrent logins 0/5"): throttle fix deployed but still 0/5 → suspect **single-session SessionTracker** invalidating concurrent same-user sessions, and/or rotated admin password mismatch in the E2E. Make concurrent logins return valid usable tokens (allow N sessions for the test path, or relax single-session for concurrent issuance).
- ⬜ **E2E-labs**: confirm `E2E_MAX_PER_TECH=3` finishes within 40m now; if still long, lower or raise timeout.
- ⬜ **Login to all servers from edge, read every container's logs**, fix anything unhealthy. (add a CI step that dumps `docker logs` per node.)

## PHASE 2 — Interview Bot, full human-like vision  (flagship; FREE/no paid API)
- ⬜ Pre-interview setup: resume upload + parse + score + improvement tips; inputs (primary tech, level, other techs, years, current company, package); instructions screen
- ⬜ Calling screen UI: candidate video+mic required; bot mic-only (speaks/listens); voice selection + voice-change option (browser TTS voices)
- ⬜ Realtime voice loop: free local STT (Vosk/whisper.cpp self-hosted) + browser SpeechSynthesis; barge-in; low latency
- ⬜ Conversational engine (rule-based + local model, self-trainable): natural, human-like, casual/fun, follow-up on the candidate's own answers, start discussions, never robotic "good answer"
- ⬜ Adaptive difficulty: after ~5 good answers → harder/trick questions or deep discussion; ramp by experience/level/resume
- ⬜ Question banks per tech incl. scenario-based, troubleshooting, ITIL/SLA, market questions
- ⬜ Practical interview: bot poses a broken-issue; candidate types commands/code in a real lab; bot validates + probes deeper
- ⬜ Rounds: configurable 3–5 (Technical 45m / Techno-managerial 30m / HR 20m); +10m extend option; skip on silence/lag to cover everything in time
- ⬜ Anti-cheat: mute/cam-off detection → warn → auto-exit after 5 min (instructed up front)
- ⬜ Per-round feedback + emailed results; pass → unlock next round; schedule next within 48h (email invite + join link)
- ⬜ Certificate after all rounds (LinkedIn/social shareable, verifiable)
- ⬜ Self-training: mine transcripts/scores to tune difficulty + expand question bank (local, no paid API)

## PHASE 3 — ServiceNow / ITSM ticketing simulation
- ⬜ Ticket-type selection per scenario (incident/request/change/problem…)
- ⬜ Multi-team model (e.g. Storage, Backup, Network, App) with queues/assignment groups
- ⬜ Ticket transfer between teams; **sub-ticket** creation with details
- ⬜ Cross-team workflow that mutates sim state: e.g. raise a sub-ticket to Storage → Storage adds a disk → on close the disk becomes visible on the server → candidate continues the parent scenario
- ⬜ SLA timers, work notes, states, close codes — faithful ServiceNow-like mock

## PHASE 4 — Content expansion
- ⬜ More cross-technology questions/scenarios in **all** technologies (e.g. Linux↔VMware, k8s↔Docker, Terraform↔Ansible↔Cloud)
- ⬜ More best phased projects (zero-to-hero) per technology + cross-tech capstones

## PHASE 5 — Docker Hub image pipeline (foundational for k8s)
- ⬜ CI builds `fixitlab/{backend,frontend,gateway}:<git-sha>` + `latest`, pushes to Docker Hub (`DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN`)
- ⬜ Compose + k8s reference pinned image tags; nodes **pull** (no on-node build)
- ⬜ Version history = every commit's image (rollback by tag)

## PHASE 6 — DOKS (managed Kubernetes on DigitalOcean)
- ⬜ `hosting_target=doks`: provision DOKS cluster, registry pull secret, manifests/Helm
- ⬜ Deployments (backend/celery/beat/frontend) + Services + Ingress (TLS) + HPA; Postgres/Redis/RabbitMQ as managed or StatefulSets; Vault
- ⬜ Zero manual steps; **modular monolith + HPA** (NOT microservices — recommended)

## PHASE 7 — AWS provider + EKS
- ⬜ `cloud_provider=aws`: provision VPC + **private subnets** (true private nodes) + EC2 + security groups + ALB — mirror of the DO scripts
- ⬜ `hosting_target=eks`: EKS cluster + same manifests/Helm as DOKS
- ⬜ Scaffolded now (option present), activates when AWS keys are added
- ⬜ This delivers the "3 private + 1 public" request properly (DO can't make private-only droplets; AWS private subnets can)

## PHASE 8 — Vault-only secrets
- ⬜ Only the AppRole bootstrap (`VAULT_ADDR`+`ROLE_ID`+`SECRET_ID`) on nodes; no plaintext `.env` of app secrets
- ⬜ App fetches secrets from Vault at startup (existing `vault_loader`); Vault Agent/init for DB/Redis init-time secrets
- ⬜ Stop emailing credentials; remove local secret copies after seeding

## PHASE 9 — Gaps, security & competitor parity
- ⬜ Implement open items in `docs/GAP_ANALYSIS.md` and `docs/SECURITY_AUDIT.md` (no item skipped)
- ⬜ Containerize the code-exec grader (network-less, read-only, non-root) — SECURITY_AUDIT C-01
- ⬜ Competitor-feature sweep (KodeKloud/Whizlabs/ACG/iLabs/HackerRank): add what's missing → "best platform"

## PHASE 10 — Test/maintenance ergonomics + sim depth
- ⬜ Split `e2e_all_scenarios_labs.py` to run **per technology** (select a tech, run only its scenarios) for fast maintenance after adding one scenario
- ⬜ Deeper Linux distro mocking in VMware/lab sims (services, systemd, networking, users) — full-distribution fidelity

---
### Architecture decisions (recommended)
- **k8s = modular monolith + HPA**, not microservices (low-ops, fits the codebase; sim engines live in the backend).
- **Images via Docker Hub**, pinned by commit SHA, pull-based.
- **Secrets via Vault** as the single source of truth.
- **True private nodes via AWS** (DO assigns a public IP to every droplet; firewall already gates D2/D3/D4).
