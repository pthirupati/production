# FixitLab — Competitive Gap Analysis

_Last updated: 2026-06-20 · Research + analysis deliverable (no application code changed)_

This document benchmarks FixitLab against the leading hands-on lab, coding-practice, and
technical-interview platforms, identifies concrete feature/UX gaps, and proposes a
prioritized, **FREE-first** roadmap (no paid third-party APIs, per the platform's standing
constraint).

Legend used throughout:

- **Impact:** High / Med / Low — expected effect on learner retention, conversion, or differentiation.
- **Effort:** **S** (≤ a few days) · **M** (~1–2 weeks) · **L** (multi-week).
- **Cost tag:** `FREE` (fits the no-paid-API rule) · `needs-paid` (would require a paid API/cloud or violate the constraint).

---

## 1. Executive summary

FixitLab is already unusually broad for a single platform: **1,034 hands-on scenarios across 21
technologies**, fully **in-browser simulations** (a real-VFS RHEL shell with a paced boot sequence,
a deep vSphere/VMware simulator, kubectl/docker engines), a **sandboxed coding IDE** with
**fail-closed grading**, a **free AI interview studio** (rule-based, browser STT/TTS), a Jira-style
ticket workflow with a 32-intent support bot, subscriptions/billing, an admin panel with
Ads/Campaigns, and a Prompt Engineering course. Most competitors specialize in **one** of these
lanes; FixitLab spans all of them at zero marginal API cost, which is its core moat.

The gaps are therefore **not "missing pillars"** — they are **depth, polish, and engagement-loop**
gaps relative to category leaders:

1. **No exam/timed mode + live verification panel.** Killer.sh and SadServers win on the *test-day*
   feeling: a countdown timer, a session you can restart, a "Check My Solution" button that grades
   the live environment, and an answer key on completion. FixitLab grades on submit but lacks the
   timed-exam wrapper and per-step inline verification that defines the CKA/CKAD/SadServers UX.
2. **No guided multi-step "track" structure inside a lab.** Instruqt/Killercoda present a lab as an
   ordered sequence of **challenges with per-step checks and tabs/hotspots** (terminal + editor +
   instructions + web preview). FixitLab has scenarios + progressive hints, but not the
   step→verify→next loop with a side-by-side instructions pane that defines modern guided labs.
3. **Thin engagement loop.** TryHackMe/LeetCode drive daily return visits with **streak calendars,
   daily challenges, XP/levels, badge showcases, weekly contests, and skill trees**. FixitLab has
   streak *achievements* (3/7/30) and a leaderboard, but no visible streak calendar, no daily
   challenge, no XP/level economy, no skill tree.
4. **Cloud + observability + CI/CD simulations are absent.** A Cloud Guru/Whizlabs/KodeKloud lean
   heavily on **AWS/Azure/GCP sandboxes and CI/CD + Prometheus/Grafana playgrounds.** FixitLab has
   a DevOps state engine and an `aws_provisioner` (real-VM oriented) but **no in-browser cloud
   console, no pipeline visualizer, and no metrics/observability sim** — all of which can be faked
   client-side for FREE.
5. **Coding IDE is narrow.** Only **Python + JavaScript** are auto-graded (bash is "needs review").
   No debugger, no autosave/resume, no multi-file projects, no Vim/Emacs keymap, no
   format-on-save. Replit/CodeSignal/LeetCode set the expectation for richer editing.

**Bottom line:** the highest-ROI work is not building new pillars — it is wrapping the *excellent*
simulations FixitLab already has in the **timed-exam + guided-track + daily-engagement** loops that
make competitors sticky, plus adding **client-side cloud/observability/CI-CD sims** that extend the
existing free-simulation moat. Nearly everything below is achievable **FREE**.

---

## 2. Competitor feature matrix

`Y` = strong/first-class · `~` = partial/limited · `–` = absent · `$` = exists but paywalled.

| Feature | FixitLab | KodeKloud | Killer.sh | SadServers | Killercoda | ACG / Pluralsight | Whizlabs | HackerRank | LeetCode | CodeSignal | Replit | Instruqt | TryHackMe / HTB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| In-browser lab terminal | Y | Y | Y | Y | Y | Y | Y | ~ | – | – | Y | Y | Y |
| Auto-graded live env check | ~ (on submit) | Y | Y | Y | Y | Y (Challenge) | Y | Y | Y | Y | – | Y | Y |
| **Timed exam / countdown mode** | – | ~ | **Y** | **Y** | ~ | Y | Y | Y | Y (contests) | Y | – | ~ | ~ |
| **Guided step→verify track** | ~ (hints) | Y | – | – | **Y** | Y | Y | – | – | Y | – | **Y** | Y (rooms) |
| Free open "playground" sandbox | Y (sims) | Y | – | ~ | Y | $ | $ | – | – | ~ | Y | – | ~ |
| Cloud sandbox (AWS/Azure/GCP) | – | Y | – | – | Y | **Y** | **Y** | – | – | – | Y | Y | – |
| CI/CD pipeline sim | – | Y | – | – | ~ | ~ | ~ | – | – | – | ~ | Y | – |
| Observability (Prom/Grafana) sim | – | Y | – | ~ | ~ | ~ | ~ | – | – | – | – | ~ | ~ |
| Coding IDE (multi-language) | ~ (Py/JS) | ~ | – | – | ~ | – | – | Y | Y | Y | **Y** | Y | ~ |
| In-IDE debugger | – | – | – | – | – | – | – | ~ | $ | ~ | Y | – | – |
| Real-time collaboration | – | – | – | – | – | – | – | Y (CodePair) | – | Y | **Y** | ~ | – |
| Autosave / resume code | – | ~ | Y | $ (Pro) | ~ | Y | Y | Y | Y | Y | Y | Y | Y |
| Guided learning paths | ~ | Y | – | – | ~ | **Y** | Y | ~ | ~ | Y | – | Y | **Y** |
| Skill tree / role tracks | – | ~ | – | – | – | Y (role IQ) | ~ | Y (roles) | ~ | Y | – | ~ | Y |
| Skill assessment / Skill-IQ | – | ~ | – | – | – | **Y** | ~ | Y (cert) | – | Y | – | – | ~ |
| Certifications / certs | Y | Y (prep) | – | ~ | – | Y | Y | **Y** | – | Y | – | Y | Y |
| Leaderboards | Y | ~ | – | ~ | – | – | – | Y | Y | Y | – | Y | **Y** |
| **Streak / daily challenge** | ~ (badges) | Y (100-days) | – | – | – | – | – | ~ | **Y** | ~ | – | – | **Y** |
| XP / levels / gamification | ~ | ~ | – | ~ | – | – | – | Y | Y | Y (Arcade) | – | ~ | **Y** |
| Spaced repetition / review | – | – | – | – | – | – | – | – | ~ | Y (Cosmo) | – | – | – |
| Hint economy / penalties | Y | ~ | – | ~ | ~ | ~ | – | – | – | ~ | – | ~ | ~ |
| AI tutor / mentor | ~ (rule-based) | Y (KK AI) | – | – | – | ~ | – | Y (AI Tutor) | ~ | **Y (Cosmo)** | **Y (agent)** | – | ~ (AI hints) |
| AI interview studio | Y (rule-based) | – | – | – | – | – | – | **Y (AI)** | ~ | **Y (AI)** | – | – | – |
| Live coding interview (pair) | – | – | – | – | – | – | – | **Y** | – | Y | Y | – | – |
| Proctoring / plagiarism | – | – | – | – | – | ~ | ~ | **Y** | ~ | Y | – | ~ | – |
| Community / discuss / forums | Y | Y (Discord) | ~ | ~ | Y | ~ | ~ | Y | Y | ~ | Y | – | Y |
| Instructor live progress dashboards | ~ (admin) | ~ | – | Y (Biz) | Y (creators) | Y | Y | Y | – | Y | – | **Y** | Y |

**Reading the matrix:** FixitLab is *competitive or leading* on breadth of simulations, hint
economy, certificates, leaderboards, and (uniquely) a free AI interview studio. It *trails* on the
test-day loop (timed exam + live check), guided multi-step tracks, cloud/CI/observability sims,
IDE depth, and the daily-engagement loop (streak calendar / daily challenge / XP).

---

## 3. Gaps by area

Each row: gap → why it matters (competitor that inspired it) → Impact × Effort × cost tag.

### (a) Scenarios / content

| Gap | Why / inspired by | Impact | Effort | Cost |
|---|---|---|---|---|
| **No AWS/Azure/GCP scenario tracks** | ACG, Whizlabs, KodeKloud center their catalog on cloud certs; FixitLab covers 21 techs but no public-cloud lane. | High | L | `FREE` (sim-backed, see 3b) |
| **Scenarios not bundled into named exam blueprints** (e.g. "CKA-style 17-task set", "RHCSA mock") | Killer.sh ships a single 22/25-task exam set that feels like the real test. FixitLab has the scenarios but no curated, weighted, single-sitting set. | High | M | `FREE` |
| **No "difficulty ladder within a topic"** surfaced to the learner | SadServers easy/medium/hard ranking is front-and-center; FixitLab has difficulty but doesn't present a progression ladder per technology. | Med | S | `FREE` |
| **Sparse coverage in some techs** (java 27, javascript 37, prompt-eng 14 vs linux 131) | Competitors keep ~50+ per major track; uneven depth weakens the "complete path" promise. | Med | M | `FREE` |
| **No community-authored scenarios** | Killercoda's growth engine is creator-authored scenarios (Markdown+Bash+JSON). FixitLab scenarios are first-party only. | Med | L | `FREE` |
| **No "real incident / breach replay" narrative scenarios** | TryHackMe 2026 added real-world breach simulations; story-driven incidents boost engagement vs isolated tasks. | Med | M | `FREE` |
| **No scenario "walkthrough / editorial" after solve** | SadServers answer key + LeetCode editorials are top-rated features; FixitLab has hints but no post-solve canonical writeup/video. | High | M | `FREE` (text/asciinema) |

### (b) Simulations — what to add / improve

The existing free-sim engine (RHEL VFS shell, vSphere, kubectl/docker, DevOps state) is the moat.
These extend it; all are renderable client-side or via mock state for **FREE**.

| Gap | Why / inspired by | Impact | Effort | Cost |
|---|---|---|---|---|
| **In-browser AWS/Azure/GCP console sim** (mock IAM, EC2/S3, VPC, ARM, gcloud CLI) | ACG/Whizlabs/KodeKloud cloud sandboxes are their #1 draw. A faked console + CLI over a JSON state model needs no real cloud account. | High | L | `FREE` |
| **CI/CD pipeline simulator** (visual stages build→test→deploy, editable YAML, simulated logs/failures) | KodeKloud CI/CD Playground, Instruqt pipelines. Pure front-end state machine + log streamer. | High | M | `FREE` |
| **Observability sim: Prometheus + Grafana** (query a canned metrics store, build a panel, set an alert) | A frequently requested DevOps skill; the existing DevOps state engine can emit fake time-series. | High | M | `FREE` |
| **Real-time live metrics in existing sims** (CPU/mem/IO/pod counts ticking during a lab) | SadServers/Instruqt feel "alive"; FixitLab sims are mostly static-state. A client-side ticker over sim state adds realism cheaply. | Med | S–M | `FREE` |
| **Windows guest console** (cmd + PowerShell over a mock filesystem/registry) | Windows has 50 scenarios but no interactive guest console like the RHEL/VMware ones; Whizlabs AZ-104 labs set the bar. | High | L | `FREE` |
| **Deeper Ansible sim** (inventory + playbook run with simulated per-task changed/ok/failed output) | KodeKloud Ansible labs. Extends the existing state engine. | Med | M | `FREE` |
| **Deeper Terraform sim** (plan/apply diff view, state-file inspection, drift detection) | Current Terraform is a state flag (`terraform_fixed`); competitors show real plan/apply diffs. | Med | M | `FREE` |
| **Git/GitHub-flow sim** (branch, merge-conflict resolution, PR review) | Common interview + DevOps skill, no real backend needed (in-memory repo model). | Med | M | `FREE` |
| **Networking packet/topology visualizer** (animate ping/traceroute/ACL drops) | Networking has 50 scenarios but is terminal-only; a topology canvas aids comprehension. | Low–Med | M | `FREE` |
| **Database query console with EXPLAIN/plan visual** | DB has 50 scenarios; a SQL console with a visual query plan beats raw psql output for learning. | Med | M | `FREE` (SQL.js / Pyodide-sqlite) |

### (c) Coding IDE

| Gap | Why / inspired by | Impact | Effort | Cost |
|---|---|---|---|---|
| **Only Python + JS auto-graded** (`SUPPORTED_LANGUAGES = {python, javascript}`) | LeetCode/HackerRank/CodeSignal offer 15–40 languages. Add **bash auto-grade** (already "needs review"), then SQL, then TS-as-JS via the existing sandbox + SQL.js. Compiled langs (Go/Rust/C++) need runtime infra. | High | M | `FREE` (bash/SQL/TS); compiled = infra cost |
| **No debugger / breakpoints / step-through** | Replit + CodeSignal expose stepping; even a Pyodide-based "variable inspector / print-trace at line N" would differentiate. Full breakpoints are L. | Med | M–L | `FREE` (limited) |
| **No autosave / resume of in-progress code** | Replit/LeetCode persist drafts; FixitLab loses work on reload. Save buffer to localStorage + a `CodeDraft` server model. | High | S | `FREE` |
| **No multi-file projects** | Replit/Instruqt IDE support file trees; current IDE is single-buffer. | Med | L | `FREE` |
| **No real-time collaborative editing** | Replit Multiplayer, HackerRank CodePair are signature features — directly relevant to FixitLab's interview studio (live pair round). Yjs/CRDT over WebSocket, no paid API. | High | L | `FREE` (Yjs + WS) |
| **No Vim/Emacs keymap, no format-on-save, no linting** | Power-user table stakes (CodeMirror has `@replit/codemirror-vim`, Prettier in-browser). | Low–Med | S | `FREE` |
| **No "run scratch / REPL" outside graded tasks** | Replit's open scratchpad lowers friction; FixitLab IDE is task-bound only. | Low | S | `FREE` |
| **No diff/test-output panel polish** (expected vs actual, failing-case isolation) | LeetCode shows the first failing testcase with I/O; sharpens the grading UX already present. | Med | S | `FREE` |

### (d) Learning UX

| Gap | Why / inspired by | Impact | Effort | Cost |
|---|---|---|---|---|
| **No guided step→verify lab structure** | Instruqt/Killercoda/KodeKloud: a lab is N ordered challenges, each with its own CHECK and a persistent instructions pane. FixitLab has one task + progressive hints. This is the single biggest UX gap. | High | M | `FREE` |
| **No visible skill tree / role tracks** | ACG role-based paths, TryHackMe paths, CodeSignal tracks. FixitLab has `LearningPathProgress` data but no tree/graph UI with prerequisites and unlocks. | High | M | `FREE` |
| **No timed exam mode + answer key on finish** | Killer.sh/SadServers: countdown, restartable session, "Check My Solution", reveal solutions at end. FixitLab grades but lacks the exam wrapper. | High | M | `FREE` |
| **No skill assessment / placement test (Skill-IQ analog)** | Pluralsight Skill IQ, CodeSignal pre-assessment route learners to the right level. Could reuse the interview scoring engine. | Med | M | `FREE` |
| **No spaced-repetition / review queue** | CodeSignal Cosmo re-checks mastery; SRS (Leitner boxes over solved scenarios) materially improves retention and return visits. | Med | M | `FREE` |
| **Hint economy is per-scenario only, no global budget/credits** | A gamified "hint credits earned by streaks/solves" loop (TryHackMe-style) drives engagement; current penalties are local. | Low–Med | S | `FREE` |
| **No "Challenge Mode"** (hide hints/walkthrough for a verified score) | ACG Challenge Mode produces a trustworthy ability signal; FixitLab interview mode blocks hints but there is no public "challenge score" badge on scenarios. | Med | S | `FREE` |
| **No certification *paths*** (exam → proctor-ish → verifiable cert) tied to tracks | FixitLab has certificates + verify page, but they aren't earned via a structured timed-exam path like ACG/HackerRank. | Med | M | `FREE` |

### (e) Interview studio

The studio is a genuine differentiator (free, browser STT/TTS, persona-driven, scored, with
adaptive difficulty and scorecards). Gaps are depth within the FREE constraint.

| Gap | Why / inspired by | Impact | Effort | Cost |
|---|---|---|---|---|
| **No live *coding* interview round** (candidate solves in the IDE while "interviewer" observes) | HackerRank CodePair, CodeSignal coding interviews. FixitLab IDE + interview engine already exist — wire them together (no paid API). | High | M | `FREE` |
| **No hands-on *lab* interview round** (debug a broken sim live) | Unique angle: most platforms can't do this. FixitLab's sims make a "fix-the-incident interview" feasible. (`services/practical_lab.py` exists — surface it as a round type.) | High | M | `FREE` |
| **Rule-based feedback only; thin rubric breakdown UI** | CodeSignal Cosmo gives structured, dimension-by-dimension feedback. FixitLab scores but the report can expose more (clarity, structure, keyword coverage, pace from STT timing). | Med | S–M | `FREE` |
| **No filler-word / pace / talk-time analytics** | Free to compute from the existing browser STT transcript + timing; adds a "communication" signal without any API. | Med | S | `FREE` |
| **No question bank tagged by company/role archetype** | LeetCode company tags are its top-ROI premium feature; FixitLab can ship role-archetype banks (FAANG-style SRE, startup generalist) for FREE. | Med | M | `FREE` |
| **No mock-interview leaderboard / shareable scorecard** | Drives virality; the certificate/verify infra can be reused. | Low–Med | S | `FREE` |

### (f) Gamification / engagement

| Gap | Why / inspired by | Impact | Effort | Cost |
|---|---|---|---|---|
| **No streak calendar UI / daily challenge** | TryHackMe 30-day streak + LeetCode daily problem are the #1 daily-return drivers. Streak data partly exists (3/7/30 achievements) but isn't visualized, and there's no "today's challenge." | High | S–M | `FREE` |
| **No XP / levels / progress-bar economy** | TryHackMe/LeetCode/CodeSignal Arcade. FixitLab has score + leaderboard but no persistent XP→level identity. | Med | M | `FREE` |
| **Badge set is small + not showcased on profile** | Achievements exist (streak/solve milestones) but there's no badge wall / shareable profile like TryHackMe/HTB. | Med | S | `FREE` |
| **No weekly/biweekly contests** | LeetCode contests + HackerRank hackathons spike engagement. The timed-exam infra (3d) can power a scheduled contest. | Med | M | `FREE` |
| **No seasonal events / challenge campaigns** ("100 Days of DevOps") | KodeKloud community challenges. Could reuse the existing Campaigns admin module for *learning* campaigns, not just ads. | Med | S–M | `FREE` |
| **Leaderboards not segmented** (global only; no per-tech/weekly/friends) | HTB/TryHackMe segment by season, country, team. Model has per-scenario+global; add weekly + per-tech + team scopes. | Low–Med | S | `FREE` |

### (g) Admin / analytics

| Gap | Why / inspired by | Impact | Effort | Cost |
|---|---|---|---|---|
| **No cohort/funnel learning analytics** (start→complete→drop-off per scenario) | Instruqt/Pluralsight instructor dashboards. The admin panel is broad (19 pages) but analytics skew operational/billing, not learning-funnel. | Med | M | `FREE` |
| **No per-scenario quality signals surfaced** (fail rate, avg time, hint-usage, abandon point) | Helps prune/fix weak scenarios; data largely exists in progress/labs tables, needs an admin view. | Med | S–M | `FREE` |
| **No live instructor/proctor view** (watch a session, screen/snippet share) | Instruqt live dashboards; relevant for B2B/teams + interview studio. | Low–Med | L | `FREE` (WS) |
| **No A/B or content experimentation hooks** | Mature platforms iterate on lessons; would let FixitLab measure which guided-track variant converts. | Low | M | `FREE` |
| **Plagiarism/integrity signals for coding submissions** | HackerRank/CodeSignal proctoring. For FREE: paste-burst detection, tab-blur counts, code-similarity hashing across submissions. | Med | M | `FREE` |

### (h) Platform / infra (performance, scale, observability)

| Gap | Why / inspired by | Impact | Effort | Cost |
|---|---|---|---|---|
| **Self-observability of the platform** (RED/USE metrics, Grafana for FixitLab itself) | Sentry is wired, but no metrics/dashboards. Prometheus + Grafana are free/OSS and dogfood the very skills taught. | Med | M | `FREE` |
| **No load/scale test for concurrent live sessions** | Killer.sh/Instruqt provision ephemeral envs at scale; FixitLab sims are client-side (a strength), but the WS terminal + Redis session model are untested under load. | Med | M | `FREE` (k6/Locust) |
| **Frontend bundle / cold-start budget for heavy IDE + sims** | Pyodide + CodeMirror + sim engines are heavy; competitors lazy-load. Audit code-splitting and time-to-interactive. | Med | S–M | `FREE` |
| **No status page / SLO publication** | Trust signal common to paid platforms. | Low | S | `FREE` |
| **E2E coverage gaps noted in project state** (frontend Playwright partial; one interview test flaky) | Quality/regression risk during rapid feature add. | Med | M | `FREE` |

### (i) Security & hardening

Findings below are from reviewing the architecture/state docs and known surfaces; treat them as a
**hardening checklist to validate**, not confirmed live vulnerabilities. (No code was changed.)

| Area | Concern / why | Impact | Effort | Cost |
|---|---|---|---|---|
| **Code-execution sandbox** (`labs/code_exec.py`) | The biggest attack surface — it runs user Python/Node. Confirm: no network egress (it claims none), RLIMIT/cgroups for CPU+mem+pids+wall-clock, no FS escape, temp-dir isolation, and that the **Node path's skipped `RLIMIT_AS`** can't be abused for memory-exhaustion DoS. Consider seccomp/nsjail/firejail for defense-in-depth. | High | M | `FREE` |
| **WebSocket terminal authz** | Ensure per-session ownership checks, idle timeouts, and message-rate limits on the lab terminal so one user can't attach to another's session or flood a worker. | High | S–M | `FREE` |
| **Fail-closed grading integrity** | Project state shows this was recently fixed (no auto-pass). Add regression tests + a periodic audit so a future scenario can't reintroduce a vacuous pass. | High | S | `FREE` |
| **Rate limiting / abuse on auth + OTP + AI-hint + validate endpoints** | NUM_PROXIES fix noted; verify throttles on register/OTP, `ai-hint`, `CodeValidate`, `PromptValidate` to prevent brute-force and compute abuse. | Med | S | `FREE` |
| **Secrets management** | Vault integration exists; verify no secrets committed in `.env`, rotation alerts work, and CI secrets are scoped. | Med | S | `FREE` |
| **Stripe/Razorpay webhook verification** | Confirm signature verification + idempotency on fulfillment webhooks (billing). | High | S | `FREE` |
| **Interview media privacy (GDPR)** | `gdpr_views.py` exists; confirm STT transcript/audio handling, retention, and deletion paths, since camera/mic are used. | Med | S | `FREE` |
| **Standard web hardening** | Verify CSP (esp. with eval-heavy Pyodide/WASM), HSTS, secure cookies, CSRF on state-changing endpoints, and dependency scanning (Dependabot/pip-audit/npm-audit) in CI. | Med | S–M | `FREE` |
| **Multi-tenant org isolation** | With org seats/teams, verify object-level authorization (no IDOR on org analytics, invoices, team data). | Med | M | `FREE` |

---

## 4. Prioritized roadmap — Next 10 highest-ROI improvements

Ranked by (Impact ÷ Effort), FREE-first, leveraging assets FixitLab already has.

| # | Improvement | Why it's high-ROI | Inspired by | Effort | Cost |
|---|---|---|---|---|---|
| 1 | **Guided step→verify lab tracks** (ordered challenges, per-step CHECK, persistent instructions pane beside terminal/IDE) | The single biggest UX gap; converts isolated scenarios into modern guided labs and reuses existing grading. Lifts completion + perceived quality across all 1,034 scenarios at once. | Instruqt, Killercoda, KodeKloud | M | `FREE` |
| 2 | **Timed exam mode + curated exam blueprints + answer key on finish** | Creates the "test-day" loop that makes Killer.sh/SadServers sticky; turns existing scenarios into mock-cert sets (CKA/RHCSA-style). Also powers contests (#9). | Killer.sh, SadServers, ACG Challenge Mode | M | `FREE` |
| 3 | **Daily challenge + streak calendar + XP/levels** | Strongest daily-return driver in the industry; streak data partly exists, just needs a visible loop + scheduler. Cheap, compounding retention. | TryHackMe, LeetCode | S–M | `FREE` |
| 4 | **Skill tree / role tracks UI over existing `LearningPathProgress`** | Gives learners a "where am I / what's next" map with prereqs + unlocks; raises multi-lab engagement and showcases the catalog's breadth. | ACG role paths, TryHackMe paths, CodeSignal | M | `FREE` |
| 5 | **In-browser cloud console sim (start with AWS: IAM/EC2/S3/VPC + CLI)** | Opens the largest content category competitors monetize (cloud certs) with zero cloud spend — a pure client-side mock over JSON state; extends the free-sim moat. | ACG, Whizlabs, KodeKloud | L | `FREE` |
| 6 | **Live coding + hands-on *lab* interview rounds** (wire IDE + sims into the interview studio) | A differentiator no competitor matches for free; both building blocks already exist (`code_exec`, `practical_lab.py`, interview engine). High conversion for the studio. | HackerRank CodePair, CodeSignal | M | `FREE` |
| 7 | **CI/CD pipeline simulator + Prometheus/Grafana observability sim** | Two of the most-requested DevOps skills; both are front-end state machines fed by the existing DevOps state engine. Big content unlock for FREE. | KodeKloud CI/CD Playground, Instruqt | M (each) | `FREE` |
| 8 | **Code IDE depth: autosave/resume + bash & SQL auto-grading + first-failing-test panel** | Removes the "lost my work" friction (autosave is **S**), and bash/SQL grading is low-effort over the existing sandbox/SQL.js — widens the IDE's reach toward HackerRank/LeetCode parity. | Replit, HackerRank, LeetCode | S–M | `FREE` |
| 9 | **Weekly contests + learning campaigns** (reuse Campaigns admin for *learning*, not just ads) | Recurring engagement spikes + virality; built on the timed-exam infra (#2) and the existing leaderboard/Campaigns modules. | LeetCode contests, KodeKloud 100-Days, HackerRank hackathons | M | `FREE` |
| 10 | **Code-execution sandbox + WebSocket terminal security hardening** (+ fail-closed regression tests) | Protects the platform's two riskiest surfaces as usage scales; cheap insurance against DoS/escape and grading-integrity regressions. | HackerRank/CodeSignal integrity posture | S–M | `FREE` |

---

## 5. Quick wins (≤ 1 day each)

All `FREE`. Each is small, self-contained, and improves perceived quality or engagement fast.

1. **Streak calendar widget** on the dashboard/profile from existing streak data (visualize the 3/7/30 logic; show "current streak: N days").
2. **"Today's challenge" surface** — pick one daily scenario (seeded by date) and feature it on Home/Dashboard. (LeetCode-style daily-problem loop.)
3. **Badge wall on the profile** — render existing `UserAchievement`s as a shareable badge grid (TryHackMe/HTB-style identity).
4. **Difficulty ladder on each Technology page** — group scenarios easy→medium→hard so progression is obvious (SadServers-style).
5. **First-failing-testcase panel in the IDE** — surface expected vs actual for the first failed hidden test (LeetCode-style), reusing existing grader output.
6. **Vim keymap + format-on-save toggle** in the CodeMirror IDE (`@replit/codemirror-vim`, in-browser Prettier).
7. **Autosave code to `localStorage`** so a reload doesn't lose work (server-side `CodeDraft` can follow).
8. **Filler-word / talk-time stats in the interview report** computed from the existing STT transcript + timing (no API).
9. **Per-scenario stats chip** (avg solve time, fail rate, hint usage) on scenario cards, from existing progress data — also seeds the admin quality view.
10. **Promote bash to an auto-gradable language** by adding a harness + tests (the sandbox already runs shell; bash currently sits in `NEEDS_REVIEW_LANGUAGES`).
11. **Segment the leaderboard** into Weekly + Per-technology tabs (the model already keys by scenario/global).
12. **Post-solve "editorial" field** on scenarios — render a canonical writeup/answer key after a pass (SadServers/LeetCode), starting with the highest-traffic scenarios.
13. **Status/SLO tile + Sentry release health** on the admin/monitoring page (trust signal; Sentry is already wired).
14. **CI dependency scanning** — enable `pip-audit` + `npm audit`/Dependabot in the existing GitHub Actions (security quick win).

---

## 6. Implementation status

Status of every roadmap item (§4) and quick win (§5) as built in the codebase.
Legend: ✅ **Implemented** · 🟡 **Partial** · ⬜ **Not implemented**. Evidence
points at the files that back each claim. All work below is **FREE** (no paid
API): engagement endpoints reuse existing models, the leaderboard segments an
existing query, the IDE features are client-side, and CI scanning uses
pip-audit / `npm audit`.

### Roadmap (§4) — Next 10 highest-ROI

| # | Improvement | Status | Evidence |
|---|---|---|---|
| 1 | Guided step→verify lab tracks | 🟡 Partial | `LearningPath` carries ordered steps `[{title, scenario_slug, description}]` (`backend/apps/question_bank/models.py`) and there are end-to-end guided **projects** driven by Jira tickets, but there is no in-lab per-step CHECK with a persistent instructions pane beside the terminal yet. |
| 2 | Timed exam mode + blueprints + answer key | ⬜ Not implemented | No `exam_mode` / blueprint model or UI. (Per-scenario `solution_explanation` exists post-solve, but no curated timed exam set.) |
| 3 | Daily challenge + streak calendar + XP/levels | ✅ Implemented | Endpoints `backend/apps/public_api/engagement.py` (`DailyChallengeView`, `StreakView`, `XpView`); XP/streak persisted on completion (`apps/progress/services.py` `compute_level`/`compute_current_streak`, `apps/jira_integration/completion.py`). Frontend: `DailyChallengeCard`, `StreakWidget`, `XpLevelCard` (`frontend/src/components/engagement/`) wired into Dashboard + Profile. |
| 4 | Skill tree / role tracks UI | ⬜ Not implemented | `LearningPathProgress` data exists but no skill-tree/prereq UI is built. (Difficulty laddering on catalog pages is done — see quick win #4.) |
| 5 | In-browser cloud console sim (AWS) | ⬜ Not implemented | No AWS/IAM/EC2/S3 console sim app. (VMware simulator exists as a separate sim.) |
| 6 | Live coding + hands-on lab interview rounds | ✅ Implemented | `backend/apps/interviews/services/practical_lab.py` provisions real `LabSession`s for interview practical segments via `apps.labs.sessions.start_lab_session`; wired through interview views/serializers. |
| 7 | CI/CD pipeline sim + Prometheus/Grafana observability sim | ⬜ Not implemented | No CI/CD or observability simulation modules under `apps/labs/provisioner/simulation/`. |
| 8 | Code IDE depth: autosave/resume + bash & SQL grading + first-failing-test | 🟡 Partial | **Autosave/resume** ✅ and **first-failing-test panel** ✅ shipped this session (`frontend/src/components/ide/CodingIDE.jsx`). **Bash/SQL auto-grading** ⬜ still pending — bash stays in `NEEDS_REVIEW_LANGUAGES` (`backend/apps/labs/code_exec.py`); only Python + JavaScript auto-grade. |
| 9 | Weekly contests + learning campaigns | ⬜ Not implemented | Ads `Campaigns` admin exists, but no learning-contest model reusing it. (Weekly **leaderboard** scope is done — see quick win #11.) |
| 10 | Sandbox + WebSocket terminal security hardening | 🟡 Partial | Code-exec sandbox runs with resource caps and a fail-closed grader (`backend/apps/labs/code_exec.py`); `tests.test_api_security` runs in CI. Dedicated fail-closed escape/DoS regression suite for the terminal not yet exhaustive. |

### Quick wins (§5)

| # | Quick win | Status | Evidence |
|---|---|---|---|
| 1 | Streak calendar widget | ✅ Implemented | `StreakWidget` (heatmap + current/longest streak) on Dashboard + Profile, fed by `/api/streak/`. |
| 2 | "Today's challenge" surface | ✅ Implemented | `DailyChallengeCard` on Dashboard, fed by `/api/daily-challenge/` (deterministic by date, fails closed). |
| 3 | Badge wall on the profile | ✅ Implemented | `BadgeWall` (`frontend/src/components/engagement/BadgeWall.jsx`) renders `/api/achievements/` + `ACHIEVEMENT_META` as a badge grid on Profile. |
| 4 | Difficulty ladder per page | ✅ Implemented | `Scenarios.jsx` groups results easy→medium→hard into sections; `TechnologyDetail.jsx` groups + difficulty-codes scenarios. |
| 5 | First-failing-testcase panel in IDE | ✅ Implemented | `CodingIDE.jsx` surfaces the first **visible** failing test (name + grader message) prominently; hidden-test internals are never revealed (`firstFailingVisible`). |
| 6 | Vim keymap + format-on-save toggle | ⬜ Not implemented | `CodeEditor.jsx` has no `@replit/codemirror-vim` / Prettier integration. |
| 7 | Autosave code to localStorage | ✅ Implemented | `CodingIDE.jsx` debounces editable files to `localStorage` keyed by session, restores on mount, shows a "Saved" indicator, clears on solve. |
| 8 | Filler-word / talk-time interview stats | ✅ Implemented | Computed from the STT transcript + timing (`backend/apps/interviews/services/stt_service.py`, `llm_engine.py`), no paid API. |
| 9 | Per-scenario stats chip | ✅ Implemented | `ScenarioStatsChip` (`frontend/src/components/engagement/`) on scenario cards (from list-serializer fields, zero extra requests) and ScenarioDetail (self-fetches `/api/scenarios/<slug>/stats/`). Safe defaults; hides if no data. |
| 10 | Promote bash to auto-gradable | ⬜ Not implemented | Bash/shell remain in `NEEDS_REVIEW_LANGUAGES` (`backend/apps/labs/code_exec.py`); no bash harness/tests yet. |
| 11 | Segment the leaderboard (Weekly + Per-tech) | ✅ Implemented | `LeaderboardView` supports `scope=weekly|all` + `technology` (`backend/apps/public_api/views.py`); `Leaderboard.jsx` adds All-time/This-Week tabs over the existing tech chips. |
| 12 | Post-solve editorial / answer key | 🟡 Partial | ScenarioDetail renders `solution_explanation` after a pass; no dedicated rich "editorial" field/curation pass yet. |
| 13 | Status/SLO tile + Sentry release health | 🟡 Partial | `AdminMonitoring.jsx` includes status/uptime/Sentry signals; full Sentry release-health tile not fully built out. |
| 14 | CI dependency scanning | ✅ Implemented | `.github/workflows/dependency-scan.yml` runs `pip-audit` (Python) + `npm audit` (frontend), advisory (`continue-on-error`) so it never blocks CI; triggers weekly + on manifest changes. |

---

## Appendix — Sources

Competitor research (WebSearch / vendor pages):

- KodeKloud — https://kodekloud.com/pricing , https://support.kodekloud.com/what-are-kodekloud-playgrounds , https://kodekloud.com/playgrounds/playground-ci-cd
- Killer.sh — https://killer.sh/cka , https://killer.sh/ckad , https://killer.sh/faq
- SadServers — https://sadservers.com/scenarios , https://sadservers.com/solutions/business , https://github.com/SadServers/sadservers
- Killercoda — https://killercoda.com/creators , https://killercoda.com/learn , https://killercoda.com/faq
- A Cloud Guru / Pluralsight — https://www.pluralsight.com/ps-and-acg , https://www.pluralsight.com/resources/blog/news/introducing-challenge-mode-for-a-cloud-gurus-hands-on-labs
- Whizlabs — https://www.whizlabs.com/ , https://www.whizlabs.com/library/
- HackerRank — https://www.hackerrank.com/products/interview , https://www.hackerrank.com/work/codepair/
- LeetCode — https://leetcode.com/ (Premium features per 2025 analyses)
- CodeSignal — https://codesignal.com/platform/ , https://codesignal.com/cosmo/ , https://codesignal.com/learn
- Replit — https://blog.replit.com/ai , https://replit.com/ (Multiplayer, Agent)
- Instruqt — https://instruqt.com/features , https://instruqt.com/feature/sandbox , https://docs.instruqt.com/reference/feature-overview
- TryHackMe / HackTheBox — https://tryhackme.com/ , https://www.hackthebox.com/ (paths, streaks, gamification per 2026 reviews)
