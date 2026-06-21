# FixitLab — Architecture Review & Refactoring Roadmap

> Status: analysis only. This document changes **no** application behavior. It is a
> reverse-engineered map of the system plus a prioritized, FREE-first roadmap.
> `docs/ARCHITECTURE.md` is the existing deployment guide; **this** file is a critical
> engineering review. All references are `path:line` against the tree as of this commit.

---

## 0. TL;DR — the eight things that matter most

| # | Problem | Severity |
|---|---------|----------|
| 1 | Two parallel state stores for simulation: in-process `_SIM_SESSIONS` dict (terminal labs) vs Redis `cache` (VMware/k8s/docker GUI). The former pins all terminal labs to one backend instance. | **Critical** |
| 2 | Two complete Linux shells — backend `RHELShell` (98k chars) and frontend `linuxShell.js` (2,000 lines) — drift independently and must be kept "behaving the same" by hand. | **High** |
| 3 | Two Kubernetes engines and two Docker engines modeling the same concepts (`vmware_sim/k8s_engine.py` + `docker_engine.py` vs `simulation/k8s_cluster.py` + `docker_state.py`), with no shared state. | **High** |
| 4 | Validation is command-pattern-matching, not real `check.sh` execution: 86 `if "x" in stripped` branches in `validation.py` + a slug→canonical-script keyword map. The 830 `check.sh` files are inert for simulation labs. | **High** |
| 5 | The coding grader (`code_exec.grade_submission`) runs a blocking subprocess **inside the request handler** (`CodeValidateView`), holding an ASGI worker for up to 20s per submission. | **High** |
| 6 | Four files exceed 2,000 lines and three exceed 40,000 *characters* of dense logic (`VMwareSimulator.jsx` 2,813 lines; `scenario_presets.py` 4,218 lines / 356-entry dispatch; `engine.py` 3,110 lines; `rhel_shell.py`). | **High** |
| 7 | Cross-technology coupling (VMware ⇄ terminal "masked IP"/bridge) is threaded through `validation.py`, `engine.py`, `vmware_bridge.py`, and `simulation_provisioner.py` with local imports and slug-string sniffing. | **Medium** |
| 8 | Admin/list endpoints return unpaginated `[:100]` / full-table slices and several N+1 loops (`adminpanel/views.py`); no DRF pagination on the scenarios/leaderboard hot paths. | **Medium** |

**Top 5 refactors:** (1) move simulation session state to Redis behind one store interface — **High impact / Med effort**; (2) move the code grader to a Celery queue — **High / Low**; (3) collapse the four GUI/terminal sim engines to one model per technology — **High / High**; (4) replace the hand-matched validator with a tiny real `check.sh` interpreter against sim state — **High / Med**; (5) split the four giant files behind their existing public surfaces — **Med / Med**.

---

## 1. Architecture Breakdown

### 1.1 Component map

```
                              ┌──────────────── D1: EDGE ────────────────┐
 Browser (React SPA, Vite) ─► │ nginx gateway  (gateway/nginx.cluster…)  │
   REST  /api/*               │   backend_pool  (least_conn → D2:8000)   │
   WS    /ws/terminal/<id>    │   backend_ws    (ip_hash   → D2:8000)    │
                              │ Redis (db0 cache, db3 channels) + RabbitMQ│
                              │ Vault                                     │
                              └───────────────┬───────────────────────────┘
                                              │ VPC private
                              ┌───────────────▼──── D2: APP ─────────────┐
                              │ Django ASGI (uvicorn)  ← REST + WebSocket │
                              │   apps.* (see below)                      │
                              │   ALL simulation engines run IN-PROCESS:  │
                              │     RHELShell / k8s_cluster / docker_state│
                              │     vmware_sim.engine (cache-backed)      │
                              │ Celery: default / provisioning /          │
                              │         maintenance / beat                │
                              └───────┬───────────────────────┬───────────┘
                                      │ pgBouncer (6432)       │ ssh://root@D4
                              ┌───────▼──── D3: DATA ──┐  ┌─────▼─── D4: LABS ───┐
                              │ PostgreSQL + pgBouncer  │  │ Docker engine for    │
                              └─────────────────────────┘  │ real container labs  │
                                                           └──────────────────────┘
```

### 1.2 Backend apps (`backend/apps/`)

| App | Role | Key files |
|-----|------|-----------|
| `accounts` / `auth_app` | Registration, JWT (cookie refresh), OTP, social OAuth, profile, GDPR delete | `accounts/views.py` (1,276 lines), `config/urls.py:14-44` |
| `public_api` | The public surface: catalog, lab lifecycle, coding/prompt validation, progress, leaderboard, blog, projects | `public_api/views.py` (2,476 lines), `public_api/urls.py` |
| `labs` | Lab orchestration: `LabSession` model, the **provisioner** package, completion, hints, code grader, IDE mentor | `labs/models.py`, `labs/provisioner/*`, `labs/code_exec.py`, `labs/completion.py` |
| `vmware_sim` | GUI-driven simulators (VMware vSphere, Kubernetes, Docker) backed by Redis cache | `vmware_sim/engine.py` (3,110 lines), `k8s_engine.py` (1,038), `docker_engine.py` (984) |
| `terminal` | WebSocket consumer bridging xterm.js ⇄ provisioner stream (Docker exec / SSH / sim) | `terminal/consumers.py` (742 lines) |
| `interviews` | AI interview rounds (free, rule-based + optional LLM), scoring, certificates, TTS/STT, billing/GDPR | `interviews/services/*`, `interviews/views.py` (689 lines) |
| `billing` | Stripe + Razorpay subscriptions, webhooks, sales inquiries | `billing/views.py` (1,555), `billing/payment_controller.py` |
| `notifications` | In-app + email notifications | `notifications/*` |
| `jira_integration` | Per-user/scenario Jira tickets; a sync that has been migrating toward simulation | `jira_integration/sync.py` |
| `adminpanel` | Admin dashboards: users, subscriptions, monitoring, analytics, campaigns | `adminpanel/views.py` (3,883 lines — largest non-seed file) |
| `progress` / `leaderboard` / `ratings` / `community` / `hints` / `support` / `audit` / `scenario_versions` | Supporting domains | each app dir |
| `question_bank` | Source of truth for `Technology` / `Scenario`; YAML→DB seeding | `question_bank/models.py`, `management/commands/seed_*` |

`Scenario` (`question_bank/models.py:64`) is the routing keystone. Its fields decide which engine a lab uses:
`lab_mode` (`:156` — docker/aws_ec2/digitalocean/simulation), `simulation_type` (`:162`), `validation_script` (`:94`), `coding_mode` (`:175`), `coding_spec` (`:194`), `requires_companion_hosts` (`:148`).

### 1.3 Frontend (`frontend/src/`)

- **`pages/`** — route components. Heaviest: `pages/vmware/VMwareSimulator.jsx` (2,813), `LabRunner.jsx` (1,632), `PaymentPage.jsx` (1,047), `pages/interviews/InterviewRoom.jsx` (890). Admin pages live under `pages/admin/`.
- **`components/`** — feature folders: `vmware/` (the simulator UI + the client shell), `ide/` (`CodingIDE.jsx` 817), `interviews/`, `promptlab/`, `engagement/`, `layout/`, `admin/`.
- **`api/`** — thin axios wrappers per domain (`client.js` is the shared instance; `labs.js`, `vmware.js`, `interviews.js`, `scenarios.js`, …).
- **`store/`** — Zustand stores: `authStore`, `dataStore`, `labStore`, `notificationStore`, `themeStore`.
- **`hooks/`** — e.g. `useInterviewVoice.js`, `useVirtualBackground.js`, `mediaDevices`.

### 1.4 The simulation engines (four families, two paradigms)

There are **two paradigms** for "fake infrastructure," and the platform implements the big technologies in *both*:

**A. Terminal paradigm** — a typed shell over an in-memory object graph, streamed over WebSocket.
- `simulation/rhel_shell.py` (98,781 chars) — the RHEL/Linux shell: hundreds of command handlers over `rhel_os.RHELOSState`.
- `simulation/k8s_cluster.py` (1,571 lines) — a mutable cluster graph for `kubectl …`, incl. `apply -f`.
- `simulation/docker_state.py` (459) — a Docker daemon graph for `docker …`.
- Plus `lvm_state`, `networking_state`, `firewall_state`, `devops_state`, `ops_state`, `boot_sequence`, `editor_mode`.
- Orchestrated by `unified_sim.UnifiedSimulationEngine` and exposed via `SimulationProvisioner`.

**B. GUI paradigm** — a JSON state blob mutated by `apply_action(...)`, rendered by React panels, persisted in Redis `cache`.
- `vmware_sim/engine.py` (3,110) — full vSphere inventory/actions/validation.
- `vmware_sim/k8s_engine.py` (1,038) — a *second* Kubernetes model (namespaces, pods, RBAC, PVCs).
- `vmware_sim/docker_engine.py` (984) — a *second* Docker model.
- Exposed via `vmware_sim/views.py` (`state` / `action` / `release` per family).

**C. Coding grader** — `labs/code_exec.py` runs the learner's Python/JS in a sandboxed subprocess (rlimits, timeout, scrubbed env) against hidden tests. Unsupported languages → `needs_review` (never auto-pass).

**D. Frontend client shell** — `components/vmware/linuxShell.js` (2,000 lines) is a *third* Linux shell, running entirely in the browser with its own VFS, used by the VMware console and SSH-terminal components (`VmwareConsole.jsx`, `VmwareSshTerminal.jsx`).

### 1.5 Deploy topologies

- **Single-droplet (dev / small prod):** `docker-compose.prod.yml` runs everything (nginx, backend, celery, postgres, redis, rabbitmq) on one host; lab containers via local Docker socket. `docs/ARCHITECTURE.md` documents this as the recommended <10k-user setup.
- **Four-droplet (cluster):** D1 edge (gateway + Redis + RabbitMQ + Vault), D2 app (`docker-compose.app.yml` — backend + all Celery + **sims in-process**), D3 data (`docker-compose.data.yml` — Postgres + pgBouncer), D4 labs (remote Docker engine reached via `ssh://root@D4`, wired through `DOCKER_HOST`). Connectivity wired by `scripts/ci-wire-cluster-env.py`; firewalls by `scripts/ci-setup-firewalls.sh`. IaC under `infra/` (`terraform/main.tf`, `digitalocean/cluster.json`, `kubernetes/deployment.yaml`, Packer golden AMI).

### 1.6 End-to-end data flow — the three core journeys

**(a) Start a lab → provision → terminal/sim → validate → complete**
1. `POST /api/labs/<scenario_id>/start/` → `StartLabView` (`public_api/views.py:550`). `_resolve_provider` (`:61`) maps `lab_mode`/`simulation_type` → provider. A `LabSession` row is created (`status=PROVISIONING`).
2. Provisioning is **async** via Celery: `provision_docker_lab.delay(...)` for docker+simulation (`views.py:778`), `provision_cloud_lab.delay(...)` for AWS/DO (`:757`).
3. `get_provisioner(provider)` (`provisioner/__init__.py:18`) returns Docker/EC2/DO/Simulation. For simulation, `SimulationProvisioner.provision` builds a `UnifiedSimulationEngine`, computes `lab_hosts`, and calls `register_sim_session(...)` storing the engine in the **in-process** `_SIM_SESSIONS` dict (`simulation/shell.py:163`).
4. Browser opens `ws://…/ws/terminal/<session_id>?host=primary`. `TerminalConsumer.connect` (`terminal/consumers.py:130`) authenticates, enforces a per-user WS cap via Redis `cache.incr`, verifies session ownership, then `create_exec_stream(...)` — Docker exec socket, SSH channel, or `SimulationStreamHolder`. Keystrokes ⇄ engine output flow over the socket.
5. `POST /api/labs/<id>/validate/` → `ValidateLabView` (`:947`). For Docker/cloud it tries to run a real `/opt/fixitlab/check.sh` (`:978`); on exit 127 (no script) it falls back to `run_validation(db_script)`. For **simulation** it calls `SimulationProvisioner.run_validation`, which resolves a canonical script (`resolve_simulation_validation_script`, `validation.py:171`) and evaluates it against in-memory state (`validate_simulation_state`, `validation.py:218`).
6. On pass, the single shared path `finalize_validated_session(...)` (`labs/completion.py`) records progress/score/achievements.

**(b) Coding-IDE scenario → grade**
1. `GET /api/labs/<id>/coding-spec/` → `CodingSpecView` (`:1049`) returns starter files + **visible** tests (hidden tests stripped, only their count, via `public_coding_spec`, `:1013`).
2. Frontend `CodingIDE.jsx` edits files, may run visible tests client-side.
3. `POST /api/labs/<id>/code-validate/` → `CodeValidateView` (`:1073`). The backend re-runs **both** visible+hidden tests via `grade_submission(...)` (`code_exec.py`) **synchronously, in-process**. Only if every required test passes does it call the same `finalize_validated_session`. Unsupported language → `needs_review` (never auto-pass).

**(c) Interview round → score**
1. `interviews/views.py` + `services/engine.py` (or `engine_v2.py` for the LLM variant) start a round, select questions (`question_selector.py`), and stream interviewer turns. Voice via `tts_service`/`stt_service`.
2. Each answer → `services/scoring.py:score_answer` → `interview_ai.compute_answer_scores` (rule-based, free: keyword hits, STAR coverage, depth/concreteness). A validated practical command adds a bonus (`scoring.py`).
3. Round end aggregates (`aggregate_round_scores`); `engine_v2.end_round` builds an AI scorecard and may issue a certificate (`services/certificate.py`).

---

## 2. Critical Problem Areas

Severity: **Critical** = blocks correctness/scale now · **High** = significant risk/cost · **Medium** = real but contained · **Low** = polish.

### 2.1 Bad architecture decisions

**[Critical] Two session-state stores for simulation; terminal state is process-local.**
`simulation/shell.py:160-220` keeps every terminal lab's live engine in a module-global `_SIM_SESSIONS: dict` guarded by a thread lock. The VMware/k8s/docker GUI sims instead persist JSON in Django `cache` (Redis) — `vmware_sim/engine.py:79-87`, `k8s_engine.py:_session_key`. Consequences:
- A learner's terminal lab is bound to **one** uvicorn process. The cluster works today only because `gateway/nginx.conf:37` pins `/ws/` with `ip_hash` and the backend pool has a single member (`gateway/nginx.cluster.conf.template:35-36`). Add `backend2` and terminal labs break unless the same client always lands on the same box.
- A worker restart/redeploy drops all live terminal labs. There is a `sim_persistence` snapshot path (`simulation_provisioner.ensure_sim_session` → `restore_engine`, and the consumer persists on certain events, `consumers.py:345`), but it is a rehydrate-on-miss patch over a fundamentally in-RAM design, not a shared store.
- The cross-tech bridge already had to special-case this: `register_sim_session` stamps `session_id` onto OS state so the VMware bridge (keyed in shared cache) can be read "even though the two simulators run in different workers" (`shell.py:171-176`). That comment is the architecture admitting the split.

**[High] Three separate Linux shells that must agree by hand.**
`simulation/rhel_shell.py` (backend, 98k chars), `components/vmware/linuxShell.js` (frontend, 2,000 lines, used by `VmwareConsole.jsx:2` and `VmwareSshTerminal.jsx:2`), and the GUI VMware guest behavior inside `vmware_sim/engine.py`. The same command (`systemctl restart nginx`, `vi`, `yum`) is implemented in Python and again in JavaScript. They drift: a fix to `nginx` state handling in one is invisible to the other, and validation (`validation.py`) only ever sees the backend state — so a learner who "fixed" things in the client-side console may still fail backend validation, and vice-versa.

**[High] Two Kubernetes engines and two Docker engines.**
`vmware_sim/k8s_engine.py` (GUI, cache-backed JSON) and `simulation/k8s_cluster.py` (terminal object graph) model pods/nodes/namespaces/RBAC independently. Same for `vmware_sim/docker_engine.py` vs `simulation/docker_state.py`. A learner using the k8s **GUI** and a learner using `kubectl` in the **terminal** are driving two different fake clusters with no shared truth. The cross-tech "Kubernetes-on-VMware" feature has to re-fold state through `vmware_bridge` at validation time (`validation.py:303-350`) precisely because the cluster the learner sees isn't the one validation inspects by default.

**[High] Validation is pattern-matching, not execution — and the `check.sh` files are largely inert.**
There are 830 `check.sh` files in `scenarios/`, but for **simulation** labs they are not executed. Instead:
- `resolve_simulation_validation_script` (`validation.py:171-217`) ignores a "trivial" script and substitutes a `CANONICAL_*` template chosen by **keyword-matching the slug** (e.g. `"terraform" in s … → CANONICAL_TERRAFORM_CHECK`). The code itself documents the fragility: ordering hacks so `"ci-pipeline"` doesn't match the `pip` python rule (`:178-180`).
- `validate_simulation_state` (`validation.py:218-266`) then "runs" that script by scanning lines and matching ~86 hard-coded substrings (`if "nginx -t" in stripped`, `if "getent passwd" … "appuser"`, …) against in-memory state. Real `check.sh` execution only happens for **Docker/cloud** providers (`ValidateLabView:978`). Net effect: three parallel validation systems (real bash on containers; canonical-template + substring matching for sims; `code_exec` for coding), and the sampled `scenarios/vmware/*/check.sh` are just `exit 0` stubs.

**[High] Heavyweight synchronous work in the request path (coding grader).**
`CodeValidateView.post` (`public_api/views.py:1085-1150`) calls `grade_submission(...)` directly. That spawns a subprocess with an 8s default / 20s max wall-clock budget (`code_exec.py:38-40`) and blocks the ASGI worker for the duration. Under load this starves the event loop and ties grading throughput to web-worker count. Provisioning was correctly moved to Celery; grading was not.

**[Medium] Cross-technology "masked-IP"/bridge plumbing is threaded through many layers via local imports + slug sniffing.**
The VMware⇄terminal bridge logic appears in `simulation_provisioner.py` (`_apply_initial_host_state`, `_build_lab_hosts` branch on `"ssh-stop"`, `"mysql-dual"`…), `validation.py:277-350` (cross-tech checks run *first* to avoid being "shadowed" by generic handlers), `vmware_sim/engine.py:30-78` (`_cross_tech_config`, `_bridge_k8s_node`), and `vmware_bridge.py`. Behavior is keyed off `slug.startswith("linux-server-hung-needs-vmware-reset")`-style string checks scattered across files, with `try/except Exception: pass` import guards because the two simulators live in different packages/workers. This is correct-but-brittle: a renamed slug silently disables the bridge.

**[Medium] `lab_hosts` topology is hardcoded by slug substring.**
`simulation_provisioner._build_lab_hosts` (`simulation_provisioner.py:30-95`) decides multi-host layout from `"ssh-stop"`, `"firewalld-dual"`, `"mysql-dual"`, `sim_type == "ansible"`, etc. Host counts, IPs (`10.0.0.10/11/12`), and SSH wiring are literals. Adding a multi-host scenario means editing provisioner code, not data.

### 2.2 Duplicate logic

- **Engines:** the four GUI/terminal duplications above (k8s ×2, docker ×2, linux ×3).
- **Per-family REST views are near-identical.** `vmware_sim/views.py` defines `*StateView` / `*ActionView` / `*ReleaseView` three times (VMware/k8s/docker) with copy-pasted ownership checks and `get_state(...); apply_action(...); return {**result, "state": …}`. ~150 lines that differ only by which engine module is imported.
- **Provisioner module loads:** `_load_session`/`_save_session`/`_session_key`/`SESSION_TTL=7200` are re-implemented verbatim in `vmware_sim/engine.py:79-90` and `vmware_sim/k8s_engine.py` (and the docker engine) instead of a shared cache helper.
- **Canonical check templates vs scenario YAML:** `validation.py` hard-codes `CANONICAL_*_CHECK` bash strings that restate what the YAML `check.sh` files already contain.
- **Completion finalization** is correctly unified (`finalize_validated_session`) and called from all three validators — this is the *good* pattern to replicate elsewhere.
- **Preset dispatch has many-to-one slug aliases:** `scenario_presets._PRESETS` (`:3339`) maps **356** slug entries onto ~**330** functions; e.g. `broken-nginx`, `sim-broken-nginx`, `sim-rhel-broken-nginx` all → `_preset_broken_nginx` (`:3696-3698`). Alias sprawl, not logic dup, but it makes the map a maintenance hotspot.

### 2.3 Performance bottlenecks

- **[High] Synchronous grader** (see 2.1) — up to 20s of worker occupancy per coding submission.
- **[Medium] Unpaginated / capped admin endpoints + N+1.** `adminpanel/views.py` uses `User.objects.all().order_by(...)[:100]` and iterates (`:796`, `:825`, `:2045`, `:2268`), and loops `UserScenarioJiraTicket.objects.filter(...)` per user (`:925`). `[:100]` is a silent cap, not pagination — data beyond 100 is invisible, and the slices still scan/sort the full table. No `pagination_class` is set on these list views.
- **[Medium] Scenarios list builds a large response.** `ScenariosListView` (`public_api/views.py:300+`) does `select_related("technology").prefetch_related("tags")` (good) and caches anonymous responses for 2 minutes (good), but there is no enforced page cap visible on the queryset itself; with 1,130 scenarios a missing/oversized `page_size` returns a heavy payload. Verify the paginator is always applied.
- **[Low] `cache.incr`/`expire` per WS connect** (`consumers.py:140-156`) is fine, but the fallback `except Exception: pass` means if Redis is down the per-user WS cap silently disables.
- **Good:** Redis cache wraps hot catalog reads; `CACHES` is configured to treat Redis errors as misses (`settings.py:628-647`) so a Redis hiccup degrades rather than 500s.

### 2.4 Maintainability issues

- **Giant files** (hard to review, test, or change safely):
  - `question_bank/management/commands/seed_projects.py` — **8,057** lines (data-as-code).
  - `simulation/scenario_presets.py` — **4,218** lines, 455 `_preset_*` functions, a 356-entry dispatch dict.
  - `adminpanel/views.py` — **3,883** lines.
  - `vmware_sim/engine.py` — **3,110** lines (150 KB).
  - `public_api/views.py` — **2,476** lines.
  - `simulation/rhel_shell.py` — **2,271** lines (98 KB).
  - `frontend: VMwareSimulator.jsx` — **2,813** lines (160 KB); `linuxShell.js` — **2,000**; `LabRunner.jsx` — **1,632**.
- **Data encoded as Python.** Scenario presets and project seeds are imperative Python, not declarative data. The 1,130 `scenario.yaml` files *are* declarative, but the behavioral "break" (preset) and the "check" (validation) live in code keyed by slug — so a scenario's truth is split across YAML + `scenario_presets.py` + `validation.py`.
- **Inconsistent state strategy** (in-proc dict vs cache) across two halves of the same feature.
- **Local imports as a coupling smell.** Many `from apps.vmware_sim.engine import …` / `from .scenario_presets import _preset_*` inside function bodies, guarded by `try/except`, to dodge cross-package/cross-worker hard deps (`simulation_provisioner.py:255-260,371-379`, `engine.py:30-37`).
- **Test coverage is meaningful but uneven.** `backend/tests/` covers k8s sim, coding IDE, simulation OS, multiuser isolation, production security (`test_k8s_sim.py` 581, `test_coding_ide.py` 466, `test_multiuser_isolation.py` 643, `test_production_security.py` 546). Gaps: the GUI `vmware_sim` engines, the validation pattern-matcher's branch coverage, and the frontend `linuxShell.js`/`VMwareSimulator.jsx` have no obvious unit tests — exactly the files most prone to silent drift.

---

## 3. Refactoring Strategy (prioritized, behavior-preserving, FREE-first)

Each item is scoped to **preserve behavior**: same endpoints, same responses, same scenario outcomes. Sequence matters — earlier items de-risk later ones.

### R1 — Put simulation session state in Redis behind one store interface
**Impact: High · Effort: Medium · Risk: Medium**
- Define `SimSessionStore` with `get/set/drop/by_resource`. Two backends: today's in-proc dict (default for single-droplet) and a Redis/`cache` backend that serializes the engine via the **existing** `sim_persistence.persist_session_snapshot` / `restore_engine`.
- Make `register_sim_session`/`get_sim_session`/`drop_sim_session` (`simulation/shell.py`) delegate to the store. The engine objects hold streams (queues) that can't serialize — keep the live `SimulationStreamHolder`s process-local, but move the **state snapshot** to Redis so any worker can rehydrate (the rehydrate path already exists in `ensure_sim_session`).
- Behavior preserved: same API, same terminal output; only the storage location changes. This is the prerequisite for ever adding `backend2`.

### R2 — Move the coding grader (and other long work) to a Celery queue
**Impact: High · Effort: Low · Risk: Low**
- Add `grade_submission_task` on the existing `provisioning`/`default` queue. `CodeValidateView` enqueues and returns `202` + a poll token, or (lower-churn option) keeps the endpoint synchronous from the client's perspective by `await`-ing the task result with a hard timeout, so the ASGI worker isn't CPU-blocked by the subprocess. Reuse the `result.public_dict(...)` shape verbatim so the frontend contract is unchanged.
- This also lets the grader move to an isolated worker container (aligns with `code_exec.py`'s own SECURITY NOTE / `SECURITY_AUDIT.md` C-01) without touching web nodes.

### R3 — Collapse the four GUI/terminal engines to one model per technology
**Impact: High · Effort: High · Risk: Medium-High**
- One canonical state model per technology (`KubernetesState`, `DockerState`, already largely present in `simulation/`). The **terminal** path drives it via the shell; the **GUI** path drives the *same* object via `apply_action`. Keep both `views.py` (GUI) and the WS consumer (terminal) as thin adapters over the shared model.
- Migrate `vmware_sim/k8s_engine.py` and `docker_engine.py` to delegate to `simulation/k8s_cluster.py` / `docker_state.py`, then delete the duplicates. VMware itself has no terminal twin, so `engine.py` stays — but factor its shared cache helpers (R5).
- Sequence after R1 (shared store) and R4 (unified validation), because a single model makes both trivial. Do it technology-by-technology behind tests; ship k8s first (best existing coverage in `test_k8s_sim.py`).

### R4 — Replace the hand-matched validator with a minimal real `check.sh` runner over sim state
**Impact: High · Effort: Medium · Risk: Medium**
- The simulator already implements the commands the checks call (`nginx -t`, `systemctl is-active`, `pgrep`, `kubectl get …`). So run the **actual** `scenarios/.../check.sh` through the existing `RHELShell.run(...)` line-by-line and honor real exit codes, instead of 86 bespoke substring branches. The 830 check files become the single source of truth for *both* sim and container labs.
- Keep `resolve_simulation_validation_script` only as a temporary shim for scenarios whose `check.sh` is still a stub, and burn that list down. Snapshot current pass/fail outcomes for a representative scenario set as a golden test before/after to prove behavior is unchanged.

### R5 — Split the giant files behind their existing public surfaces
**Impact: Medium · Effort: Medium · Risk: Low**
- `scenario_presets.py` → one module per technology (`presets/linux.py`, `presets/k8s.py`, …) re-exported through `apply_scenario_preset`; the `_PRESETS` dict is assembled from per-module registrations. Collapse pure slug-aliases into a small alias table.
- `adminpanel/views.py` and `public_api/views.py` → split by domain into a `views/` package (users/subscriptions/monitoring/analytics; catalog/labs/coding/progress). Pure move, no signature changes.
- `vmware_sim/engine.py` → extract a shared `cache_store.py` (`_session_key/_load/_save/SESSION_TTL`) reused by all three GUI engines (kills the triplicated helpers), then split inventory vs actions vs validation.
- Frontend `VMwareSimulator.jsx` → break into panel components (inventory tree, console host, configure tabs, modals) that already exist as siblings under `components/vmware/`; lift shared state to a store. `linuxShell.js` is mooted by R3/R6.

### R6 — Make the client-side Linux shell a thin view, not a second engine
**Impact: Medium · Effort: Medium · Risk: Medium**
- The browser shell (`linuxShell.js`) exists to avoid a round-trip in the VMware console. Re-point `VmwareConsole.jsx`/`VmwareSshTerminal.jsx` at the same WebSocket terminal the rest of the platform uses (the backend `RHELShell`), so there is exactly one Linux engine and validation always reflects what the learner did. If an offline/instant feel is required, generate the client shell's command table from the backend rather than maintaining it twice.

### R7 — Make scenario topology & behavior declarative
**Impact: Medium · Effort: Medium · Risk: Low**
- Move `lab_hosts` layouts and the "which preset / which bridge" decisions out of `simulation_provisioner._build_lab_hosts` and the slug-`startswith` checks into the `scenario.yaml` (a `hosts:` block and an explicit `preset:`/`bridge:` key). Eliminates string-sniffing and makes adding multi-host or cross-tech scenarios a data change.

### R8 — Add pagination + kill N+1 on admin/list endpoints
**Impact: Medium · Effort: Low · Risk: Low**
- Apply DRF `PageNumberPagination` to the `adminpanel` list views currently using `[:100]`, and replace per-row `for u in qs: …filter(user=u)…` with `prefetch_related`/annotations. Confirm `ScenariosListView` always paginates. No response-shape change beyond standard `{count,next,previous,results}` (or keep current shape via a custom paginator if the frontend expects a bare list).

---

## 4. Scalability — the four-droplet topology

### 4.1 Where state lives
| State | Location | Scales horizontally? |
|-------|----------|----------------------|
| Relational data (users, scenarios, sessions, billing) | Postgres on D3 via pgBouncer (transaction pool, `MAX_CLIENT_CONN=1000`, `DEFAULT_POOL_SIZE=25`) | Yes (read replicas later) |
| Cache + GUI sim sessions (VMware/k8s/docker) | Redis on D1 (`cache`, db0; `vmware_session:*`, `k8s_session:*`, 2h TTL) | **Yes** — already shared |
| Channels layer (WS group routing) | Redis on D1 (`channels_redis`, db3 — `settings.py:317-327`) | Yes |
| **Terminal sim sessions (RHEL/k8s/docker shells)** | **In-process `_SIM_SESSIONS` dict on D2** (`simulation/shell.py:160`) | **No** — the hard blocker |
| Live terminal/WS stream objects | In-process queues in the consumer/holder | No (inherently per-connection) |
| Lab containers | Remote Docker on D4 (`DOCKER_HOST=ssh://root@D4`) | D4 is a single engine host today |
| Celery broker | RabbitMQ on D1 | Yes |

### 4.2 What blocks horizontal scaling of the app tier
1. **`_SIM_SESSIONS` is process-local (Critical).** This is *the* reason `gateway/nginx.cluster.conf.template:30-36` points both `backend_pool` and `backend_ws` at a single `{{APP_PRIVATE_IP}}:8000`, and why `nginx.conf` leaves `backend2` commented out. With sims in RAM, a second app instance would serve a *different* set of live labs; `ip_hash` keeps a given client sticky but cannot share a lab opened on box A with a validate call routed to box B. **Fix: R1.** Until then, D2 scales only *vertically* (note the 3G memory limit on `backend` and concurrency-8/10/2 Celery workers in `docker-compose.app.yml`).
2. **Synchronous grader (High).** Grading throughput == web-worker count, and a slow submission steals an ASGI worker. **Fix: R2.**
3. **WebSocket fan-out is actually fine** once R1 lands: `channels_redis` already provides a cross-process channel layer, and `ip_hash` provides stickiness; the only thing missing is shared *session state*, not shared *messaging*. After R1 you can uncomment `backend2`, switch `backend_ws` from `ip_hash` to least-conn (or keep `ip_hash` for connection affinity), and scale out.
4. **D4 single Docker host.** Real-container labs all land on one engine. Beyond a few hundred concurrent container labs you need multiple D4 hosts and a scheduler (pick least-loaded host, store host on `LabSession`). The provisioner factory (`provisioner/__init__.py`) is the natural seam.
5. **pgBouncer pool sizing.** `DEFAULT_POOL_SIZE=25` against one Postgres is fine for one app node; multiple app nodes share that ceiling — size it with the number of app workers in mind.

### 4.3 Concrete scale-out path (FREE-first, in order)
1. **R1 + R2** — make app state shareable and get long work off the request path. *Now the app tier is stateless enough to replicate.*
2. Add `backend2` (commented stub already in `gateway/nginx.conf:31,40` and the cluster template) → two uvicorn replicas on D2 (or a second app droplet). Verify a lab opened on one is validatable on the other.
3. Split a dedicated **grader/worker** container (isolated, network-less) for `code_exec` — satisfies both scale and the security note in `code_exec.py` / `SECURITY_AUDIT.md` C-01.
4. When container-lab volume grows, add D4-class hosts and record the chosen host on the session.
5. Postgres read replica for the read-heavy catalog/leaderboard once a single primary is the bottleneck.

### 4.4 Already-good scalability properties (keep these)
- Provisioning is async and queue-isolated (`provisioning`/`default`/`maintenance`/`beat`).
- Redis is the cache **and** channel layer **and** GUI-sim store — one shared substrate.
- Cache treats Redis errors as misses (degrade, don't 500).
- pgBouncer transaction pooling fronts Postgres.
- Per-user WebSocket cap (`MAX_WS_PER_USER`) bounds abuse.
- Anonymous catalog responses are cached; hot list queries use `select_related`/`prefetch_related`.

---

## 5. Suggested sequencing

```
Phase 1 (unblock scale, low risk):      R2 (grader→queue),  R8 (pagination/N+1)
Phase 2 (the keystone):                 R1 (sim state → Redis store)   ── enables backend2
Phase 3 (kill duplication):             R4 (real check.sh) → R3 (one engine/tech) → R6 (one Linux shell)
Phase 4 (sustained maintainability):    R5 (split giant files),  R7 (declarative scenarios)
```
Phases 1 and 4 are independently shippable and behavior-neutral; Phase 2 is the single highest-leverage change for the four-droplet story; Phase 3 removes the largest source of drift and is safest *after* R1/R4.

---

*Appendix — sizes referenced:* `scenarios/`: 1,130 `scenario.yaml`, 830 `check.sh`. Largest backend files: `seed_projects.py` 8,057 · `scenario_presets.py` 4,218 (356-entry dispatch) · `adminpanel/views.py` 3,883 · `vmware_sim/engine.py` 3,110 · `public_api/views.py` 2,476 · `rhel_shell.py` 2,271. Largest frontend: `VMwareSimulator.jsx` 2,813 · `linuxShell.js` 2,000 · `LabRunner.jsx` 1,632. `validation.py` 869 lines / 86 match branches.
