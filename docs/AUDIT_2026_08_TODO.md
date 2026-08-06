# FixitLab Deep Audit — 2026-08-06

Scope: 16,372 tracked files. 7,280 scenario YAMLs across 46 technologies, 435k LOC backend
(excl. venv), 130k LOC frontend, 22 backend sim engines, 25 frontend simulators, 830 tutorials,
213 projects, 5 journeys, 7 cert tracks, 21 CI workflows, 7 compose files.

Method: 17 parallel deep-dive agents across four passes, all findings evidence-backed with
`file:line`. Backend test suite executed (1677 pass / 52 skip). Frontend build, lint, tests, and
`npm audit` executed. Interview scorer executed against synthetic answers. AWS grading path executed
in a Django shell. Open-source model licences verified against upstream sources.

**693 actionable checkboxes.** Nothing here is inferred — where a claim needed empirical
verification it is marked ⚠️.

---

## HOW TO READ THIS DOCUMENT

**Start at the end.** [`MASTER PLAN — FINAL CONSOLIDATED`](#master-plan--final-consolidated) is the
only authoritative sequencing. The three earlier phase plans (v1/v2/v3) are marked **⚠️ SUPERSEDED**
and kept for their reasoning — do not schedule work from them.

| Pass | Sections | Covers |
|---|---|---|
| **1st** | §S, §G, §I, §H, §D, §A, §F, §C, §W, §B, §O | Security · grading integrity · interview scoring · lab routing · 3D datacenter · AI/ML content · simulator fidelity · learning path · frontend · backend · docs/CI/infra |
| **2nd (§X)** | X1–X7 | Owner-reported: datacenter stuck in 2D · @mention no reply. New epics: golden image→AMI→EC2 · artifact provenance · operational rough edges · datacenter as a game · platform-wide sweep |
| **3rd (§Y)** | Y1–Y4 | Voice call agent (EN/HI/TE) · coding IDE language bug · in-IDE API/Postman client · IDE backlog |
| **4th (§Z)** | Z1–Z6 | Billing/revenue · auth/authz · user-generated content · privacy/PII/compliance · scale/capacity/leaks · API/email/SEO/analytics/PWA/testing/DX |

**Reference tables at the end:** the five shared components (build each once — eleven epics depend on
them) and the ten highest-value single changes ranked by impact ÷ effort.

---

## THE HEADLINE

**Breadth is real. Depth is manufactured. Grading is decorative.**

The platform's engineering substrate is genuinely strong — the backend is secure and well-tested,
the simulator engines are state-driven with fail-closed validators, the cert exam engine is
rigorous, the tutorial content is deep. Three things undermine all of it:

1. **63.8% of scenarios (4,642) have no scenario-specific verification.** 81.7% of `check.sh`
   files are byte-identical to another file — 5,788 files in 57 distinct groups. One group has
   n=863 (all of aws + openstack + azure + gcp).
2. **1,340 scenarios are graded on the wrong technology.** A "Dell EMC PowerMax storage pools"
   lab passes when `crond` is running. NetApp 149/150, Dell EMC 149/150, OpenStack 149/151,
   datacenter 148/150, Azure/GCP 133/150, SOC 129/150.
3. **The connective tissue between layers is severed.** 5,403 scenarios point at tutorial slugs
   that do not exist (0% resolve). 213 projects launch 0 labs. 5 journeys have no frontend route.

Two acute failures on top of that: **420 AWS labs are literally unpassable**, and the **AI
interview scores a keyword-stuffer 79/100 (PASS) and a genuine expert 16.9/100 (FAIL)**.

---

# P0 — SECURITY (do today, before anything else)

## S1. Tracked production secrets in `SETUP_COMPLETE.md`
**Verified directly.** File is tracked (`git ls-files --error-unmatch` succeeds). 10 secret-shaped
assignments at lines 26, 27, 28, 29, 30, 158, 167, 174, 188, 194. Values are 20–87 chars with no
placeholder markers (`CHANGE`, `your-`, `<`, `xxx`) — i.e. real.

- [ ] Replace all 10 values in [SETUP_COMPLETE.md](SETUP_COMPLETE.md) with placeholders
- [ ] **Rotate every one out-of-band on the servers** — Django `SECRET_KEY`, Postgres, Redis,
      RabbitMQ, Razorpay key secret. Do NOT use the deploy workflow's `rotate_secrets` flag
      (known to break login — see memory `deploy_flag_gotchas`)
- [ ] Treat as public: they are in git history and cannot be un-published

## S2. The secret scanner is blind to S1
**Verified directly.** [scripts/check-no-secrets-in-git.sh:29-38](scripts/check-no-secrets-in-git.sh#L29)
has 8 patterns — `dop_v1_`, PEM header, `ghp_`, `github_pat_`, `sk_live_`, `rzp_live_`, `AKIA`.
Zero generic patterns. `grep -c 'PASSWORD\|SECRET_KEY'` on the script returns 0.

- [ ] Add generic high-entropy rules: `(SECRET_KEY|PASSWORD|_PASS|KEY_SECRET|API_TOKEN)\s*[:=]\s*\S{16,}`
- [ ] Confirm the scanner then **fails** on the current tree (regression proof)
- [ ] Add an allowlist mechanism for the known-safe AWS doc-example keys already excluded at
      [check-no-secrets-in-git.sh:44-45](scripts/check-no-secrets-in-git.sh#L44)

## S3. The scanner never runs on PR
**Verified directly.** Wired only into `production.yml` (`on: workflow_dispatch`) and `tests.yml`
(`on: workflow_dispatch`). A PR that adds secrets merges green.

- [ ] Add the scanner as a step in `.github/workflows/ci.yml` (runs on PR + push-to-main)

## S4. Env blobs remain in git history
`.env.backup.20260401` and `deploy/production.env` were committed in `3d35f6b46` / `cbd721f75`,
deleted in `337260bbf`. Blobs persist. Key names present: `AWS_SECRET_ACCESS_KEY`, `DO_API_TOKEN`,
`POSTGRES_PASSWORD`, `EMAIL_HOST_PASSWORD`, `SUPERUSER_PASSWORD`, `*_KEY_PEM`.

*Good news:* live `.env` / `.env.production` are correctly gitignored and were **never** tracked
(`git log --all --full-history` empty). The 2026-07 ".env secrets" P0 is resolved as literally scoped.

- [ ] Decide: history rewrite (`git-filter-repo`) vs. formally accept + rotate everything those held
- [ ] Document the decision in `docs/SECURITY_AUDIT.md`

## S5. SSRF via org webhook URL
- [ ] [backend/apps/accounts/org_views.py:454](backend/apps/accounts/org_views.py#L454) — `setattr` +
      `save(update_fields=...)` bypasses `URLField` validation (no `full_clean()`)
- [ ] [backend/apps/accounts/webhooks.py:37](backend/apps/accounts/webhooks.py#L37) — `requests.post`
      to that URL, server-side, **synchronously in the request path** via
      [labs/completion.py:72](backend/apps/labs/completion.py#L72) and
      [accounts/views.py:261](backend/apps/accounts/views.py#L261)
- [ ] Fix: enforce `https` scheme, resolve DNS and reject private/link-local/loopback ranges
      (169.254.0.0/16, 10/8, 172.16/12, 192.168/16, 127/8), move the POST to Celery
- [ ] Any org owner can currently reach the DO metadata endpoint, Vault, or Postgres

## S6. Pin `appleboy/ssh-action`
Used 19× and **receives `PROD_SSH_KEY`**. Pinned by mutable tag `@v1`. A tag move upstream =
production SSH key compromise.

- [ ] Pin to a commit SHA. Then `digitalocean/action-doctl@v2` (9×),
      `docker/build-push-action@v6`, `actions/github-script@v7`
- [ ] Add `github-actions` ecosystem to `dependabot.yml` (currently npm + pip only)

## S7. Two auth controls fail open silently
- [ ] [backend/apps/accounts/views.py:358](backend/apps/accounts/views.py#L358) — IP-block check
      inside `except: pass` → fails **open**
- [ ] [backend/apps/accounts/views.py:369](backend/apps/accounts/views.py#L369) — brute-force
      throttle recording silently lost → login throttle stops counting
- [ ] Both must log at WARNING minimum

## S8. Frontend dependency CVEs
`npm audit`: 8 vulns (4 high, 3 moderate, 1 low).
- [ ] `npm audit fix` — non-breaking for `postcss`, `undici`, `brace-expansion`, `dompurify`
- [ ] Schedule `react-router-dom` 6.30.4 → v7: **open-redirect via backslash** in `<Link>`/
      `useNavigate` (GHSA-wrjc-x8rr-h8h6) — the only vuln reachable by an anonymous visitor
- [ ] `vite` <=6.4.2 high → vite@8 (major, plan separately)

---

# P0 — GRADING INTEGRITY (the platform does not verify what it teaches)

This is the single largest defect class. It affects ~64% of the catalog. **Fix this before
authoring any new content** — new content inherits the same broken graders.

## G1. The `exit 0` template neutralizes 4,522 checkers
Canonical shape, e.g. [scenarios/aws/academy-aws-001-learn-ec2/check.sh](scenarios/aws/academy-aws-001-learn-ec2/check.sh):
```bash
#!/usr/bin/env bash
systemctl is-failed --quiet 2>/dev/null; test $? -ne 0
exit 0                     # <- discards line 2 entirely
```
6,963 of 7,083 `check.sh` files have <10 effective lines. Only 33 exceed 30 lines.

*Mitigating:* the runtime does not exec these as bash. `simulation_provisioner.py:960` routes to
dedicated engines and `validation.py:241` interprets line-by-line, then applies a **fail-closed
sentinel sweep** at `validation.py:339-357`. So labs are not trivially auto-passing. But the sweep
is generic, not topical — see G2.

- [ ] Scripted pass: replace `exit 0` with the real probe's exit status across all 4,522 files
- [ ] 602 of 761 in the AI verticals specifically (gpu 150/172, ai-ml 104/145, ai-infra 145/145,
      data-science 103/144, prompt-engineering 100/100)
- [ ] 197 scenarios have **no** `check.sh` at all (python 57, javascript 50,
      prompt-engineering 50, vmware 12, baremetal 11)

## G2. The universal pass condition is "append FIXED-OK to a planted file"
[validation.py:262-266](backend/apps/labs/provisioner/simulation/validation.py#L262) and `:359-370`.
A learner satisfies a NetApp SVM lab by editing a marker file. The check never verifies ONTAP
knowledge. This is the fail-open class from the `incident_academy_broken_fix_regression` memory,
one layer up.

- [ ] Replace the generic sweep with per-scenario state assertions read from the engine's own
      world model (the engines already expose it — see G6)

## G3. 1,340 scenarios graded on an unrelated Linux daemon
Service distribution across non-Linux techs: `crond` 445, `nginx` 437, `rsyslog` 429, `firewalld` 29.

| tech | off-topic | % | evidence |
|---|---|---|---|
| dellemc | 149/150 | 99% | `scenarios/dellemc/academy-dellemc-001-learn-storage-pools/scenario.yaml` |
| netapp | 149/150 | 99% | `scenarios/netapp/academy-netapp-001-learn-svm/scenario.yaml` — objectives = `` `crond` service is active `` |
| openstack | 149/151 | 99% | `scenarios/openstack/academy-openstack-001-learn-nova/scenario.yaml` |
| datacenter | 148/150 | 99% | `scenarios/datacenter/academy-datacenter-001-learn-racks/scenario.yaml` |
| azure / gcp | 133/150 | 89% | `scenarios/azure/academy-azure-001-learn-virtual-machines/scenario.yaml` |
| soc | 129/150 | 86% | `scenarios/soc/academy-soc-001-learn-siem/scenario.yaml` |
| opentelemetry | 125/150 | 83% | |
| service-mesh / devsecops | 113 / 112 of 150 | 75% | |

Root cause for the AI verticals:
[academy_service_presets.py:38-137](backend/apps/labs/provisioner/simulation/academy_service_presets.py#L38)
maps 90 ai-ml **and 100 prompt-engineering** slugs to one lambda breaking `model-server`. So
"ReAct", "RAG Prompting", "Prompt Injection Defense" and "LLM-as-Judge" are all *restart a dead
systemd unit*. Data-science: 100 × `_break_service(jupyter)`.

- [ ] [topic_faults.py:13-30](backend/apps/labs/provisioner/simulation/topic_faults.py#L13) has
      keyword families for CI, GitOps, perms, netsec, k8s, Terraform, Docker, DB, Java, security,
      OpenStack, memcached, MQ — and **none** for GPU, LLM, model, inference, training, RAG, agent,
      or vector. The module's own docstring says it exists to stop recycling nginx breaks for
      unrelated titles; the AI verticals are exactly what it never covered. Add those families.
- [ ] Author real per-topic faults for the 9 worst technologies, or unpublish them (shipping
      "Agents — Integration Lab" graded on nginx is worse than not shipping it)

## G4. 420 AWS labs are unpassable — proven by execution
Django shell, `academy-aws-001-learn-ec2`:
```
unfixed                            : False
after real AWS work (ec2/s3 CLI)   : False   <- real work does NOT count
after appending FIXED-OK to marker : True
```
Chain:
| Step | Location | Effect |
|---|---|---|
| Dispatcher excludes academy | `simulation_provisioner.py:1345-1348` | `_is_aws_academy` routes **away** from `validate_aws_lab` |
| Resolver excludes academy | `validation.py:206` | `and not s.startswith("academy-aws-")` — stub not replaced |
| Fault plants marker | `topic_faults.py:47-48, 331-340` | writes `/opt/fixitlab/academy/<slug>.conf` |
| Sweep decides grade | `validation.py:345-357` | fails until that file contains `FIXED-OK` |

Consequences:
- `validate_aws_lab` ([aws_engine.py:1432](backend/apps/vmware_sim/aws_engine.py#L1432), ~180 lines
  of real objective grading) is **dead code for 100% of shipped AWS scenarios**. There are zero
  console-hero AWS labs, so its branch is unreachable.
- The console GUI **cannot pass a lab**. `aws_engine.py` has 0 references to `vfs`/`FIXED-OK`.
- `grep -rl FIXED-OK scenarios/aws` → 0. The one thing that passes is mentioned in no
  description, hint, or solution.
- Fail-**closed**, not fail-open: nobody can legitimately pass. This is the "aws lab issues" report.

- [ ] **Recommended fix:** delete the `_is_aws_academy` exclusion at `simulation_provisioner.py:1345`,
      seed per-slug `broken` markers so `validate_aws_lab`'s existing checks (launch/stop/
      restrict-SSH/encrypt-bucket) activate. Reuses ~180 lines already written; makes the console
      load-bearing instead of decorative.
- [ ] Same root cause for azure (147), gcp (147), openstack (149) — **863 cloud labs total**

## G5. Coding labs have placeholder tests
- [ ] 82 labs: `visible_tests`/`hidden_tests` are literally `assert callable(solution)` —
      e.g. [scenarios/ai-ml/ai-ml-lab-33/scenario.yaml](scenarios/ai-ml/ai-ml-lab-33/scenario.yaml).
      Starter raises `NotImplementedError`, but `callable()` passes without calling it.
      Only 5 ai-ml and 6 data-science coding labs have real tests.
- [ ] 100 prompt-engineering coding labs have **zero** `hidden_tests`
- [ ] 1,051 of 1,334 `coding_spec` labs (79%) have only 1–2 hidden tests; average 1.82

## G6. Validators check "the action fired", not "the system is healthy"
NetApp / Dell EMC / SOC validators do `if broken: return False` against a generic dict rather than
inspecting real world state. Correct in practice (presets seed the keys) but an alternate valid
repair path is not recognized, and error feedback is generic.

- [ ] Replace with per-key messages naming the specific unmet objective — same rigor, far better
      learner feedback
- [ ] [openstack engine](backend/apps/vmware_sim/) has **0 validators** — the only engine with
      none. Those 151 labs cannot be graded server-side at all. Add one.

## G7. CI cannot detect any of this
`scripts/scan_grader_integrity.py` replays `validate_simulation_state` on the unfixed state and
flags fail-OPEN. These labs fail-open on the *fixed* state too, and the ai-ml/prompt labs do
genuinely break `model-server`, so they classify as FAIL-CLOSED and pass the gate.

- [ ] Add a **topic-coherence rule**: fail CI when a scenario's `technology` has no lexical
      overlap with its `validation.command`. This alone catches all 1,340 of G3.
- [ ] Add a **checker-uniqueness rule**: fail when >N scenarios in one technology share an
      identical `check.sh`. Catches G1/G4 (aws has 1 unique checker for 420 labs).
- [ ] Add a **cross-layer slug rule**: fail on unresolvable `linked_tutorial`,
      `validation_scenario_slug`, `lab_scenario_slug`, cert pool refs. Catches C1/L2/L5.
- [ ] Keep `test_academy_fix_alignment.py` (memory: it is the only BROKEN_FIX guard)

---

# P0 — AI INTERVIEW SCORING IS INVERTED

Measured by executing the real scoring path. There is **no LLM** —
[interviews/services/llm.py:1](backend/apps/interviews/services/llm.py#L1) reads *"LLM module
deprecated — FixitLab uses free native interview AI."* Scoring is regex + substring keyword
matching + TF-IDF cosine. Server TTS/STT are hardcoded to `browser`/empty.

| answer | score | quality | correctness |
|---|---|---|---|
| empty | 0 | skipped | unknown |
| gibberish, 120 words | 2 | adequate | **correct** |
| question repeated back | **43** | adequate | correct |
| keyword stuffing, no meaning | **61** | strong | correct |
| **genuine good answer** | **14** | strong | correct |
| lorem ipsum, 150 words | 4 | adequate | correct |

End-to-end round, 6 answers, threshold 65:
```
KEYWORD-STUFFER    overall=79.0   PASS=True
GENUINE EXPERT     overall=16.9   PASS=False
```

- [ ] **I1** [conversation/scorer.py:39-40](backend/apps/interviews/services/conversation/scorer.py#L39)
      — `depth_score`/`concrete_score` are `substring in text` counts over generic English
      (`"because"`, `"second"`, `"request"`, `"when"`). Stuffing hits 100/100; a real answer that
      *explains* rather than name-drops hits 24/45.
- [ ] **I2** [scorer.py:75](backend/apps/interviews/services/conversation/scorer.py#L75) — the
      anti-gaming rule `if word_count > 80 and relevance < 35: composite *= 0.55` **fires on the
      good answer** (93 words, relevance 7) and not on the shorter stuffed one. The guard actively
      penalizes real answers.
- [ ] **I3** [analysis.py:55-72](backend/apps/interviews/services/analysis.py#L55) —
      `TfidfVectorizer` fit on **2 documents**. IDF over n=2 is degenerate; relevance is noise
      (genuine 0.067 vs stuffed 0.123 — the stuffer scores *higher*). Weighted 25–30% of composite.
- [ ] **I4** [scoring.py:51-53](backend/apps/interviews/services/scoring.py#L51) — with no
      `expected_keywords` (the generated-question path supplies none), `quality == "strong"`
      returns `CORRECTNESS_CORRECT` unconditionally. Gibberish grades "correct".
- [ ] **I5** [scorer.py:34](backend/apps/interviews/services/conversation/scorer.py#L34) —
      `_detect_topic(f"{question_text} {candidate_answer}")`. Topic is detected from the
      **question**, so `topic_detected` is always non-null regardless of the answer, upgrading
      quality via `_refine_quality` and correctness.
- [ ] **Fix (highest-value change in this audit):** replace the heuristic with a real rubric judge.
      Given the no-paid-API constraint, use a local embedding model (`sentence-transformers`
      MiniLM, free/offline, ~80MB) for semantic similarity against reference answers — fixes
      I1/I3/I5 together. Add a **golden-set regression test**: 20 known-good + 20 known-bad
      answers, assert good > bad. All 77 existing interview tests pass because they assert
      *absence of paid APIs* and structural invariants, never scoring validity — that is why this
      survived the prior audit.

## I6. Unlimited tab-hidden time extension = open-book cheating
[InterviewRoom.jsx:739-759](frontend/src/pages/interviews/InterviewRoom.jsx#L739) pauses the timer
when the tab hides and **extends `ends_at` by the full away-duration** on return.
[engine.py:1318-1338](backend/apps/interviews/services/engine.py#L1318) `pause_round`/
`resume_round` have no cap, no pause counter, no max. Tab-switching is *rewarded*, never flagged.

- [ ] Cap at 2 pauses × 60s; log every pause to `metadata`; surface "3 tab switches" on the report
- [ ] [views.py:873-901](backend/apps/interviews/views.py#L873) — `pause`/`resume`/`extend` have
      **no `throttle_classes`**, unlike start/message/practical

## I7. Question bank ceiling
73 generated templates + 40 DB-seeded = ~113 total.
```
difficulty     d1   d2   d3   d4   d5
count          26   25   18    4    0
```
- [ ] **Zero d5, only 4 d4** (k8s/docker/linux only). `_band()`
      [question_generator.py:717-728](backend/apps/interviews/services/question_generator.py#L717)
      silently snaps a senior candidate down to d2/d3. Adaptive difficulty
      ([engine.py:964](backend/apps/interviews/services/engine.py#L964)) escalates to `min(5, ...)`
      — a band with no content. **Seniors are interviewed at mid level and never told.**
- [ ] Author d4/d5 banks for all 13 topics (~50 questions)
- [ ] 0 of 73 coding questions, 4 of 73 system design, 0 behavioral STAR in the main bank
- [ ] d1 coverage is 26 items across 13 topics — a candidate doing two rounds on one tech
      exhausts the bank
- [ ] *Preserve:* question wording is genuinely good — 13.9 words avg, 0 closed yes/no,
      0 answer leakage, 0 duplicates

## I8. Question generation is non-deterministic across processes
[question_generator.py:876-880](backend/apps/interviews/services/question_generator.py#L876) uses
Python `hash()`, not blake2b. 3 runs → 3 different seeds. The docstring claims determinism; the
test only covers in-process. **The `interview_generator_determinism` memory is stale on this point.**

- [ ] `blake2b(blob.encode()).digest()[:8]` in `_seed_from`
- [ ] Add a subprocess test asserting stable seeds across interpreter runs
- [ ] Same `hash()` bug in [datacenter_facility_ops.py:27](backend/apps/vmware_sim/datacenter_facility_ops.py#L27)

## I9. `hr` / `manager` rounds silently use technical weights
- [ ] [interview_types.py:192](backend/apps/interviews/interview_types.py#L192) — no `eval_weights`
      key, so `get_eval_weights("hr")` returns the technical defaults (35% technical weight on an
      HR round). Verified by execution.

## I10. Voice hook leaks
- [ ] [useInterviewVoice.js:1271](frontend/src/hooks/useInterviewVoice.js#L1271) — returns with
      **no unmount teardown**. Active `SpeechRecognition`, in-flight `speechSynthesis` queue,
      module-level `_currentAudio`, `_speechHoldTimer` all keep running. Navigate away mid-answer
      → mic stays hot and the interviewer keeps talking.
- [ ] `:721` — `speechSynthesis.onvoiceschanged` assigned, never nulled
- [ ] `:290` — module-level `_unlockAudioCtx` never closed; repeated room entries accumulate
      AudioContexts (browsers cap ~6, after which audio dies)
- [ ] `:6-7` — header claims "ElevenLabs/Polly → Browser" and "Whisper API → Browser"; both
      server paths are hard-disabled. Fix the comment.
- [ ] No `aria-live` on interim transcript; hands-free auto-submit has no opt-out for users with
      speech disfluency; Firefox has no `SpeechRecognition` and the room degrades to typing
      without saying why
- [ ] *Preserve:* barge-in and the dynamic silence window that widens on trailing "and…"/
      "because…" (`:184-211`, `:1112-1118`) is genuinely well-engineered

## I11. Interview enhancement backlog
- [ ] Per-competency anchored rubrics (correctness / depth / tradeoffs / communication, 0–4 with
      written level descriptors)
- [ ] Real coding execution — wire the existing `labs.code_exec` sandbox into a proper editor
      (currently a paste-a-solution textarea at `InterviewRoom.jsx:2373`)
- [ ] Adaptive difficulty that works — probe follow-ups on weak answers, escalate on strong ones,
      only within bands that have content
- [ ] Proctoring signals: tab-switch count, paste-into-answer detection, fullscreen prompt.
      Report them rather than blocking. No screen share (`getDisplayMedia` absent) today.
- [ ] System-design whiteboard; mock panel; JD-targeted interviews; percentile benchmark vs prior
      candidates (`InterviewTemplate` + `RecruiterCompare.jsx` already scaffold most of this)
- [ ] In-room auto-reconnect + transcript replay (round survives refresh server-side but the room
      does not resume)
- [ ] *Preserve:* fail-closed practical validation (`practical_lab.py:226`), server-side-only
      `command_validated` (`views.py:739`), correct `escapeHtml` in report export, no
      `dangerouslySetInnerHTML` anywhere in the interview UI

---

# P0/P1 — "LINKS OPEN HIDDEN, NO LAB BUTTONS"

Your report is **confirmed, but the root cause differs from the stated interpretation.** Simulators
are *not* generally rendered without chrome — the `LabChromeBar` + `LabChromeControls` system is
well-built and wired into VyOS, Packer, Datacenter, AWS, Terraform. There are four specific defects
plus a genuine orphan-route problem.

## H1. VMware login gate is a full-screen dead end (150 scenarios) — strongest match
- [ ] [VMwareSimulator.jsx:1203](frontend/src/pages/vmware/VMwareSimulator.jsx#L1203) — `if (!vcAuth)
      return <VmwareLoginGate onAuthenticated={...} />`.
      [VmwareLoginGate.jsx:50](frontend/src/components/vmware/VmwareLoginGate.jsx#L50) accepts
      **only** `onAuthenticated` — no `sessionId`, no back link, no chrome, renders `min-h-screen`
      full-bleed at `:77`.
- [ ] Reached by 150 `simulation_type: vmware` scenarios via
      [LabRunner.jsx:767-770](frontend/src/pages/LabRunner.jsx#L767), which uses
      `navigate(..., { replace: true })` — **destroying the history entry**, so browser-Back cannot
      return to `/lab/:sessionId`. A learner who cannot guess the vCenter credentials is stranded.
- [ ] The sibling error state at `VMwareSimulator.jsx:1194` **does** render `← Back to lab` —
      proving the gate is an oversight, not a design choice. Copy that.
- [ ] Change `replace: true` → `replace: false` at `LabRunner.jsx:768`

## H2. Mobile lab buttons buried under every companion overlay
- [ ] [LabRunner.jsx:3612](frontend/src/pages/LabRunner.jsx#L3612) — the mobile bottom action bar
      (Instructions / Hints / **Check** / Stop) is `z-30`, while companion overlays are `z-[80]`
      (`companionOverlayClass`, `LabRunner.jsx:1806`). On a phone, opening any companion console
      **buries the entire lab-button bar**. Literal instance of "hidden … not having lab buttons."
- [ ] The sidebar correctly escalates to `z-[70]` in the same situation (`LabRunner.jsx:2299`) —
      the bottom bar was simply missed. Raise to `z-[85]` (above `z-[80]`, below the `z-[90]`
      `CompanionToolStrip`).

## H3. Two fullscreen layouts drop chrome (1,334 + 150 scenarios)
- [ ] **Coding IDE** — [LabRunner.jsx:2182-2234](frontend/src/pages/LabRunner.jsx#L2182). Header at
      `:2185-2208` has only title, difficulty, Jira link, timer, Stop. **Missing Hints, +30m/Extend,
      and any Back-to-scenario link.** `simChromeProps` is built at `:1795-1803` and **never passed**
      to `LazySimPanel` at `:2214-2221`. `CodingIDE.jsx:138` has its own Run/Check/hints, so it is
      not a blank dead end — but **+30m is unreachable** and timeout ejects the learner.
- [ ] **Prompt Playground** — [LabRunner.jsx:2133-2179](frontend/src/pages/LabRunner.jsx#L2133).
      Header at `:2136-2153` has only timer + Stop. `PromptPlayground.jsx` has **no Check/validate
      control at all**. No Check, no +30m, no Back.
- [ ] Fix both: spread `{...simChromeProps}` via `<LabChromeControls>`, add a Back link using the
      existing `getLabExitPath()` helper (`LabRunner.jsx:83`)

## H4. `/simulators` is reachable by nobody
- [ ] Route is inside the **authenticated** `MainLayout`
      ([AppRouter.jsx:189](frontend/src/router/AppRouter.jsx#L189)).
- [ ] Its **only** inbound link is `PUBLIC_NAV_SECONDARY`
      ([publicNav.js:17](frontend/src/constants/publicNav.js#L17), "Lab Consoles"), rendered
      unconditionally for anonymous visitors in `PublicLayout.jsx:105`, `MarketingNav.jsx:79`,
      `Pricing.jsx:492`.
- [ ] It is **not** in the authenticated sidebar (`MainLayout.jsx:17-28`).
- [ ] Net: logged-out users click "Lab Consoles" → bounced to `/login`. Logged-in users never see
      the link. Fix: add to `MainLayout` nav, or move the route out of `MainLayout` and make it public.
- [ ] Also: every card in `SimulatorLauncher.jsx:8-21` links to `/technologies/:slug`, so the page
      has no lab buttons by design — it is a signpost, not a lab surface. Set expectations or add
      direct launch.

## H5. Dead `/aws-sim/*` route with zero chrome
- [ ] [AppRouter.jsx:182](frontend/src/router/AppRouter.jsx#L182). Only producer is
      `awsConsoleUrlForResource()`
      ([terraformAwsBridge.js:527-530](frontend/src/utils/terraformAwsBridge.js#L527)), which is
      **exported but never imported anywhere**. Standalone `AwsConsole`
      (`components/aws/AwsConsole.jsx:41`) has **zero lab chrome** — if reached, a total dead end.
- [ ] Delete the route + the dead helper, or give `AwsConsole` chrome when `embedded === false`

## H6. Jira ticket links lose lab context
- [ ] [JiraTicketLink.jsx:17,62](frontend/src/components/JiraTicketLink.jsx#L17) — opens a new tab
      with `openInNewTab=true` default. [JiraTicketPage.jsx:140-144](frontend/src/pages/JiraTicketPage.jsx#L140)
      offers only "Back to FixitLab → /dashboard". **No session/attempt id**, so the return path
      drops the learner out of the lab entirely. Thread `sessionId` through.

## H7. Packer IDE mount is unguarded
- [ ] [LabRunner.jsx:3864-3878](frontend/src/pages/LabRunner.jsx#L3864) uses a bare `<Suspense>`
      with **no `SimErrorBoundary`**, unlike every other companion which uses `LazySimPanel`. A
      throw escapes to the route boundary and blanks the whole lab.

## H8. Other orphan / duplicate routes
- [ ] `/vmware/:sessionId` vs `/vmware-sim` — duplicate mounts of the same component
      (`AppRouter.jsx:180-181`)
- [ ] `/unsubscribe` (`AppRouter.jsx:162`) — 0 refs, email-only entry, by design; document it
- [ ] Dead map entries in `PRIMARY_SIM_COMPONENTS`: `openshift`, `k8s` (alias),
      `datadashboard`/`agent` (only 3+4 scenarios use `data-dashboard`/`ai-agent`)

## H9. Non-bugs verified — do NOT "fix" these
- `PrimaryLabSim.jsx:10` `if (!Sim) return null` blank-panel path is **never hit**: all 25 keys
  producible by the `LabRunner.jsx:1770-1792` chain exist in
  [labSimLoader.js:41-67](frontend/src/components/lab/labSimLoader.js#L41).
- `LazyVyosConsole` / `LazyPackerWorkspaceIde` / `LazyCodingIDE` / `LazyPromptPlayground` absent
  from `PRIMARY_SIM_COMPONENTS` is **intentional** — documented at `scenarioConsoles.js:10`
  (`NON_PRIMARY`); they mount as companions.
- Datacenter walk mode exits correctly (`DatacenterTwin3D.jsx:1601-1614` Esc menu with
  `onExitImmersive`/`onExitTo2D`; `DatacenterSimulator.jsx:283-402` renders `LabChromeBar` in every branch).
- Toolbars use `flex-wrap`; **no `display:none` on any control**; no clipping.
- Auth/paywall gating is healthy — proper toasts + redirects, no blank renders.

## H10. Dispatch-table drift (cosmetic but invites bugs)
- [ ] [simScenario.js:5-21](frontend/src/utils/simScenario.js#L5) `SIM_TYPES` has only 16 keys.
      `LabRunner.jsx:1642-1751` routes many more. It is a *badge* registry, not the router, and the
      two lists have drifted. Reconcile or rename to make the distinction obvious.
- [ ] `consoles:` in YAML is used by **only 150 ai-infra scenarios**. All other 7,000+ rely on
      slug/tech regex heuristics at `LabRunner.jsx:1600-1792` — brittle. Migrate to explicit
      `consoles:` declarations.
- [ ] `simulation_type: nodejs` (100 files) has **no `_LEGACY_MAP` entry**
      ([sim_types.py:47-60](backend/apps/labs/provisioner/simulation/sim_types.py#L47)) so all 100
      silently degrade to `generic` via `sim_types.py:69` — Node labs boot a plain RHEL persona.
      `shell` (100 files) maps correctly.

---

# P0/P1 — 3D DATACENTER GAME

Stack confirmed: **real three.js via react-three-fiber** — `three@^0.170.0`,
`@react-three/fiber@^8.17.14`, `@react-three/drei@^9.121.4`, `@react-three/rapier@^1.5.0`.
Not CSS 3D. Root `<Canvas>` at [DatacenterTwin3D.jsx:1881-1917](frontend/src/components/datacenter/DatacenterTwin3D.jsx#L1881).
Defaults to 3D + immersive + walk.

**The structural root cause of "controls don't work right": Rapier is mounted but the player is not
a physics body.** `<Physics>` wraps the scene at `:1887`, racks get `RigidBody` colliders at
`:971-995`, but `WalkController` (`:266-349`) is a pure kinematic camera that mutates
`camera.position` directly and **never queries the physics world.** The entire collision system
exists, is paid for, and excludes the player.

## D1. No collision detection at all (P0)
- [ ] [DatacenterTwin3D.jsx:314-320](frontend/src/components/datacenter/DatacenterTwin3D.jsx#L314) —
      the only constraint is an axis-aligned box clamp:
      `pos.x = clamp(-8.5, 7.5)`, `pos.z = clamp(-5.5, 6.5)`.
      Racks sit at `rackPosition()` (`:870-875`) spanning x −2.1..2.1, z −0.5..−7.1 — squarely
      inside the walkable box with zero exclusion. **You walk through every rack, wall, CRAC and
      the mantrap door.**
- [ ] Fix: capsule-vs-AABB resolution against a memoized collider list (racks, CRACs, walls, MDF
      cage, door), **resolving X and Z independently** so you slide along walls instead of sticking
- [ ] This also makes the badge gate meaningful — `:1713-1720` explicitly disabled it ("Badge-in
      still opens the mantrap door — it no longer blocks movement") because there was no collision

## D2. Pointer-lock loss is never detected (P0) — likely your "controls broken" report
- [ ] No `pointerlockchange` or `pointerlockerror` listener anywhere (only three
      `exitPointerLock` calls at `:302`, `:1739`, `:1745`).
- [ ] Esc is **double-bound**: the browser consumes it to exit pointer lock *and* `:1753` toggles
      the pause menu. One Esc both unlocks the pointer and opens the menu; the second Esc closes
      the menu **without re-locking**. Player is left in a dead state where WASD moves but the
      mouse does not.
- [ ] `CrosshairInteract` (`:391`) early-returns when `document.pointerLockElement !== gl.domElement`,
      so **E silently stops working with no feedback**.
- [ ] The auto-lock `setTimeout` at `:293-295` throws `SecurityError` in Chrome (no user gesture)
      and is swallowed by an empty catch → silent no-mouse-look on first entry. The toolbar hint at
      `:1824` ("click canvas to look") is an admission of this bug.
- [ ] Fix: add `pointerlockchange`/`pointerlockerror`; on loss → open pause menu + "click to
      resume"; drop the illegal auto-lock in favour of an explicit "Click to play" overlay

## D3. Camera Y is one frame stale (P0)
- [ ] `:330-331`:
      ```js
      camera.position.set(pos.current.x + sway, pos.current.y + bob, pos.current.z)
      pos.current.y = 1.55   // <- set AFTER it is read
      ```
      Masked today because Y is constant. Becomes visible jitter the moment crouch/jump/stairs
      exist. Move the assignment above the `set()`.

## D4. `dt` unclamped (P0)
- [ ] Speed **is** correctly `* dt` at `:310` (good). But an alt-tab or GC pause yields a huge `dt`
      and **teleports the player through geometry**. Clamp to ~0.1s.
- [ ] `RackMesh`/`ServerStack` intro animations use `performance.now()` deltas rather than `dt`
      (`:947-953`, `:728-758`) — they run while the tab is hidden and complete instantly on return.

## D5. No gravity, floor constraint, jump, or crouch (P0)
- [ ] `grep Space|KeyC|ControlLeft|crouch|jump` returns only the unrelated `Physics gravity` prop
      at `:1887`. Vertical space does not exist as a concept.

## D6. Input handling defects (P1)
- [ ] `:309` — sprint reads only `keys.current.ShiftLeft`. **Right Shift does nothing.**
- [ ] `:286-288` — `keydown` bound to `window` with **no `e.target` tag guard and no
      `preventDefault`**. WASD types into every text input in the app; Space/arrows scroll the page.
- [ ] No `blur`/`visibilitychange` handler clears `keys.current`. **Alt-Tab while holding W and you
      return drifting forward forever.** (`keys.current = {}` only on pause, `:308`.)
- [ ] `:282-283` — mouse sensitivity is a hardcoded `0.0026` for both axes. No slider, no invert-Y,
      no per-axis scaling. Table stakes for FPS controls and an accessibility issue.
- [ ] `:288-289` — `mousemove` on `window`, not the canvas.
- [ ] `:304` — `paused` is in the effect dep array, so every menu toggle tears down and rebuilds all
      four listeners and re-copies camera position from `pos.current` (`:290`), resetting in-flight
      state. Split the pause check into a ref. (Cleanup itself is correct — no leak.)
- [ ] `:385-402` — E-to-interact **dispatches a synthetic `MouseEvent` at canvas center** to fake a
      raycast. Bypasses R3F's raycaster ordering; picks the wrong object with overlapping `Html`
      overlays. Replace with `raycaster.setFromCamera(new Vector2(0,0), camera)` against an
      interactables registry — which also gives you the hover prompt (D11).
- [ ] No gamepad, no touch/mobile controls, no key rebinding. `DatacenterSimulator.css:848` merely
      hides the minimap on small screens — **on mobile the game is unplayable, not degraded.**

## D7. Per-frame `setState` — the classic killer (P0)
- [ ] [DcCableSystem.jsx:196-197](frontend/src/components/datacenter/DcCableSystem.jsx#L196):
      ```js
      if (recoil > 0) setRecoil((r) => Math.max(0, r - dt * 2.2))
      if (snapFlash > 0) setSnapFlash((s) => Math.max(0, s - dt * 3))
      ```
      `recoil`/`snapFlash` are React state (`:137-138`) decremented **every frame**. Each triggers a
      full re-render of that `InteractiveCable`, and because `tipWorld` (`:150`), `curve` (`:162`)
      and `tube` (`:173`) are `useMemo`'d **on `recoil`**, every frame allocates a brand-new
      `CatmullRomCurve3` and `TubeGeometry` (36 × 8) — **and the old one is never disposed.** With
      dozens of cables this is a GPU-memory leak and a frame-time cliff.
- [ ] Fix: move both to `useRef`, mutate the tube via pooled geometry or `curve.points`

## D8. Zero `dispose()` calls in the entire directory (P1)
- [ ] `ServerStack` `useMemo`'d geometry + material (`:721-722`) and every `TubeGeometry` in
      `DcCableSystem` leak on unmount/prop-change. The whole twin unmounts on every 2D/3D toggle
      and room switch (`DatacenterSimulator.jsx:480`), so it leaks **per toggle**.
      Add `useEffect(() => () => geo.dispose(), [geo])`.

## D9. FPS counter re-renders the entire twin once per second (P1)
- [ ] `FpsMeter` (`:49-60`) → `onFps={setFps}` (`:1902`) → `setFps` on the root (`:1669`) →
      re-renders `<Canvas>` children → **the entire `SceneContent` tree reconciles every second.**
      Move the readout to a ref-driven DOM node or a portal outside the tree.

## D10. `<Html>` used 16×, several inside per-item loops (P1) — biggest FPS win
- [ ] Every rack (`:927`), **every server** (`:861`), every cable port (`DcCableSystem.jsx:91`),
      every ticket waypoint, CRAC, portal. drei's `Html` mounts a real DOM element per instance and
      runs a matrix-project + CSS transform write on **every one, every frame**. 8 racks × ~10
      servers = 100+ absolutely-positioned DOM nodes transformed at 60Hz.
- [ ] Fix: single canvas-texture sprite atlas, or render only the crosshair target's label

## D11. No hover / proximity interaction prompt (P1)
- [ ] There is a crosshair but nothing says *what* you are aiming at or that E does anything.
      Classic immersive-sim affordance (`[E] Open rack RACK-01`) entirely absent. Combined with D2
      this is why E "appears broken."

## D12. Visual gaps (P1/P2)
- [ ] **No textures at all.** Every surface is flat `meshStandardMaterial` color — no albedo/normal/
      roughness maps anywhere. No perforated floor tile, no brushed metal, no rack mesh-door alpha.
      **Single biggest "doesn't look real" lever.** Floor is ~231 individual boxes with per-tile
      materials (`:438-449`) — slow *and* flat.
- [ ] **~22 `pointLight`s** from `CeilingLights` (`:465-482`, 5 x-positions × 2 rows) will blow past
      WebGL's uniform limit in a single forward pass and tank shader compile time. Bake to emissive
      strips + 2–3 real lights.
- [ ] **No post-processing** — no `@react-three/postprocessing` dep. **Bloom is the single highest-
      value visual addition** for a dark room full of glowing LEDs (they currently use
      `toneMapped={false}` as a poor substitute). Also no SSAO, no vignette, no motion blur.
- [ ] **No LOD, no distance culling.** Every LED on every server in every rack renders every frame.
      `ServerFaceDetail` (`:805-868`) renders ~13 separate meshes **plus an `Html`** per server,
      **defeating the instancing** that `ServerStack` (`:763`) correctly set up. Racks themselves
      are not instanced (`RoundedBox` per rack, `:906`).
- [ ] Shadows: single 1024² cascade-less directional over a 24×16 hall — very coarse.
- [ ] `Environment preset="warehouse"` (`:1395`) **fetches an HDRI from a CDN at runtime.**
      Offline/air-gapped labs hang or throw into `Twin3DSafe` and silently drop to the 2D floor.
      Self-host it.
- [ ] Minimap (`:1514-1550`) draws **no walls or racks** — just a ring and 4 portal dots — and the
      player dot has **no heading indicator** even though `posRef.current.yaw` is already populated
      at `:345`. It also drives a `requestAnimationFrame` loop **outside R3F** (`:1516-1529`) that
      runs forever even when the menu is open.
- [ ] Particle counts **scale with stress** (`:1424` `220 * animBoost * (1 + thermalStress * 1.4)`
      plus a second system at `:1429`) — worst framerate exactly during a thermal crisis.
      `HallDust` (`:363-372`) and `AirflowParticles` (`:519-537`) do per-particle JS loops with a
      full `needsUpdate` buffer upload each frame; move to a vertex shader.
- [ ] Estimated **>1,500 draw calls** at 8 racks before any rack-count increase. `Bvh` (`:1440`)
      only accelerates raycasting, not rendering.
- [ ] *Preserve:* fog tightening in walk mode (`:1390`), `StatusLed` blink states
      (`DcCableSystem.jsx:11-40`), `FanSpinner` RPM-proportional spin + stall-on-fault (`:585-631`),
      `InteractiveCable` catmull-rom sag with per-type QSFP/LC/RJ45 connector geometry (`:119-324`),
      head-bob + sprint FOV punch (`:322-340`), server tray slide-in install (`:728-758`).
      These are genuinely good.

## D13. Game feel gaps (P2)
- [ ] **No progression, score, fail state, or timer.** Ticket beacons (`:1089-1144`, floating
      rotating cones over faulted racks) are good quest markers, but closing a ticket just removes
      a beacon. No XP, no SLA clock, no consequence for thermal runaway.
- [ ] **Onboarding is a 5.2s toast that appears once** (`:1496-1503`); `coachShown` is a ref
      (`:1681`) so it never re-shows. No tutorial, **no controls screen in the pause menu** (`:1602-1623`
      lists hotkeys in a single hint line at `:1618`), no way to re-read the controls.
- [ ] **Audio is 3 oscillators + one square-wave stinger** (`DcAmbientAudio.jsx:98-121` — proximity
      attenuation is nice). No footsteps — **and `bobPhase` at `:326` already computes the step
      phase, so footstep audio is nearly free.** No door/fan/relay/alarm SFX, no `PositionalAudio`.
- [ ] No day/night or alarm lighting state. A thermal/power emergency should turn the hall red and
      strobe; it only nudges haze opacity.
- [ ] Missing vs immersive sims: inventory with real weight, tool wheel, build/place mode,
      save/load of player position, controller support.
- [ ] Missing vs DCIM tools (Nlyte/Sunbird/NetBox): true rack elevation front/rear U views,
      patch-panel port mapping, power-chain one-line diagram, capacity what-if planning, asset
      barcode/serial lookup, change management tied to the 3D asset, cable length/bend-radius
      validation, airflow CFD overlay (you have haze, not vectors).

## D14. Datacenter domain physics gaps (P2, backend)
The backend is substantially **more sophisticated than the 3D layer that visualizes it** —
`datacenter_engine.py` (3021 L), `datacenter_facility_ops.py` (818 L), `datacenter_physics_ops.py`
(417 L). Modelled well: ATS + generator + UPS + rack PDUs with breaker state (`engine:300-328`),
UPS SoC drain and battery temp rise on transfer (`facility_ops:792-798`), rack tip risk from
**weighted center-of-gravity** (`physics_ops:40-51` — genuinely correct physics), 42U / 1360 kg
capacity (`:153-156`), ASHRAE A1 class (`facility_ops:225`), cold/hot aisle sensors at 21.2/33.8 °C
(`:205-207`, realistic ~12 °C delta-T), hotspot injection (`:271-280`), PUE/WUE panels.

- [ ] **Biggest domain gap — CRAC temperature is a `sin()` of a hash, not a thermal model.**
      [datacenter_facility_ops.py:27](backend/apps/vmware_sim/datacenter_facility_ops.py#L27):
      `s["temp_c"] = round(base + 0.6 * math.sin(phase + hash(s.get("id")) % 7), 1)`.
      **No coupling between IT load and inlet temperature** → no thermal runaway. Kill every CRAC
      and rack temps do not rise, servers do not throttle, nothing trips. Replace with
      `inlet = f(IT load, CRAC capacity, containment)` driving throttle → thermal shutdown.
- [ ] Same line uses raw `hash()` — **not stable across Python processes.** Same bug class the
      interview generator has (I8). Use blake2b.
- [ ] **No A/B dual-feed redundancy.** `ups` is a list and PDUs have `feeds`, but there is no
      per-PSU A/B mapping, so "pull the A feed — the B feed carries it, unless someone single-corded
      that server" is unrepresentable. In 3D, `PduStrips` (`:633-679`) draws exactly **one** PDU per
      rack; real racks have two, one per side.
- [ ] **Breaker trip has no overcurrent physics.** `engine:2373-2379` toggles `breaker` as a
      scripted fault. No amps-vs-rating, no 80% branch-circuit derate, no cascading trip when
      failover doubles load onto one feed. The 3D layer computes
      `load = (pdu.load_amps || pdu.amps || 12) / 32` (`:641`) — hardcoded 32 A, fabricated 12 A default.
- [ ] **Cabling is visually rich but topologically fake.** The `cables` memo (`:1306-1371`)
      synthesizes links from `rackPosition()` geometry with `if (switchCount > 0 || i <= 8)`
      (`:1314`) — **cables are drawn whether or not a switch exists.** No spine-leaf adjacency, no
      patch panel, no port map, no fiber-vs-copper distance rule. Cable type is guessed from a
      string (`DcCableSystem.jsx:99-104`). `TorSwitch` is instantiated **twice at nearly the same
      coordinates** (`:1437-1438`, y 0.95 and 1.25) labelled "MDF / Spine" and "Leaf / ToR agg" —
      but ToR switches belong *in each rack*.
- [ ] **`u_height` ignored in 3D.** `u_slot` drives Y (`:736`) but multi-U chassis (tracked in
      `physics_ops:31`) all render as 1U. No blanking panels, no visible free-U, no weight
      distribution shown despite `mass_kg` being computed and surfaced only as text (`:931`).
- [ ] No walk-up-and-read environmental sensor objects, no in-world capacity forecast, no BMS/DCIM
      integration surface.

**Bottom line on the 3D game:** roughly 200 lines — collision resolution, a pointer-lock state
machine, and moving two `useState`s to `useRef` — converts this from "camera flying through walls"
to something that genuinely reads as a first-person game. The renderer, art direction and backend
domain model are all much stronger than the player controller.

---

# P1 — AI / ML / LLM / AGENTS / DATA SCIENCE (largest content hole)

817 scenarios across ai-ml (150), ai-infra (195), gpu (172), prompt-engineering (150),
data-science (150). ~78% are template-generated filler. **Coverage of the modern LLM stack is
effectively zero.** Grep counts are over all five verticals' scenario YAML.

| Vertical | Total | `academy-*` | `*-lab-NN` | Hand-crafted |
|---|---|---|---|---|
| ai-infra | 195 | 145 | 0 | **50** |
| gpu | 172 | 99 | 0 | **73** |
| ai-ml | 150 | 100 | 36 | **14** |
| prompt-engineering | 150 | 100 | 0 | **50** |
| data-science | 150 | 100 | 36 | **14** |

Note: `ai-infra` is mis-scoped — it is *datacenter provisioning* (MAAS/PXE/IPMI, Packer, LXD,
VyOS, AWX, DCOps RMA), not AI infrastructure.

## A1. GPU state model is one boolean (P1) — highest-leverage single change
- [ ] [rhel_os.py:473](backend/apps/labs/provisioner/simulation/rhel_os.py#L473) —
      `self.gpu_healthy: bool = True`. That is the *entire* GPU model. Consequences in
      `simulation_modules.py`:
  - `_render_nvlink_status()` (`:568`) always emits `26.562 GB/s` on every link → the "NVLink
    Degraded to Lower Width" lab **cannot show a degraded link**
  - `dcgmi diag -r N` (`:1325`) — the code comment says *"the sim renders a clean pass run"*; every
    subtest is `Pass` at every level → "DCGM Diagnostic Level 1/2/4 Fails" labs **cannot fail**
  - `_render_topo_matrix()` (`:578`) always `NV18`
  - `dcgmi health` always `Healthy`; `dcgmi stats` (`:1362-66`) uses `random.randint` → readings do
    not correlate across calls, which an expert notices immediately
  - `grep -c "OOM\|CUDA out of memory"` in the module = **0**
  - No per-GPU ECC counters, retired pages, XID injection, temperature curve, clock/power state, or
    MIG instance table
- [ ] **Fix:** replace with a per-GPU dataclass — `index, uuid, sku, temp_c, power_w, power_cap_w,
      sm_clock, throttle_reasons[], ecc_volatile/aggregate, retired_pages, remap_pending,
      xid_events[], mig_mode, mig_instances[], persistence_mode,
      nvlink_links[{id, width, active, replay_errors}]`. **Every renderer in
      `simulation_modules.py:386-1216` already exists** — point them at this state and ~70
      hand-written GPU scenarios become genuinely solvable and gradeable **with no UI work.**
- [ ] Make `dcgmi diag` fail from state (map PCIe / GPU Memory / Memory Bandwidth / Targeted Stress
      / Power subtests onto those fields)
- [ ] Drop `random.randint` from `dcgmi stats`; derive from state so readings are diagnosable
- [ ] GPU title coverage is genuinely the best in the repo (XID 48/79, ECC row-remap, NVLink width,
      NVSwitch fabric manager, MIG profiles, MPS, cgroups v2, secure boot, nouveau, ROCm/xGMI, NUMA
      pinning, power cap, DCGM diag levels) — the titles are already written, only the state is missing

## A2. LLM serving — essentially absent (P1)
Grep: `vllm` 3 files, `tensor.parallel` 2. **Zero** for TensorRT-LLM, SGLang, Ollama, llama.cpp,
paged attention, continuous batching, speculative decoding, KV-cache, GPTQ, AWQ, FP8, quantization,
pipeline parallelism.

The entire vLLM simulation is
[simulation_modules.py:859-888](backend/apps/labs/provisioner/simulation/simulation_modules.py#L859)
— 30 lines of fixed strings:
```python
"INFO  tensor_parallel_size=8\n"        # hardcoded — ignores the learner's --tensor-parallel-size
"INFO  Avg prompt throughput: 1842.3 tokens/s\n"
"vllm: READY — OpenAI-compatible /v1/completions"
```
`vllm bench` always returns `42.8 req/s / Mean TTFT: 48.2 ms / Result: PASS`. **It cannot fail.**

- [ ] Build a real vLLM sim: KV-cache blocks, `--gpu-memory-utilization`, `--max-model-len`,
      `--tensor-parallel-size` validated against actual GPU count and weight footprint
- [ ] New scenarios (all genuine first-week vLLM failures):
      *vLLM OOM at startup* (TP size doesn't divide attention heads) ·
      *KV cache exhausted* (`--max-model-len` × concurrency > free VRAM) ·
      *TTFT regression* (chunked prefill disabled) ·
      *AWQ/FP8 load fails* (kernel/compute-capability mismatch) ·
      *speculative decoding regresses throughput* (draft model too large)
- [ ] Add TensorRT-LLM, SGLang, Ollama, llama.cpp tracks

## A3. Distributed training — zero coverage (P1)
**Zero** real hits for FSDP, DDP, DeepSpeed, Megatron, torchrun, mixed precision, gradient
accumulation, bf16, checkpointing. (`ZeRO`=42 and `amp`=17 are substring false positives from
"zero-shot"/"example".) NCCL in 5 files, OOM in 5 — prose only, no simulated state.

- [ ] New vertical: *torchrun FSDP OOM → activation checkpointing* · *NCCL hang requiring
      `NCCL_DEBUG=INFO` + `NCCL_IB_DISABLE` bisection* · *DeepSpeed ZeRO-3 stage misconfig* ·
      *loss→NaN under fp16 needing bf16/loss-scaling* · *checkpoint resume silently dropping
      optimizer state*
- [ ] Multi-node is entirely absent — everything is single-node. No cross-node fabric.

## A4. RAG is 3 hardcoded chunks (P1)
- [ ] [aiml_v2_facades.py:161-179](backend/apps/vmware_sim/aiml_v2_facades.py#L161) returns **the
      same 3 chunks for every query**, with fabricated scores computed as `0.93 - i*0.04`. No
      embedding, no similarity, no index. Only query-dependence is
      `if "crash" in query.lower() or "error" in query.lower()`.
- [ ] `llm_chat` (`:181-193`) is string concatenation:
      `f"[{model}] Based on the lab knowledge base: {prompt[:120]}…"`, tokens faked as `len(prompt)//4`.
- [ ] **Zero** coverage for pgvector, Qdrant, Weaviate, Milvus, FAISS, Chroma, reranking, ragas,
      chunking, token budgeting, LangChain, LlamaIndex, DSPy, LangSmith, Langfuse, MLflow, W&B.
      ReAct 1, embedding 1, streaming 1, prompt injection 4.
- [ ] **Fix:** real RAG engine — small local corpus, deterministic hash embeddings, real cosine
      top-k, tunable chunk size/overlap, optional reranker. Scenarios: *chunk size too large →
      recall collapse* · *no overlap → answer split across boundary* · *reranker off → wrong doc
      cited* · *ragas-style faithfulness/recall scoring*

## A5. Agent simulator — best of the three, but not an agent (P1)
`AgentWorkflowSimulator.jsx` (940 L) over
[aiml_engine.py](backend/apps/vmware_sim/aiml_engine.py) (1240 L). The graph engine (`:539-668`) is
**real** — BFS with branch-aware traversal, payload accumulation, cycle cap, per-node trace. The
React canvas (drag, port-to-port wiring, branch flipping at `AgentWorkflowSimulator.jsx:866-876`)
is well built. `_grade` (`:1174`) checks path-type presence and output requirements — genuinely
fail-closed. Keep all of that.

- [ ] **The "LLM" is a keyword table.** `llm_classify` (`:177-220`) is first-match-wins over
      `_CLASSIFY_RULES` (`:156`); confidence is *arithmetic*: `0.55 + 0.15 * hits` (`:194`).
      `llm_summarize` (`:247`) returns first sentence + `…` + last sentence.
- [ ] **MCP is not MCP.** `_MCP_SERVERS` (`:370-396`) maps `server.tool` → a frozen dict.
      `mcp_call` (`:399`) accepts `args` and **never reads them**. No JSON-RPC, no `tools/list`, no
      input schema, no validation, no error taxonomy. → Add `tools/list`, input schemas, argument
      validation, real error codes.
- [ ] **No agent loop.** It is a static DAG. No ReAct reason→act→observe cycle, no re-planning, no
      scratchpad/memory, no iteration cap, no self-correction. → Add a genuine ReAct loop with cap.
- [ ] **No failure modes.** Tools cannot time out, rate-limit, 500, or return malformed JSON.
      `tool_http_get` (`:323`) only 404s on an unknown URL. → Add injectable failures + retry/backoff.
- [ ] **No cost/latency/token model** — nothing to budget or optimize. → Per-node token+cost
      accounting with a budget the grader enforces.
- [ ] **Only 4 presets** (`:872-877`) for 150 ai-ml scenarios; `_apply_preset` (`:880`) falls back
      to `_preset_support_triage`, and the substring rule `elif "fix" in s` captures a large share of
      slugs by accident.
- [ ] Add a prompt-injection scenario where poisoned tool output actually attempts to hijack the loop

## A6. PromptPlayground is a keyword checker, not a prompt lab (P1)
The file's docstring (`:11-20`) is admirably candid: *"There is NO real language model here."*
Rubric is dual-implemented client
([PromptPlayground.jsx:35-98](frontend/src/components/promptlab/PromptPlayground.jsx#L35)) and
server ([prompt_eval.py:25-52](backend/apps/labs/prompt_eval.py#L25)), so completion is properly
re-gated server-side. Keep that.

- [ ] `analyzePrompt` (`:57-70`) awards "Context" for `words > 25` and "Clear task" for `words >= 6`.
      Grading is `text.includes(...)` over `ROLE_HINTS`/`LIMIT_HINTS`. **A learner passes "Role &
      System Prompts" by typing the literal string `you are` — and fails a genuinely excellent
      prompt that never uses a listed phrase.** `CONTRADICTIONS` (`:41`) has 5 hardcoded pairs.
      Sandbox reply (`:225-231`) is a 3-branch if on the score.
- [ ] It cannot demonstrate the thing prompt engineering *is about* — that different prompts yield
      different outputs. `29-prompt-injection-defense` never actually attacks;
      `50-output-schema-validation-practice` never actually violates a schema.
- [ ] **Fix:** add a tiny deterministic response *generator* so different prompts visibly produce
      different outputs, then grade on **output conformance** (schema valid? under word limit?
      refused off-topic?) rather than input substrings. That is the difference between a checklist
      and a prompt lab.

## A7. Data Science — SQL and notebook façades actively miseducate (P1)
- [ ] [datascience_v2_facades.py:49-70](backend/apps/vmware_sim/datascience_v2_facades.py#L49) —
      the "SQL editor" **parses no SQL**. It branches on `"COUNT" in upper` and otherwise returns
      `rows[:20]` with all columns. WHERE, GROUP BY, JOIN, ORDER BY are **silently ignored while
      reporting `"Query executed"`.** A learner writing a wrong query gets a success message and
      plausible rows. **This is worse than absent — it teaches that incorrect SQL is correct.**
- [ ] `:120-140` — the notebook executes no Python; it substring-matches `head`/`shape`/`len` and
      otherwise returns `"Executed in Lab Environment · N sample rows"`.
- [ ] **Fix:** real execution via SQLite/DuckDB over the in-memory dataset; sandboxed pandas for
      the notebook (the `labs/code_exec.py` sandbox already exists and is well-built)
- [ ] Coverage: pandas 151, jupyter 200, leakage 10, cross-validation 10. **Zero** for polars,
      sklearn, SMOTE, feature store, dbt, Airflow, ARIMA/Prophet, p-value/t-test, DuckDB.
      Spark 1, imbalance 1.
- [ ] New scenarios: leakage detection · imbalanced-data CV strategy · timezone/dtype traps ·
      join-cardinality explosion · missing-data profile · EDA · statistical testing · time-series ·
      Spark · dbt · Airflow · feature stores · experiment tracking
- [ ] *Preserve:* the pivot UI (dimension/measure/aggregation/filter recomputed server-side) and
      hand-rolled SVG bar/line/pie renderers (`DataDashboardSimulator.jsx:116-241`) are genuinely fine

## A8. LLMOps is cosmetic (P2)
- [ ] [aiml_v2_facades.py:20-77](backend/apps/vmware_sim/aiml_v2_facades.py#L20) seeds two
      MLflow-shaped experiments and a registry. `log_run` (`:98`) invents metrics via
      `random.uniform(0.85, 0.96)` — no training produces them, no relationship to params. Registry
      stage transitions are a string field with no gate, no lineage, no rollback.
- [ ] Zero drift detection, A/B, canary, red-teaming. Add model registry gating, drift, canary
      rollout, LLM-as-judge evals, guardrails.

## A9. k8s GPU depth (P2) — cheapest extension
[k8s_cluster.py:26-30](backend/apps/labs/provisioner/simulation/k8s_cluster.py#L26) is the
**honourable exception** — real `gpu_capacity`/`gpu_allocatable`/`gpu_resource` with device-plugin
repair semantics (`:636-644`). Strongest model in the repo.
- [ ] `grep -c "mig\|time-slic"` = **0**. Add MIG profiles, time-slicing, GPU taints/tolerations,
      node autoscaling. Cheapest high-fidelity win in the AI verticals.

## A10. Fresher on-ramp does not exist in AI (P1)
- [ ] All 622 AI-vertical `linked_tutorial` refs are dead slugs (see C1)
- [ ] Every scenario lists prerequisite `Basic ai ml literacy` — undefined and unlinked
- [ ] **No conceptual content**: nothing explains what a token, embedding, attention head, GPU
      memory hierarchy, or batch *is*. Labs jump straight to "fix the broken thing."
- [ ] The `Learn Lab` scenarios (`academy-ai-ml-001-learn-dataset`, `academy-gpu-001-learn-drivers`)
      are the on-ramp *by name* but are the nginx/nvidia-smi shells — they teach nothing
- [ ] Only 5 real ai-ml coding labs exist, all classical numerics (gradient step, kNN, TF-IDF).
      **A fresher cannot learn anything about LLMs here.**

## A11. Experienced engineer has nothing to bite on (P1)
- [ ] Success is a banner-string grep, so an expert clears any GPU lab in one command with zero diagnosis
- [ ] No metric-driven work: no latency/throughput/TTFT/ITL/tokens-per-sec/cost targets to optimize
- [ ] Every hard failure mode an SRE actually hits — Xid 13/31/48/79 mid-run, ECC row-remap pending
      forcing a drain, NCCL hang, CUDA OOM at a specific batch/seq-len, thermal throttle under
      sustained load — is a **scenario title with no simulated state behind it**

---

# P1 — SIMULATOR FIDELITY (non-AI)

**Good news first: no simulator in scope is a pure hardcoded-string stub.** All 22 backend engines
share one shape (`_base_state()` → `_apply_preset(slug)` → `apply_action()` → `validate_*_lab()`,
Django-cache-persisted, `SESSION_TTL = 7200`), and **21 of 22 have fail-closed validators a
do-nothing learner cannot pass.** OpenStack is the single exception (0 validators — see G6).

**The real fidelity problem: config files and service state are decoupled.**

| Simulator | LOC | State-driven | Fidelity | Biggest gap |
|---|---|---|---|---|
| VyOS | 386 fe | Yes — candidate/running DB | **5** | No `show interfaces` counters/errors; no config-tree validation on commit |
| Nmap | 1120 + 1245 | Yes — protocol decision tree | **5** | NSE scripts catalog-only; no `-sU`/`-sA`/`-O` depth |
| MAAS/baremetal | 1150 + 2480 | Yes — wall-clock FSM | **4.5** | No curtin/preseed authoring |
| Wireshark | 1108 + 903 | Yes — dual filter evaluators | **4.5** | Fixed packet corpus; no live capture; no IO graph |
| Monitoring | 1811 + 1389 | Yes — real PromQL | **4.5** | No alert-rule YAML → evaluation loop; no Alertmanager routing/silences |
| Backend RHEL shell | 5840 | Yes — VFS + exit codes | **4** | `systemctl start` ignores `nginx -t`; no unit-file parsing |
| K8s | 773 + 1205 | Yes — object graph, `apply -f` parses YAML | **4** | No RBAC denial, no admission webhooks |
| VMware | 3111 + 871 + 3550 | Yes — inventory graph, perf tick | **4** | DRS/HA/vMotion outcome-only; no resource-pool admission control |
| IDE | 2194 | N/A — real code validation | **4** | — |
| Windows | 1371 + 1710 | Yes — AD/GPO/SCCM world | **3.5** | **No PowerShell at all**; no service dependency chain; GPO precedence not computed |
| CI/CD | 1010 + 580 | Yes — real YAML parser | **3.5** | Faults from catalog, not from parsed YAML — fixing the file doesn't clear the fault |
| Docker | 638 + 1102 | Yes | **3.5** | No Dockerfile build-layer semantics; compose shallow |
| Terraform | 1449 + 993 | Partial — regex HCL probe | **3** | `_hcl_has_private_nat_route` (`:324-338`) greps two substrings; no HCL parse, no graph, no state file |
| AWX | 843 + 988 | Partial | **3** | `will_fail` is a **preset boolean** (`awx_engine.py:206,211`), never derived from playbook content |
| LXD | 810 | Yes | **3** | No `lxc exec` into instance shell |
| OpenStack | 398 + 458 | Yes — **0 validators** | **3** | Ungradeable; no `openstack` CLI |
| Packer | 707 + 627 | Weak — single marker | **2.5** | `_has_nvidia_marker` (`:57-62`) — any file containing "nvidia" passes |
| SOC | 587 + 416 | Yes — generic `broken` | **2.5** | No query language (SPL/KQL); static alert rows |
| Commvault | 579 + 494 | Yes — job FSM | **2.5** | No restore-verify; retention/dedup not modeled |
| PeopleSoft | 1331 + 1219 | Yes | **2** | Thin PIA surface |
| NetApp | 597 + 373 | Yes — generic `broken` | **2** | 373 LOC for all of ONTAP; no CLI, no capacity math on write |
| Dell EMC | 602 + 350 | Yes — generic `broken` | **2** | Thinnest engine; 12 actions total |
| Azure | 855 + 810 | Yes — 20 actions | **2** | **No `az` CLI**; no ARM/Bicep; portal-only |
| GCP | 692 + 650 | Yes — 15 actions | **2** | **No `gcloud` CLI**; no IAM policy evaluation |
| ITSM | 425 | Partial | **2** | No workflow state machine / SLA clock |

## F1. Gate `systemctl start` on config validity (P0) — highest fidelity-per-line
- [ ] [rhel_shell.py:1563-1566](backend/apps/labs/provisioner/simulation/rhel_shell.py#L1563) —
      `if action == "start": svc.active = "active"` **unconditionally.** Meanwhile `nginx -t` at
      `rhel_shell.py:2724-2737` **already reads the real VFS** and correctly emits
      `nginx: [emerg] open() ... failed`. The validation exists and is never called from the start path.
- [ ] Same in [linuxShell.js:2231-2240](frontend/src/components/vmware/linuxShell.js#L2231).
      `services` is seeded as a flat dict at `:928-940`, **entirely disjoint from the VFS**. Unit
      files *are* written (`:747`, `:762`) and `nginx.conf` at `:648` — **nothing ever parses them.**
      `systemctl status` fabricates the ExecStart line from the service *name* (`:2225`, `:2228`).
- [ ] Net effect today: **a learner can corrupt `nginx.conf` beyond repair and `systemctl start
      nginx` still reports active.** `failed` is only reachable if a preset seeds it.
- [ ] ~10-line fix with outsized payoff: on config-check failure set `active = "failed"`,
      `last_exit_code = 1`, emit the real systemd text (`Job for nginx.service failed because the
      control process exited with error code.`). **This single change makes every "break the
      config, fix the config" lab genuinely causal.**

## F2. Parse unit files from the VFS (P0)
- [ ] Both shells *write* unit files they never read. Read `ExecStart`/`WantedBy` so
      `systemctl cat`/`show`/`enable` reflect edits, and a malformed unit fails to load.

## F3. `journalctl -u` is a fixed two-branch template (P1)
- [ ] [linuxShell.js:2262-2272](frontend/src/components/vmware/linuxShell.js#L2262) — keyed only on
      `s.active === 'failed'`, **always** cites the same
      `bind() to 0.0.0.0:80 failed (98: Address already in use)` regardless of which service or what
      the config says. Derive from actual state + config.

## F4. Reconcile frontend/backend shells (P1)
- [ ] Browser shell: 244 verbs, **no exit codes**, no pipes/redirection into the VFS, no `nginx -t`.
      Backend: ~200 handlers, full exit codes (`is-active` unknown unit → 3, `is-enabled` → 1,
      `status` → 4, `reload` on stopped → 5, at `rhel_shell.py:1531-1580`), config reads.
      **The same learner action grades differently depending on which terminal they used.**
- [ ] Port exit codes + `nginx -t` into `linuxShell.js`, or route the VMware guest terminal to the
      backend engine.

## F5. Derive faults from parsed input, not from slug catalogs (P1)
- [ ] **CI/CD:** [CicdPipelineSim.jsx:357-361](frontend/src/components/devops/CicdPipelineSim.jsx#L357)
      injects faults from `CICD_FAULTS_CATALOG` keyed by scenario slug while `parsePipeline` runs
      independently at `:159`. Wire fault detection to the parsed model so correcting the `image:`
      tag or adding `needs:` actually turns the job green.
- [ ] **AWX:** derive `will_fail` from playbook content, not the preset boolean at
      [awx_engine.py:206](backend/apps/vmware_sim/awx_engine.py#L206). Job stdout (`:221`) is
      templated from that boolean.
- [ ] **Packer:** replace the marker scan at
      [packer_factory.py:57](backend/apps/vmware_sim/packer_factory.py#L57) with HCL block parsing —
      require an actual `provisioner "shell"` block referencing the driver install.
- [ ] **Terraform:** real HCL parsing at
      [terraform_engine.py:324](backend/apps/vmware_sim/terraform_engine.py#L324) — parse
      blocks/attributes, build a dependency graph, emit true `+/-/~` plan diffs and a state file.

## F6. Missing primary interfaces (P1)
- [ ] **PowerShell for Windows.** Zero matches for `Get-`/cmdlets. Even 30 cmdlets
      (`Get-Service`, `Get-ADUser`, `Set-ADAccountPassword`, `Unlock-ADAccount`,
      `Install-WindowsFeature`, `Get-GPO`) over the **existing** `_base_world()` roughly doubles
      fidelity — the state model is already there, only the language surface is absent.
- [ ] **`az` CLI** over the existing 20 Azure engine actions (reachable only by clicking today)
- [ ] **`gcloud` CLI** over the existing 15 GCP actions
- [ ] **`openstack` CLI** for OpenStack (151 scenarios)
- [ ] **ONTAP CLI** for NetApp (`volume show`, `snapmirror show`)

## F7. Depth backlog (P2)
- [ ] Windows: service dependency chains (stopping a dependency cascades); computed GPO precedence
      (LSDOU + enforcement)
- [ ] Wireshark: live capture fed from nmap/networking state instead of the fixed
      `_full_packet_set()` (`wireshark_engine.py:100`)
- [ ] Monitoring: alert-rule authoring → evaluation → firing loop with Alertmanager routing + silences
- [ ] NetApp (373 L) / Dell EMC (350 L): capacity arithmetic enforced on write
- [ ] SOC: SPL or KQL subset so hunting is a skill, not row-clicking
- [ ] K8s: RBAC denials, admission webhooks
- [ ] VMware: resource-pool admission control; make DRS/HA/vMotion causal not outcome-only
- [ ] Docker: Dockerfile build-layer semantics, deeper compose
- [ ] LXD: `lxc exec` into instance shell
- [ ] ITSM: workflow state machine + SLA clock
- [ ] Missing across the board: exit codes in the frontend shell, resource-exhaustion errors (disk
      full on write, OOM), permission denials on config edits, partial/timeout failures, cascading
      dependency failures

## F8. Preserve these — they are genuinely high fidelity
- Nmap `nmap_engine.py:539-588` models the real TCP/ICMP decision tree (ICMP-blocked host missed by
  `-sn` but revealed by SYN touching an open port; `-Pn` overrides; stateful firewall turns open →
  filtered unless `sudo` + `-sS`). Real protocol reasoning, not a lookup table.
- Wireshark `wireshark_engine.py:303-400` recursive display-filter evaluator (field presence, `!=`
  via negated `==`, `and/or/not`, flag predicates, `tcp.analysis.retransmission`) + separate BPF
  capture-filter evaluator (`:239`).
- Monitoring `monitoring_engine.py:184, 440-502` real PromQL — `sum|avg|min|max|count|stddev|stdvar|
  topk|bottomk|quantile` with `by()`, plus `rate/irate/increase/delta/deriv/histogram_quantile` with
  true counter slopes and interpolated `le` buckets.
- VyOS `vyos_views.py:50-125` — the only simulator that correctly models a two-stage commit database
  (`commit-confirm N`/`confirm`/`rollback N`/`compare`/`discard`, candidate vs running, `?`/Tab help).
- MAAS `baremetal_engine.py:1019-1090` wall-clock FSM (Commissioning → Ready → Deploying → Deployed)
  with `phase_duration`, threshold-triggered log lines, terminal-state branching incl. `Failed testing`.
- NetApp `netapp_engine.py:238-247` — breaking SnapMirror pops exactly the seeded key; a do-nothing
  learner cannot pass.

---

# P0/P1 — LEARNING PATH: THE LAYERS EXIST, THE WIRING IS SEVERED

The four layers are individually populated and the *models* are well-designed. Almost every
cross-layer link is broken, unresolved, or has no UI.

## C1. 5,403 scenarios point at tutorial slugs that do not exist (P0)
Independently confirmed twice. **0 of 44 distinct `linked_tutorial` values resolve.** Every
scenario points at `<tech>-fundamentals`; every real course is `<tech>-<topic>-zero-hero`. The two
namespaces never intersect.

**Worse — the field is dead code.** `linked_tutorial` is **not a field on the `Scenario` model**,
and `seed_scenarios.py:284-300` never reads it. Its only appearance is the validator, which
**auto-fabricates the broken value**:
```python
# validate_scenario_catalog.py:286
set_missing("linked_tutorial", f"TODO: link-tutorial-for-{_tech_from_path(path)}")
```
The check at `:329` only asserts non-emptiness, so the fabricated string always passes.

- [ ] Add `linked_tutorial` as a real `Scenario` model field + serializer
- [ ] Ingest it in `seed_scenarios.py:284`
- [ ] Apply the 44-row slug mapping (41 of 44 resolve to an existing course):

| Dangling | N | → real `course_slug` |
|---|---|---|
| `aws-fundamentals` | 420 | `aws-cloud-zero-hero` |
| `linux-fundamentals` | 191 | `linux-sysadmin-zero-hero` |
| `gpu-fundamentals` | 172 | `gpu-nvidia-zero-hero` |
| `windows-fundamentals` | 151 | `windows-server-zero-hero` |
| `terraform-fundamentals` | 150 | `terraform-iac-zero-hero` |
| `database-fundamentals` | 150 | `database-engineering-zero-hero` |
| `postgresql-fundamentals` | 150 | `postgresql-dba-zero-hero` |
| `nodejs-fundamentals` | 150 | `nodejs-zero-hero` |
| `rhel-linux-fundamentals` | 150 | `rhel-linux-zero-hero` |
| `devops-fundamentals` | 150 | `devops-engineering-zero-hero` |
| `docker-fundamentals` | 150 | `docker-containers-zero-hero` |
| `python-fundamentals` | 150 | `python-devops-zero-hero` |
| `peoplesoft-fundamentals` | 150 | `peoplesoft-zero-hero` |
| `data-science-fundamentals` | 150 | `data-science-zero-hero` |
| `security-fundamentals` | 150 | `cybersecurity-zero-hero` |
| `prompt-engineering-fundamentals` | 150 | `prompt-engineering-zero-hero` |
| `networking-fundamentals` | 150 | `tcpip-networking-zero-hero` |
| `baremetal-fundamentals` | 150 | `bare-metal-datacenter-zero-hero` |
| `grafana-fundamentals` | 150 | `grafana-visualization-zero-hero` |
| `java-fundamentals` | 150 | `java-zero-hero` |
| `html-fundamentals` | 150 | `html-web-zero-hero` |
| `sqlite-fundamentals` | 150 | `sqlite-embedded-zero-hero` |
| `ansible-fundamentals` | 150 | `ansible-automation-zero-hero` |
| `ai-ml-fundamentals` | 150 | `ai-infrastructure-zero-hero` |
| `shell-script-fundamentals` | 150 | `bash-shell-zero-hero` |
| `mysql-fundamentals` | 150 | `mysql-dba-zero-hero` |
| `prometheus-fundamentals` | 150 | `prometheus-grafana-zero-hero` |
| `javascript-fundamentals` | 150 | `javascript-language-zero-hero` |
| `nmap-fundamentals` | 150 | `nmap-zero-hero` |
| `kubernetes-fundamentals` | 150 | `kubernetes-platform-zero-hero` |
| `react-fundamentals` | 150 | `react-frontend-zero-hero` |
| `wireshark-fundamentals` | 150 | `wireshark-zero-hero` |
| `vmware-fundamentals` | 150 | `vmware-vsphere-zero-hero` |
| `devsecops-supplychain-fundamentals` | 26 | `devsecops-zero-hero` |
| `gitops-fundamentals` | 26 | `argocd-gitops-zero-hero` |
| `opentelemetry-fundamentals` | 25 | `jaeger-tracing-zero-hero` |
| `service-mesh-fundamentals` | 25 | `kubernetes-deep-zero-hero` |
| `soc-fundamentals` | 6 | `soc-operations-zero-hero` |
| `azure-fundamentals` | 3 | `azure-cloud-zero-hero` |
| `gcp-fundamentals` | 3 | `gcp-cloud-zero-hero` |
| `datacenter-fundamentals` | 2 | `bare-metal-datacenter-zero-hero` |
| `netapp-` / `commvault-` / `dellemc-fundamentals` | 1 ea | **no course exists — must author** |

- [ ] Change `validate_scenario_catalog.py:286` to **fail** on an unresolvable slug instead of
      fabricating one

## C2. AWS tutorials all link to a Terraform lab (P0) — one-line fix, 421 labs
- [ ] [completeness.py:184-185,199](backend/apps/tutorials/management/commands/curriculum/completeness.py#L184)
      hardcodes `"aws": "terraform"`, `"azure": "terraform"`, `"gcp": "terraform"`. 421 AWS
      scenarios exist under `scenarios/aws/`, yet **every AWS tutorial links to a Terraform lab.**
      Drop the aliases. **Highest ROI single change on the platform.**
- [ ] Same file: 130 of 830 tutorials fall back to `academy-linux-001-learn-users-groups` — a Redis
      or MongoDB learner is sent to a Linux users/groups lab. (570 exact, 130 glob, 130 fallback.)
      Affected: Redis, MongoDB, Jenkins, Django, ELK, Jaeger, pfSense, Cisco.

## C3. 213 projects, 0 launchable labs, 0 validated tasks (P1)
`seed_projects.py:11367-11369` appends `EXTRA_PROJECTS`, so the real total is **213** (149 + 64),
across 37 of 44 technologies, with **1,255 tasks**.

- [ ] **`ProjectTask.validation_scenario`: 0 of 1,255 populated.** All tasks are self-attested.
      The model supports real grading — [models.py:509-520](backend/apps/question_bank/models.py#L509)
      gates completion on a passed `LabSession` — and `test_project_stages.py:200`
      (`test_done_blocked_without_passed_lab`) proves the machinery works. It is simply unused.
- [ ] **`Project.lab_scenario`: 0 of 213 populated** ([models.py:399-406](backend/apps/question_bank/models.py#L399)).
      **Nothing launches an environment.** A "project" is a checklist of tickets the user ticks
      off themselves.
- [ ] **No `/projects` route** in `AppRouter.jsx` — confirmed. Projects are reachable only as a
      *tab* on [TechnologyDetail.jsx:687](frontend/src/pages/TechnologyDetail.jsx#L687) (start call
      works at `:310`). No browsable index.
- [ ] Zero projects for 8 technologies: `azure`, `gcp`, `soc`, `rhel-linux`, `datacenter`, `netapp`,
      `dellemc`, `commvault`
- [ ] Only **1 staged/cross-tech capstone in 213** (`capstone-black-friday-sre-incident`, 7 stages)
      despite full `ProjectStage` support with handoff artifacts and breakpoint notes.
      `docs/ROADMAP.md:53` already flags this.
- [ ] Difficulty: 44 beginner / 71 intermediate / 98 advanced

## C4. 5 journeys, invisible, with a dead first step (P0)
| Journey | Tech | Level | Steps |
|---|---|---|---|
| `junior-linux-admin-rhcsa` | linux | beginner | 7 |
| `cloud-engineer-terraform-aws` | terraform | intermediate | 7 |
| `kubernetes-sre-cka` | kubernetes | advanced | 6 |
| `devsecops-engineer-supply-chain` | devsecops | advanced | 6 |
| `sre-incident-responder` | prometheus | advanced | 6 |

- [ ] **No frontend route, no consumer.** `/api/journeys/` is registered
      (`config/urls.py:110`) but grep finds **zero** references to `/journeys` anywhere in
      `frontend/src/`. The entire journey layer is unreachable. Add `/journeys` + `/journeys/:slug`.
- [ ] **Tutorial steps never resolve.**
      [journeys_views.py:78-91](backend/apps/question_bank/journeys_views.py#L78) pre-resolves
      `Scenario`, `Project` and `CertificationTrack` titles but **never queries `Tutorial`**. So
      `tutorial_course` steps always fall back to stored text — **the first step of every journey is
      a dead label.**
- [ ] Only 5 journeys for 44 technologies, and **4 of 5 are intermediate/advanced** — exactly one
      beginner on-ramp exists. Author beginner journeys for AWS, Python, Docker, security, AI/data.
- [ ] Validated all 37 step refs: 34 resolve, 3 broken (all `certification` steps — `rhcsa`,
      `terraform-associate`, `cka` — resolve at runtime once cert YAML is seeded; low risk)
- [ ] *Preserve:* step ordering (tutorial→scenarios→project→cert→milestone) is coherent

## C5. Cert pools erode silently (P0)
| Track | Tech | Dur | Pass | Obj | Pool | Dangling | Usable |
|---|---|---|---|---|---|---|---|
| RHCSA | linux | 180m | 70% | 9 | 70 | 18 | 52 |
| RHCE | ansible | 240m | 70% | 7 | 51 | 7 | 44 |
| CKA | kubernetes | 120m | 66% | 5 | 52 | 16 | 36 |
| CKAD | kubernetes | 120m | 66% | 5 | 45 | 15 | 30 |
| CKS | kubernetes | 120m | 67% | 6 | 39 | 5 | 34 |
| LFCS | linux | 120m | 67% | 5 | 49 | 9 | 40 |
| Terraform Assoc | terraform | 60m | 70% | 8 | 17 | 0 | 17 |

- [ ] **70 of 323 (21.7%) exam-pool scenario refs point at non-existent scenarios** (e.g.
      `sim-k8s-rbac`, `linux-ssh-key-auth-fail`). With `EXAM_SCENARIOS_PER_OBJECTIVE = 2`
      ([views.py:43](backend/apps/certifications/views.py#L43)), an objective whose pool erodes
      below 2 **stops randomizing** — repeat attempts serve identical scenarios. Purge and enforce
      ≥2 live scenarios per objective.
- [ ] Certs cover only **4 of 44** technologies (linux, kubernetes, ansible, terraform).
      **No AWS, Azure, GCP, Python, security, or networking cert.** Add them.
- [ ] **Proctoring: none.** No webcam, lockdown, tab-switch or fullscreen detection anywhere in
      `certifications/views.py`. Integrity rests solely on the attempt-window constraint. Add basic
      signals before certs carry external weight.
- [ ] *Preserve — this is the best-built part of the platform:* scoring
      ([views.py:389-446](backend/apps/certifications/views.py#L389)) counts completions only
      *inside the attempt window* (`since=attempt.started_at`), re-reads weights from the DB rather
      than trusting the snapshot, and divides by the **full track weight** so an untested objective
      drags the score down — a cert cannot be earned on partial coverage. Certificates issue with
      UUID + unique `certificate_id`, public verification, and Ed25519-signed **Open Badge 3.0 /
      W3C VC** credentials (`openbadge.py`, `models.py:238-279`) that re-verify offline.

## C6. Tutorials — deepest content on the platform, wrong taxonomy (P1/P2)
**83 courses × 10 modules = 830 tutorials.** `completeness.py:98-152` enforces 6 sections, exactly
1 architecture + 1 sequence Mermaid diagram, a shell block with expected output, a **5-question
quiz**, ≥2 callouts, and a linked lab. This is genuinely strong.

- [ ] **Zero tutorial coverage for 21 technologies:** `ai-infra`, `ai-ml`, `commvault`,
      `data-science`, `database`, `datacenter`, `dellemc`, `devsecops-supplychain`, `gitops`,
      `grafana`, `netapp`, `nmap`, `opentelemetry`, `prometheus`, `prompt-engineering`, `react`,
      `rhel-linux`, `service-mesh`, `shell-script`, `soc`, `wireshark`
- [ ] **Many are only *nominally* missing** — courses exist under a divergent `playground_slug`
      taxonomy (`aiml`, `bash`, `monitoring`, `nginx`, `redis`, `git`, `github`, `gitlab`,
      `mongodb`, `simulation`) that **never joins to canonical `Technology.slug`.** Unify the
      taxonomy (`aiml`→`ai-ml`, `bash`→`shell-script`, `monitoring`→`prometheus`/`grafana`) —
      makes ~10 existing courses discoverable **with no new authoring.**
- [ ] Author tutorials for `netapp`, `commvault`, `dellemc` (no course exists at all)
- [ ] `github-actions-zero-hero` is **duplicated** across `course_catalog.py` and
      `course_catalog_tracks.py`

## C7. Fresher path traced — where it actually breaks (P0)
**Answer: no technology currently works end-to-end.** The content largely exists; the connective
tissue does not. There is no `/projects` or `/journeys` route, so a logged-in beginner **has no
"start here" surface at all.** The intended path exists only in the database.

- **Linux — closest to working.** `linux-sysadmin-zero-hero` (10 modules, quizzes, diagrams) →
  `academy-linux-001-learn-users-groups` resolves exactly → 7 projects → RHCSA/LFCS with a real
  exam engine and a verifiable badge. Journey `junior-linux-admin-rhcsa` chains all of it correctly.
  **Breaks:** journey unreachable (C4); its tutorial step never resolves (C4); all 7 Linux projects
  launch no lab and self-attest (C3); 18/70 RHCSA pool refs dangle (C5). A determined fresher *can*
  self-assemble Linux competence — but only by ignoring the guidance layer.
- **AWS — breaks hardest, despite the most content.** 421 scenarios + a 10-module course exist. But:
  the 420 scenarios' `linked_tutorial` refs are dead **and the field isn't even ingested** (C1); the
  tutorial links *forward* to a **Terraform** lab (C2), never touching `academy-aws-001-learn-ec2`;
  the only AWS-bearing journey is *intermediate* Terraform-first; **there is no AWS certification**;
  and **all 420 labs are unpassable** (G4). Largest content-to-value gap on the platform.
- **AI/Data — breaks earliest.** `ai-infra` (9 projects) and `ai-ml` (6) have **zero tutorials
  under their canonical slugs**; `ai-engineering-zero-hero` and `ai-infrastructure-zero-hero` sit
  under `playground_slug: aiml` which never joins to `Technology.slug`, so they are **invisible from
  the technology page**. No AI/data journey, no cert, projects self-attest. **A fresher cannot even
  find the entry point.**

## C8. Experienced path — dead-ends later (P1)
- [ ] Ceiling is CKS; no expert tier beyond
- [ ] Advanced journeys unreachable (C4)
- [ ] **Because no project validates against a lab, a senior gets no signal harder than a checkbox**
- [ ] Only 1 staged cross-tech capstone in 213 (C3)
- [ ] No difficulty granularity in the corpus: **zero scenarios use beginner/intermediate/advanced/
      expert.** Only `easy` (1330) / `medium` (4374) / `hard` (1576). 60% is `medium`. Consider a
      real `expert` tier.

---

# P1 — FRONTEND

Build/lint/test all pass: `npm run build` exit 0 in 31.36s; `npm run lint` exit 0 with **229
warnings** (0 errors — passes only because `--max-warnings 300`; headroom 71); `npm test` **83
passed / 0 failed / 0 skipped** in 19 files.

## W1. No refresh mutex — highest-probability user-facing bug (P0)
- [ ] [api/client.js:64-92](frontend/src/api/client.js#L64) — no `isRefreshing` flag, no
      `failedQueue`. Grep for `isRefreshing|refreshPromise|failedQueue` returns **nothing**.
      Any page firing parallel requests that 401 together fires **N concurrent
      `POST /api/auth/refresh/`**. [Dashboard.jsx:161](frontend/src/pages/Dashboard.jsx#L161) fires
      **10**. With refresh-token rotation/blacklisting (which `auth.js:44` confirms the backend
      does), the first rotates and the rest present a blacklisted token → fail →
      `redirectToLogin()` at `:88` → **user bounced to `/login` mid-session** with "Your session has
      expired." Lands exactly on the busiest page.
- [ ] Fix: single in-flight refresh promise + queue for concurrent 401s

## W2. Cross-user state leak on logout (P0)
- [ ] [api/auth.js:37-52](frontend/src/api/auth.js#L37) resets only `resetAwsSimOnLogout()` +
      `store.logout()`. **Never reset:** `notificationStore` (`notifications[]`, `unreadCount`),
      `dataStore` (`technologies` + 5-min TTL cache), `labStore` (`activeSession`).
- [ ] Logout navigates via **SPA `navigate('/login')`** (`MainLayout.jsx:179-181`,
      `Profile.jsx:759`), not a full reload, so the JS heap survives. User A logs out → User B logs
      in same tab → `NotificationBell` renders **A's notifications and unread badge** until the 60s
      poll at `NotificationBell.jsx:28`.
- [ ] Note the asymmetry that hid this: `api/client.js:55` (`redirectToLogin`) **does** use
      `window.location.href`, so the forced-401 path is safe. Only user-initiated logout leaks.
- [ ] Fix: add `reset()` to all three stores and call from `auth.js:52`, or make logout a hard
      `window.location.href = '/login'`

## W3. 707kB gzip eager critical path (P0)
`dist/index.html` `modulepreload`s these on **every** page load including `/`, `/login`, `/pricing`:
`index 185kB · vendor 161kB · icons 877kB · state 53kB · lab-shared 25kB · aws-console 1214kB ·
proxy 108kB · index.css 325kB · aws-console.css 33kB` = **2,982kB raw / 707kB gzip.**

Root cause: [App.jsx:13](frontend/src/App.jsx#L13) **statically** imports `awsStore`, and
[vite.config.js:52](frontend/vite.config.js#L52) maps everything under `/src/components/aws/` to the
`aws-console` chunk. So one import drags the entire AWS console (awsStore 2,294 LOC →
`SERVICE_CONFIGS`, `iamEngine`, `instanceTypes`, `lifecycle`) into the entry graph. `AwsConsole` **is**
correctly `lazyWithRetry`'d at `AppRouter.jsx:84` — that boundary is simply defeated.
**A logged-out visitor downloads ~1.2MB of AWS EC2/IAM simulator to see the login page.**

- [ ] Make `App.jsx:13`, `api/auth.js:3`, `pages/LabRunner.jsx:17` dynamic-import `awsStore`, or
      move it out of `/components/aws/`. Cuts first paint by ~322kB gzip (~45%).
- [ ] Split the `icons` chunk ([vite.config.js:46](frontend/vite.config.js#L46)) — 256
      `from 'lucide-react'` sites forced into one always-loaded 898kB chunk, defeating tree-shaking.
      ~167kB gzip off the eager path.

**Chunks over 500kB (7):**
| Chunk | Raw | Gzip |
|---|---|---|
| `DatacenterTwin3D` | 3,086.75 kB | 1,052.09 kB |
| `aws-console` | 1,242.35 kB | 329.75 kB |
| `icons` | 898.34 kB | 167.58 kB |
| `CodeEditor` | 788.06 kB | 270.38 kB |
| `cynefin-VYW2F7L2` | 690.57 kB | 154.58 kB |
| `mermaid.core` | 605.68 kB | 140.40 kB |
| `cytoscape.esm` | 443.69 kB | 141.74 kB |
| `BaremetalSimulator.css` | 461.24 kB | 58.29 kB |

- [ ] `DatacenterTwin3D` is correctly lazy but a **1MB gzip transfer on click with only a generic
      `PageLoader` spinner.** Add a progress UI; narrow the `drei` imports.

## W4. Memory leak in PaymentPage (P1)
- [ ] [PaymentPage.jsx:211-216](frontend/src/pages/PaymentPage.jsx#L211) — the only effect in the
      codebase with listeners and no cleanup:
      ```js
      existing.addEventListener('load', () => setRazorpayReady(true))
      existing.addEventListener('error', () => setRazorpayFailed(true))
      return   // <- bare return, no cleanup fn
      ```
      Both closures leak per mount + `setState` after unmount.
- [ ] Cleanup hygiene elsewhere is genuinely strong (75 `clearInterval` vs 59 `setInterval`;
      63 `removeEventListener` vs 77 `addEventListener`; `LabTerminal.jsx:583-594` nulls
      `ws.onclose` before close and disposes xterm). This is the lone outlier.

## W5. 104 `.catch(() => [])` sites hide failures as empty states (P1)
56 of ~60 data-fetching pages have **no error state** — only `loading` and empty. The boundary never
fires; the user sees "No bookmarks yet" instead of "couldn't load."
- [ ] [Dashboard.jsx:161-171](frontend/src/pages/Dashboard.jsx#L161) — 10 parallel calls, each
      `.catch(() => null/[])`. Only `prog` sets `loadError` (`:174`); **the other 9 fail invisibly.**
      A user with an active lab sees an empty dashboard on a backend blip.
- [ ] Same: `Achievements.jsx:27`, `Profile.jsx:60-65`, `SessionReplay.jsx:26-27`, `Team.jsx:96`
- [ ] No loading *or* error state (render blank on failure): `About.jsx:205`,
      `home/HomePage.jsx:40`, `home/sections/CertificationsSection.jsx`
- [ ] 3 fully empty `catch {}` blocks
- [ ] `LabHistory.jsx:42` and `Bookmarks.jsx:31` do it right (toast + empty state) — apply broadly
- [ ] *Preserve:* the top-level error architecture is genuinely well done — `App.jsx:88` global
      boundary, `AppRouter.jsx:146` per-route boundary keyed on `location.pathname` (a crash
      self-heals on navigation), `lazyWithRetry.js` + `main.jsx:23-41` handling all three
      stale-chunk surfaces (`vite:preloadError`, `window.error`, `unhandledrejection`)

## W6. Zero request cancellation (P1)
- [ ] `AbortController|CancelToken|signal:` → **0 matches in 130k LOC.** 21 `useEffect`
      fetch→`setState` chains have no unmount guard: `Dashboard.jsx:160`, `Profile.jsx:56`,
      `LabRunner.jsx:896`, `InterviewRoom.jsx:1212`, `Pricing.jsx:163` and `:174`,
      `BlogPost.jsx:737` and `:755`, `MainLayout.jsx:150` and `:158`. Fast navigation → setState on
      unmounted component + wasted in-flight requests.
- [ ] Introduce a shared `useFetch` with `AbortController` + real error state; retrofit those 21
- [ ] No retry/backoff for idempotent GETs (the only "retry" is the 401 replay)
- [ ] Single global 45s timeout; no per-call override for slow lab provisioning vs fast reads

## W7. 403 handled inconsistently (P2)
- [ ] No central rule. Four modules special-case it locally (`api/monitoring.js:5`, `api/vmware.js:5`,
      `api/nmap.js:18`, `api/wireshark.js:19`) to soft-open demos; everywhere else a 403 falls
      through silently (the 500+ branch starts at `>= 500`). **A user hitting an entitlement
      boundary gets a blank panel and no explanation.** Centralize alongside 429/500.

## W8. Storage keys unscoped and unversioned (P2)
37 localStorage + 46 sessionStorage calls, **no versioning anywhere**.
`utils/userScopedStorage.js` exists (`userScopedKey`) but has only **3 consumers**
(`tutorialProgress.js:1`, `aws/ui/primitives.jsx:4`, `useInterviewVoice.js:213`); `awsStore.js:32`
reimplements it.
- [ ] Unscoped, survive logout, shared across accounts on one browser:
      `fixitlab_changelog_dismissed` (`ChangelogModal.jsx:5`),
      `fixitlab_tour_completed` (`OnboardingTour.jsx:41`),
      `fixitlab_support_bot_hidden` (`SupportBotWidget.jsx:7`),
      `fixitlab_campaigns_dismissed` (`CampaignBanner.jsx:6`),
      `fixitlab_ide_auth` (`CodingIDE.jsx:44`)
- [ ] **Worst: `fixitlab:ide-draft:${sessionId}`** (`CodingIDE.jsx:41`) — **user-authored code**,
      keyed by sessionId only, never expired, readable by the next account on that browser
- [ ] No key carries a schema version. `aws/ui/primitives.jsx:190` parses into `visibleKeys` with no
      shape validation.
- [ ] *Preserve:* `authStore.js:31` correctly keeps tokens out of localStorage (`partialize`
      persists only `user`/`isAuthenticated`); `labStore` guards timer expiry with `timerSessionId`

## W9. Accessibility — forms are unusable on a screen reader (P1)
| Check | Result |
|---|---|
| Form controls without `aria-label`/`aria-labelledby`/`id` | **1,088 / 1,098 (99%)** |
| `<label htmlFor>` in the entire app | **6** |
| Icon-only buttons without accessible name | **71** |
| `aria-label` total uses | 88 (vs 2,268 `<button>`) |
| `aria-live` regions | **1** |
| `role="dialog"`/`aria-modal` | 8 of ~50 modals |
| Pages with `h2`/`h3` but no `h1` | **56** |
| `<img>` missing alt | 0 real (3 `alt=""` correctly decorative) |

- [ ] Label the top-5 offenders (~190 of 1,088): `windows/os/apps/ADUC.jsx` (55),
      `monitoring/MonitoringSimulator.jsx` (37), `vmware/VmwareResourceModals.jsx` (37),
      `admin/AdminSettings.jsx` (31), `admin/AdminScenarios.jsx` (29)
- [ ] Add `aria-label` to the 71 icon-only buttons
- [ ] **`aria-live` count of 1** against a UI whose core loop is async lab/terminal/job status.
      Toasts, lab transitions, and job completion are announced to nobody. Add regions.
- [ ] ~42 modals are undifferentiated `<div>`s — no focus trap, no Escape, no focus restore
      (e.g. `baremetal/MachinesTable.jsx:418`, the 11 `w-[400px]` login gates). Only 20 `'Escape'`
      handlers app-wide. **Copy `ConfirmModal.jsx:19-58`** — it is exemplary (trap + Escape +
      `previousFocus` restore + scroll lock).
- [ ] Skip link exists and is correct at `MainLayout.jsx:186` → `#main-content` (`:333`), but
      `PublicLayout.jsx` and `AdminLayout.jsx` have **neither the link nor the landmark** — all
      public marketing/blog and all 23 admin pages lack it
- [ ] Add `h1` to the 56 pages missing one
- [ ] Contrast risk: `text-surface-500` on `bg-surface-950` used for body copy
      (`AppRouter.jsx:101`, `ErrorBoundary.jsx:53`) lands near **4.0:1**, under the 4.5:1 AA
      threshold. `text-[10px]`/`text-[11px]` labels (`Leaderboard.jsx:326`) compound it. Token audit needed.
- [ ] Note: `MediaPermissionDialog.jsx` is one of the 8 correctly-accessible dialogs — **and it is
      dead code** (W12).

## W10. Unstable `useMemo` deps in the heaviest components (P1)
229 lint warnings: `no-unused-vars` 150, `react-hooks/exhaustive-deps` 74, `no-empty` 3.
Worst files: `LabRunner.jsx` (19), `VMwareSimulator.jsx` (12), `AdminSubscriptions.jsx` (9).

- [ ] The dangerous subset — `foo || {}` / `foo || []` literals in dep arrays, new identity every
      render, **so the memo never hits**, all in the heaviest simulators:
      `DatacenterSimulator.jsx:166` (twice), `:170`, `:171`, `:196`, `:199`, `:204`;
      `MaasNavPages.jsx:742-743`; `AzureConsole.jsx:120`; `GcpConsole.jsx:105`;
      `LxdConsole.jsx:114`; `GrafanaAlertingPanel.jsx:61`; `AgentWorkflowSimulator.jsx:329`.
      Hoist to stable constants.
- [ ] Stale-closure risks (missing deps): `LabTerminal.jsx:598` (`onReady`, `session`),
      `NotificationBell.jsx:33` (`fetchNotifications`), `aws/ui/primitives.jsx:205` (`columns`)
- [ ] Ratchet `--max-warnings` down from 300 as these are cleared

## W11. Ungated background polling (P1)
12 `visibilitychange` guards vs ~20 polling intervals. Running in background tabs:
- [ ] `awx/AwxSimulator.jsx:93` — **1.2s**
- [ ] `commvault/CommvaultSimulator.jsx:91` — **1s**
- [ ] `vyos/VyosConsole.jsx:79` — 2s
- [ ] `baremetal/BaremetalSimulator.jsx:301` — 2s
- [ ] `peoplesoft/PeopleSoftSimulator.jsx:65` — 3.5s
Each is a network round-trip + full re-render. Gate on `document.visibilityState`.

## W12. Dead code (P2)
- [ ] **7 orphaned modules, 0 external references** (verified individually, not barrel re-exports):
      `components/CompactPageHeader.jsx`, `components/InterviewDemoWidget.jsx`,
      `components/VMwareDemoWidget.jsx`, `components/interviews/LiveTranscriptPanel.jsx`,
      `components/interviews/MediaPermissionDialog.jsx`, `components/interviews/TranscriptPlayer.jsx`,
      `hooks/useLabProvisioning.js`
- [ ] **4 unused barrels** (consumers deep-import instead): `components/design/index.js`,
      `components/engagement/index.js`, `components/marketing/index.js`,
      `components/sim/shared/index.js`
- [ ] 150 `no-unused-vars` = unused imports/vars still shipped
- [ ] **`mockData/` does NOT leak into production** — verified. 943 LOC, imported by 7 simulator
      components; content is legitimate fixture data (real `prometheus.yml` configs, PeopleSoft nav
      trees). **Rename to `simFixtures/`** — the name is misleading.
- [ ] No unreachable routes: all `AppRouter.jsx` routes reachable, `*` → `NotFound` catch-all,
      `/support` → `/contact` redirect

## W13. Mobile breakage at 375px (P1)
`<meta viewport>` correct; 651 responsive prefixes; 36 `overflow-x-auto`. Most large `w-[1320px]`
hits are `max-w-*` containers or decorative orbs — safe.
- [ ] **11 simulator login gates hardcoded `w-[400px]` with no `max-w`** — overflow a 375px viewport
      by 25px+, clipping form fields. One-line fix each (`w-[400px]` → `w-full max-w-[400px]`):
      `docker/DockerConsole.jsx:104`, `k8s/K8sConsole.jsx:134`, `azure/AzureConsole.jsx:201`,
      `gcp/GcpConsole.jsx:183`, `openstack/OpenStackConsole.jsx:107`,
      `netapp/NetAppSimulator.jsx:92`, `commvault/CommvaultSimulator.jsx:123`,
      `dellemc/DellEmcSimulator.jsx:93`, `awx/AwxSimulator.jsx:127`, `soc/SocSimulator.jsx:103`,
      `datacenter/DatacenterSimulator.jsx:329`
- [ ] `vmware/VmwareResourceModals.jsx:5` — default `width = 'w-[440px]'`, no cap; applies to all
      VMware resource modals
- [ ] `styles/aws-sim.css:195` — `.aws-modal` sets `min-width: 400px` **and** `width: 100%`, so it
      cannot shrink below 400px. `styles/vmware-sim.css:339` — `.vm-table { min-width: 520px }`
- [ ] `styles/aws-sim.css:213` — `.aws-leftnav { width: 220px; min-width: 220px; flex-shrink: 0 }`
      consumes **59% of a 375px viewport** with no mobile collapse
- [ ] **Touch targets:** 35 buttons at `p-1`/`w-6 h-6`/`w-5 h-5` (~24px) vs the 44px WCAG 2.5.5
      minimum. Only **1** `min-h-[44px]` in the whole codebase. Same set as the 71 unnamed icon buttons.

## W14. Build/tooling debt (P2)
- [ ] **537 suppressed Sass deprecation warnings** — all from `vanilla-framework` 4.21.1 (legacy JS
      API, `@import`, global builtins). **Dart Sass 2.0/3.0 will break this build.** It is also the
      source of most of the 333kB `index.css`, and it **coexists with Tailwind** — two full CSS
      frameworks. Migrate off it.
- [ ] `framer-motion` overlaps hand-rolled CSS keyframes in `styles/index.css` — pick one
- [ ] [vite.config.js:6](frontend/vite.config.js#L6) sets `environment: 'node'` globally; jsdom is
      opted in per-file, so **a new `.test.jsx` silently gets the wrong environment.** Set `jsdom`.
- [ ] Test coverage: 83 tests over 130k LOC, concentrated in utils/sim logic. **Zero tests for
      `api/client.js`** (the refresh interceptor — see W1), any store, or any page component.
- [ ] Version drift vs manifest: `react-hot-toast` 2.6.0 (declared ^2.4.1),
      `@vitejs/plugin-react` 4.7.0 (declared ^4.3.2)

---

# P1/P2 — BACKEND

**The backend is in far better shape than project memory suggests.** Test suite:
```
DJANGO_SETTINGS_MODULE=config.test_settings python manage.py test tests apps
Ran 1677 tests in 1342s → OK (skipped=52), exit 0
```

**The 2026-07 audit's 6 P0 blockers are largely remediated.** Verified fixed: **RS256 JWT is
default and production hard-fails (`ImproperlyConfigured`) without keys** (memory's "RS256 pending"
is DONE), capacity locking, session pool, DEMO_PAYMENT, `.env` secrets.
→ **Update `audit_p0_blockers` memory accordingly.**

Security negatives, verified not assumed: no SQL injection (only parameterized `cursor.execute` +
`%s`), no `pickle`/`yaml.load`/`eval`/`exec` on user data, no `shell=True`, no path traversal, no
hardcoded secrets, CORS explicitly allowlisted, `DEBUG=True` only in `test_settings`, all webhooks
HMAC + `compare_digest` (Jira fails closed when secret unset). **Zero true bare `except:`.**
Only 8 TODO strings in the whole backend, all intentional generated placeholders.

API surface: 820 routes → 458 DRF. DRF defaults are **secure-by-default**: `IsAuthenticated` +
`CookieJWTAuthentication` + Anon/User throttles + `PageNumberPagination` (20). 63 `AllowAny`, all
reviewed and intentionally public. Only 3 non-admin function views. Throttling well-tiered
(`login: 10/min` on failures only, `lab_start: 60/hr`, `payment: 30/hr`).

Performance: systematic N+1 scan found **exactly 1** (`accounts/views.py:248`,
`invite.organization.member_count`). 237 `select_related`/`prefetch_related`, 32 `Meta.indexes`,
135 cache sites. No `time.sleep` in request path. **No external LLM/AI SDK anywhere** in
`requirements.txt` — the interview engine is fully local (confirms I1's root cause).

## B1. Capacity lock contract violated on the interview lab path (P1, race)
- [ ] [practical_lab.py:131-136](backend/apps/interviews/services/practical_lab.py#L131) calls
      `lab_start_block_reason()` (which takes `pg_advisory_xact_lock`) then `start_lab_session()` —
      **with no `transaction.atomic()`** (confirmed absent). The lock is transaction-scoped, so it
      releases **before** the INSERT, reopening the exact TOCTOU that `capacity.py`'s docstring says
      the caller must prevent. Concurrent interview starts can overshoot `MAX_CONCURRENT_LABS`.
- [ ] Contrast the **correct** main path at
      [public_api/views.py:776-875](backend/apps/public_api/views.py#L776), which holds the lock
      through `LabSession.objects.create`. Wrap the gate + start in one `transaction.atomic()`.

## B2. Lost update on attempt counter (P2)
- [ ] [progress/services.py:12-35](backend/apps/progress/services.py#L12) — `get_or_create` →
      `progress.attempts += 1` → `save()`, no `select_for_update`. Concurrent attempts undercount.
      (XP is correct — uses `F()` at `:253`.)

## B3. Duplicate function definition (P2) — smells like a bad merge
- [ ] [start_gates.py:131](backend/apps/labs/start_gates.py#L131) and `:143` both define
      `lab_start_block_http_status`, identical body; the second silently shadows the first. In a
      152-line file. **Check neighbouring code from the same merge.**

## B4. Missing migration trips `makemigrations --check` (P2)
- [ ] `question_bank` needs `0028_alter_scenario_cross_technology_and_more` (4 `AlterField`).
      **Cosmetic only** (`help_text`/`choices`, no DB schema change) but it will fail any CI drift
      gate. Working tree is clean, so this is committed state.

## B5. Container hardening inconsistency (P2)
- [ ] [docker_provisioner.py:184-209](backend/apps/labs/provisioner/docker_provisioner.py#L184)
      (SSH-client container) omits `pids_limit` and `cap_drop`, while the other two paths set
      `pids_limit=256` + `cap_drop=["ALL"]` (`:311`/`:319`, `:407`). **Fork-bomb gap.**

## B6. Celery reliability (P2)
- [ ] Only **3 of 26 tasks declare retry** (`notifications/tasks.py:8,147`,
      `celery_app/tasks.py:285`); no `acks_late` anywhere. Add both to the other 23.
- [ ] `recalculate_leaderboard` ([celery_app/tasks.py:275-280](backend/celery_app/tasks.py#L275))
      does `delete()`-then-`bulk_create` in one atomic block — correct, but **leaderboard reads see
      an empty table mid-run.** Consider a shadow table + swap.

## B7. Half-built / dead apps (P3)
- [ ] `scenario_versions` (75 LOC) — rows written by `question_bank/apps.py:16-33`, **never read.**
      Give it a reader or drop it.
- [ ] `hints/service.py:3` `get_next_hint` — 0 callers
- [ ] `labs/cleanup.py:7` `cleanup_lab` — 0 callers, **shadowed** by the real logic in
      `celery_app/tasks.py`. Delete to prevent future mis-wiring.
- [ ] `labs/timers.py:3` `end_session` — same
- [ ] `leaderboard` (180 LOC) — model + beat only, no API
- [ ] `adminpanel` — **88 routes, 1 test file.** Thinnest test coverage relative to surface.
- [ ] `billing` — 0 app-level tests (covered in `backend/tests/`, but consider co-locating)

## B8. Race tests silently skip locally (P2)
- [ ] All 52 skips are legitimate env guards, **but the PostgreSQL-only advisory-lock/race tests
      skip on SQLite** — so local runs never exercise the locking paths that B1 breaks. Run them in CI.
- [ ] `--parallel 4` fails on macOS (`TypeError: cannot pickle '_contextvars.Context'`) —
      harness-only, CI runs serially. Not a code defect.

## B9. Verified-good — do not regress (reference)
- Session lifecycle complete: `expires_at` auto-computed (`labs/models.py:156-160`), indexed
  `(status, expires_at)`, `cleanup_expired_labs` every 5 min handles expiry **and** stuck-PROVISIONING
  >10 min, `cleanup_orphaned_containers` hourly, chunked `.iterator(chunk_size=200)`
- Resource limits bounded: `MAX_CONCURRENT_LABS=60`, per-user 2, mem 512m, CPU 1.0,
  `TERMINAL_MAX_WS_PER_USER=20`
- Money paths correctly locked: `entitlements.py:106` (atomic + `select_for_update` + conditional
  `F()` decrement), `billing/payment_controller.py` (5 atomic blocks), `subscription_utils.py:200`
- Code sandbox `labs/code_exec.py:257-300` — scrubbed env, rlimits, `start_new_session`,
  process-group SIGKILL, timeouts. Well-built; **reuse it for A7 and I11.**
- WebSockets: JWT middleware + revocation check, auth gate, per-user conn cap, ownership scoped via
  `.get(id=session_id, user=user)`
- 273 `except…: pass` — sampled the risky ones; nearly all defensive best-effort with
  `# noqa: BLE001` rationale. Only the two in S7 are security-relevant.

---

# P1/P2 — DOCS, CI, INFRA, OPS

## O1. Delete dead docs (P1)
- [ ] **`DOCUMENTATION_INDEX.txt` is 100% dead.** It self-describes as "3,974 lines | 8 files" and
      **every file it points to is gone**: `00_START_HERE.md`, `JIRA_QUICK_REFERENCE.md`,
      `JIRA_AUTO_TICKET_IMPLEMENTATION.md`, `JIRA_BEST_PRACTICES_AND_USECASES.md`,
      `JIRA_IMPLEMENTATION_CHECKLIST.md`, `JIRA_SYSTEM_ARCHITECTURE.md`,
      `JIRA_INTEGRATION_SUMMARY.md`, `DELIVERY_COMPLETE.md`. Delete it.
- [ ] **`docs/ARCHITECTURE.md` and `docs/architecture.md` are byte-identical** — a case-collision on
      macOS/Windows checkouts. Delete one; **promote `docs/ARCHITECTURE_REVIEW.md` to canonical**
      (it is the most accurate arch doc).
- [ ] `docs/GAP_ANALYSIS.md` (324 L) vs `docs/gap-analysis.md` (142 L) — different content,
      confusingly near-identical names. Rename one.

## O2. Write a root README (P1)
- [ ] **There is no root `README.md`.** The de-facto entry point is `SETUP_COMPLETE.md` — a
      **secret-leaking deployment log** (S1). Also missing: `CONTRIBUTING.md`, `LICENSE`, a runbook,
      an API reference.

## O3. Broken doc references (P2)
- [ ] `SETUP_COMPLETE.md:18,298` → `AWS_EC2_SSH_SETUP.md` **missing** (the doc claims at `:17` that
      it "Created" this file)
- [ ] `SETUP_COMPLETE.md:134` → `python manage.py health` — **no such management command**
      (verified across all `management/commands/`)
- [ ] `docs/INTERVIEW_BOT_PLAN.md:124` → `backend/apps/interviews/routing.py` **missing**;
      `voice_consumer.py` **missing**
- [ ] `docs/INTERVIEW_BOT_PLAN.md:125` → `management/commands/train_from_transcripts.py` **missing**
- [ ] `docs/ARCHITECTURE_REVIEW.md:108` → `kubernetes/deployment.yaml` (actual path
      `infra/kubernetes/deployment.yaml`)
- [ ] `marketing/README.md:17` → `npm run render`, but **`marketing/package.json` does not exist**
- [ ] `.github/workflows/performance.yml:162` → `tests.test_query_counts` — **file does not exist**;
      masked by `|| true` so it silently no-ops
- [ ] Verified good: all 13 CI-referenced scripts exist; 7 of 8 doc-referenced management commands
      exist; `docs/SECURITY_AUDIT.md` and `docs/GAP_ANALYSIS.md` test refs all resolve

## O4. CI coverage gaps (P1)
**On PR + push-to-main, only 3 workflows run.** `ci.yml` is genuinely good — backend pip install,
`lint_scenarios.py --strict-heroes`, `--all --max-failures 0`, `manage.py test tests apps` against
real postgres:16 + redis:7; frontend `npm ci && lint && test && build`. Plus `grader-integrity.yml`
and `dependency-scan.yml` (path-filtered to dependency manifests).

**The other 18 workflows are `workflow_dispatch`-only.** All five e2e workflows carry
`# schedule removed — all runs are manual only`. Only `health-check.yml` is scheduled (`*/30`).

- [ ] Secret scan not on PR (S3) — highest-value gap
- [ ] **No e2e on PR or on merge to main.** 5 e2e suites exist; all need a human to click. Nothing
      validates a merge before it reaches `production.yml`. Add a post-merge or scheduled run.
- [ ] **Masked failures:** `dependency-scan.yml:46,60` both `continue-on-error: true` — a critical
      CVE is advisory-only, permanently. `performance.yml:162` `|| true` masks a suite whose file is
      missing. `production.yml` has 6 `continue-on-error: true` (746, 1114, 1165, 1240, 1630, 1676)
      — 1114/1240 annotated as intentional; **746/1630/1676 are unannotated and need review.**
- [ ] **No SAST/CodeQL, no container image scanning, no IaC scanning** (tfsec/checkov) despite
      substantial Terraform + K8s surface
- [ ] `production.yml` is **1,806 lines / 90KB in one file** — unreviewable, untestable. Split.
- [ ] `production.yml:340,1150` do `git push origin HEAD:main || true` mid-deploy — matches the
      known metadata-push race (memory `deploy_metadata_push_race`); failure is **swallowed**
- [ ] Node version drift: `ci.yml` uses Node 20, `dependency-scan.yml` uses Node 24
- [ ] No secret-into-`$GITHUB_ENV` leaks found; `notify-slack` correctly no-ops on empty webhook

## O5. Compose / container hardening (P2)
7 compose files (not 9 — `.dev`/`.data`/`.edge`/`.app`/`.prod`/`.vault`/base).
- [ ] **Data ports bound to `0.0.0.0`**, relying **solely** on the DigitalOcean cloud firewall
      (`scripts/ci-setup-firewalls.sh`) — a single control-plane failure exposes them to the
      internet: `docker-compose.data.yml:25` Postgres 5432, `:59` pgBouncer 6432,
      `docker-compose.edge.yml:26` **Vault 8200**, `:95` Redis 6379, `:117` RabbitMQ 5672,
      `docker-compose.app.yml:46` backend 8000. Bind to the private IP (`${PRIVATE_IP}:5432:5432`).
- [ ] **`:latest` unpinned third-party:** `edoburu/pgbouncer:latest` (data:37, prod:285),
      `certbot/certbot:latest` (edge:65, prod:53), `mailhog/mailhog:latest` (dev:192, base:200).
      First-party images default to `:latest` when `IMAGE_TAG` is unset — **a deploy without
      `IMAGE_TAG` silently reuses a stale local image.**
- [ ] **No `user:` directive in any of the 7 files — every container runs as root.** No `read_only`,
      no `cap_drop`, no `security_opt` anywhere.
- [ ] **`/var/run/docker.sock` mounted read-write into 4 prod services** (prod:92,173,209,245) —
      i.e. host root. `app.yml:59` correctly mounts `:ro`; **prod does not.**
- [ ] Healthchecks thin: app 5/8, data 2/4, dev 5/15, **edge 3/13**, prod 11/22, base 5/17
- [ ] Resource limits nearly absent: `edge.yml` 0, `data.yml` 0, `vault.yml` 0.
      **Postgres on D3 has no memory limit.**
- [ ] Vault runs `disable_mlock = true` (`infra/vault/config.hcl:2`) with `tls_disable = 1` on
      `0.0.0.0:8200` — **plaintext Vault API over the VPC**

## O6. Infra risks (P1/P2)
- [ ] **Terraform:** `backend "s3"` with **no `dynamodb_table`** → **no state locking**; concurrent
      applies corrupt state. Hardcoded `bucket`, `region`, `domain_name = "fixitlab.in"`, and
      `acm_certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT-ID"` (placeholder —
      **will not apply**). `master_password = "change-me-use-secrets-manager"` at
      [main.tf:160](infra/terraform/main.tf#L160) → move to Secrets Manager.
      `cluster_endpoint_public_access = true` on EKS. No `variables.tf`/`outputs.tf` split, no
      `terraform.tfvars.example`, no remote-state encryption flag.
- [ ] **Two competing K8s definitions.** `infra/kubernetes/deployment.yaml` (monolith, **5
      `CHANGE-ME` secrets**, `fixitlab/backend:latest`, `hostPath` docker.sock,
      `DJANGO_ALLOWED_HOSTS: "*"`) vs `infra/k8s/base/` + `overlays/{doks,eks}` (kustomize, has
      `secret.example.yaml`). **Delete the monolith**; `docs/ARCHITECTURE_REVIEW.md:108` still cites it.
- [ ] K8s missing: `securityContext`/PSP, `NetworkPolicy`, `PodDisruptionBudget`. Single-replica
      Postgres StatefulSet is a SPOF.
- [ ] **`infra/packer/` contains no `.pkr.hcl` template at all** — only two shell scripts. It is not
      Packer, it is a bash AMI builder wrapping AWS CLI. Either write real Packer templates or
      rename the directory.
- [ ] SPOFs: D3 Postgres single container; D1 Vault single node with `storage "file"` — no Raft/HA,
      no replication

## O7. Scripts cleanup (P2)
86 entries: 24 `ci-*` deploy orchestration, 18 scenario generation/enrichment, 13 `e2e_*`,
20 under `scripts/vault/`, 4 platform lifecycle, 6 validation, 4 secret upload.
- [ ] **Destructive ops are well-guarded** — `platform-stop.sh:3,18` explicitly refuses `down -v`;
      `restore-pg-backup.sh` requires typed DB-name confirmation or `--yes`; all 5 `rm -rf` are
      apt-cache cleans, `mktemp` traps, or `/tmp`-scoped. **No unguarded destructive op found.**
- [ ] **Duplicate deploy scripts:** root `deploy.sh` (243 L) vs `scripts/deploy.sh` (425 L) —
      different content, **neither referenced by any workflow**. Both appear obsolete vs
      `production.yml`. Same for `ci-create-production-droplet.sh` vs `create-production-droplet.sh`.
- [ ] `scripts/__pycache__/` and `scripts/coding_gen/__pycache__/` are checked into the working tree

## O8. Observability gaps (P1)
**Present:** `sentry-sdk[django]>=2.63.0` wired in `settings.py`; `LOGGING` at `settings.py:973`;
Prometheus telemetry on Vault (`127.0.0.1:8203`); `health-check.yml` every 30 min with Slack alert +
auto-open/auto-close GitHub issue (well-built); daily `pg_dump` with 7-day retention, integrity
check, off-site Spaces upload and Redis heartbeat (`ci-pg-backup-cron.sh`); documented restore;
`rollback.yml` for both topologies.

- [ ] **No frontend error tracking** — `sentry` absent from `frontend/package.json`. **Browser
      exceptions are invisible.** Add it (highest-value ops gap given W1/W4/W5).
- [ ] No Prometheus/Grafana for the *application* (the `scenarios/prometheus` hits are lab content).
      No app-level metrics endpoint.
- [ ] **No evidence the restore path has ever been tested.** Add a CI restore drill.
- [ ] No documented DR/RTO/RPO, no on-call/incident runbook

---

# PHASED EXECUTION PLAN (v1 — ⚠️ SUPERSEDED)

> **⚠️ SUPERSEDED by `MASTER PLAN — FINAL CONSOLIDATED` at the end of this document.** Kept for the
> reasoning only — do not sequence work from this section. It predates the §X, §Y and §Z findings and
> has no Phase 0 (instrument first).

Per your standing preference: phase big epics, stabilize each phase before the next, and do **not**
re-run a prod deploy repeatedly. **Do not deploy until Phase 1 and 2 land.**

## Phase 1 — Security + stop-the-bleeding (days)
S1 rotate + scrub secrets · S2 fix scanner · S3 scanner on PR · S5 SSRF · S6 pin ssh-action ·
S7 log fail-open auth · S8 `npm audit fix` · W1 refresh mutex · W2 store reset on logout ·
H1 VMware gate exit · H2 mobile z-index.

Stabilize: full backend suite + frontend suite green, scanner fails on a deliberately planted
secret, manual smoke of login → dashboard → start a VMware lab → exit.

## Phase 2 — Grading integrity (1–2 weeks) — do NOT author content before this
G1 `exit 0` scripted pass · G4 route academy-aws to the console engine (+ azure/gcp/openstack) ·
G6 OpenStack validator · G5 replace placeholder coding tests · G7 add the three CI rules
(topic-coherence, checker-uniqueness, cross-layer slug) · G3 add AI keyword families to
`topic_faults.py`.

Stabilize: the new CI rules must pass on the fixed corpus and **fail** on a deliberately reverted
scenario. Spot-solve 10 AWS labs end-to-end through the console.

## Phase 3 — Reconnect the learning path (1 week, mostly config — highest ROI/effort)
C2 drop the `aws→terraform` alias (**one line, 421 labs**) · C1 `linked_tutorial` model field +
ingest + 44-row mapping + fail-on-unresolvable · C4 `/journeys` routes + resolve Tutorial titles ·
C3 `/projects` index route · C5 purge 70 dangling cert refs + enforce ≥2/objective ·
C6 unify `playground_slug` → `Technology.slug`.

Stabilize: trace the fresher path for linux, aws, and ai-ml end-to-end in a browser. All three must
complete without a dead link.

## Phase 4 — 3D datacenter becomes a game (~1 week; ~200 lines does most of it)
D1 collision · D2 pointer-lock state machine · D3 camera-Y order · D4 clamp `dt` · D5 gravity/
jump/crouch · D7 per-frame setState → refs · D8 dispose · D9 FPS out of React state ·
D10 kill per-item `<Html>` · D11 crosshair hover prompt · D6 input hygiene (ShiftRight, blur-clear,
input guard, sensitivity + invert-Y in the pause menu).
Then: D12 bloom + textures + self-host HDRI + minimap yaw · D13 footsteps off `bobPhase`, controls
screen, alarm lighting.

Stabilize: walk the full hall without clipping a rack; Esc→resume restores mouse-look; E shows a
prompt and opens a rack; 60fps at 8 racks on a laptop.

## Phase 5 — Simulator causality (1–2 weeks)
F1 gate `systemctl start` on `nginx -t` (**~10 lines, makes every config lab causal**) · F2 parse
unit files · F3 real `journalctl` · F4 reconcile fe/be shells · F5 derive faults from parsed input
(CI/CD, AWX, Packer, Terraform) · F6 PowerShell + `az` + `gcloud` + `openstack` CLIs.

## Phase 6 — AI interview credibility (1–2 weeks)
I1–I5 replace the scorer with local `sentence-transformers` semantic rubric + **golden-set
regression test** · I6 cap pausing + log tab switches · I7 author d4/d5 + coding + behavioral banks ·
I8 blake2b determinism + subprocess test · I9 hr/manager weights · I10 voice cleanup.

## Phase 7 — AI/ML/LLM/Data Science content (3–4 weeks, the big content epic)
A1 per-GPU dataclass (**converts ~70 written GPU scenarios to real, no UI work**) · A2 real vLLM
sim + serving scenarios · A3 distributed-training vertical · A4 real RAG engine · A5 ReAct loop +
real MCP + failure injection + cost model · A6 PromptPlayground output-conformance grading ·
A7 real SQL/notebook execution + DS scenario set · A8 LLMOps · A9 k8s MIG/time-slicing ·
A10 fresher conceptual on-ramp · A11 metric-driven expert labs.

## Phase 8 — De-templatize the 9 storefront technologies (ongoing)
netapp, dellemc, datacenter, openstack, azure, gcp, soc, commvault, ai-infra — 100% validator
failure, ~10 real topics stretched to 150 files, graded on an unrelated Linux daemon.
Also: F7 depth backlog, C3 populate `lab_scenario`/`validation_scenario` for 213 projects,
C5 add AWS/Azure/GCP/Python/security certs, more staged cross-tech capstones.

## Phase 9 — Polish (ongoing)
W3 eager-chunk split · W5 error states + `useFetch` · W6 AbortController · W9 a11y ·
W10 memo deps · W11 poll gating · W12 dead code · W13 mobile · W14 drop vanilla-framework ·
B1–B8 backend P1/P2 · O1–O8 docs/CI/infra/ops.

---

## Duplication reference (for Phase 8 scoping)

| Signal | Files in shared groups | % of 7,280 |
|---|---|---|
| Identical `solution.summary` | 7,114 | **97.7%** (only 55 distinct) |
| Identical `check.sh` | 5,788 | **81.7%** (57 distinct) |
| Identical hint ladder (5 rungs) | 5,373 | 73.8% |
| Identical task structure | 5,121 | 70.3% |
| Identical `summary` | 5,120 | 70.3% |
| Identical `description` | 4,657 | **64.0%** |

Largest clusters: 1,877 files share the null task/solution signature (the entire missing-schema
block) · 684 share `"Implement the function so visible and hidden tests pass in the coding IDE."` ·
420 (all of aws) share `"Identify the misconfiguration affecting this aws lab and apply the minimal
fix."` · 341 share the nginx root-cause text across ai-ml/data-science/grafana/networking/devops/
linux · 238 the postgresql equivalent.

Boilerplate: `"and verify success with the checker"` → **5,262 (72.3%)**; `"apply the minimal fix"`
→ 2,559 (35.2%). **Every one of the 3,764 `guided_mode` blocks has exactly 3 steps.**

Concrete example: `scenarios/netapp/academy-netapp-{001,011,...,141}-learn-svm*/scenario.yaml` —
15 scenarios with **identical title** (`"NetApp ONTAP Storage: Svm — Fundamentals Lab"`), identical
description, identical hint 1, identical difficulty. Only variation: the objective service flips
`crond`→`nginx`. **NetApp's 150 scenarios = 10 topics × 15 clones.**

Shallow-vs-deep, by topical diversity / distinct descriptions / distinct check.sh:
- **Deep:** linux (191: 161 topics / 167 desc / 103 checks — the only tech deep on all three axes),
  gitops, commvault (mechanically varied), terraform, ai-infra, networking, kubernetes, baremetal
- **Shallow:** netapp & dellemc (11 topics / 31 desc / **4** checks), datacenter & openstack
  (12 / 32 / 3), azure & gcp (13 / ~30 / **2**), soc (16 / 32 / 7), html (60 / 60 / **1**),
  aws (280 topics — good spread — but **1** unique check.sh for 420 labs)

Also: 569 `technology` field mismatches (display names stored where slugs belong: `ai-infra` → `"AI
Infrastructure Engineering"` 195, `opentelemetry` → `"Opentelemetry"` 125, `service-mesh` 125,
`devsecops-supplychain` 124) · 250 files where `slug` ≠ dirname (cosmetic) · **0 duplicate slugs**
(clean, guarded by `seed_scenarios.py:129-171`) · **7,280/7,280 parse cleanly.**

The corpus is structurally sound and semantically hollow: breadth (46 techs × 150) was manufactured
by templating, and the grading layer verifies a marker file rather than the skill each lab advertises.

---
---

# ADDENDUM — 2026-08-06 (second pass)

Three newly verified P0 bugs (two of them reported live by the owner), plus four new epics.
Everything below was confirmed by reading the actual code, not inferred.

---

# X1 — DATACENTER RENDERS 2D FOREVER (P0) — ✅ ROOT CAUSE FIXED 2026-08-06

**Owner report:** *"datacenter is not coming as steam game… it is still coming as 2d which is not
feel like real datacenter."* Then, with the actual error text:
*"Using a recoverable path — the isometric floor is optional. Reason: Could not load
empty_warehouse_01_1k.hdr: Failed to fetch"* — **which confirmed the X1b prediction exactly.**

**This is a bug, not missing work. The 3D twin exists, builds (3,086kB chunk), and is the coded
default (`floorView` initialises to `'3d'` at `DatacenterSimulator.jsx:141`). Three independent
mechanisms are forcing it to 2D.**

> ## ✅ FIXED 2026-08-06 — four changes, built and behaviourally verified
>
> **The owner's error message proved a single root cause produced BOTH reported symptoms** (2D
> datacenter *and* "links asking to reload the pages"). See the new **§X1e** below — that reload
> bug was not in the original audit and was only found by tracing the real error string.
>
> | # | Change | File |
> |---|---|---|
> | 1 | **Removed the CDN HDRI entirely.** `<Environment preset="warehouse" />` → new `HallEnvironment` using procedural drei `<Lightformer>`s rendered to an offscreen cube target. **Zero network requests.** Tuned for a dark hall: overhead cold-aisle strips, side rims so rack metal reads as metal, warm floor bounce, faint cyan LED ambient. | `DatacenterTwin3D.jsx` (`Environment` call site + new `HallEnvironment`) |
> | 2 | **Narrowed the stale-chunk matcher** — see §X1e | `main.jsx` |
> | 3 | **Versioned the prefer2d key** to `fixitlab.dc.prefer2d.v2` and added a one-time `removeItem` of the poisoned v1 key, so **every browser already pinned to 2D is released back into 3D exactly once.** Only an explicit "2D floor" click writes the flag now. | `DatacenterSimulator.jsx` (`PREFER_2D_KEY`) |
> | 4 | **Moved `<Suspense>` OUTSIDE `Twin3DSafe`.** The twin chunk is ~1MB gzip; nested inside, a slow/dropped chunk fetch surfaced as a thrown error and was treated as a permanent WebGL failure. Outside, it stays a retryable loading state. | `DatacenterSimulator.jsx` |
>
> **Verification performed (not assumed):** `npx eslint` on all three files → **0 errors**;
> `npm run build` → **clean, 15.65s**; shipped-bundle checks → `preset:"warehouse"` passed
> **0 times**, `HallEnvironment`'s Lightformer colors present, both prefer2d keys present exactly
> once each; app loaded in a real browser with **zero console errors**.
> *The residual `warehouse:"empty_warehouse_01_1k.hdr"` string in the bundle is drei's internal
> preset lookup table, which ships regardless of use — it is a map entry, not a fetch.*
>
> **Not yet done:** §X1c (3D exists in only 1 of 10 rooms) and the §X6 game layer. Those are
> features, not this bug. Also unverified: the 3D hall rendering visually, because reaching the
> datacenter simulator needs auth + a live lab session.
>
> ⚠️ **Note for whoever reads §X1a below:** `Twin3DSafe` had *already* been partially improved
> before this session — it no longer auto-persists 2D on crash and it now shows a Retry banner with
> an explicit "Use 2D floor" button. The remaining defect was the **unversioned key**, so browsers
> poisoned by the older build stayed stuck. That is what change 3 fixes.

## X1a. The crash handler permanently poisons a localStorage flag — **the primary cause**
- [ ] [DatacenterSimulator.jsx:481](frontend/src/components/datacenter/DatacenterSimulator.jsx#L481):
      ```jsx
      <Twin3DSafe onFallback={() => setFloorViewPersist('2d')}>
      ```
- [ ] `setFloorViewPersist('2d')` (`:143-150`) writes **`localStorage['fixitlab.dc.prefer2d'] = '1'`**
- [ ] On every subsequent mount, `:136` reads that flag and returns `'2d'` **before anything else is
      evaluated**
- [ ] **There is no expiry, no retry, no schema version, and no UI to clear it.** One transient
      throw — ever — pins that browser to the 2D isometric plan permanently, across every scenario
      and every future session.
- [ ] The code comment at `:131-133` proves this was *already fixed once* for a different flag:
      *"Only honor an explicit prefer2d flag (set when the learner clicks '2D floor') — legacy
      `floorView=2d` alone used to trap people in the isometric plan forever."*
      **But `onFallback` at `:481` writes that same sticky flag from the crash path.** The documented
      intent and the wiring disagree. The trap was moved, not removed.
- [ ] `Twin3DSafe.render()` returns `null` when failed (`:50`), so there is **no "3D failed — retry"
      affordance**. The learner is silently demoted with no explanation and no way back.
- [ ] **Fix:** `onFallback` must set transient component state only — never persist. Persist
      `prefer2d` *only* from the explicit "2D floor" button click at `:458`. Add a versioned key
      (`fixitlab.dc.prefer2d.v2`) so every existing poisoned browser is released on deploy. Render a
      "3D unavailable — Retry / Report" panel instead of `null`.

## X1b. Likely trigger: a 1MB lazy chunk inside the error boundary
- [ ] `<Suspense>` is **inside** `Twin3DSafe` (`:481` → `:482`), so a `LazyDatacenterTwin3D` load
      rejection propagates into the boundary → `onFallback` → permanent 2D (X1a).
      `DatacenterTwin3D` is **1,052kB gzip** (§W3). On a slow, flaky, or mid-deploy connection the
      chunk times out and the learner is permanently demoted. `lazyWithRetry` retries the *import*,
      but an exhausted retry still throws into the boundary.
- [ ] Second trigger: `Environment preset="warehouse"` (`DatacenterTwin3D.jsx:1395`) **fetches an
      HDRI from a CDN at runtime** (§D12). Offline, air-gapped, or CDN-blocked → throw → permanent
      2D. Self-host the HDRI.
- [ ] Move `<Suspense>` **outside** `Twin3DSafe` so a chunk-loading failure is a retryable loading
      state, not a permanent capability downgrade.

## X1c. 3D exists in only 1 of 10 rooms — by design
- [ ] Both `:480` and `:559` are gated on `currentRoom.type === 'data_hall'`. The other **nine** room
      types — `network`, `mechanical`, `electrical`, `campus`, `security`, `office`, `ops`,
      `logistics`, `safety` (`ROOM_ICONS`, `:73-77`) — have **no 3D path at all** and render 2D
      panels unconditionally.
- [ ] So even with 3D working, walking through a portal out of the data hall **drops you out of the
      3D world entirely.** The twin already has `onEnterRoom` (`:511`) and portal geometry —
      the shell just refuses to render 3D for the destination.
- [ ] This is the second reason it "doesn't feel like a real datacenter": you cannot walk the
      facility, only one hall. **Extend the 3D twin to all 10 room types** (see X6).

## X1d. The UI already promises what the bug prevents
- [ ] `:467` tooltip: *"Steam-class animated 3D hall — Walk (WASD) · falls back to 2D on GPU errors"*
- [ ] `:475` hint: *"2D floor · switch to 3D hall for Steam immersion"*
      The intent is documented in the UI copy. Fix X1a/X1b/X1c and the promise becomes true.

## X1e. ✅ NEW FINDING — one over-broad regex turned ANY network error into a page reload
**Not in the original audit. Found only by tracing the owner's actual error string, and it is the
cause of the second reported symptom: *"links are asking to reload the pages."***

`main.jsx:29` matched stale-chunk failures with:
```js
/dynamically imported module|Importing a module script failed|ChunkLoadError|Failed to fetch/i
```
That final bare **`Failed to fetch`** alternative matches **any** network error whose message happens
to contain the phrase — including the HDRI failure
(`"Could not load empty_warehouse_01_1k.hdr: Failed to fetch"`), a failed image, or an aborted API
call. Each match called `recoverFromStaleChunk()` → **`window.location.reload()`**.

So the HDRI fetch failure did two things at once: threw into `Twin3DSafe` (→ 2D) **and** tripped the
stale-chunk handler (→ full page reload). Reloading never fixed it, because it was never a stale
chunk — it just bounced the user off whatever page they were on, repeatedly. Note `:38` already used
the correct narrow `Failed to fetch dynamically`; only `:29` was wrong.

- [x] **FIXED** — extracted a single shared `STALE_CHUNK_RE` used by both the `error` and
      `unhandledrejection` listeners, with every pattern module-specific:
      `dynamically imported module | Importing a module script failed | ChunkLoadError |
      Loading chunk N failed | Failed to fetch dynamically imported module`.
      Added a comment stating the rule: **if a pattern does not name a module or chunk, it does not
      belong in this list.**
- [x] **Behaviourally verified against the shipped bundle** by dispatching synthetic `ErrorEvent`s
      and probing the handler's own `sessionStorage['fixitlab:chunk-reload']` loop-guard (which is
      written immediately before `reload()`, so its presence proves the handler fired):

      | Dispatched message | Handler fired? | Expected |
      |---|---|---|
      | `Could not load empty_warehouse_01_1k.hdr: Failed to fetch` | **false** | ✅ was the bug |
      | `TypeError: Failed to fetch` | **false** | ✅ |
      | `Failed to fetch /assets/logo.png` | **false** | ✅ |
      | `Failed to fetch dynamically imported module: /assets/Foo-abc.js` | **true** | ✅ no regression |
      | `ChunkLoadError: Loading chunk 42 failed` | **true** | ✅ no regression |
      | `Importing a module script failed` | **true** | ✅ no regression |

- [ ] **Follow-up worth doing:** two other runtime CDN dependencies remain and will hit the same
      class of failure offline — `pyodideRunner.js:17` (`cdn.jsdelivr.net/pyodide`, powers
      Python-in-browser for coding labs) and `useVirtualBackground.js:28`
      (`cdn.jsdelivr.net/npm/@mediapipe/selfie_segmentation`). Neither reloads the page any more, but
      both fail silently in an air-gapped environment. Self-host or degrade explicitly.

**Verification after fix:** clear `fixitlab.dc.prefer2d*`, load a datacenter scenario, confirm 3D on
first paint; then force a throw inside the twin and confirm you land on a *retryable* panel and that
a reload still attempts 3D. ✅ Done for the reload path and the bundle checks; the 3D hall itself
still needs a visual pass behind auth.

---

# X2 — @TEAM MENTIONS NEVER REPLY (P0)

**Owner report:** *"No reply is coming"* — with evidence: `@storage team test` (14:40) and
`@database team / @application team — stop or start DB/app services` (14:41), both unanswered.

**The bot logic is correct. I traced both of your exact comments through it:**
- `"@storage team test"` → `parse_team_mentions` → `['storage']` → `resolve_team_actions` → `[]`
  (no `disk`/`please`/`lvm`) → `build_team_reply` falls through to `:227-231` and **does** return a
  reply.
- `"@database team / @application team — stop or start DB/app services"` → `['database','application']`
  → `_is_start_request` matches `"start"` → `[database_started, application_started]` →
  `:237-238` returns *"Services restored: …"*.

**So a reply is always built. Delivery and display are what fail — two compounding causes.**

## X2a. The comment UI never refetches — 100% failure to display
- [ ] **`JiraTicketPanel.jsx` and `JiraTicketPage.jsx` contain zero `setInterval`, zero polling,
      zero refetch, and zero WebSocket subscription.** Verified by grep.
- [ ] The reply is delivered **30 seconds later** (`team_reply_delay_seconds()` →
      `JIRA_TEAM_REPLY_DELAY_SECONDS`, default 30, `team_bots.py:61-62`) by writing a comment row via
      `add_comment` (`:446`). **Nothing tells the open UI that a new comment exists.** The learner
      stares at a panel that will never update.
- [ ] `schedule_team_replies` **already returns** `{scheduled, teams, delay_seconds, pending_author}`
      (`team_bots.py:365-370`) — and **nothing in the frontend consumes any of it.** There is not
      even a "Storage Team is responding… (~30s)" pending indicator.
- [ ] **Fix (this alone resolves the report):** on a successful comment POST, read
      `delay_seconds`/`pending_author` and render a pending chip; then poll the comment list (or push
      over the existing WS infrastructure) until the reply lands. Cap polling and gate on
      `document.visibilityState` (§W11).

## X2b. Celery-queued replies can be silently dropped
- [ ] `team_bots.py:344-363` — `deliver_jira_team_reply.apply_async(..., countdown=30)`. The
      `except Exception` fallback to `deliver_team_reply_now` **only catches failures of the enqueue
      call itself** (broker unreachable).
- [ ] **If the broker accepts the message but no worker consumes that queue, the task sits forever:
      no reply, no exception, no log line.** This is the classic silent-drop, and it is invisible to
      the learner *and* to ops.
- [ ] `deliver_team_reply_now` also has a silent `return` when the ticket is missing
      (`:384-386`) — no log.
- [ ] **Fix:** treat delivery as durable work — persist a `pending_team_reply` row at schedule time
      and have a periodic beat task deliver any row older than `delay + grace`. That makes the reply
      arrive even with no worker at enqueue time. Log every drop path at WARNING.
- [ ] Reduce the default delay for interactive labs, or surface it explicitly so 30s of silence reads
      as "waiting", not "broken".

## X2c. Near-miss coaching is built but unreachable in this path
- [ ] `looks_like_failed_team_mention()` (`:40-44`) and `build_mention_coach_reply()` (`:47-58`)
      exist to catch mistyped mentions — but `schedule_team_replies` returns early at `:331-333`
      when `parse_team_mentions` is empty and **never calls them.** Verify the caller in
      `jira_integration/views.py` invokes the coach path; if not, a mistyped mention is answered by
      total silence.

**Note:** your second comment is verbatim the platform's own help text
(`jira_integration/sync.py:160`). A learner copying the documented example and getting silence is the
worst possible first impression of the collaboration feature — this deserves priority over most of
the content work.

---

# X3 — NEW EPIC: GOLDEN IMAGE → AMI → EC2 PIPELINE (ai-infra)

**Owner ask:** take an upstream Ubuntu image, customise it, run the full test suite, convert/import
it as an AWS AMI, register it in the AWS simulation, launch EC2 from it — **all simulated, including
the image build** — and **if the build fails, the EC2 instance must not work.** Instance behaviour
must derive from what is actually in the image.

**Good news: ~70% of this already exists and is not connected.** This is a wiring epic, which is the
same theme as the rest of this audit.

## What already exists
- [ ] [packer_factory.py](backend/apps/vmware_sim/packer_factory.py) is a real Image Factory:
      phases `packer-init → validate → build → vuln-scan+remediate → gpu-sanity → publish` (`:103-140`),
      per-phase logs, `attempts`, required checks (`:176-181`), a matrix of SKUs, **real failure
      phases** (`:140` remediate, `:148` `gpu-sanity` fail), and it already emits
      `build_succeeded`, `artifact_ready`, and `suggested_boot_resource` (`:85-87`).
- [ ] [aws_engine.py](backend/apps/vmware_sim/aws_engine.py) has an `AMI_CATALOG` (`:170-173`) with
      real `ubuntu-22.04` / `ubuntu-24.04` / `rhel-9` / `amazon-linux-2023` AMI IDs, per-AMI
      `os`/`platform`/`arch`/`user`, a private custom AMI example (`:272`), AMI-ID generation
      (`_hex`, `:59`), and `create_image` / `deregister_image` actions (`:1185`, `:1208`).
- [ ] `PackerWorkspaceIde.jsx` (707 L) is the authoring surface.
- [ ] MAAS/`baremetal_engine.py` already consumes boot resources and has a real commissioning FSM.

## The gap — build the bridge
- [ ] **No import path.** `aws_engine.py` has `create_image` (snapshot a running instance) but **no
      `import_image` / `register_image` / `ImportSnapshot` / `ImportImage` task.** Packer's artifact
      (`suggested_boot_resource: "custom/h100-jammy"`) is a **MAAS** boot resource; there is no
      AWS-side consumer. **Add `aws ec2 import-image` / `import-snapshot` with a real async
      `ImportImageTask` (progress %, `StatusMessage`, terminal `completed`/`deleted` states).**
- [ ] **No artifact identity.** Packer produces no content manifest. **Give the artifact a real
      manifest** — base image + digest, applied provisioners, installed package set, kernel/driver
      versions, cloud-init/`user-data` handling, SSH host keys, enabled services, CIS/vuln findings —
      and carry it through import into the registered AMI.
- [ ] **No failure propagation — this is the owner's core requirement.** Today `build_succeeded` is
      never read by AWS. Wire it so:
  - build failed → **no artifact** → `import-image` returns the real AWS error
    (`ClientError: Disk validation failed`) → **no AMI** → `run-instances` fails with
    `InvalidAMIID.NotFound`
  - build succeeded but `vuln-scan` unremediated → AMI registers but is **quarantined**; a policy
    check blocks `run-instances` (mirrors real Image Builder / Inspector gating)
  - `gpu-sanity` failed → AMI boots but `nvidia-smi` fails **on the instance** (ties straight into
    the per-GPU dataclass in §A1)
  - **cloud-init/SSH key not baked → instance reaches `running` but SSH is refused and console
    output shows the cloud-init trace.** This is the single most realistic golden-image failure and
    the one that teaches the most.
- [ ] **Instance behaviour must derive from the image.** An EC2 instance launched from a custom AMI
      must boot a shell whose installed packages, services, users, and kernel come from that AMI's
      manifest — not a generic RHEL persona. Bridge the AMI manifest into the `rhel_os.py` /
      `linuxShell.js` seed so `dpkg -l`, `systemctl`, `uname -r`, and `id` all reflect the image the
      learner actually built.
- [ ] **Grading must assert the chain, not a marker file** (§G2): assert the artifact manifest
      contains the required package, that the AMI is registered in the right region, that the
      instance launched from *that* AMI ID, and that the in-guest state matches the manifest.

## Scenarios to author (ai-infra)
- [ ] Golden image zero-to-hero: fetch upstream Ubuntu 22.04 cloud image → verify checksum/GPG →
      customise (packages, hardening, agents) → build → test → import as AMI → launch EC2 → validate
- [ ] Build fails on a bad provisioner → prove no AMI is produced → fix → rebuild
- [ ] Checksum/GPG mismatch on the upstream image → refuse to build (supply-chain gate)
- [ ] `import-image` fails: unsupported VM format · unpartitioned volume · missing
      `vmimport` service role / trust policy (the real #1 cause) · wrong bucket region
- [ ] AMI boots but SSH refused — cloud-init never ran / `authorized_keys` not baked
- [ ] AMI missing the ENA driver → instance type incompatible → launch fails
- [ ] Wrong architecture (arm64 image, x86 instance type) → `InvalidAMIID`-class error
- [ ] Unencrypted snapshot vs an org policy requiring encryption → copy with a KMS key
- [ ] Cross-region AMI copy + share to another account, then a launch permission failure
- [ ] Image drift: instances on a deprecated AMI; build N+1, canary, roll forward, deregister N
      **without** orphaning snapshots (a real cost leak — ties to X5)
- [ ] Vuln scan finds a critical CVE → remediate → rebuild → re-scan → publish
- [ ] Golden image bake time regression — layer/provisioner ordering and cache
- [ ] Multi-SKU matrix build where one SKU fails and must not block publish of the others

---

# X4 — NEW EPIC: ARTIFACT PROVENANCE ACROSS ALL TECHNOLOGIES

**Owner ask:** the same "build an artifact → test it → publish it → consume it, and failure
propagates" pattern for kubernetes, docker, MAAS, linux, aws, gcp, peoplesoft, dellemc, commvault
and the rest.

This is the **single strongest cross-cutting realism upgrade available**, because it makes the
technologies *depend on each other* the way they do in a real shop — and because every dependency
edge is objectively gradeable (§G2). Same principle throughout: **the artifact carries a manifest;
downstream behaviour derives from the manifest; a failed build must produce a broken downstream.**

- [ ] **Docker** — real Dockerfile layer semantics: build cache, layer digests, multi-stage, base
      image pinning by digest. Failure propagation: build fails → no image → `docker run` →
      `Unable to find image`. Push to a registry, pull by digest, image-scan gate, cosign
      signature verification, `.dockerignore` bloat, wrong `CMD`/`ENTRYPOINT` → `CrashLoopBackOff`
      downstream in k8s.
- [ ] **Kubernetes** — deploy *the image built above*. `ImagePullBackOff` on a bad tag/digest,
      `ErrImagePull` on a private registry with no `imagePullSecret`, admission policy rejecting an
      unsigned or unscanned image, a Helm chart pinning a digest that no longer exists, rollout →
      readiness fail → automatic rollback. **This makes the Docker→k8s edge real.**
- [ ] **MAAS / baremetal** — consume Packer's `suggested_boot_resource` for real: upload a custom
      boot resource, commission → deploy from *that* image, and have a bad image fail commissioning
      with real logs. The FSM (`baremetal_engine.py:1019-1090`) is already excellent; it just needs
      the image to matter.
- [ ] **Linux** — the in-guest state must be a *consequence* of the image (see X3), plus package
      repo/GPG trust, `dnf`/`apt` transaction rollback, kernel upgrade + `grub` + reboot into the
      wrong kernel, `dracut`/initramfs rebuild.
- [ ] **GCP** — the mirror of X3: `gcloud compute images import`, custom image families, shielded
      VM / secure boot rejecting an unsigned image, instance templates + MIG rolling update from a
      new image version. Requires the `gcloud` CLI from §F6.
- [ ] **Terraform** — plan/apply against the AMI/image ID produced upstream: state drift when the
      image is deregistered out of band, `data.aws_ami` filter returning the wrong image,
      `create_before_destroy` on an ASG launch-template image bump. Needs the real HCL parse (§F5).
- [ ] **Commvault** — backup/restore *provenance*: restore to a point in time and prove the restored
      filesystem matches the manifest; a corrupt/incomplete backup must fail restore verification
      (today there is no restore-verify at all, §F7). Retention/dedup/aux-copy actually affecting
      what can be restored.
- [ ] **Dell EMC / NetApp** — the artifact is a **LUN/volume/snapshot with real capacity
      arithmetic**: thin provisioning overcommit, snapshot reserve exhaustion, a clone that pins
      space, SnapMirror lag breaching RPO. Enforce the arithmetic on write (§F7) so overcommit
      genuinely fails.
- [ ] **PeopleSoft** — the artifact is a **migration/change package**: build in DEV → compare
      report → apply to TEST → fail on a customisation conflict → resolve → promote to PROD. Plus
      Change Assistant, App Designer project promotion, and a bad patch requiring rollback. This
      turns 150 shallow labs into a real lifecycle.
- [ ] **Ansible / AWX** — role/collection artifact with `requirements.yml` pinning; a playbook whose
      failure is *derived from parsed content* (§F5) rather than a preset boolean; check-mode diff vs
      apply; idempotency proven by a second run producing zero changes.
- [ ] **GitOps** — the full chain end-to-end: commit → CI builds the image → digest written back to
      the manifest repo → Argo syncs → drift detection → auto-heal. This is the capstone that makes
      every edge above visible in one flow.

**Add a shared `Artifact` primitive** (id, type, digest, manifest, provenance chain, build status,
scan findings) that every engine can produce and consume. That single abstraction is what makes the
cross-technology edges gradeable instead of narrative — and it is the natural home for the staged
cross-tech capstones §C3 says are missing (1 of 213 today).

---

# X5 — NEW EPIC: OPERATIONAL ROUGH EDGES

**Owner ask:** *"real world ops always add layers like managing API keys securely or dealing with
unexpected cloud cost spikes — how our platform handles those operational rough edge cases beyond
just lab exercises."*

This is the most under-served dimension on the platform: **every lab is a clean-room technical
puzzle. None of them is an operational judgement call.** These scenarios are what separate a
certified engineer from a trusted one, and none of them exist today.

## X5a. Secrets & API key management
- [ ] Leaked key in git history → detect, rotate, invalidate, backfill (**you are living this
      exact incident right now — see §S1/S4; it is the best possible scenario source**)
- [ ] Key rotation with **zero downtime**: dual-key overlap, staged rollout, verify old key unused
      before revoking
- [ ] Vault: sealed vault outage → unseal → restore service (you have this incident documented);
      AppRole vs token auth; **dynamic short-lived DB credentials** vs a static password;
      lease renewal and revocation
- [ ] A key with excessive scope → cut to least privilege without breaking the caller
- [ ] Secret in a container env var visible via `docker inspect` → move to a mounted secret
- [ ] Kubernetes `Secret` base64 mistaken for encryption → enable encryption at rest / external
      secrets operator
- [ ] CI secret exfiltration via a malicious PR from a fork (`pull_request_target`) — **exactly the
      unpinned-action risk in §S6**
- [ ] Expired TLS cert / expired service-account key at 03:00 — detect, replace, prevent
- [ ] Cross-account IAM `AssumeRole` with a missing/incorrect trust policy and `ExternalId`
- [ ] Long-lived static AWS access key → migrate to OIDC / IRSA / workload identity federation

## X5b. Cloud cost spikes and FinOps
- [ ] **Bill jumped 4× overnight — find the cause with the data available.** Cost Explorer /
      billing surfaces exist (`billing` app, `cost-explorer` scenarios) but there is **no `ce` CLI
      support** (§4 of the AWS audit) and no cost model. Build one: per-resource hourly rate, so
      cost becomes a *derived metric a learner can move*.
- [ ] Orphaned resources: unattached EBS volumes, **snapshots orphaned by AMI deregistration**
      (ties to X3), idle NAT gateways, unassociated Elastic IPs, forgotten load balancers
- [ ] NAT gateway data-processing charges from in-VPC S3 traffic → add a VPC endpoint
- [ ] Cross-AZ / egress transfer charges from a misplaced replica
- [ ] A runaway autoscaling loop, or a CronJob spawning unbounded pods
- [ ] GPU instances left running after a training job (highest-value in the AI verticals)
- [ ] S3 lifecycle absent → petabytes in Standard; incomplete multipart uploads billed invisibly
- [ ] CloudWatch/log ingestion cost from a debug-level logger left on in prod
- [ ] Reserved-instance / savings-plan coverage vs on-demand tradeoff under changing load
- [ ] **Budget alarm → anomaly detection → tag-based showback → a kill switch that must not take
      prod down.** The judgement call is the lesson.
- [ ] Untagged resources make attribution impossible → enforce tagging via policy retroactively

## X5c. The wider operational surface (all currently absent)
- [ ] **Change management under pressure** — you have the Jira @team change-window machinery (X2)
      and it is genuinely good. Extend it: emergency change vs CAB approval, a change that must be
      rolled back mid-window, a conflicting concurrent change, a freeze period.
- [ ] **Incident command** — sev classification, comms cadence, status page, stakeholder updates,
      handoff across shifts, blameless postmortem with action items. `warroom_consumer.py` already
      exists as scaffolding.
- [ ] **On-call reality** — alert fatigue, a noisy alert that must be tuned not silenced, a runbook
      that is wrong, paging the wrong team, escalation timeout
- [ ] **Capacity & quota** — hitting an AWS service quota mid-incident and needing a limit increase;
      k8s `ResourceQuota` / `LimitRange` blocking a deploy; disk filling at 02:00
- [ ] **Data safety** — restore-verify drills (§F7), a backup that has silently failed for 3 weeks,
      PII in logs, a GDPR deletion request across systems
- [ ] **Multi-tenancy & blast radius** — a change correct in staging that breaks one tenant;
      canary/percentage rollout; feature-flag kill switch
- [ ] **Vendor & dependency reality** — an upstream provider outage you cannot fix, a deprecation
      notice with a deadline, a breaking minor-version bump, an expiring license
- [ ] **Communication artifacts as graded output** — the learner writes the incident update, the
      RFC, the postmortem, the runbook. Grade the *artifact*, which is exactly what the interview
      rubric work in §I11 needs anyway (shared rubric engine — build once, use twice).

**Why this matters more than more technical labs:** the platform currently has ~7,280 technical
puzzles and **zero** scenarios where the right answer is "escalate", "roll back", "accept the cost
and file a ticket", or "do nothing until the change window". Freshers do not know these exist;
experienced engineers judge a platform by whether they do. **A dedicated `ops-engineering` /
`sre-practice` technology with 60–100 of these would differentiate the product more than another
150 templated YAMLs.**

---

# X6 — DATACENTER: FROM DIGITAL TWIN TO ACTUAL GAME

**Owner reference:** [Data Center Simulator (Steam 1917160)](https://store.steampowered.com/app/1917160/Data_Center_Simulator_Game/)
and the Softonic *Data Center* title. These are **management/tycoon sims with a walkable 3D world** —
build mode, economy, contracts, progression — not read-only digital twins.

**Sequencing is non-negotiable: X1 first.** Fixing the sticky-2D trap and the one-room limit is what
makes any of the rest visible. Then §D1–D13 (collision, pointer lock, dispose, bloom, textures).
**Everything below is the layer that is genuinely missing after that** — it is game design, not
rendering.

## X6a. Walk the whole facility (prerequisite)
- [ ] Extend the 3D twin to all 10 room types (X1c) — data hall, network/MDF, mechanical (chillers,
      CRAC plant), electrical (switchgear, UPS room, generator yard), campus/exterior, security
      (mantrap, badge desk, CCTV wall), office/NOC, logistics (loading dock, staging, e-waste),
      safety (FM-200, EPO)
- [ ] Real transitions — doors, corridors, stairwells, badge-gated zones — not portal teleports
- [ ] Multi-floor with elevators/stairs; raised-floor and ceiling-plenum crawl spaces
- [ ] Persist player position per room across sessions (currently nothing is saved)

## X6b. Build / place mode — the core tycoon loop
- [ ] Place and remove racks on a floor grid with **real constraints**: floor loading (kg/m²),
      aisle clearance, hot/cold aisle orientation, containment panels
- [ ] Install servers into specific U positions honouring `u_height` (§D14), blanking panels, rails,
      cable management arms
- [ ] Run cabling by hand: pick a route, respect bend radius and length limits, patch through panels,
      label it. **Bad cabling must have consequences** (airflow blockage, a link that negotiates
      down, an unlabelled cable you cannot trace during an incident).
- [ ] Place PDUs (two per rack, A/B feeds — §D14), CRAC units, containment, sensors, cameras
- [ ] A validation/inspection pass that flags code violations before you can energise
- [ ] Undo/redo, blueprint save/load, and a copy-a-row tool

## X6c. Economy, contracts, progression
- [ ] Capital vs operating cost: buy hardware, pay for power (kWh × PUE), cooling, bandwidth, staff
- [ ] **Customer contracts with SLAs** — accept a tenant needing N kW and M U at 99.99%; breach the
      SLA and pay credits. This is the mechanic that makes every technical failure *matter*.
- [ ] Revenue, P&L, and a cost dashboard — **shares the cost model with X5b, build it once**
- [ ] Tech tree / upgrades: higher-density racks, liquid cooling, free cooling, on-site solar +
      battery, better UPS efficiency, DCIM automation
- [ ] Reputation and growth: unlock a second hall, then a second site with DR obligations
- [ ] Certification/compliance objectives — Tier II/III/IV concurrent maintainability, ASHRAE
      envelope (`facility_ops.py:225` already models the class), PUE/WUE targets

## X6d. Live ops as gameplay
- [ ] **A real-time incident feed with an SLA clock** — the ticket beacons
      (`DatacenterTwin3D.jsx:1089-1144`) are already good quest markers; give them stakes, a timer,
      and a consequence
- [ ] Requires the thermal model from §D14 — **without load→temperature coupling there is no
      jeopardy at all.** This is the highest-value backend change for game feel.
- [ ] Cascading failures: a breaker trips → a feed drops → single-corded servers die → a rack goes
      dark → an SLA breaches → a customer churns
- [ ] Scheduled maintenance windows you must plan around live load
- [ ] Hire/schedule staff with skills, shifts, and fatigue; dispatch them to tickets
- [ ] Inventory: spares on the shelf, RMA lead times, a part you do not have at 03:00
- [ ] Environmental events: heat wave, utility brownout, water restriction, a fire alarm requiring
      evacuation and EPO judgement
- [ ] Physical security as gameplay: tailgating, an unescorted visitor, a propped door

## X6e. Presentation to close the gap with the reference titles
- [ ] Bloom + SSAO + a proper tone-mapped dark room (§D12) — **highest visual return per hour**
- [ ] PBR textures: perforated floor tile, rack mesh doors, brushed metal, cable jackets (§D12)
- [ ] Animated hardware: spinning fans (exists), LED activity tied to real traffic (exists), hot-swap
      drive caddies, sliding rails, opening doors
- [ ] Full sound design — footsteps off the existing `bobPhase` (§D13, nearly free), fan wall
      hum by proximity, relay clacks, alarm klaxon, HVAC startup
- [ ] Alarm lighting state: red wash + strobe on thermal/power emergency (§D13)
- [ ] Camera modes: first person, orbit, top-down build view, and a CCTV/NOC wall view
- [ ] Photo mode / shareable floor plan — free marketing
- [ ] Gamepad + a real mobile control scheme, not a hidden HUD (§D6)
- [ ] Onboarding: a proper tutorial and a controls screen in the pause menu (§D13)

**Framing:** you already have a stronger *domain simulation* than either reference title — correct
center-of-gravity tip risk, UPS SoC drain, ASHRAE classes, PUE/WUE. What those games have that you
do not is **agency (build), stakes (economy/SLA), and progression.** Add those three on top of a
fixed 3D world and this becomes a genuinely differentiated product, not a twin with a walk mode.

---

# X7 — PLATFORM-WIDE ENHANCEMENT SWEEP

Owner ask: *"check more enhancements in all technologies and projects and simulations and scenarios
and lab and buttons and links and pages and views."* §H1–H10 and §W1–W14 cover the verified defects;
these are the systematic gaps found alongside them.

## X7a. Navigation, links, buttons — make everything reachable
- [ ] Ship the missing routes: `/projects`, `/journeys`, `/journeys/:slug` (§C3, §C4); fix
      `/simulators` reachability (§H4); delete `/aws-sim/*` (§H5)
- [ ] **Add a route-reachability CI test**: assert every route in `AppRouter.jsx` has ≥1 inbound
      `Link`/`navigate`, or is explicitly allowlisted as deep-link-only. This is what would have
      caught §H4/§H5, and it is cheap.
- [ ] Audit every button for a disabled state with **no explanation** — `checkDisabled` /
      `extendDisabled` are threaded everywhere but there is no tooltip saying *why*
- [ ] Consistent primary action per page — several pages have two competing primary buttons
- [ ] Breadcrumbs on all detail pages; every fullscreen surface needs a visible exit (§H1, §H3)
- [ ] Empty states must offer the next action, not just say "nothing here" (§W5)
- [ ] Global search / command palette across scenarios, technologies, tutorials, projects — 7,280
      scenarios with only per-technology browsing is the real discoverability ceiling
- [ ] Keyboard shortcuts + a discoverable shortcut sheet
- [ ] Deep links that survive auth: bounce to login and **return to the intended page**

## X7b. Views and pages
- [ ] Dashboard: surface the active lab, the next journey step, and the weakest competency — it is
      currently 10 parallel fetches that silently fail (§W5)
- [ ] Scenario list: filter by difficulty, free/paid, sim type, completion, **and whether it is
      actually gradeable** once §G is fixed
- [ ] Technology detail: show real depth per technology (topics covered, not scenario count) so the
      §Phase-8 storefronts stop looking equivalent to `linux`
- [ ] A learner-facing progress/competency view mapped to journey steps and cert objectives
- [ ] Session replay exists (`SessionReplay.jsx`) — surface it after every lab as a review tool
- [ ] Admin: the 88 `adminpanel` routes have 1 test file (§B7) — content-health dashboards for
      grader coverage, dangling slugs, and duplication would make §G regressions visible
- [ ] Print/export: certificates work; add exportable lab reports and postmortems (§X5c)

## X7c. Scenario and lab UX
- [ ] Hints: 5 rungs exist on most scenarios but 73.8% are identical ladders (§Phase 8) — make
      hints progressive and scenario-specific, and show a cost/XP tradeoff
- [ ] Show acceptance criteria as a **live checklist** that ticks off as the learner satisfies each
      one — needs §G's per-objective assertions, and is the single best learner-facing payoff from
      fixing grading
- [ ] "Why did this fail?" on a failed check — currently generic (§G6)
- [ ] Reset-to-clean-state and reset-to-broken-state buttons
- [ ] Difficulty is `easy/medium/hard` with 60% `medium` (§C8) — introduce a real `expert` tier
- [ ] Estimated time vs actual, so `estimated_minutes` becomes honest
- [ ] Bookmarks and notes per scenario (`Bookmarks.jsx` exists — wire it into the lab surface)

## X7d. Cross-cutting engineering
- [ ] **One shared rubric/grading engine** for scenario objectives, interview answers (§I11), and
      written ops artifacts (§X5c) — three consumers, build once
- [ ] **One shared cost model** for FinOps scenarios (§X5b) and the datacenter economy (§X6c)
- [ ] **One shared `Artifact` primitive** (§X4)
- [ ] A shared `useFetch` with abort + error states (§W6) and centralized 403 handling (§W7)
- [ ] Frontend Sentry (§O8) — without it, every bug in this document is invisible in production

---

# REVISED PHASE PLAN (v2 — ⚠️ SUPERSEDED)

> **⚠️ SUPERSEDED by `MASTER PLAN — FINAL CONSOLIDATED` at the end of this document.** Kept for the
> per-epic rationale — do not sequence work from here.

Phases 1–9 stand as written. These are the insertions and changes.

**Phase 1 (Security + stop-the-bleeding)** — add the two owner-reported bugs. They are small,
high-visibility, and independent of everything else:
- **X1a/X1b — datacenter sticky-2D trap** (transient fallback + versioned key + `Suspense` outside
  the boundary + self-host the HDRI). Small fix, and it is the reason the 3D work looks absent.
- **X2a — Jira comment polling + pending-reply indicator.** Fixes "No reply is coming" outright.
- **X2b — durable team-reply delivery** (pending row + beat sweeper) and log every drop path.

**Phase 4 (3D datacenter)** — prepend **X1c** (extend 3D to all 10 rooms) as the first task; walking
the facility is prerequisite to game feel. Keep §D1–D13. Append **X6e** presentation work.

**New Phase 4.5 — Datacenter becomes a game** (after Phase 4 and the §D14 thermal model):
X6b build/place mode → X6c economy, contracts, SLA, tech tree → X6d live-ops gameplay.
Gate on the load→temperature coupling in §D14 — **without it there is no jeopardy.**

**New Phase 5.5 — Artifact provenance** (after Phase 5 simulator causality):
X3 golden image → AMI → EC2 with real failure propagation, then X4 across docker → k8s → MAAS →
linux → gcp → terraform → commvault → dellemc/netapp → peoplesoft → ansible/awx → gitops.
Build the shared `Artifact` primitive first. This is also where the missing staged cross-tech
capstones (§C3) come from.

**New Phase 7.5 — Operational rough edges** (can run parallel to Phase 7 content work):
X5a secrets/API keys → X5b cost spikes/FinOps → X5c change management, incident command, on-call,
capacity, data safety, comms artifacts. Consider a dedicated `ops-engineering` technology.
Shares the rubric engine with §I11 and the cost model with X6c.

**Phase 9 (Polish)** — absorb X7a/X7b/X7c, and add the **route-reachability CI test** alongside the
three CI rules from §G7.

## Dependency notes worth respecting
- X3/X4 failure propagation depends on §G's real state assertions — a marker-file grader cannot
  verify a provenance chain.
- X6d gameplay depends on §D14's thermal model. Build the model before the game loop.
- X5b and X6c are the **same cost model**. X5c and §I11 are the **same rubric engine**. X3/X4 share
  one **`Artifact`** primitive. Three shared components carry six epics — build them deliberately
  rather than three times.
- X1 before all other datacenter work. It is a few lines, and until it lands, every improvement to
  the 3D twin remains invisible to anyone whose browser is already poisoned.

---
---

# ADDENDUM 2 — 2026-08-06 (third pass)

Voice/multilingual interview, the IDE language bug, and the in-IDE API client. Everything verified
against code; the open-source model recommendations were verified against upstream sources
(licences and language coverage confirmed, not assumed).

---

# Y1 — AI INTERVIEW AS A REAL VOICE CALL AGENT (EN / HI / TE)

**Owner ask:** a real voice call-agent — conversational, responds to the candidate's answers *and
their questions*, sounds like a human not a machine, works in **Telugu / English / Hindi**, **free**.

## Y1a. Current state — measured, not estimated
| Layer | Reality | Evidence |
|---|---|---|
| TTS | Browser `speechSynthesis` **only** | `tts_service.py:28-39` returns the literal `"browser"`, `audio_b64=None`. `/tts/synthesize/` (`tts_views.py:38-52`) is live and returns null audio for every request. |
| STT | `webkitSpeechRecognition` **only** | `stt_service.py:39-61` returns `transcript: ""` always. `_transcribe_vosk()` (`:64-68`) is a bare `NotImplementedError`, and **`vosk` is not in `requirements.txt`**. |
| Generation | **Zero generated tokens** | `llm.py:1` — *"LLM module deprecated."* No LLM/AI SDK anywhere in `requirements.txt`. |
| Templates | **586 hardcoded entries** | Full inventory below. |
| Languages | **English only** | Every hit for `hi-IN`/`te-IN`/i18n across the stack is an `en-*` accent tag. |
| Transport | HTTP POST per turn | **Zero** WebSocket/SSE in the interview stack. Host sync is HTTP polling (`InterviewRoom.jsx:1214-1224`). |

**Template corpus — 586 entries, 0 generated:** `interview_ai.py` 306 (incl. `_REACTIONS` 37,
`_TOPIC_FOLLOWUPS` 49, `_TERM_DEFINITIONS` 33, `_ACK_GENERIC` 16, `_PHRASE_STOPWORDS` 100) ·
`question_generator.py` 134 (incl. `_TOOL_DRILLS` 58, `_CROSS_QUESTION_TEMPLATES` 15) ·
`realism/` 35 · `conversation/` 28 · `conversation_intelligence.py` 17 · others 66.

**Turn latency, measured:**
| Stage | Cost |
|---|---|
| Trailing-silence endpointing | **2200–5000 ms** (`InterviewRoom.jsx:53`, `useInterviewVoice.js:1078-1079`) |
| SpeechRecognition finalization | 100–500 ms |
| POST → score + reply + next question | 150–600 ms |
| **Artificial** thinking delay | **500–3500 ms** (`timing.py:24-25`) |
| TTS first audio | 50–300 ms |
| **Total** | **~3.0 s best, ~9.9 s worst, ~4.5–6 s typical** |

Human conversational turn gaps are **~200 ms**. This is **10–30× too slow** — which is why it reads
as a machine *regardless of voice quality*. Two dominators, both deliberate: endpointing was
deliberately raised so a between-sentence breath never cuts the candidate off
(`InterviewRoom.jsx:48-52`), and the thinking delay was added *on top* to feel human. **The thinking
delay is now solving a problem the system no longer has.**

## Y1b. Why the voice sounds robotic — three specific causes (one is a real bug)
- [ ] **`browser_voice_hint` hard-overrides the quality ranker.** There *is* a good ranker —
      `_voiceNaturalnessScore()` (`useInterviewVoice.js:56-92`) gives **+60** for `\bnatural\b|\bneural\b`
      (correctly catching Edge's `Microsoft Aria Online (Natural)`), −50 for eSpeak/`david`/`zira`,
      −25 for `desktop`/`compact`. But `voice_service.py:34-66` defaults every profile to a *name*
      hint (`Neerja`, `Prabhat`, `Ryan`, `Samantha`, `Daniel`), and `pickBrowserVoice():114-117`
      treats a hint match as a **hard win that bypasses ranking entirely**. A box with the legacy
      macOS voice literally named "Daniel" gets pinned to it even when a Natural voice scoring far
      higher is present. **Delete the stale name hints — highest naturalness-per-line-changed fix
      in the file.**
- [ ] **Architectural ceiling.** On stock Chrome/Linux or Windows without the Edge Natural pack, the
      *entire* candidate list is eSpeak/SAPI5. The ranker can only find the least-bad robot. There is
      no better fallback because there is no server synthesis. **Not fixable client-side.**
- [ ] **No prosody variation.** `segmentForSpeech()` (`:134-162`) + `pauseAfter()` (`:167-174`,
      `?`→340ms `.`→240ms `,`→150ms) is genuinely good work, but the Web Speech API has no SSML — no
      emphasis, no intra-sentence pitch contour, no breath, no variable rate. **Every sentence gets
      identical prosody, which is exactly what the ear identifies as synthetic.**
- [ ] **Fake STT confidence — real bug.** `:1088` seeds `lastConfidence = 0.8` and `:1191` uses
      `res[0].confidence || lastConfidence`. Chrome reports `confidence: 0` on interim and often on
      final, so the `||` short-circuits to the **fabricated 0.8**. Consumers treat it as real:
      `assessTranscriptClarity()` (`InterviewRoom.jsx:88`) flags unclear below 0.42 and
      `phrasing.py:89` injects disfluency below 0.45. **Both recovery paths are effectively
      unreachable** — the interviewer never says "I didn't catch that."
- [ ] ~200 lines (`:290-501`) fight Chrome's autoplay policy — `_speechHoldActive`, near-silent
      `'.'` utterances at `volume=0.02`, a 2500 ms `resume()` keepalive for Chrome's ~15 s cutoff,
      `waitForSynthIdle()` to avoid `cancel()` ("the #1 silent-join cause", `:789`). **All of it
      becomes deletable** once audio is server-generated and played through `<audio>`.

## Y1c. Conversation realism — what's genuinely there vs missing
**Real and worth preserving:** barge-in via `AnalyserNode` VAD (`InterviewRoom.jsx:374-393`);
dynamic endpointing that extends on trailing connectors — `endsOnConnector()`
(`useInterviewVoice.js:198-211`, 44 words + 19 phrases) so "and…"/"because…" earns think time
(a genuinely clever idea a pure-energy VAD cannot replicate); `continuous` restart resilience
(`:1221-1234`) so a pause-laden answer stays one turn; thinking-pause modelling with persona windows
and ±15% jitter (`timing.py:28-90`); phrase quoting (`_extract_quote_phrase()`,
`interview_ai.py:733`) producing *"You touched on 'the cache TTL' — let's dig into that"*; the
probe ladder narrow→hint→move_on (`probe.py:47-93`); `CampaignMemory` (`memory.py:12-52`).

- [ ] **The substance is always a pool pick.** `interview_ai.py:1014-1024` — strong→9 lines,
      weak→5, brief→5. The interviewer reacts to **quality buckets and detected topic, never to the
      actual claim.** Ask about Kafka consumer lag, get a generic Kafka question from a 4-item list.
      With pools of 4–9 and a 20-turn round, **the candidate hears the same opener 3–5 times**
      (de-dup only spans the last 6 messages, `engine.py:607`).
- [ ] **Candidate questions ARE handled — within 33 terms.** `is_candidate_question()`
      (`:1359-1399`) → `detect_question_intent()` (`:1267-1301`, repeat/definition/clarify/scope) →
      `_define_term()` against `_TERM_DEFINITIONS` (`:396-437`, **33 entries**, mostly K8s/AWS/SRE).
      Anything else deflects to *"think of it in plain terms."* **A real interviewer answers
      anything; this answers 33 things.** Ask "what's the on-call rotation like?" and you get a
      brush-off.
- [ ] **Backchannels are text-only and never heard.** `backchannel.py:13-22` has 8 cues;
      `InterviewRoom.jsx:1402-1404` explicitly disables audio because *"speaking over the live mic
      pollutes Web Speech STT."* They **tried** it and it broke STT. This is an **AEC problem, not a
      logic problem** — and audible "mm-hmm" is one of the strongest human signals available.
- [ ] **Strictly half-duplex.** `voiceAnswer()` calls `cancelSpeech()` before listening. No AEC, no
      listen-while-speaking.
- [ ] **Reply RNG is unseeded** despite the comment at `interview_ai.py:890` claiming *"Seed RNG off
      what's been said."* `:891` is `random.Random()`. Same in `generate_clarify_probe():1152`,
      `generate_round_closing():1123`, `generate_transition_bridge():1181`,
      `generate_force_advance_reply():1231`. Nondeterministic and untestable.
- [ ] Firefox and Safari have **no voice interview at all** (no `webkitSpeechRecognition`).
- [ ] **Chrome Web Speech is not offline** — it streams audio to Google. `stt_service.py:4,60`
      comments claim "100% FREE / offline-capable." For an interview product handling candidate
      speech, **this needs to be stated explicitly or replaced.** Replacing it (Y1e) fixes the
      privacy posture *and* the quality *and* the confidence bug in one move.

## Y1d. Multilingual — currently zero, and the hard part is scoring not TTS
Complete inventory of language-adjacent code: `models.py:67` `voice_locale` default `"en-IN"` ·
`voice_service.py:37-65` six profiles (`en-IN`×2, `en-GB`×2, `en-US`×2) ·
`useInterviewVoice.js:89` **`if (voice.lang?.startsWith('en')) score += 8`** — a hard English bias
in the ranker, with the comment *"Prefer English overall for these interviews."*
There is **no `USE_I18N`, no translation catalog, no language selector, and no non-English string
anywhere in the interview stack.** `voice_locale` is an *accent* picker for English, not a language.

What must change end to end:
- [ ] **Question text** — ~15 English template banks composed by f-string slot-filling. Hindi and
      Telugu are SOV with postpositions, and Telugu is agglutinative. **English slot templates cannot
      be mechanically translated** — `"You used {tool} for {claim} — how'd you confirm it held up?"`
      has no word-order-preserving Telugu equivalent. Needs generation (Y1f), not translation.
- [ ] **Scoring — the deepest breakage.** `_STAR_*` (`interview_ai.py:20-44`, ~100 English phrases),
      `_TECHNICAL_DEPTH` (`:46-54`), `_CONCRETE_EVIDENCE` (`:56-61`), `_KEYWORD_SYNONYMS` (`:70-112`)
      — **zero Hindi/Telugu recall**. `_FILLER_RE` (`:64-67`) strips `um/uh/like`; Hindi (`मतलब`,
      `यानी`) and Telugu (`అంటే`) fillers pass through and **inflate word counts**, which feeds the
      §I1 length heuristics. `analysis.py:49` hardcodes `spacy.load("en_core_web_sm")` — **spaCy has
      no Telugu model at all**, so entity extraction returns empty and follow-up slot-filling
      (`generate.py:72-86`) degrades to raw text slices. `analysis.py:63` is
      `TfidfVectorizer(stop_words="english")`. `normalize.py:8-24` has 15 English STT repairs
      (`"kube cuttle"`→`kubectl`); Indic mishearings are entirely different.
- [ ] **The fix also solves code-switching for free.** The realistic case is Telugu grammar with
      English technical nouns — *"ఆ pod restart చేసి logs check చేస్తాను"*. **No keyword list will
      ever handle that.** Replace the keyword lists with multilingual embeddings
      (`paraphrase-multilingual-MiniLM-L12-v2`, Apache-2.0, or AI4Bharat **IndicBERT**) scoring
      cosine similarity to reference answers. This is the **same change §I1 needs anyway** — build
      it once, get English rigour and multilingual support together.
- [ ] `InterviewRound.language` field (`en`|`hi`|`te`), candidate-facing selector, threaded to ASR
      language, TTS voice, generation prompt, and UI locale
- [ ] Make the `startsWith('en')` bonus (`useInterviewVoice.js:89`) conditional on round language
- [ ] Frontend i18n (`react-i18next`) — mechanical but `InterviewRoom.jsx` alone is 2,571 lines of
      literals
- [ ] **Do not translate the 586 templates.** Once generation lands they retire to few-shot English
      examples — they encode real interviewer voice and are valuable as exemplars, not as output.

## Y1e. The verified free stack
**Licences and language coverage below were checked against upstream sources, not assumed.
Items marked ⚠ still need empirical verification on your hardware and your accents.**

**TTS**
- [ ] **English → [Piper](https://github.com/rhasspy/piper)** (MIT, ONNX, CPU-only, ~50–150 ms/sentence).
      `en_US-lessac-medium` / `en_GB-alba-medium`. Clearly better than eSpeak/SAPI.
      ⚠ Piper advertises 35+ languages and lists Telugu among them, but I could **not confirm a
      specific `te_IN` voice exists** — verify against the live catalog before relying on it.
- [ ] **Hindi + Telugu → [IndicF5](https://huggingface.co/ai4bharat/IndicF5) (AI4Bharat).
      Verified: MIT licence, 0.4B params, 11 Indian languages explicitly including Hindi AND
      Telugu**, trained on 1,417 h (Rasa, IndicTTS, LIMMITS, IndicVoices-R), described as
      near-human. **This is the answer for Telugu** — and MIT means commercial use is fine.
      Note: it is a **reference-audio voice-cloning** model — it needs a prompt clip + that clip's
      transcript, so you must record or licence a consented reference voice per interviewer persona.
      Their terms require permission for any cloned voice. ⚠ Verify latency on your droplet; 0.4B is
      likely GPU-preferred for realtime.
- [ ] **Stream sentence-by-sentence** over WS as the reply composes → time-to-first-audio ~200 ms
      instead of waiting for the full string. Keep browser `speechSynthesis` as offline fallback.
- [ ] Avoid **XTTS-v2** for this: expressive, but the Coqui Public Model License is **not
      unrestricted commercial** — verify before any commercial use. Kokoro-82M (Apache-2.0) is a
      good English alternative.

**STT**
- [ ] **English → [faster-whisper](https://github.com/SYSTRAN/faster-whisper)** (MIT wrapper,
      CTranslate2, MIT weights). Use `small`/`medium` — **`tiny`/`base` are too weak for
      Indian-accented technical English.** Gives real `avg_logprob`/`no_speech_prob`, which finally
      makes the unclear-audio and disfluency paths in Y1b functional.
- [ ] **Hindi + Telugu → AI4Bharat [IndicWhisper](https://ai4bharat.iitm.ac.in/areas/model/ASR/IndicWhisper)
      / [IndicConformer](https://github.com/AI4Bharat/IndicConformerASR).** Verified: IndicWhisper
      fine-tuned on the [Vistaar](https://github.com/AI4Bharat/vistaar) train set achieves the
      **lowest WER on 39 of 59 benchmarks**, outperforming public models; IndicConformer covers all
      22 official Indian languages. ⚠ Verify licence per model before shipping.
- [ ] ⚠ **Code-switching is the make-or-break case and I could find no Telugu code-switch benchmark.**
      Test with your own recordings before promising Telugu. Dedicated Hinglish ASR models exist and
      are worth evaluating for the Hindi case.
- [ ] Feed `initial_prompt` with the domain vocab **already in the repo** —
      `callbacks.py:14` `_TECH_HINTS` (40) and `question_generator.py:318` `_TOOL_DRILLS` keys (30) —
      a cheap, large accuracy win on `kubectl`/`nginx`/`terraform`.
- [ ] The `AudioRecorder` + `serverTranscribe` path (`useInterviewVoice.js:601-660`) is **already
      written and dead-gated** on `uses_server_stt`. Wiring it live is mostly deleting a false gate.

**Endpointing + duplex**
- [ ] **[Silero VAD](https://github.com/snakers4/silero-vad)** (MIT, ~1 MB, sub-ms per 30 ms frame).
      Target **400–700 ms** endpointing vs today's 2200–5000. Run it on the `AnalyserNode` pipeline
      that **already exists** for barge-in (`InterviewRoom.jsx:374-393`) — the signal is there and
      simply isn't wired to endpointing.
- [ ] **Keep `endsOnConnector()` as a semantic override** — combine both signals rather than
      replacing one with the other.
- [ ] **Delete the artificial thinking delay** (or cap ~300 ms with small jitter).
- [ ] **WebRTC/speex AEC** so TTS doesn't bleed into ASR → unblocks the audible backchannels
      disabled at `InterviewRoom.jsx:1402-1404`.
- [ ] **Post-fix budget: ~500 ms VAD + ~300 ms ASR + ~200 ms generation + ~200 ms TTS ≈ 1.2 s** —
      not human-200ms, but firmly "acceptable phone call", a **4× improvement**.

**Prerequisite: ASGI + WebSocket.** Streaming TTS, streaming ASR and sub-second turns are all
impossible over POST-per-turn. Add **Django Channels** (`channels` + `daphne`/`uvicorn`) — one WS per
round carrying bidirectional audio frames + JSON events. Note the platform **already runs Channels
consumers** for the terminal (`apps/terminal/consumers.py`) and baremetal, so this is an established
pattern here, not new infrastructure.

## Y1f. Generation — the only path to "indistinguishable"
- [ ] No template corpus at any size responds to unanticipated content. 586 entries is already past
      diminishing returns. Self-host via `llama.cpp` (MIT) or vLLM (Apache-2.0):
      **Qwen2.5-7B-Instruct (Apache-2.0)** is the strongest permissive multilingual option in this
      class with real Hindi capability. ⚠ Telugu is weaker — for Telugu specifically evaluate
      AI4Bharat's **Airavata / IndicLLM** family (verify licence). Avoid Gemma (Gemma Terms, not
      standard OSS) and Llama (community licence restrictions) unless you accept those terms.
      ⚠ Q4_K_M ≈ 5 GB VRAM; realtime on CPU-only is doubtful — verify on target hardware.
- [ ] **Architecture: rules decide *what* to say, the LLM decides *how* to say it.** Keep
      `policy.py:36-79` `decide_next_move()` (9 well-reasoned moves) as the **plan**; keep
      `probe.py:47-93` as the state machine and let the LLM phrase each rung; feed
      `CampaignMemory` as context. **Do not let an LLM grade** — keep `analysis.py`/`scorer.py`
      deterministic so a disputed score is auditable and defensible.
- [ ] This also gives the candidate-question path unbounded coverage instead of 33 terms.

## Y1g. Immediate fixes, independent of the whole stack
- [ ] Drop stale `browser_voice_hint` names — `voice_service.py:34-66` (Y1b)
- [ ] Stop faking STT confidence — `useInterviewVoice.js:1088` (Y1b)
- [ ] Seed the reply RNG — `interview_ai.py:891` + 4 more (Y1c)
- [ ] `hash()` → `blake2b` — `question_generator.py:876-880` (§I8)
- [ ] Fix false docstrings advertising Whisper/ElevenLabs/Polly — `stt_views.py:31`, `tts_views.py:31`
- [ ] Qualify the "offline/100% free" claims — `stt_service.py:4,60` (privacy-relevant)

---

# Y2 — CODING IDE: WRONG LANGUAGE FOR 855 LABS, AND A NEW P0

**Owner report:** *"for html technology it is opening python ide, but it should be html and related
ide based on scenario."*

**Confirmed, and worse than reported.** Editor is **CodeMirror 6** (`CodeEditor.jsx:2-16`), not
Monaco. `CodingIDE.jsx:204` is `const language = spec?.language || 'python'` — **a missing or
unknown language silently yields a Python IDE**, with a Python Run button and Python new-file hints.

## Y2a. Language mismatches — 855 labs
| Tech | n | declared `language` | `entrypoint` | Verdict |
|---|---|---|---|---|
| **html** | **150** | `javascript` | `solution.js` | Labels lie; editable files are `index.html`/`styles.css`, hidden test asserts on `PAGE_HTML`. **Grader is right, metadata is wrong.** |
| **java** | **100** | `javascript` | `solution.js` | **Wrong language *and* wrong subject** — `parseMavenCoord()` implemented in JS. Zero Java in a Java lab. |
| **shell-script** | **100** | `javascript` | `solution.js` | **Wrong subject** — JS string exercises *about* shell, e.g. `assert(expandVar('hi $X','Ada')==='hi Ada')` |
| react / nodejs | 210 | `javascript` | `solution.js` | Label accurate; content is plain JS, no JSX |
| react / nodejs (2nd cohort) | 90 | **`python`** | `solution.py` | **Literally your report** — a React "key warning" lab in Python |
| sqlite / postgresql / mysql | 135 | `python` | `solution.py` | Placeholder |
| data-science / ai-ml | 82 | `python` | `solution.py` | Placeholder |
| prompt-engineering | 150 | `text` | *missing* | Routes to `PromptPlayground`, not the IDE — correct |

## Y2b. NEW P0 — 307 coding labs award XP for zero work
This supersedes the "82 placeholder labs" figure in §G5. Verified count:
`grep -rl "assert callable(solution)" --include=scenario.yaml scenarios/ | wc -l` → **307**
(sqlite 45, react 45, postgresql 45, nodejs 45, mysql 45, data-science 41, ai-ml 41).

```yaml
files: [{path: solution.py, content: "def solution():\n    raise NotImplementedError('Apply the fix')\n"}]
visible_tests: [{name: placeholder,        code: "assert callable(solution)"}]
hidden_tests:  [{name: placeholder_hidden, code: "assert callable(solution)"}]
```
**`assert callable(solution)` passes against the unmodified stub** — `NotImplementedError` never
raises because the function is never called. This is **fail-OPEN**: click Check Solution, get XP.
Exactly the class `incident_academy_broken_fix_regression` says grader-integrity does not catch.

Why CI misses it: `validate_scenario_catalog.py:410-414` only asserts `hidden_tests` is
**non-empty** — a tautology satisfies it — and CI runs `--flagship-only`
(`tests.yml:92`, `production.yml:422`), so **all 1,334 coding labs are essentially unvalidated.**

- [ ] Add the CI rules (Y2f) **first**, so no new ones can land
- [ ] Set `coding_mode: false` on all 307 and route to their real engines (mysql/postgresql/sqlite
      have working SQL surfaces; data-science/ai-ml have `aiml_engine.py`), or mark unpublished
- [ ] Backfill real tests tech-by-tech, flipping `coding_mode` back per lab
- [ ] **Do not ship a schema migration that leaves 307 tautologies gradeable under a new,
      more-official-looking `grader:` field**

## Y2c. Runtimes — only Python and Node exist
`backend/Dockerfile:9-17` installs `nodejs` on `python:3.12-slim`. **No JDK, Go, Rust, PHP, Ruby,
or dotnet anywhere.** Sandbox images (`sandbox_runner.py:55-56`): `python:3.12-alpine`,
`node:20-alpine`, `network_mode="none"`. `code_exec.py:63` `SUPPORTED_LANGUAGES = {"python","javascript"}`;
`:66` bash/shell → `NEEDS_REVIEW`; `:533` everything else → `needs_review`, never gradeable.

- [ ] **Ungradeable today:** Java, TypeScript, Bash/Shell, HCL/Terraform, Go, Rust, PHP, Ruby, C#, C/C++
- [ ] **`spec.language` currently selects the grading runtime** — so simply relabelling html to
      `language: html` makes all 150 hit `code_exec.py:533` and become `needs_review`.
      **Add explicit `runtime` + `grader` fields and consume them in `CodeValidateView:1337` in the
      same commit as any relabel.** This is the load-bearing change.
- [ ] Optional: add `default-jdk-headless` + `eclipse-temurin:21-jdk-alpine` and a `_build_java_harness`
      emitting the same `__FIXITLAB_RESULT__:` line so `_parse_verdict` (`:401-408`) is untouched —
      then rewrite the 100 Java labs in actual Java
- [ ] Prod fail-closed note: `_inprocess_grading_allowed` (`:424-442`) returns `False` when
      `SANDBOX_DOCKER` is on, so **a Docker-socket outage makes every coding lab ungradeable** with
      no operator alert. Add monitoring.

## Y2d. Live preview — exists, and is broken in seven ways
Path: `composeHtmlPreview.js` → `HtmlPreviewPane.jsx:24-29` → `<iframe sandbox="allow-scripts" srcDoc>`.
**Works:** hot reload on every keystroke (`useMemo` over `files`), sibling CSS and JS land via inline
injection (`:54-70`), harness files excluded by basename (`:19-20`), opaque origin (no
`allow-same-origin`).

- [ ] **Relative refs are never resolved or removed.** `<link href="styles.css">` and
      `<script src="app.js">` **remain in the output** (404 against `about:srcdoc`); CSS/JS work only
      via a *parallel inline copy*. Consequence: **`<script src>` position is destroyed** — a script
      authored in `<head>` is silently relocated to end-of-body, so a lab teaching script-placement
      semantics is unteachable and behaves differently from a real browser.
- [ ] **All CSS files are concatenated into every preview** (`:46-48`) regardless of what the page
      links. `theme-dark.css` + `theme-light.css` both apply.
- [ ] **No module support** — `<script type="module">`, `import`/`export`, `defer`, and JSX are all
      inlined as classic scripts. **React labs cannot preview at all.**
- [ ] **No console — the single biggest gap for 150 HTML labs.** No `postMessage` bridge, no error
      listener. The previewed page's `console.log` and uncaught exceptions **vanish**; the Logs pane
      only ever shows Pyodide/Worker output.
- [ ] No image/font/asset resolution (no `blob:` virtual FS)
- [ ] **Preview does not exist below the `lg` breakpoint** (`VsCodeWorkbench.jsx:86` `hidden lg:flex`,
      capped 420 px at `CodingIDE.jsx:1054`) — on a surface whose own scenario text says "open Preview"
- [ ] Only the first `index`-named file is previewable; `<a href="about.html">` 404s. No multi-page.
- [ ] Preview root is **guessed** (`index.html`, `:36`), never declared by the spec
- [ ] No responsive/device frame, no zoom, no element inspector

## Y2e. Other IDE defects
- [ ] **Hardcoded credentials in the shipped public bundle** — `CodingIDE.jsx:42-43`
      `IDE_LAB_USER='lab_ide'` / `IDE_LAB_PASS='lab_ide@123'`, compared client-side at `:736`, **printed
      on screen at `:780`**, with an autofill button. Bypassed entirely when `sessionId` is truthy
      (`:140`), so it is pure theatre — but any scanner will flag it. Delete it.
- [ ] **`composedSource()` concatenates every file into one blob** (`:331-335`, and
      `code_exec.py:69-111`). No module system: two files each declaring `const x` →
      `SyntaxError: Identifier 'x' has already been declared`; Python files are textually appended so
      `import` between learner files never works. **The 8-tab explorer and New Folder button advertise
      a project structure the execution model cannot honour.**
- [ ] Toy autocomplete: two hardcoded keyword lists (28 Python, 26 JS words, `CodeEditor.jsx:151-172`).
      Nothing for HTML/CSS/Java/shell.
- [ ] Toy linter: global paren/brace balance + tab-vs-space (`:174-207`). No parser. **No Problems panel.**
- [ ] Fake formatter: `formatDoc` (`:244-257`) re-indents to 4-space multiples of *existing*
      whitespace. Not a formatter. Wired to Ctrl+Shift+F **and format-on-save**.
- [ ] Toy grammars: HTML/CSS/Java/Shell/HCL are hand-rolled ~20-line `StreamLanguage` regex
      tokenizers (`:44-130`) — **no nesting, so CSS-in-HTML and JS-in-HTML are unhighlighted**
- [ ] **No integrated terminal** — `@xterm/xterm` is already a dependency and drives `LabTerminal`,
      but `coding_mode` replaces the entire lab surface (`LabRunner.jsx:2215`), so **coding labs are
      shell-less**. The "Terminal" tab is a read-only action transcript.
- [ ] **No server-side draft persistence** — localStorage only. Clearing site data or switching
      browser **loses all graded work**.
- [ ] Undo history destroyed on tab switch (`key={activePath}`, `:961`)
- [ ] No split view, no resizable panels (fixed CSS vars, `VsCodeWorkbench.jsx:30-35`), no
      find-across-files, no go-to-definition, no debugger, no snippets, no command palette (~18
      toolbar buttons, unusable below `lg`), no minimap, no breadcrumbs, no git/diff, no package
      install, no per-test re-run, editor theme is coupled to the **global** app theme (`:871`)
- [ ] Two divergent new-file-default implementations: `fileTree.js:57-68` vs `IdeExplorer.jsx:66-72`
      (the latter uses looser substring matching)

## Y2f. Fix: scenario-driven `coding_spec` + CI rules
```yaml
coding_spec:
  language: html            # AUTHORING language — drives editor, grammar, new-file hints
  runtime: node20           # EXECUTION target: node20 | python312 | java21 | bash5 | none
  grader: js-page-assert    # js-page-assert | js-unit | py-unit | http-assert | manual
  entrypoint: index.html    # must exist in files[] and match `language`
  preview:
    enabled: true
    root: index.html        # explicit — no more index.html guessing
    resolve_relative: true  # rewrite <link href>/<script src> to blob: siblings
    keep_script_position: true
    console: true           # bridge console.* + window.onerror to the Logs pane
    viewport: { width: 375, height: 667 }
  files:
    - { path: index.html,  role: source }
    - { path: styles.css,  role: source }
    - { path: solution.js, role: harness, readonly: true, hidden: true }   # NEW: never sent to client
  api_client: { enabled: false }   # see Y3
```
`hidden: true` matters: `public_coding_spec` (`views.py:1265-1276`) currently ships **every** file
including readonly harness stubs, so the learner sees a locked `solution.js` explaining the grading
mechanism.

**CI rules** — add to `validate_scenario_catalog.py` in the `if coding_mode:` branch, and **drop
`--flagship-only` for coding labs**:
- [ ] **R1** `language` declared (no silent `|| 'python'`)
- [ ] **R2** entrypoint extension agrees with `language`
- [ ] **R3** entrypoint exists in `files[]`
- [ ] **R4** `language` plausible for the parent technology (catches all 855 of Y2a)
- [ ] **R5** `runtime` has a real server interpreter (catches ungradeable labs at author time)
- [ ] **R6** at least one editable non-harness file
- [ ] **R7** hidden tests present (existing)
- [ ] **R8** no tautological tests — regex `^assert\s+callable\(\s*\w+\s*\)\s*$|^assert\s+(True|1)\s*$`
      (catches the 307)
- [ ] **R9 — the decisive one:** grade the **unmodified starter files** and require `all_passed ==
      False`. R1–R8 are metadata hygiene; **only R9 catches a fail-OPEN grader in general.**
      `backend/tests/test_academy_coding_ide.py:26` already does this for two labs — generalize to
      the whole catalog as a nightly job.
- [ ] **R10** `preview.root` exists in `files[]` when preview is enabled

---

# Y3 — IN-IDE API / POSTMAN CLIENT

**Owner ask:** *"if we play with api and that api response checker like postman also should show
right in ide and it should work that way."*

**Nothing exists today.** Zero hits for `postman|request-builder|ApiClient|HttpClient` in
`frontend/src/components/`; no `fetch`/`axios` in any `components/ide/` file. The only HTTP-shaped
thing in the platform is `_cmd_curl` (`rhel_shell.py:2687-2715`) — 28 lines, GET-only, resolves 4
hardcoded hosts, returns a canned `<html>` body based on nginx state. Everything else →
`curl: (6) Could not resolve host`.

**Hard constraint:** `sandbox_runner.py:235-236` sets `network_mode="none"` + `network_disabled=True`.
**A graded submission can never make a real socket call.** So the client needs two surfaces backed by
one definition.

- [ ] **`api_client` spec block** — environments/vars, seeded collection (method, URL, headers, auth,
      body), and **gradeable declarative assertions** (`status equals`, `header matches`,
      `json path equals`, `timing max_ms`), with hidden assertion variants
- [ ] **Request builder** as a new bottom-panel tab (`BOTTOM_TABS`, `CodingIDE.jsx:820-826`):
      method dropdown, URL bar with `{{var}}` interpolation, tabbed Params/Headers/Body/Auth.
      **Reuse `CodeEditor` with `language="json"` for bodies** — real `lang-json` grammar and lint for free.
- [ ] **Response viewer:** status pill + reason, wall-clock ms, byte size, headers table, body tabs
      Pretty (collapsible JSON tree) / Raw / Preview (reuse the sandboxed iframe machinery) / Headers.
      **Show the exact post-interpolation request that was sent** — essential for debuggability.
- [ ] **Interactive surface:** `POST /api/labs/<session_id>/api-client/send/` dispatching to an
      **in-process mock router** — never a real socket. Reuse the ephemeral session pattern already
      in `playground_engine.py:206-231` (`_Session`, `_LOCK`, `IDLE_TTL_SECONDS`, `MAX_SESSIONS=500`).
- [ ] **Grading surface:** inject a `globalThis.fetch = mockFetch` prelude into `_build_js_harness`
      (`code_exec.py:365-398`) generated from the same mock definition, so assertions run with **zero
      network** inside the network-less container. **Verdict parity is by construction — one source.**
- [ ] **Environments/variables**, collections, history ring buffer — persist into the existing
      localStorage draft (`CodingIDE.jsx:41,65-72`), seeded from the spec so labs are reproducible
- [ ] **Pre-request + test scripts** in the **existing `jsRunner.js` Web Worker** with a small
      `pm`-like shim (`pm.environment.set/get`, `pm.request.headers.add`). Zero new sandbox surface —
      the worker already has no DOM/cookie access.
- [ ] Keep the **advisory vs authoritative split** that already exists: interactive results are
      advisory (like `runVisibleTests`), grading re-runs the collection server-side (like `handleCheck`)

**Mock surfaces from engines you already have** — this is what makes it a *platform* feature rather
than a toy:
- [ ] **Kubernetes API** from `k8s_cluster.py` (already models `apiVersion`/`kind` objects at
      `:842,:864`) — `/api/v1/pods`, `/apis/apps/v1/deployments`. **Highest value: "talk to the K8s
      API instead of kubectl" is a real SRE skill.**
- [ ] **REST-over-SQL CRUD** from `playground_engine.py` sqlite — `/api/products`, `/api/orders`
      with real per-session persistence. The natural default for generic REST teaching.
- [ ] **Docker Engine API** from `docker_state.py` — `/containers/json`, `/images/json`
- [ ] **Prometheus HTTP API** from `monitoring_presets.py` — `/api/v1/query`, `/api/v1/query_range`
- [ ] **Jira REST v3** from the `jira` app — pairs with the existing `JiraTicketPanel` for a
      differentiated ITSM lab
- [ ] Cloud control-plane REST from `aws_bridge.py` / `azure_bridge.py` / `gcp_bridge.py`
- [ ] SIEM/alert API from `soc_bridge.py`
- [ ] **This is also the natural home for the X5a secrets scenarios** — API key in a header, rotate
      it, hit a 401, scope it down, and for X4 provenance (call a registry API to verify a digest)

---

# Y4 — IDE FEATURE BACKLOG
- [ ] **Server-side draft persistence** (P1 — localStorage-only is unacceptable for graded work)
- [ ] **Real module system** — per-file writes + real `import`/`require`, replacing blob concat.
      Unlocks the multi-file labs the explorer already advertises.
- [ ] **Integrated terminal** — `@xterm/xterm` is already a dependency; mount `LabTerminal` as a
      bottom-panel tab so coding labs aren't shell-less
- [ ] Real formatter (Prettier WASM for js/json/css/html, Black for python) replacing `formatDoc`
- [ ] Real diagnostics (Acorn / Pyright-lite via WASM) → **Problems panel**
- [ ] Real `lang-html` / `lang-css` / `lang-java` grammars replacing the toy tokenizers
- [ ] Split view + resizable panels; **preview must survive below `lg`**
- [ ] Command palette (Ctrl+Shift+P) — collapses ~18 toolbar buttons, fixes the mobile toolbar
- [ ] Preserve undo history across tab switches (per-path `EditorState` map, drop `key={activePath}`)
- [ ] Find-across-files; go-to-definition via a per-project symbol index (no LSP needed)
- [ ] Decouple editor theme from the global app theme
- [ ] Unify the two new-file-default implementations
- [ ] Per-test run / re-run-failed in the test explorer

---

# REVISED PHASE PLAN (v3 — ⚠️ SUPERSEDED)

> **⚠️ SUPERSEDED by `MASTER PLAN — FINAL CONSOLIDATED` at the end of this document.** Kept for the
> per-epic rationale — do not sequence work from here.

**Phase 1 (Security + stop-the-bleeding)** — add:
- **Y2e** delete hardcoded IDE credentials from the public bundle
- **Y1g** the six one-line interview fixes (voice hints, fake confidence, unseeded RNG, blake2b,
  false docstrings, "offline" claim)

**Phase 2 (Grading integrity)** — add, and note the count correction:
- **Y2b — the 307 tautological coding graders supersede the "82 placeholder labs" in §G5.**
  This is fail-OPEN and awards XP for zero work: **treat as the highest-priority item in Phase 2.**
- **Y2f CI rules R1–R10**, with **R9 (stub-must-fail) as the decisive rule**, and drop
  `--flagship-only` for coding labs

**New Phase 2.5 — IDE correctness** (small, high-visibility, unblocks 855 labs):
Y2c add `runtime`/`grader` and decouple from `spec.language` (**do this first — it is load-bearing**)
→ Y2a relabel html 150 → Y2d preview fixes (resolve relative refs, preserve script position, scope
CSS, **console bridge**, preview below `lg`) → honest labels or real runtimes for java 100 and
shell-script 100 → fail loudly on missing `language` instead of defaulting to Python.

**New Phase 6.5 — Voice call agent** (after Phase 6 interview credibility):
Y1e Piper for English **first — it is independent of everything else, needs no ASGI, no LLM, no
schema change, and it is what a candidate notices in the first three seconds.** Then ASGI/Channels
(pattern already established in `apps/terminal/consumers.py`) → faster-whisper + Silero VAD + AEC
together (shared audio path) → **IndicF5 (MIT, Telugu+Hindi verified)** and IndicWhisper →
Y1f generation with rules-plan/LLM-phrasing → Y1d multilingual end-to-end.
**Verify Telugu ASR code-switching empirically before promising it.**

**New Phase 7.6 — API client** (after Y3's mock surfaces have engines to point at):
Y3 spec + mock router + request/response panel, then the Kubernetes API and REST-over-SQL surfaces,
then wire it into the X5a secrets scenarios and X4 provenance checks.

**Phase 9 (Polish)** — absorb Y4.

## Cross-epic reuse (now four shared components, carrying eight epics)
- **Rubric engine** → scenario objectives (§G) + interview scoring (§I1) + ops artifacts (§X5c)
- **Multilingual embeddings** → fixes §I1 English rigour **and** Y1d Telugu/Hindi **and**
  code-switching, in one change
- **Cost model** → FinOps scenarios (§X5b) + datacenter economy (§X6c)
- **`Artifact` primitive** → all provenance chains (§X3/§X4) + API-client digest verification (Y3)

Build these four deliberately. Eight epics depend on them; building them per-epic is the single
largest avoidable cost in this plan.

---
---

# ADDENDUM 3 — FINAL SWEEP (2026-08-06, fourth pass)

Six remaining areas: the money path, auth/authorization, user-generated content, privacy/compliance,
scale/capacity/leaks, and the API/growth/testing/DX surface.

**Two things this pass proves that change the risk picture:**
- **`MAX_CONCURRENT_LABS = 60` is arithmetically impossible.** Verified: *all four* droplets are
  `s-2vcpu-8gb-160gb-intel` (`infra/digitalocean/cluster.json:4`). 60 × `512m`
  (`settings.py:569,573`) = **30 GB on an 8 GB box**. The graceful 503 gate never fires; you OOM instead.
- **The dynamic sitemap is unreachable in production.** Verified: `frontend/public/sitemap.xml`
  exists with **11 URLs**, there is **no nginx `location` for `/sitemap.xml`** anywhere in
  `gateway/`, and the real sitemap index *is* registered at `backend/config/urls.py:28`. nginx serves
  the stale static file; **~13,000 URLs are invisible to crawlers.**

---

# Z1 — BILLING & REVENUE

The **primary** Razorpay technology-subscription path (`billing/views.py:370-887`) is genuinely well
hardened: official SDK HMAC, `payment.fetch` capture re-verification, amount+order match, row locks,
durable `ProcessedWebhookEvent` idempotency. **Risk is concentrated in the five secondary payment
paths bolted on later**, each re-implementing verification with weaker rules and bypassing the ledger.

- [ ] **Z1-1 (P0, live revenue loss) — cart charges for ONE technology, UI collects the full total.**
      [Pricing.jsx:370-403](frontend/src/pages/Pricing.jsx#L370): `cartTotal` sums all items (`:264`)
      and the drawer renders `Subscribe All ({cart.length})` with that total (`:990,1001`) — then
      `const tech = cart[0]` (`:382`) creates an order for **one** item. Cart 5 × ₹499 → displays
      ₹2,495, charges ₹499, delivers 1. `createBatchOrders` exists (`api/subscriptions.js:113`) and is
      **never called**. Either disable multi-item checkout or wire the batch path.
- [ ] **Z1-2 (P0) — cert purchase breaks on the second sale ever.**
      [certifications/billing_views.py:66-86](backend/apps/certifications/billing_views.py#L66) omits
      `idempotency_key`, which is `unique=True` with no default (`billing/models.py:209`). First
      insert writes `""`; **every subsequent cert purchase raises `IntegrityError`** — after capture
      is already verified (`:174`) and after the subscription row is created (`:55-61`). Depending on
      `ATOMIC_REQUESTS`, either the customer is charged and the grant rolls back, or the ledger row is
      lost. Add a deterministic key + `get_or_create`.
- [ ] **Z1-3 (P0) — interview signature check lacks the DEBUG gate.**
      [interviews/billing_views.py:28-38](backend/apps/interviews/billing_views.py#L28) returns
      `DEMO_PAYMENT_ENABLED` when the secret is empty. Every sibling requires
      `DEBUG and DEMO_PAYMENT_ENABLED` (`views.py:817,852`, `razorpay_fulfillment.py:325`).
      Currently saved only by the settings clamp at `settings.py:777-785`. Add `and settings.DEBUG`,
      and set `DEMO_PAYMENT_ENABLED=false` in the server env (§pending_security_actions).
- [ ] **Z1-4 (P0) — Stripe webhooks are deduped by Redis cache only.**
      `payment_controller.py:591-598` uses `cache.add(..., 60*60)`; Razorpay was correctly hardened
      with durable `ProcessedWebhookEvent` (`:395-407`) *for exactly this reason*. **Stripe retries
      for up to 3 days**; a Redis restart re-runs `activate_interview_plan` → another 365 days on one
      payment. Wrap both Stripe dispatches in the same durable gate.
- [ ] **Z1-5 (P1) — the idempotency key includes `timezone.now()`, so the gate is a no-op.**
      `billing/models.py:240-243`. Every call is unique → the duplicate check at
      `payment_service.py:51-59` can never match, and `get_or_create(idempotency_key=…)` in the Stripe
      path (`interviews/billing_views.py:308-322`) always creates. **Prerequisite for Z1-4 being
      effective.** Key on `(user, product, amount, currency)` or the gateway order id.
- [ ] **Z1-6 (P1) — Stripe-tech and org-seat purchases write NO `PaymentTransaction`.**
      `billing/extended_views.py:374-391` and `:394-421` call `_create_technology_subscription`
      (`:128-145`) directly → no invoice, no GST breakup, no `gateway_payment_id`, invisible to
      payment history and revenue totals, and **impossible to refund through the product**. Org seats
      are ₹4,999 each (`:321`), so a 20-seat order is ₹99,980 with zero accounting record. Also never
      sets `payment_verified=True`, so paid subs read as unverified everywhere.
- [ ] **Z1-7 (P1) — legacy `/api/billing/create-order/` breaks on every renewal.**
      `payment_controller.py:102-134`: the duplicate guard filters `is_active=True`, but
      `TechnologySubscription` has `unique_together=("user","technology")` — so an expired/cancelled
      sub passes the guard and hits the constraint → 500. Use `get_or_create_technology_subscription`
      (`subscription_utils.py:189`) as the parallel path does. Same endpoint writes no GST breakup.
- [ ] **Z1-8 (P1) — refunds are built and unreachable, and the FAQ promises them.**
      `views.py:1546-1709` `RazorpayRefundView` is excellent (Decimal paise, row lock, cumulative
      ceiling, gateway idempotency header) with **zero frontend callers** — no method in
      `api/admin.js`, no UI in `AdminSubscriptions.jsx`. Meanwhile `FAQ.jsx:46-47` publicly commits to
      *"refunds within 7 days."* Also **a refund never revokes entitlement** — refunded users keep a
      year of access. Expose it, revoke on full refund, or amend the FAQ.
- [ ] **Z1-9 (P1) — interview certificates are a paid feature enforced nowhere.**
      `entitlements.py:213` exposes `certificate_enabled` (Free=False, Pro/Premium=True) but
      `issue_certificate` (`services/certificate.py:13-64`) is called unconditionally from
      `engine.py:1598`. `grep certificate_enabled` finds only serializers/admin/seeds. **The clearest
      UI-only paywall in the codebase.**
- [ ] **Z1-10 (P1) — client controls `currency` on the legacy order path.**
      `payment_controller.py:124`. Posting `{"currency":"USD"}` creates a **$499** order for a ₹499
      product — an ~83× overcharge that then passes verification (`payment_service.py:181` compares
      against the stored value). `CreateRazorpayOrderView` correctly hardcodes INR (`views.py:453`).
- [ ] **Z1-11 (P2) — no proration, no dunning, and `Subscription.expires_at` is never enforced.**
      `services.py:38-48` reads `max_labs_per_day` with **no expiry check** → a lapsed Pro plan keeps
      its elevated cap forever. Upgrades overwrite the term (`payment_service.py:257-267`) so
      remaining days are **forfeited**; `activate_interview_plan` **discards unused credits**.
      Cancellation is immediate with no end-of-term honouring (`views.py:1213-1266`). `past_due` flips
      inactive with no grace or retry (`views.py:242-257`). Seats are ratchet-only — an org can never
      shrink its bill (`extended_views.py:405`).
- [ ] **Z1-12 (P2) — no trial-abuse controls.** `free_campaigns_per_month` resets monthly per-user
      with no lifetime cap; `sample_interview_used` is one boolean; free-tech activation is
      one-per-user-per-tech. **All reset by registering a new email.** (Coupons, by contrast, are
      well handled — `coupon_service.py:63-83` uses a race-safe conditional UPDATE.)
- [ ] **Z1-13 (P2) — GST is misclassified on every sale.** `compute_gst(amount)` is always called
      **without `place_of_supply`** (`razorpay_fulfillment.py:46,212`, `certifications/billing_views.py:65`),
      so it defaults to the seller's state and **every Indian B2C sale is booked intra-state
      CGST+SGST**. No international tax treatment for USD Stripe charges. Invoice numbers
      (`invoice_service.py:10-13`) are **not a gapless series**, which Indian GST invoicing requires.
      (`gst.py` itself is genuinely good — tax-inclusive Decimal math so the sticker price is charged.)
- [ ] **Z1-14 (P2) — frontend payment UX.** No double-submit guard on `openRazorpayCheckout`
      (`PaymentPage.jsx:353`); network failure mid-verify shows a dead end with no retry or poll
      (`:484`); **`GST (included) ₹0` is hardcoded** (`:894-896`); `₹499` fallbacks are invented in 5
      places (`Pricing.jsx:264,343,392,688,943`); the displayed amount comes from an **editable URL
      query param** (`:165`).
- [ ] **Z1-15 (P2) — support can grant paid access with no record.**
      `billing/admin.py:164-167` and `:109-112` do bare `queryset.update(is_active=True)` — no audit
      row. `interviews/admin_views.py:384-403` grants a 10-year premium entitlement unlogged.
      `grant_complimentary_access` (`subscription_utils.py:225-240`) **does** write an `AuditLog` —
      that is the pattern to copy. There is **no immutable ledger**; `PaymentTransaction` is mutated
      in place.
- [ ] **Z1-16 (P2) — monetization gaps.** Interview prices are **hardcoded in the frontend**
      (`Pricing.jsx:819-821`) and will silently diverge from the DB. No monthly SKU (everything is
      365 days) at a ₹2,499 entry point. The `Plan` model (free/pro/enterprise) is **wired to Stripe
      and sold nowhere** — two parallel monetization models, one dead. Team/enterprise is
      contact-sales only. Regional pricing is naive FX division (`:243-249`).

---

# Z2 — AUTH & AUTHORIZATION

**This is the strongest area of the platform.** A programmatic sweep of **228 id/pk/slug-taking view
methods** across all 24 apps flagged 21 candidates; **all 21 verified as false positives. Zero
exploitable IDOR.** All **88 adminpanel routes** carry `IsPlatformAdmin`; Django admin is
superuser-only behind IP restriction. No privilege escalation or mass assignment — profile updates
field-pick (`accounts/views.py:504`), org settings use an `ALLOWED` tuple (`org_views.py:439`),
`is_staff` writes require superuser (`adminpanel/views.py:1075`). Password reset is textbook:
256-bit token, **SHA-256 hashed at rest**, 1h expiry, single-use, user-bound, and it blacklists every
outstanding refresh token (`:780-784`). Cookies are `httponly`+`secure`+`SameSite=Lax` with explicit
CSRF enforcement for cookie-auth (`cookie_auth.py:50`); **no token in localStorage.** Client IP comes
from the trusted proxy hop, not left-most XFF (`middleware_security.py:113`). Admin observer access is
**consent-based** with candidate approval (`join_views.py:195`). Keep all of this.

- [ ] **Z2-1 (P1) — the `audit` app is dead for all JWT traffic.**
      `apps/audit/middleware.py:39` only logs when `request.user.is_authenticated`, but the sole
      `request.user` provider is session `AuthenticationMiddleware`; JWT auth happens later at DRF
      dispatch, and `JWTSessionValidationMiddleware` sets only `request.jwt_user_id`
      (`middleware_security.py:92`). **Net: no `admin_action` row for any of the 88 admin routes, and
      `login` can never be captured.** The admin dashboard renders permanent zeros for `login`
      (`adminpanel/views.py:4304`), `lab_reset` (`:4305`), `security_alert` (`:4307`), `otp_failed`
      (`:4362`). Unlogged today: successful login, logout, password change, `is_staff` grant/revoke,
      admin delete/bulk ops, org role changes, complimentary grants. Only `login_failed` ×2 and one
      plan-change are actually written.
- [ ] **Z2-2 (P1) — the org invite token is decorative.** `org_views.py:387` mints
      `secrets.token_urlsafe(32)`, stores it, emails it — and **nothing ever validates it.**
      Redemption (`accounts/views.py:248`) matches on `email__iexact` only. A stale pending invite
      silently confers its role (**including `admin`**) on whoever next registers that address.
      Bounded by OTP email verification, so not directly exploitable. Same block: when seats are full
      `accepted_at` is still set (`:257`) — **the invite is silently burned with no membership created.**
- [ ] **Z2-3 (P1) — no MFA/2FA and no SSO/SAML/SCIM**, despite org seat billing at ₹4,999/seat.
      Every `saml`/`sso` hit in the repo is simulated lab content. This is an enterprise deal-blocker.
- [ ] **Z2-4 (P2) — staff can delete audit rows with no meta-audit** (`adminpanel/views.py:4510-4529`).
- [ ] **Z2-5 (P2) — password reset deliberately confirms account existence** (`accounts/views.py:697-702`
      returns 404 "No active account found", with a comment marking it a product decision). Login
      itself is correctly generic. Worth re-ratifying now that the product takes payments.
- [ ] **Z2-6 (P2)** — admin-set passwords bypass the validator chain with a bare `len < 8`
      (`adminpanel/views.py:1082`); `ContactView` is `AllowAny` with a DB write + email and **no
      throttle** (`accounts/views.py:1438`); catalog scraping is effectively unthrottled at the global
      anon 12000/h.

---

# Z3 — USER-GENERATED CONTENT & ENGAGEMENT

**XSS: clean.** Every UGC render path uses JSX text interpolation. The only
`dangerouslySetInnerHTML` is `BlogPost.jsx:874-951` fed by DOMPurify with a tight allowlist
(`ALLOWED_TAGS: strong/em/code/br/span`), and the source is `IsPlatformAdmin`-gated. **Empirically
tested against 7 payloads** — all inert. All **20** `target="_blank"` carry `rel="noopener"`. SVG
upload is blocked by actual PIL decode, not extension sniffing (`common/media_utils.py:37-75`) — the
strongest control in the UGC path.

- [ ] **Z3-1 (P0) — abuse reports are written to a table nobody reads.** `ThreadReport`
      (`community/models.py:163-193`) is well-modelled with reason/status/unique-per-reporter, and the
      write path works (`views.py:381-409`). But it is **not registered in `community/admin.py`**
      (which registers only Thread/Reply/Attachment) and **has no adminpanel endpoint**.
      `AdminThreadModerationView` (`adminpanel/views.py:2676`) lists recent threads with **no
      report-count annotation and no filter**. `status` stays `"open"` forever. ~30 lines turns a
      write-only table into a working queue — highest-ROI item in this section.
- [ ] **Z3-2 (P0) — zero rate limiting on any community write.** `ThreadListView`, `ReplyView`,
      `VoteView`, `ThreadAttachmentUploadView`, `ReplyReactionView`, `ThreadReportView` — no
      `throttle_classes` anywhere in `apps/community/` (contrast `ratings/views.py:60`,
      `support/views.py:17`). A script can post unbounded threads and 5 MB images in a loop.
- [ ] **Z3-3 (P0) — the weekly leaderboard is directly replay-inflatable.**
      `public_api/views.py:2162-2191` `_build_weekly()` does `Sum("score")` over **every**
      `LabSession` with `validation_passed=True` in 7 days. The all-time board correctly uses
      per-scenario `best_score` (`:2136-2159`). Solve one 30-second lab 200× and top the weekly board;
      `scenarios_completed` uses `distinct=True` so it reads `1` against a huge total — the
      inconsistency is the tell, and nothing rejects it.
- [ ] **Z3-4 (P0) — XP is replayable per scenario.** `award_xp_for_completion`
      (`progress/services.py:240-260`) increments unconditionally. The `completion_finalized`
      `SELECT FOR UPDATE` guard (`jira_integration/completion.py:56-62`) is genuinely correct
      **per-session** — it defeats duplicate webhooks and double-clicks — but a lab *restart* creates
      a fresh session, so re-solving awards full XP again (150–250 each time). **`compute_score`
      rewards speed (`labs/completion.py:28`), so the fastest replay pays most.** Composes with the
      307 tautological coding labs (§Y2b) and the fail-open graders (§G) into an unbounded XP faucet.
      No completion rate limit, no minimum-elapsed floor, no per-scenario cooldown, no anomaly detection.
- [ ] **Z3-5 (P1) — certificates cannot be revoked.** `CertEarnedCertificate`
      (`certifications/models.py:195-234`) has no `revoked` field; `CertVerifyView:646` computes
      `"valid": not cert.is_expired` — **expiry is the only invalidation.** Certs earned through the
      fail-open graders can only be removed by raw DB delete, which orphans the `OpenBadgeCredential`
      while the already-distributed Ed25519-signed credential **stays independently verifiable
      forever.** Signed credentials with no revocation list is a correctness problem for something
      users post on LinkedIn. Also `ExamSubmitView.post` is **not transactional** — `attempt.save()`
      (`views.py:440`) happens *after* `_issue_certificate()` (`:437`), so a crash between them issues
      a cert while the attempt still reads `in_progress`, and re-submit re-grades.
- [ ] **Z3-6 (P1) — two notification writers bypass user preferences.** `community/views.py:157`
      (mentions) and `jira_integration/webhooks.py:65` create `Notification` rows directly, ignoring
      `should_notify_inapp()` — so `inapp_system=False` is silently disregarded. The mention path is
      also **fan-out abuse**: attacker-controlled `@username` targets *and* body text
      (`message=reply_content[:200]`), no rate limit, whole block wrapped in `except Exception: pass`.
- [ ] **Z3-7 (P1) — the leaderboard app is dead code with a loaded gun.**
      `LeaderboardEntry` is **never read** — the live endpoint aggregates directly. Meanwhile
      `recalculate_leaderboard` runs **hourly** (`beat_schedule.py:12-15`) writing that unread table,
      and `leaderboard/services.py:18,41` still does bare `.delete()` + N individual `.create()`
      **with no transaction** (the Celery task was fixed, the service wasn't). Any future code that
      switches to `get_global_leaderboard()` inherits an empty-table window.
- [ ] **Z3-8 (P2) — no edit history, no moderation audit, and user deletion nukes conversations.**
      `ThreadDetailView.patch` (`views.py:97-101`) overwrites in place with **no length validation**
      (so a >300-char title is a 500, not a 400). Admin soft-delete/pin/lock uses bare
      `queryset.update()` — no record of who moderated what. `Thread.author`/`Reply.author` are
      **CASCADE** (`models.py:11,54`), so deleting a user hard-deletes their threads *and every reply
      on them*, orphaning other users' conversations mid-thread. No anonymize-on-delete path.
- [ ] **Z3-9 (P2) — support bot leaks scenario metadata cross-user.**
      `support/service.py:157-187` `resolve_lab_context` extracts a session UUID from the
      caller-supplied `page_path` and looks it up **with no ownership check**, on an `AllowAny`
      endpoint. Low impact (UUID4 is unguessable, leak is scenario metadata only) — one-line fix.
      Separately, thumbs-down feedback logs username + first 200 chars of the user's message to
      application logs with no consent surface (ties to Z4-1). *Architecturally the bot is right:
      a deterministic ~40-intent rule engine, no LLM, so no prompt to leak and no injection surface.*
- [ ] **Z3-10 (P2) — ratings are brigadeable.** No completion gate (a fresh account can 1★ every
      scenario), **no throttle on `RateView`** (`ratings/views.py:17`), unvalidated `scenario_id` → 500,
      unguarded `int(score)` → 500, review text unmoderated and shown publicly, and `average_score`
      is displayed with **no minimum-sample suppression** — one 5★ renders identically to a thousand.
      Also 7 queries per list call (a per-star `.count()` loop at `:78-81`).
- [ ] **Z3-11 (P2) — achievement/gamification defects.** Streak badges bypass the `_award` helper
      (`services.py:171-176`) so they **never notify**. `perfect_score` fires on `score >= 100` but
      `compute_score` returns `100 + time_bonus`, so **every** timely completion is a "Perfect Score" —
      the badge is meaningless. `Notification.TYPE_CHOICES` declares `"streak"` and **nothing ever
      creates one.** Missing mechanics: weekly digest email (highest-value retention lever — streak
      data already exists), streak freeze/recovery (a single missed day zeroes it with no warning),
      social proof (`completions_count` is computed and unused), referral, team leaderboard (the org
      data model already supports it), level rewards (levels confer nothing).
- [ ] **Z3-12 (P2) — blog content is duplicated between the React bundle and the DB.**
      `BlogPost.jsx:11-724` hardcodes ~700 lines of article prose as a fallback, seeds from it
      synchronously, then overlays the API. Editing in admin does **not** update the fallback, so any
      API hiccup silently serves stale content — and every visitor downloads the prose. `slug` has no
      uniqueness check before create (`adminpanel/views.py:4914`) → 500 on duplicate title.

---

# Z4 — PRIVACY, PII, COMPLIANCE

Mechanics are better than typical: a **real hard delete** with password re-auth and JWT blacklisting
(`accounts/views.py:560-620`), correct resume-blob erasure (`interviews/gdpr_views.py:21-26`), a
working Sentry scrubber (`settings.py:797-836`, `send_default_pii=False`, fails closed), and retention
jobs for OTPs/reset tokens/audit/read-notifications. Legal docs are **real and specific**, not
boilerplate. The failures are concentrated in three places.

- [ ] **Z4-1 (P0) — the log PII masker is decorative.** `common/logging_utils.py:47` sets
      `"message": record.getMessage()` — the fully interpolated string — and masking applies **only**
      to `record.fields`/`record.structured`, i.e. only to `extra={}` on the `StructuredLogger`
      wrapper. That wrapper is used in **4 files; plain `logging.getLogger` in 84.** So every f-string
      email goes to stdout in cleartext: `accounts/views.py:134,136,698,715,717,786` (OTP + reset),
      `notifications/email_dispatch.py:41-89`, `billing/email_service.py:84`, `webhooks.py:42,64`,
      ~30 sites total. **Worst: `accounts/views.py:616` and `account_lifecycle.py:136` log `email=`
      at the moment of deletion — defeating the erasure.** Add a regex redactor over
      `record.getMessage()`.
- [ ] **Z4-2 (P0) — the most sensitive data class has no retention and no purge.** No beat entry
      exists for interview **transcripts** (`interviews/models.py:309-335`, free-text candidate
      speech), **reports** (incl. `recommendation`, `dressing_notes`), **async video**
      (`:712`), **resumes** (`:49-51`, full text + parsed), or `CommandHistory`. All plaintext,
      indefinite, stored alongside employer and `current_package_lpa`.
- [ ] **Z4-3 (P0) — deletion doesn't delete the blobs.** No `django-cleanup`, no `post_delete`
      handlers — so `interviews/resumes/` and `interviews/async_video/` files **survive
      `user.delete()` on disk** even though the rows vanish.
- [ ] **Z4-4 (P0) — two privacy-policy claims are false.** `Privacy.jsx:32` says candidate
      *"audio stays on your device"* and `:110` *"no paid third-party TTS/STT"*. In Chrome/Edge,
      `webkitSpeechRecognition` **streams audio to Google** (`useInterviewVoice.js:909,949,1068`).
      "No *paid* service" is technically true; "stays on your device" is not. `Privacy.jsx:56` /
      `Terms.jsx:117` also overstate deletion (see Z4-3 and the retained lifecycle email).
- [ ] **Z4-5 (P0) — interview consent is collected and never persisted.**
      `InterviewRoom.jsx:1880-1893` requires an explicit camera/mic/transcript checkbox, gated at
      `:2092` — but **zero `consent` references in `backend/apps/interviews/`. You cannot prove
      consent was given.** Store timestamp + policy version on the round.
- [ ] **Z4-6 (P1) — no processor is named in the privacy policy.** Razorpay and Stripe appear in
      Terms §3 only; **Google (Gmail API + Web Speech), Sentry, Jira, DigitalOcean/AWS, and the CDN/HDRI
      hosts are absent entirely.** DPDP §8(2) makes you liable for processor compliance regardless.
      No data-location or transfer statement; no SCCs for US processors. Privacy contact is a
      **gmail.com address** (`Privacy.jsx:125`) — not credible for a payment-taking business.
- [ ] **Z4-7 (P1) — no security disclosure channel.** No `security.txt` (RFC 9116), no `SECURITY.md`,
      no VDP, no safe-harbour statement, **no breach-notification runbook** — and DPDP breach
      notification has no owner or timeline.
- [ ] **Z4-8 (P1) — no cookie consent banner and no cookie policy** anywhere in `frontend/src`.
      Marketing consent **defaults to opt-IN** (`notifications/models.py:44`
      `email_marketing = default=True`) — pre-ticked consent is invalid under GDPR and inconsistent
      with DPDP's affirmative-action standard. Terms/privacy acceptance is **never recorded** — no
      `tos_version` field, so you cannot establish which text a user agreed to.
- [ ] **Z4-9 (P1) — DPDP Act gaps** (primary obligation, Indian-owned): no itemised consent notice at
      collection (§5), no consent-withdrawal mechanism beyond marketing opt-out (§6(4)), **no DPO or
      Grievance Officer named** and no published redressal timeline (§8(9), §13), no breach procedure.
      **Children's data is a total gap** — no age gate, no DOB, no parental-consent path; §9 bans
      processing under-18 data without verifiable parental consent *and* bans behavioural tracking to
      minors. An interview-practice product will attract 16–18 year-olds; penalties reach ₹200 crore.
- [ ] **Z4-10 (P1) — automated decision-making with no disclosure.** `recommendation`
      (`interviews/models.py:374`) + `pass_threshold` is an automated evaluation of professional
      capability. Under GDPR Art. 22 that needs disclosed logic, human review, and a contest path; a
      DPIA is arguably mandatory (automated evaluation + voice processing). **Flag for counsel** —
      this is where the code creates exposure, not a settled conclusion.
- [ ] **Z4-11 (P2)** — `Organization.webhook_secret` stored **plaintext** (`accounts/models.py:227`);
      `EmailVerificationOTP.code` plaintext for 24h (`:70`) while the reset token is hashed;
      `gateway_response` persists the **raw provider JSON** unfiltered (`billing/models.py:212`),
      widening PCI/DPDP surface for no functional gain; unsubscribe token rides a **query string**
      (`Unsubscribe.jsx:21`) so it lands in history/Referer/access logs; Jira pushes candidate email
      and full name to a third party (`jira_integration/sync.py:76,116`) — default-off but undisclosed.
- [ ] **Z4-12 (P2)** — data export is **transcripts-only**, not a whole-account SAR (excludes profile,
      labs, billing, community, audit). `AccountLifecycleEvent.email` is deliberately retained
      post-deletion (`accounts/models.py:326`) — defensible as anti-abuse, but **undisclosed and
      unbounded**; needs a stated basis and TTL. No `LICENSE` file; no third-party attribution file.
      Missing pages: cookie policy, standalone refund/cancellation policy (Indian gateways expect a
      linkable one), acceptable use, DPA, SLA. **PCI scope is genuinely minimal** — no card fields,
      redirect-only, practically SAQ-A.

---

# Z5 — SCALE, CAPACITY, RESOURCE LEAKS

**All four droplets are `s-2vcpu-8gb-160gb-intel`** (`infra/digitalocean/cluster.json:4`) — there is
no larger labs node. D1 co-locates gateway + frontend + **Redis + RabbitMQ + Vault**.

Genuinely well-built and not to be disturbed: the pgBouncer/Django transaction-mode pairing
(`settings.py:166-181` — `CONN_MAX_AGE:0` + `DISABLE_SERVER_SIDE_CURSORS` keyed off
`_USING_PGBOUNCER`, with migrations correctly bypassing the pooler) and the `pg_advisory_xact_lock`
capacity gate (`capacity.py:104-146`), whose docstring argument for counting live rows over a
decrement counter is correct. **The only thing wrong with the gate is the constant it compares against.**

- [ ] **Z5-1 (P0, CRITICAL) — `_SIM_SESSIONS` leaks across 5 processes and is freed from one.**
      `simulation/shell.py:244` is a plain process-local dict: **no maxsize, no TTL, no eviction.**
      There are 4 uvicorn workers (`scripts/startup.sh:46`) plus `celery_provisioning`, each with its
      own copy. Provisioning populates the Celery process's dict; the terminal connects to an
      arbitrary uvicorn worker whose dict is empty, so `ensure_sim_session`
      (`simulation_provisioner.py:537`) **builds a second engine**; a reconnect may build a third.
      Teardown calls `drop_sim_session` in **one** process. Each orphan holds a full
      `UnifiedSimulationEngine` — entire VFS, users, services, processes, LVM, git
      (`sim_persistence.py:55-155`). Celery children recycle at 200 tasks; **uvicorn workers never
      recycle**, so D2's 5 GB cgroup OOM-kills all four workers and every in-flight lab dies.
      **The fix pattern is already in-repo:** all 22 `apps/vmware_sim/*_engine.py` use cache-backed
      state with `SESSION_TTL=7200` (`aws_engine.py:28,186-194`). Port `UnifiedSimulationEngine` to
      the same shape. This also fixes Z5-3 (sim side) and the reconnect-lands-on-wrong-engine bug.
      *Interim:* set `UVICORN_WORKERS=2` (halves the fan-out, matches 2 vCPU) and export
      `len(_SIM_SESSIONS)` so the leak is at least visible.
- [ ] **Z5-2 (P0, CRITICAL) — a full-engine JSONB snapshot is written on EVERY command.**
      `terminal/consumers.py:474-478` calls `persist_session_snapshot` per command line;
      `sim_persistence.py:277-291` serialises the **entire simulated filesystem** plus all state and
      does a JSONB `UPDATE`. At 60 labs × ~20 commands/min that is ~20 large-JSONB writes/sec, each a
      full-row rewrite generating dead tuples at the same rate — **this is the dominant DB write load
      in the system and it will autovacuum-thrash `labs_labsession`.** It is also on the interactive
      path: every keystroke-line pays serialise+write latency before the shell responds. Debounce
      (≥30 s) or snapshot only on state-mutating commands; once Z5-1 is Redis-backed, drop it entirely.
- [ ] **Z5-3 (P0) — `MAX_CONCURRENT_LABS=60` is fiction on both engines.** Verified arithmetic:
      8 GB D4 − ~1.2 GB OS/dockerd = 6.8 GB usable ÷ `512m` = **13 containers**, and companion/SSH
      containers add another 512m each (`docker_provisioner.py:169,270`;
      `simulation_provisioner.py:698` attaches a jump box whenever `len(lab_hosts) >= 2`), so a 3-host
      scenario is 1536 MB → **real ceiling 4–13.** CPU is worse: `nano_cpus = 1.0×1e9` on 2 vCPU
      means 60 labs oversubscribe **30:1**. Make the cap **provider-aware** — `capacity.py:74` already
      distinguishes providers.
- [ ] **Z5-4 (P0) — Redis is 1 GB with `allkeys-lru`, shared by cache + Celery results + Channels.**
      `docker-compose.prod.yml:340-341`. `allkeys-lru` evicts **any** key ignoring TTL, and the 22
      vmware_sim engines treat Redis as their **source of truth** — eviction mid-lab silently resets
      the learner's state, because `_ensure` (`aws_engine.py:428-435`) sees `None` and cheerfully
      builds a fresh base state. Only `datacenter_engine` has a snapshot fallback; **the other 21 do
      not.** Compounded by `IGNORE_EXCEPTIONS: True` (`settings.py:917`), which is correct for
      read-through catalog caches but converts "Redis is down" into "lab silently reset." Use
      `volatile-lru`, or put engine state on its own DB/instance with `noeviction`, and raise
      `maxmemory` (D1 has 8 GB).
- [ ] **Z5-5 (P0) — no Docker log rotation anywhere.** Grepped every compose file for
      `max-size`/`log-opts`: **zero hits.** `json-file` defaults to unlimited and the backend logs
      JSON at INFO to stdout (`settings.py:1002`). `/var/lib/docker/containers/*/*-json.log` grows
      unbounded on **every** droplet until the 160 GB disk fills. **This is the most likely cause of a
      "everything died at once" outage.** Cheapest fix on this list.
- [ ] **Z5-6 (P1) — `BaremetalConsumer`: no per-user cap, 1.5 s DB poll per socket forever.**
      `TERMINAL_MAX_WS_PER_USER=20` is enforced only in `TerminalConsumer` (`consumers.py:295`);
      `baremetal_consumer.py:57-91` has no equivalent, so one user can open unlimited sockets.
      `_tick_loop` (`:110-118`, `PUSH_INTERVAL_SECONDS=1.5`) runs a `select_related` query **plus** a
      Redis get every tick; the dedupe at `:132` suppresses the *send* but not the *work*. **100 idle
      sockets = 4,000 DB queries/min on 2 vCPU, sending nothing.** Also missing the
      `finally: self._release_connection_slot()` guard that `TerminalConsumer.__call__` models
      (`consumers.py:223-224`), so an abrupt drop leaks the slot.
- [ ] **Z5-7 (P1) — `_active_holders` leaks docker-py clients and live D4 sockets.**
      `exec_stream.py:26` — same process-local pattern as Z5-1. `release_holder` runs in a different
      process than the one that registered it, and each orphan pins a docker client + **a live HTTP
      socket to the D4 daemon** (deliberately, as a GC root, `:127`), so this leaks **file descriptors
      against D4**, not just RAM.
- [ ] **Z5-8 (P1) — tables that only grow, with no purge:** `labs_commandhistory` (one row per
      command, output TEXT), `labs_sessionrecording` (**up to 5,000 I/O events per session in a
      JSONField** — ~500 MB/day of JSONB at 1,000 labs/day), `labs_labsession` (keeps its
      multi-hundred-KB `simulation_snapshot` forever), `billing_processedwebhookevent`,
      `labs_incidentrun`/`labs_postmortem`, unread notifications. **No read replica**, D3 is 2 vCPU,
      `pg_dump` duration grows linearly and restore is single-threaded — at 50 GB that is hours of RTO,
      **untested at scale.**
- [ ] **Z5-9 (P1) — synchronous D4 SSH teardown inside `StartLabView`'s transaction.**
      `public_api/views.py:857-865` terminates prior sessions — network I/O over SSH to D4 — **while
      holding both a row lock and the global advisory lock.** One slow D4 response serialises every
      lab start platform-wide. Move to the `provisioning` queue.
- [ ] **Z5-10 (P1) — readiness ignores Redis, RabbitMQ, and Docker.** `accounts/health.py:53-80`
      checks **only** DB + Vault, so Redis can be dead while the container reports healthy and sim
      labs silently reset (Z5-4). Add informational sub-statuses, following the existing Vault
      treatment (`:62-77`) which is genuinely graceful and is why the prior Vault outage was diagnosable.
- [ ] **Z5-11 (P1) — Docker images, build cache, and volumes are never pruned.** Container and
      network cleanup is correct and label-scoped (`docker_provisioner.py:709,739`), but there is no
      `image prune`, no `builder prune`, no `volume prune`, and `container.remove(force=True)`
      (`:684`) omits `v=True` so anonymous volumes orphan on **every** teardown. Also
      `cleanup_orphaned_containers` runs hourly with a **7200 s age floor**, so a crashed orphan parks
      512 MB (2 of ~13 slots) for **up to 3 hours** — lower it toward `LAB_MAX_DURATION_MINUTES`.
- [ ] **Z5-12 (P2) — Postgres is tuned for a 1 GB box on an 8 GB droplet.**
      `database/postgresql.conf:6-7` — `shared_buffers=256MB`, `effective_cache_size=768MB` (the
      file's own comment says 25% of RAM, i.e. 2 GB). `effective_cache_size` at 768 MB **actively
      misleads the planner into rejecting index scans.** `work_mem=4MB` will spill catalog ORDER BYs to
      disk. Pool sizing is inverted: `DEFAULT_POOL_SIZE=25` against `max_connections=100` **strands
      75 connections**, while `MAX_CLIENT_CONN=1000` is 40× the ~24 real clients.
- [ ] **Z5-13 (P2) — `TechnologyDetailView` is O(n) per request.** `public_api/views.py:315-326`:
      4 `COUNT(*)` + a `.distinct()` + **unpaginated serialisation of every scenario** for the
      technology; then the authenticated path `copy.deepcopy`s the whole payload (`:343-345`) plus two
      unbounded per-user queries on **every** request, so authenticated users get no cache benefit.
      Also `ScenarioViewSet` (`question_bank/views.py:20-27`) is a full **`ModelViewSet`** exposing
      CRUD over all 7,280 rows.
- [ ] **Z5-14 (P2) — cache invalidation misses four key families.**
      `question_bank/cache_utils.py:8-11` deletes 3 keys and never touches `tech_detail_anon:{slug}`,
      `categories_list`, `tags_list`, or `scenarios_list:*`. Editing a scenario serves stale data for
      the full TTL. `django_redis` provides `cache.delete_pattern()` — unused.
- [ ] **Z5-15 (P2) — `celery_beat` is a silent SPOF.** Its healthcheck only greps a pidfile
      (`docker-compose.app.yml:229`), so a wedged-but-alive beat means **no expiry cleanup, no orphan
      cleanup, no monitoring, unbounded engine fill — with zero alerts.**
- [ ] **Z5-16 (P2) — the `ip_hash` comment encodes a false belief.**
      `gateway/nginx.cluster.conf.template:34-38` claims "ip_hash sticky sessions across
      Daphne/uvicorn workers" — but `ip_hash` over a **one-server** upstream is a no-op, and nginx
      cannot see uvicorn's 4 workers behind a shared listening socket. **Worker affinity is impossible
      here; the state must leave process memory** (Z5-1). Also: no backpressure in `_read_output`
      (`consumers.py:671-748`) — a firehose command is bounded only by the client's TCP window.
- [ ] **Z5-17 (P2) — observability gaps that matter in an incident:** no frontend Sentry (a
      white-screen SPA crash is invisible); **`len(_SIM_SESSIONS)` and per-process memory are
      unobservable, so an OOM-137 looks like a random restart**; no `/metrics`, no APM/tracing, no
      SLOs, no dashboards; the active-lab gauge is computed and thrown away (`capacity.py:99`);
      **`ALERT_WEBHOOK_URL` is unset by default so `send_alert` is a no-op** and the blind window is
      up to 30 minutes; **logs are JSON to stdout with no shipping**, so post-OOM the logs explaining
      it may already be gone. *Credit: the prior "no queue depth visibility" gap is now FIXED —
      `tasks_monitoring.py:81-110` inspects reserved+active and correctly refuses to alert when it
      cannot measure; the backup dead-man's-switch (`:59-79`) is real.*
- [ ] **Z5-18 (P2) — failure modes that cascade:** RabbitMQ down → `provision.delay()` raises 500
      **and no beat task runs**, so the engine fills with zombies; Docker daemon down → 500s **plus**
      Z5-9's lock hold stalls all lab starts. Vault is the **best-handled** dependency
      (`health.py:62-77` keeps the node ok and serves baked env). **No per-failure runbooks exist** —
      grepped `docs/`/`scripts/` for `runbook`: only architecture/audit docs.
- [ ] **Z5-19 (P2) — cost.** 4 × ~$48/mo ≈ **$192/mo fixed**, billed 24/7 regardless of load. **D4 is
      entirely idle whenever the simulation path is chosen — which `capacity.py:22-27` says is *most
      scenarios*. That is 25% of infrastructure spend on a droplet the architecture routes around.**
      D3 runs a 1 GB-tuned Postgres on 8 GB. Backup storage grows **faster than users** because of
      Z5-2/Z5-8 — cost driven by a leak, not usage. At the limit you don't degrade, you cliff.
      **Answer explicitly whether D4 still earns its keep.**
- [ ] **Z5-20 (P2) — load testing exists and is dormant.** `performance.yml` has real k6 + Lighthouse
      CI but is `workflow_dispatch`-only, and the k6 profile is **20 VUs against 6 anonymous
      read-only endpoints** — it never touches lab start, never opens a WebSocket, never exercises the
      simulation engine. **It cannot detect any of Z5-1 … Z5-7.**

*Caveat: capacity numbers are derived from config and code, not live measurement. Get
`len(json.dumps(snapshot_engine(engine)))` and the real per-engine footprint before choosing the new
`MAX_CONCURRENT_LABS`.*

---

# Z6 — API, EMAIL, SEO, ANALYTICS, PWA, TESTING, DX

- [ ] **Z6-1 (P0, highest SEO ROI in the audit) — the stale static sitemap shadows the dynamic one.**
      **Verified:** `frontend/public/sitemap.xml` has **11 URLs**; there is **no nginx `location` for
      `/sitemap.xml`** in `gateway/`; the real index **is** registered
      (`backend/config/urls.py:28-37`) and `public_api/sitemaps.py` is careful work (5 classes,
      `.only()` projections, 5000-URL pagination). nginx falls through to the SPA handler and serves
      the stale file, and `robots.txt:4` points crawlers straight at it. **~7,280 scenarios + ~830
      tutorials + all technology hubs are absent from the sitemap crawlers actually fetch.**
      Fix: add the 6 routes the static file has and the dynamic one lacks (`/blog`, `/faq`,
      `/leaderboard`, `/mock-interviews`, `/verify-certificate`, `/register`) to
      `StaticViewSitemap.ROUTES` (`sitemaps.py:60-70`) **first**, then delete the static file and add
      the nginx location. Also add blog to `SITEMAPS` (`:174-180`) — `BlogPost` already has
      `slug`/`is_published`/`updated_at`.
- [ ] **Z6-2 (P0) — every uncovered route declares the homepage as canonical.**
      `usePageTitle.js` is good (upserts description, full OG set, Twitter, canonical, with unmount
      cleanup) but is used in **only 19 of 95 page files**. Missing on `Home.jsx`, `Scenarios.jsx`,
      `Technologies.jsx`, `Blog.jsx`, `About.jsx`, `FAQ.jsx`, `Leaderboard.jsx` and more — and
      `index.html:11` hardcodes `canonical=https://fixitlab.in/`, so **`/scenarios` and every
      uncovered route actively instruct Google to de-index them.** Add the hook to the top routes,
      then remove the hardcoded canonical.
- [ ] **Z6-3 (P0) — a marketing blast can cause an auth outage.** `settings.py:496-498` shows the
      senders are **consumer Gmail accounts** (`fixitlab@gmail.com`, `kubelearn464@gmail.com`) at
      ~**500 recipients/day**. Transactional and marketing share the same account and the same
      `_deliver` chain, so exceeding the cap **stops OTP and password reset**. Also
      `gmail_api.py:80` sends `From: no-reply@fixitlab.com` while authenticating as a gmail.com
      user — a **From/authenticated-sender mismatch across domains** that receivers may treat as
      spoofing. **No SPF/DKIM/DMARC evidence anywhere in docs or config.**
      Split the streams now; move to SES/Postmark/Mailgun on a dedicated subdomain next.
- [ ] **Z6-4 (P0) — no `List-Unsubscribe` headers.** `gmail_api.py:78-84` sets only
      `Subject`/`From`/`To`. Gmail and Yahoo have **required** one-click `List-Unsubscribe` +
      `List-Unsubscribe-Post` for bulk senders since Feb 2024. The signed-token machinery already
      exists (`unsubscribe.py:10-25`) — this is a header away.
- [ ] **Z6-5 (P0) — verify `og-image.png` ships.** Referenced at `index.html:20` and
      `usePageTitle.js:5`; **not found in `frontend/public/`** (which contains only `robots.txt`,
      `sitemap.xml`, `tutorials/`). If absent from `dist/`, **every social share renders a broken image.**
- [ ] **Z6-6 (P1) — zero product analytics and zero frontend error tracking.** Grepped for
      `gtag|posthog|mixpanel|amplitude|segment|plausible|hotjar|clarity` — every hit is *simulated
      lab content*. No funnel instrumentation, and `ErrorBoundary.jsx`/`SimErrorBoundary.jsx` report
      **nowhere**. You cannot answer "where do signups drop off", "what % start a lab", "does the
      paywall convert", or "did that deploy break checkout." **Every prioritization decision in this
      document is currently made blind.** Minimum funnel: `signup_started/completed` →
      `scenario_viewed` → `lab_started` → **`lab_first_command` (the real activation signal)** →
      `lab_validated` → `paywall_viewed` → `checkout_started` → `purchase_completed`, plus
      `lab_provision_failed`. Recommend **PostHog** (funnels + replay + **feature flags**, which
      also closes Z6-11) and `@sentry/react`, both env-gated like the existing `SENTRY_DSN`.
- [ ] **Z6-7 (P1) — no SSR/prerender, and 650 kB gzip is eager.** Measured: `dist/index.html`
      `modulepreload`s **`aws-console` (322 kB gz)**, `icons` (164), `lab-shared`, `state`, `proxy` on
      **every** page load — a marketing visitor downloads the AWS console simulator before LCP.
      Root cause is `vite.config.js:57` promoting `/src/components/aws/` into the entry graph; the
      fix must drop the static import that roots it while **keeping** the `manualChunks` isolation
      that fixes a documented circular-init crash (`:52-54`). Crawlers get an empty
      `<div id="root">`, so Bing/LinkedIn/Slack previews fall back to the generic card.
      **No JSON-LD anywhere** — add `Course` per scenario (highest-value structured data on the site,
      7,280 of them), `Organization`, `BreadcrumbList`, `Article`.
- [ ] **Z6-8 (P1) — the `public_api` name is a false promise.** It is an internal BFF: **schema and
      docs are `IsAdminUser`** (`backend/config/urls.py:134-135`), there is **no versioning** (no
      `/v1/`, no `DEFAULT_VERSIONING_CLASS`; `VERSION:"2.0.0"` is decorative), **no API keys** (JWT
      only, 15-min access token — unusable server-to-server), no per-key limits, no `X-RateLimit-*`
      headers, no deprecation policy, no SDK, no outbound webhooks. Yet `settings.py:293` advertises
      *"Public REST API."* **Cheapest correct move: rename to `apps/bff/` and drop the claim.**
      Also trim `ScenarioListSerializer` — docstring'd "lightweight", emits **27 fields** including
      `blocked_commands`, `consoles`, `lab_servers` that no list renders, at `page_size` up to 200.
      Three confirmed N+1s: `views.py:318-319` (5 COUNTs → 1 aggregate), `:2359-2365` (**2N queries**),
      `:146-148`.
- [ ] **Z6-9 (P1) — labs are startable on phones with no warning.** Mobile responsiveness *is*
      implemented (`useIsMobile()` threaded through 11 sites in `LabRunner.jsx`), but there is **no
      gating message** — so a phone user burns a provisioned droplet and lab-start quota in a terminal
      needing a physical keyboard and `Ctrl-C`, and `DatacenterTwin3D` is **1,029 kB gz of WebGL +
      Rapier physics** that will OOM many mobile browsers. Gate launch below 1024px with an explicit
      interstitial; keep browse/catalog/blog/progress fully mobile. **No PWA at all** — no manifest,
      no service worker, no `apple-touch-icon`, not installable. (Viewport is correct and pinch-zoom
      works — a11y pass.)
- [ ] **Z6-10 (P1) — Lighthouse, k6, and the migration check are all built and all dormant.**
      `integration-tests.yml:118` contains `makemigrations --check --dry-run` and is
      `workflow_dispatch`-only, so **missing-migration detection never gates a PR** (this is why §B4
      exists). `performance.yml` has Lighthouse CI + k6 and never runs. `e2e-smoke.yml:8` is
      `workflow_call`-shaped and **called by nothing automatic.** *These are trigger changes, not
      code.* `ci.yml` itself is solid and does gate PRs properly.
- [ ] **Z6-11 (P1) — ~225,000 lines of Python have no formatter, linter, or type checker.**
      **No `pyproject.toml`, `setup.cfg`, `.flake8`, or `ruff.toml` anywhere**; zero matches for
      `black|ruff|mypy|flake8|isort` in `requirements*.txt`; **no `.pre-commit-config.yaml`.** CI lints
      scenario YAML and JS but never Python. Type coverage is effectively 0%. **Largest
      maintainability gap in the repo and the cheapest to start** — `ruff` with a generous ignore list
      catches unused imports and undefined names across the tree in seconds.
- [ ] **Z6-12 (P1) — testing gaps on the paths that matter most.** Measured: backend **1,724 tests /
      101 files**; frontend **87 tests / 20 files over 130,418 LOC (~1 per 1,500 lines)**; 5 Playwright
      suites, all manual. **Apps with ZERO tests: `auth_app`, `progress`, `leaderboard`, `hints`,
      `ratings`, `audit`, `scenario_versions`.** `auth_app` is the alarming one — login, JWT issuance,
      OAuth, password reset, OTP, account deletion, and specifically **`ROTATE_REFRESH_TOKENS` +
      `BLACKLIST_AFTER_ROTATION` are subtle, security-critical, and untested** (directly relevant to
      the logged `rotate_secrets` login-breaking history). **Payment has zero frontend tests** —
      Razorpay checkout can break on any frontend merge undetected. **All 95 page components have
      zero tests.** Missing categories entirely: contract tests, visual regression, **a11y in CI**
      (no `eslint-plugin-jsx-a11y`, no axe), mutation testing, migration tests.
      *Grading is the best-covered critical path* — `grader-integrity.yml` +
      `test_academy_fix_alignment.py` + `test_validation_integrity.py`, all automatic. Target:
      frontend 87→400 (paywall logic, PaymentPage, auth forms, labStore, router guards); `auth_app`
      0→60; contract layer via schemathesis against an un-gated CI schema.
- [ ] **Z6-13 (P2) — no task runner and 147 env vars.** No `Makefile`/`justfile`/`Taskfile`; setup is
      tribal knowledge across four docs. Seed data is good (7 commands) but you must know all seven
      names and their order. **No boot-time validation of required env vars** — a typo silently takes
      a default, exactly as `JWT_ALGORITHM`, `SENTRY_DSN`, and `ALERT_EMAIL` all do. Given the
      Vault-sealed outage history, add a startup assertion.
- [ ] **Z6-14 (P2) — files needing decomposition** (measured): `seed_projects.py` **11,537**,
      **`adminpanel/views.py` 5,862 (with 1 test file)**, `rhel_shell.py` 5,840,
      `project_data_extra.py` 5,022, `scenario_presets.py` 4,968, `simulation_modules.py` 4,116,
      `LabRunner.jsx` 3,983, `engine.py` 3,550, `production.yml` 1,808. The two seed commands are
      **16.5k lines of data-as-code** — convert to YAML/JSON fixtures with a thin loader so they
      become diffable and lintable by the existing `lint_scenarios.py`. `production.yml`'s undeclared
      flag coupling (`rotate_secrets`/`build_scenarios` must stay false) belongs in a guarded
      preflight script, **not in tribal memory**.
- [ ] **Z6-15 (P2) — no CHANGELOG, no ADRs, no feature flags, no CODEOWNERS, no error budgets.**
      `Changelog.jsx:16` *parses* markdown but ships a hardcoded `FALLBACK_RELEASES` array because
      **no `CHANGELOG.md` exists**; no semver tags, no version surfaced in the app. Zero ADRs — Vault,
      RS256, Gmail-over-SMTP, the four-droplet topology, and simulation-vs-real provisioning are all
      undocumented as decisions. **No feature flags** (`grep FEATURE_` → zero), so shipping is
      all-or-nothing via env + redeploy — a real velocity tax given the phased plan below.
      `rollback.yml` exists, manual, **with no evidence of a drill** — untested rollback ≈ no rollback.
- [ ] **Z6-16 (P2) — the referral system is dead schema.** `accounts/models.py:49-51` has
      `referral_code` and `referred_by`; grep across all views/serializers → **zero**. No UI, no
      attribution, no reward. Either activate it or drop the columns. Also: no email
      bounce/complaint/suppression handling of any kind (`grep bounce|suppress|complaint` → zero), so
      hard-bounced addresses are retried forever and reputation degrades invisibly; `critical=True`
      email uses a **daemon thread** (`email_dispatch.py:63-70`) that **dies on process exit**, so a
      deploy mid-send silently drops an OTP with no queue and no retry; email retry has **no
      idempotency key**, so a send that succeeds at Gmail but times out client-side **duplicates** —
      real risk for invoices and OTP.

---
---

# MASTER PLAN — FINAL CONSOLIDATED

This document is complete. Structure: **§S–§O** first pass (security, grading, AWS, routing,
interview, simulators, learning path, frontend, backend, docs/CI/infra) · **§X** owner-reported bugs +
golden-image/provenance/ops epics · **§Y** voice + IDE + API client · **§Z** billing, auth, UGC,
privacy, scale, growth.

## The five sentences that summarize 2,800 lines

1. **The engineering substrate is strong** — 1,724 backend tests green, zero IDOR across 228
   handlers, all 88 admin routes gated, RS256 + hashed reset tokens + httpOnly cookies, a
   race-safe capacity gate, correct pgBouncer pairing, a rigorous cert exam engine, real PromQL
   and real nmap protocol modelling, and 830 genuinely deep tutorials.
2. **The content layer is hollow** — 63.8% of 7,280 scenarios have no topic-specific verification,
   1,340 are graded on an unrelated Linux daemon, 307 coding labs pass against an untouched stub,
   and 420 AWS labs cannot be passed at all.
3. **The connective tissue is severed** — 5,403 dead tutorial links, 213 projects that launch no
   lab, 5 journeys with no route, 70 dangling cert refs, and ~13,000 URLs invisible to crawlers.
4. **Three latent operational failures will bite before growth does** — the `_SIM_SESSIONS`
   cross-process leak, a full-VFS JSONB write per keystroke-line, and unrotated Docker logs on
   160 GB disks; with `MAX_CONCURRENT_LABS=60` set 4.6× above physical capacity, the graceful
   503 never fires.
5. **You are flying blind** — no product analytics, no frontend error tracking, a dead audit
   middleware, and `ALERT_WEBHOOK_URL` unset, so every decision above is currently made without data.

## Phase order (revised, final)

**Phase 0 — Instrument first (days).** Do this *before* the fix phases, so you can see the effect
of everything after it: frontend Sentry + PostHog with the §Z6-6 funnel; set `ALERT_WEBHOOK_URL`;
export `len(_SIM_SESSIONS)`, active-labs-vs-cap, and 503-shed count; fix the dead audit middleware
(§Z2-1). *Rationale: this is the cheapest phase and it converts every later phase from
faith-based to measured.*

**Phase 1 — Security, money, and stop-the-bleeding (days).**
§S1–S8 (rotate the tracked secrets, fix + PR-gate the scanner, SSRF, pin ssh-action, log the
fail-open auth checks, `npm audit fix`) · §Z1-1…Z1-4 (cart mischarge, cert idempotency, DEBUG gate,
Stripe webhook durability) · §Z5-5 Docker log rotation · §Z5-4 Redis eviction policy · §Z5-3 set the
lab cap to reality · §W1 refresh mutex · §W2 store reset on logout · §X1 datacenter sticky-2D ·
§X2 Jira reply polling · §H1 VMware exit · §H2 mobile z-index · §Y2e delete IDE credentials ·
§Y1g the six one-line interview fixes.

**Phase 2 — Grading integrity (1–2 weeks). No new content before this lands.**
§Y2b the 307 tautologies (**highest priority — they award XP for zero work**) · §G1 the `exit 0`
sweep · §G4 route academy-aws to the console engine (+azure/gcp/openstack = 863 labs) · §G6 OpenStack
validator · §G7 + §Y2f CI rules, with **R9 (grade the untouched stub, require failure) as the
decisive one** · §Z3-3/Z3-4 close the leaderboard and XP replay faucets · §Z3-5 certificate revocation.

**Phase 2.5 — IDE correctness (small, unblocks 855 labs).**
§Y2c `runtime`/`grader` split **first (load-bearing)** → §Y2a relabel → §Y2d preview fixes incl. the
console bridge → honest labels or real runtimes for java/shell-script.

**Phase 3 — Reconnect the learning path (1 week, mostly config, highest ROI/effort).**
§C2 drop the `aws→terraform` alias (**one line, 421 labs**) · §C1 `linked_tutorial` field + 44-row
mapping · §C4 `/journeys` + resolve Tutorial titles · §C3 `/projects` index · §C5 purge dangling cert
refs · §C6 unify `playground_slug` · §Z6-1 sitemap + §Z6-2 canonicals (**~13,000 URLs**).

**Phase 4 — 3D datacenter fixes** (§X1c all 10 rooms → §D1–D13) →
**Phase 4.5 — datacenter as a game** (§X6b build mode → §X6c economy/SLA → §X6d live ops; **gated on
§D14's thermal model — without load→temperature coupling there is no jeopardy**).

**Phase 5 — Simulator causality** (§F1 gate `systemctl start` on the `nginx -t` that already
exists — **~10 lines, makes every config lab causal** → §F2–F7) →
**Phase 5.5 — Artifact provenance** (§X3 golden image → AMI → EC2 with real failure propagation,
then §X4 across docker/k8s/MAAS/linux/gcp/terraform/commvault/dellemc/peoplesoft/ansible/gitops).

**Phase 6 — Interview credibility** (§I1–I11 rubric judge + golden-set regression) →
**Phase 6.5 — Voice call agent** (§Y1e **Piper for English first — independent of everything, and
what a candidate notices in three seconds** → ASGI/Channels → faster-whisper + Silero VAD + AEC →
**IndicF5 (MIT, Telugu+Hindi verified)** + IndicWhisper → §Y1f generation → §Y1d multilingual).

**Phase 7 — AI/ML/LLM/data-science content** (§A1 per-GPU dataclass **converts ~70 written GPU
scenarios to real with zero UI work** → §A2–A11) →
**Phase 7.5 — Operational rough edges** (§X5 secrets, cost spikes, change management, incident
command — **currently zero scenarios where the right answer is "escalate" or "roll back"**) →
**Phase 7.6 — API client** (§Y3, with the Kubernetes API and REST-over-SQL mock surfaces).

**Phase 8 — De-templatize the 9 storefront technologies** (§Phase 8 + §F7 + populate the 213
projects' `lab_scenario` + more certs + cross-tech capstones).

**Phase 9 — Compliance, scale, and polish (continuous).**
§Z4 (log PII redaction, interview retention, blob deletion, consent persistence, processor
disclosure, security.txt, DPDP officer + age gate) · §Z5 (port `_SIM_SESSIONS` to Redis, debounce
snapshots, retention beats, readiness probes, Postgres tuning) · §Z6 (email streams + SPF/DKIM/DMARC,
JSON-LD, ruff/pre-commit, the dormant CI triggers, testing pyramid, CHANGELOG/ADRs/flags) ·
§W3–W14 · §B1–B8 · §O1–O8 · §X7 · §Y4.

## Shared components — five, carrying eleven epics. Build each once.
| Component | Consumers |
|---|---|
| **Rubric engine** | scenario objectives (§G) · interview scoring (§I1) · written ops artifacts (§X5c) |
| **Multilingual embeddings** | English scoring rigour (§I1) · Telugu/Hindi (§Y1d) · code-switching — *one change, three wins* |
| **Cost model** | FinOps scenarios (§X5b) · datacenter economy (§X6c) |
| **`Artifact` primitive** | all provenance chains (§X3/§X4) · API-client digest checks (§Y3) |
| **Analytics + flags (PostHog)** | funnel (§Z6-6) · feature flags (§Z6-15) · phased rollout of every phase above |

Building these per-epic instead of once is the single largest avoidable cost in this plan.

## Ten highest-value single changes, ranked by impact ÷ effort
1. `completeness.py:184` — drop the `aws→terraform` alias · **421 labs** · 1 line
2. Delete `frontend/public/sitemap.xml` + add the nginx location · **~13,000 URLs** · 1 hour
3. `rhel_shell.py:1563` — gate `systemctl start` on the existing `nginx -t` · **every config lab
   becomes causal** · ~10 lines
4. `simulation_provisioner.py:1345` — delete `_is_aws_academy` · **420 labs + activates 180 lines of
   written grading** · small
5. Docker log rotation in every compose file · **prevents a whole-cluster disk-full outage** · minutes
6. `rhel_os.py:473` — per-GPU dataclass replacing one boolean · **~70 GPU scenarios become real,
   zero UI work**
7. `voice_service.py:34-66` — drop the stale voice name hints · **best naturalness-per-line in the
   voice stack**
8. `api/client.js:64` — refresh mutex · **stops random mid-session logouts on the busiest page**
9. Delete the 307 `assert callable(solution)` graders · **stops awarding XP for nothing**
10. `DatacenterSimulator.jsx:481` — make the 3D fallback transient + versioned key · **releases every
    browser currently pinned to 2D**

---
---

# IMPLEMENTATION LOG — 2026-08-06 (session 2)

Branch: `feat/ai-infra-dc-living-world`. Every item below was built, linted, and
verified — verification method stated per item. **This is a progress log, not a
completion claim: 690+ items in this document remain open.**

## ✅ Landed

### 1. Datacenter 3D root cause — §X1 (see the ✅ block in §X1 for detail)
Four changes: procedural `HallEnvironment` replacing the CDN HDRI · narrowed
`STALE_CHUNK_RE` in `main.jsx` · versioned `PREFER_2D_KEY` releasing poisoned
browsers · `<Suspense>` moved outside `Twin3DSafe`.
**Verified:** eslint 0 errors · build clean · `preset:"warehouse"` passed 0 times in
the shipped bundle · behavioural test of the reload matcher (6 cases, table in §X1e)
· zero console errors in a real browser.

### 2. §X1e — the page-reload bug (NEW finding, not in the original audit)
A bare `/Failed to fetch/` in the stale-chunk matcher turned **any** network error
into `window.location.reload()`. This was the owner's *"links are asking to reload
the pages"* symptom, and the same HDRI failure caused both it and the 2D fallback.

### 3. Home page now markets the 3D datacenter + GPU track
- [x] **New `DatacenterGpuShowcase`** (`pages/home/components/`) — animated,
      CSS/SVG-only (deliberately no video, no WebGL, no network asset, so the
      marketing path can never repeat the CDN-HDRI failure). Isometric hall with
      receding rack rows, blinking status LEDs, airflow particles, a crosshair with
      an `[E] Open rack RACK-03` prompt, facility chips (cold/hot aisle, PDU A/B
      load, PUE), a real rack elevation with U positions and a failed-PSU sled, and
      an `nvidia-smi`-style GPU telemetry panel including an SW-thermal-slowdown flag.
- [x] **New `DatacenterGpuSection`** (`pages/home/sections/`) wired into `HomePage`
      after `VMwareSection`. Headline *"Walk a real datacenter. Run a real GPU
      fleet."* with two CTAs.
- [x] Motion respects `prefers-reduced-motion`; compacted under 640px.
- **Verified in a real browser at 1440×900:** section found, 8 racks, 6 U-rows,
      4 GPU rows, 3 facility chips, both CTAs present — screenshot reviewed.

### 4. Hero copy rewritten — the owner's specific ask
The old paragraph said "30+ technologies", listed 8, and never mentioned GPUs, AI
infrastructure, the 3D datacenter, tutorials, or projects. Now: live technology
count, the AI-infra/GPU/LLM/data-science track named explicitly, and the full
journey — tutorials → Jira incident → 3D datacenter → portfolio projects → voice AI
interview → certificates. Split into two paragraphs for scannability.
Home `usePageTitle` description updated to match (also helps §Z6-2).

### 5. Mobile — measured improvements
- [x] **Technology grid: 3,839px → 1,364px of scroll (−64%)**. It collapsed to ONE
      column under 540px while each card kept 24px padding, a 54px icon and an 18px
      icon margin = 175px per card × 22 cards. Now two compact columns, card 104px.
      **Gotcha worth remembering:** the first attempt placed the media query *above*
      the base `.fx-tech-*` rules — identical specificity, so source order lost and
      only the grid columns applied. The override block must sit **after** the base
      rules. Verified by computed style, not by reading the CSS.
- [x] **11 simulator login gates** `w-[400px]` → `w-full max-w-[400px]`
      (openstack, datacenter, netapp, azure, docker, commvault, soc, awx, k8s, gcp,
      dellemc). They overflowed a 375px viewport and clipped form fields.
      `MainLayout`'s `w-[400px] h-[400px]` is a decorative blurred orb — deliberately
      left alone.
- [x] **§H2 mobile lab action bar `z-30` → `z-[85]`** — it sat *below* the `z-[80]`
      companion overlays, so opening any console buried Instructions / Hints /
      **Check** / Stop. This was the owner's "no lab buttons" report. The sidebar
      already escalated to `z-[70]`; the bar was simply missed.
- [x] `aws-sim.css` / `vmware-sim.css` mobile blocks: `.aws-modal` had
      `min-width:400px` **and** `width:100%` so it could never fit a 375px screen;
      `.aws-leftnav` took 220px (59%) of the viewport; `.vm-table` forced a 520px
      floor. All relaxed in `@media (max-width:640px)` only — desktop untouched.
- **Verified:** no horizontal overflow at 375px (`scrollWidth === clientWidth`); the
      20 wider-than-viewport elements are all intentional (marquee tracks,
      decorative orbs, the isometric floor) inside `overflow:hidden`.

### 6. §C2 — the aws→terraform alias (421 labs)
`apps/tutorials/completeness.py` mapped `aws`/`azure`/`gcp` → `terraform`, so every
AWS tutorial linked to a Terraform lab despite `scenarios/aws/` holding 420 of its
own. Aliases removed with a comment saying not to re-add them.
**Verified behaviourally** by executing the real function:
`aws → academy-aws-001-learn-ec2`, `azure → academy-azure-001-learn-virtual-machines`,
`gcp → academy-gcp-001-learn-compute-engine`, and `terraform`/`linux`/`kubernetes`
unchanged (no regression).

### 7. Static technology catalog — breadth now visible
`constants/techCatalog.js` is the offline/first-paint fallback. It had 22 entries,
**19 with the identical generic tag "Hands-on labs"**, and was missing three
technologies the owner explicitly wants marketed. Added **3D Datacenter**,
**AI / ML & LLM Ops**, and **Data Science** (all three verified against real
`scenarios/<slug>/technology.yaml`), and replaced every generic tag with a specific
one (GPU fleet ops · Walkable 3D twin · LLM & agent labs · Full vCenter console · …).

## ⚠️ Correction to this document — §Y2e was an overreach
§Y2e called for deleting the "hardcoded IDE credentials" as a security issue. On
inspection that is **wrong, and acting on it would have removed intended UX.**

`lab_ide` / `lab_ide@123` is one of **14** simulated-console logins
(awx, azure, commvault, datacenter, dellemc, docker, gcp, ide, k8s, netapp,
openstack, soc, terraform, windows). Every one displays its own credentials on
screen with an autofill button, and every gate is bypassed once a provisioned lab
session exists. They are **lab flavour, not authentication** — they protect nothing,
so there is nothing to leak.

**What was done instead:** all 14 sites annotated with a `SIMULATED-CREDENTIAL`
marker explaining what they are and stating that scanners should allowlist the
marker.

**This matters for §S2.** The recommendation there was to add generic
`(SECRET_KEY|PASSWORD|_PASS)=\S{16,}` patterns to
`scripts/check-no-secrets-in-git.sh`. Done naively that would have produced **14+
false positives on day one** — the classic way a secret scanner gets muted and stops
being trusted. **§S2 must exclude lines within 6 lines of a `SIMULATED-CREDENTIAL`
marker**, or match on real-secret shapes rather than the word "PASS".

### 8. §S2/§S3 — secret scanner: catches real leaks, gated on PR, and fast
- [x] Generic `NAME=value` pass added. **10 of 10** known-leaked lines in
      `SETUP_COMPLETE.md` flagged; **zero false positives** across all 16,372
      tracked files. Wired into `ci.yml` so it gates every PR (it previously ran
      only in deploy/manual workflows, which is how those credentials merged green).
- [x] **Performance regression I introduced and then fixed: 8m10s → 1.6s (~300×).**
      The first version was a per-file bash loop spawning grep once per file per
      pattern — 16,372 files × 8 patterns ≈ 131,000 process spawns. Replaced with
      two `git grep` invocations that apply pathspec exclusions in-process.
      **Caught only because a background run had `time` around it.** An 8-minute PR
      gate would have been deleted by someone, which is worse than no scanner.
      *Do not reintroduce a per-file loop in that script.*

**Four false positives found and eliminated, each from a live run — this is the
list to consult before widening the patterns again:**
| Hit | Why it is not a secret |
|---|---|
| `.github/workflows/*` `SECRET_KEY` | throwaway key for the ephemeral CI test DB; real CI secrets come from GitHub Environments |
| `tutorials_extra.json` k8s Secret manifest | the manifest **is** the lesson content |
| `test_billing_webhooks.py`, `test/smoketest_e2e.py` | test fixtures (note `test/` singular + `smoketest_*` matched neither `**/tests/**` nor `**/test_*.py`) |
| `setup-gmail-oauth.py` f-string | `print(f"...={creds.refresh_token}")` **emits** a secret at runtime, does not contain one; the filter knew `${VAR}` but not f-string fields |

**Two false negatives, which matter more:** the value class started as
`[A-Za-z0-9+/_@%.-]` and caught only **4 of 10** real leaks, because a Django
`SECRET_KEY` contains `!#$%^&*()=+` and the 16-char run broke at the first special
character. And a bare `/your/` placeholder filter silently suppressed a real
`AWS_SECRET_ACCESS_KEY` whose value contained that substring. Both tightened.
- [x] Self-test: a planted `AKIA` key confirms the rewritten prefix pass still
      fires, rather than being silently broken by the rewrite.
- [ ] **The leaked credentials themselves still need rotating out-of-band** (§S1).
      The scanner only stops new ones landing. It will keep failing CI until
      `SETUP_COMPLETE.md` is scrubbed — that is intentional.

## Still open from this turn's asks
- [ ] **§X1c — 3D exists in only 1 of 10 rooms.** `currentRoom.type === 'data_hall'`
      gates it, so walking a portal out of the data hall leaves 3D entirely. This is
      the next concrete step toward the game feel and the twin already has
      `onEnterRoom` + portal geometry.
- [ ] **§X6 — the game layer** (build/place mode, economy, SLA contracts,
      progression). Multi-week; §X6d is gated on §D14's thermal model, because
      without load→temperature coupling there is no jeopardy to build a game around.
- [ ] The 3D hall has **not** been visually confirmed rendering — reaching the
      datacenter simulator needs auth plus a live lab session.
- [ ] Two runtime CDN deps remain and will fail the same way offline:
      `pyodideRunner.js:17` and `useVirtualBackground.js:28`.
- [ ] Technology cards show `scenario_count` when the API supplies it; with the API
      down they fall back to the static tag. Worth confirming the live
      `/api/technologies/` payload actually includes `scenario_count`.

---

# IMPLEMENTATION LOG — 2026-08-06 (session 3)

## ✅ Landed

### 9. Signup page — live stats, and two untrue claims removed
- [x] Stats were fully static: **"9+ Live Labs" against 7,280 scenarios and
      "5 Technologies" against 46** — understating the catalogue by three orders of
      magnitude and reading as placeholder copy. Now live from `/api/stats/`
      (`PlatformStatsView`, 2-min cached, returns zeros rather than 500ing):
      Hands-on labs / Technologies / Labs solved / Engineers training, `k+`
      formatted, em-dash while in flight, never blocks signup.
- [x] **Removed a fabricated endorsement.** `Register.jsx` carried a five-star
      quote from *"Sarah K., SRE at Cloudflare"*. No such person, and Cloudflare
      has not endorsed the product — a fake testimonial using a real company's name
      to imply one. That is a misleading advertisement under the Consumer
      Protection Act 2019 / CCPA endorsement rules. Replaced with three claims
      checkable from the product. **Do not reintroduce invented testimonials.**
      *Checked the rest of the codebase:* the home page uses generic role personas
      ("DevOps Engineer · Enterprise") with no named individual or employer — a
      defensible middle ground, left alone.
- [x] **Removed "99.9% Uptime"** from `AuthShell` (shown on `/login`). The platform
      does not measure or publish availability — monitoring is a 30-minute health
      check with no SLO (§Z5-17), so it was an unsubstantiated SLA claim. Now
      "Isolated labs", which is true and covered by `test_multiuser_isolation.py`.
- **Verification gotcha worth remembering:** the signup illustration panel is
      desktop-only. An initial check at a narrow viewport reported every string
      absent — a **false pass**, because `innerText` excludes hidden subtrees while
      `querySelectorAll` still finds them. Always confirm this panel at ≥1024px.
      A second false negative: `includes('Included from day one')` failed because
      CSS `uppercase` makes `innerText` return `INCLUDED FROM DAY ONE`.

### 10. Payment correctness — four money bugs fixed (§Z1)
143 billing / payment / certification / interview tests pass after these.
- [x] **§Z1-1 live revenue loss.** Cart showed the full total beside
      "Subscribe All (N)" while charging `cart[0]` only — a 5-item cart displayed
      ~₹2,495 and charged ₹499 for one technology. No multi-line order endpoint
      exists server-side, so the CTA now names the technology and amount actually
      being charged and states how many remain.
- [x] **§Z1-2 cert purchase broke on the second sale ever.** `idempotency_key` is
      `unique=True` with no default and was omitted, so the first purchase inserted
      `""` and every later one raised `IntegrityError` **after capture was verified
      and the subscription row created**. Now a deterministic sha256 of
      (user, track, order) via `get_or_create`.
- [x] **§Z1-3 free paid plans on one settings regression.** The interview signature
      check returned `DEMO_PAYMENT_ENABLED` without the `DEBUG` gate every sibling
      verifier has. Now requires both.
- [x] **§Z1-4 Stripe replay re-granted a year.** Deduped by a 1-hour Redis key while
      Stripe retries for up to three days; a restart inside that window let a replay
      re-run `activate_interview_plan`. Now uses the durable `ProcessedWebhookEvent`
      row the Razorpay path already had.
- [x] **§Z1-5 the enabler.** `generate_idempotency_key` mixed in `timezone.now()`,
      so every call was unique and the duplicate check it feeds could never match.
      Now takes an explicit `scope`: the Stripe session id where one exists (it was
      already in scope and ignored), and product identity + a 10-minute bucket in
      `payment_service` — collapses double-submits without blocking a legitimate
      renewal months later.

### 11. §S1 — the 10 tracked credentials redacted
- [x] Values replaced with `<REDACTED-ROTATE-ME>`; scanner now clean across all
      16,372 files, which unblocks the PR gate added in §S3.
- [ ] **STILL OPEN AND OWNER-ONLY: the credentials are in git history and must be
      treated as public. Rotate out-of-band on the servers** — Django `SECRET_KEY`,
      Postgres, Redis, RabbitMQ, Razorpay key secret, AWS secret access key.
      **Not** via the deploy workflow's `rotate_secrets` flag (known to break
      login). Redacting the file does not reduce the exposure.

## ⚠️ Why production deploy is NOT triggered in this session
Everything above is committed and locally green, but four things gate a 4D deploy
and three of them are owner-only:
1. **The leaked credentials are unrotated** (§S1 above). Deploying does not fix it.
2. **Real payment flow cannot be validated end-to-end without live Razorpay keys.**
   Entering payment credentials is not something to automate — the code paths are
   fixed and unit-tested, but "securely transacting" needs a real test charge by
   the owner in the Razorpay dashboard.
3. **Deploy flag invariants** (`rotate_secrets=false`, `build_scenarios=false`) and
   the **metadata-push race** (push and verify-sync *before* triggering) — see the
   deploy memories. These are easy to get wrong under time pressure.
4. GitHub Actions CI has not run yet; only the equivalent checks locally.

---

# IMPLEMENTATION LOG — 2026-08-06 (session 4)

## ✅ Landed — security

### §S5 — blind SSRF via org `webhook_url` (was the one genuinely exploitable bug)
- [x] New `apps/accounts/url_safety.py`. **Resolves** the host and rejects if any
      A/AAAA record is non-public — string matching is insufficient because a
      public-looking name can resolve to `127.0.0.1`. Fails closed on resolution
      failure. `https` + port 443 only, which also removes the
      scan-the-private-network-by-port primitive. Blocks embedded credentials and
      cloud metadata addresses explicitly.
- [x] Wired into `org_views.py` — the write used `setattr` +
      `save(update_fields=...)`, which skips `full_clean()`, so `URLField`
      validation never ran.
- [x] **Delivery moved to Celery** (`deliver_org_webhook`), so lab completion no
      longer blocks on a 5s timeout against a user-controlled URL. **Gotcha:**
      autodiscovery only imports each app's `tasks.py`, and this task lives in
      `webhooks.py`, so it is explicitly imported in `celery_app/tasks.py`
      following the `check_business_signals` precedent. Verified registered as
      `apps.accounts.webhooks.deliver_org_webhook` — without that import `.delay()`
      raises and silently degrades to the synchronous send it exists to remove.
- [x] 16 tests, incl. DNS-rebinding and mixed A records. Verified end-to-end:
      IMDS / Vault-on-private / Postgres / rebind-to-loopback / plain-http all
      **BLOCKED**, a legitimate Slack-style webhook **ALLOWED**.
- [ ] Documented residual risk: TOCTOU between check and connect. Closing it fully
      needs address pinning in the request layer. Mitigated by https+443 only, the
      move off the request path, and re-validation inside the task.

### §S7 — two auth controls failing open in silence
- [x] `accounts/views.py:358` IP-blocklist check and `:369` brute-force counter
      were both `except: pass`. They still fail **open** (an outage must not lock
      everyone out of login) but now log at WARNING. The brute-force one matters
      more than it looks: the login throttle counts **failures only**, so a
      swallowed exception meant the counter stopped incrementing and the rate limit
      stopped enforcing while still appearing configured.

### §Z3-2 — community writes were completely unthrottled
- [x] All eight write views had no `throttle_classes`. Four per-user scopes added:
      `ugc_write` 60/h, `ugc_light` 300/h, `ugc_upload` 20/h, `ugc_report` 20/h.
- [x] **Two mistakes made and caught by writing the tests:**
  1. A plain `UserRateThrottle` would have **broken public browsing**.
     `ThreadListView`/`ThreadDetailView` allow anonymous GETs and DRF keys on IP
     when unauthenticated, so reads would have been capped at the *write* rate for
     every logged-out visitor and every NAT'd office. Hence
     `_WriteOnlyUserThrottle`, which short-circuits safe methods.
  2. **`config/test_settings.py` REPLACES `DEFAULT_THROTTLE_RATES` rather than
     extending it.** Adding the scopes to `settings.py` alone made every existing
     community test 500 with `ImproperlyConfigured`. Mirrored there with a comment;
     `test_scopes_registered_in_both_settings` locks it in. **Remember this for any
     future scope.**

## ✅ Landed — the two grind faucets

### §Z3-3 — weekly leaderboard rewarded replays
- [x] `_build_weekly` used `Sum("score")` over every session in the window.
      Measured: grinder solving one 100-point lab ×40 scored **4000 → rank 1**;
      honest user with two labs (120+130) scored 250 → rank 2. Now per-scenario
      bests: grinder **100 → rank 2**, honest **250 → rank 1**.
- [x] The bug was visible in its own output and nobody looked —
      `scenarios_completed` used `distinct=True`, so a grinder rendered as
      *"1 scenario"* beside an enormous total.
- [x] Implementation note: Django cannot `Sum()` over an aggregate annotation in
      one chain (`Sum("best")` where `best=Max(...)` raises at
      `resolve_expression`), so the per-user roll-up is Python over one row per
      `(user, scenario)`, streamed with `.iterator()` and bounded by the 7-day window.

### §Z3-4 — XP was awarded per session, not per scenario
- [x] The `completion_finalized` lock is genuinely correct **per session** (it
      defeats duplicate Jira webhooks and double-clicked Check) and its comment
      claimed "exactly once per scenario completion" — but a lab **restart** makes a
      new session, so re-solving minted the full 150–250 XP again. `compute_score`
      rewards speed, so the fastest replay paid most.
- [x] Now gated on `UserScenarioProgress.completed`, read *before*
      `record_attempt()` sets `completed_at`. Practice still updates `best_score`,
      `best_time`, `attempts` and achievements — it just mints no XP.
- [x] 5 tests incl. "a DIFFERENT scenario still pays" so the fix is not over-broad.

## ✅ Landed — signup / marketing honesty (session 3 items, verified)
See session-3 log. Notable: removed a **fabricated testimonial** attributed to a
named person at a real company, and a **"99.9% Uptime"** claim the platform does
not measure.

## ⚠️ Two pre-existing test-layout defects found
- [ ] **`apps/jira_integration/` has no `__init__.py`** — it is a namespace
      package, so `manage.py test apps.jira_integration` dies with
      `TypeError: expected str, bytes or os.PathLike object, not NoneType` and its
      tests are unreachable by app label. Not fixed blind here because adding it
      changes package semantics for a working app.
- [x] `apps/public_api/tests/` cannot be a package — `tests` collides with the
      top-level `backend/tests` package (`ImportError: 'tests' module incorrectly
      imported`). That is why it had no `__init__.py`. New tests for that app
      belong in `backend/tests/` (102 modules there already).

## Still open — highest value next
- [ ] **§Z1-8** refunds: `RazorpayRefundView` is well-built and has **zero frontend
      callers**, while `FAQ.jsx:46` promises 7-day refunds. A refund also never
      revokes entitlement.
- [ ] **§Z1-9** interview certificates are a paid feature enforced nowhere.
- [ ] **§Z3-1** abuse reports write to a table with no admin queue.
- [ ] **§Z3-5** certificates cannot be revoked (signed Open Badges, no revocation
      list) — needed to unwind anything earned via the fail-open graders.
- [ ] **§Z4-1** log PII: the masker only covers `extra={}`; ~30 f-string email
      sites bypass it, including two that log the address **at deletion**.
- [ ] **§Z5-1/Z5-2** the `_SIM_SESSIONS` cross-process leak and the full-VFS JSONB
      write per command — the two things that will bite before growth does.

---

# IMPLEMENTATION LOG — 2026-08-06 (session 5)

## ✅ Landed

### §Z1-8 — a refund returned the money but not the access
- [x] `RazorpayRefundView` touched only the `PaymentTransaction` row, so a refunded
      customer kept a **full year** of paid access. `FAQ.jsx:46` publicly promises
      refunds within 7 days, which made this a standing leak rather than an edge case.
- [x] `_revoke_entitlement_for_transaction` now deactivates the linked
      `TechnologySubscription` (or one resolved from gateway metadata via the
      existing `technology_id_from_transaction`), a `CertificationTrackSubscription`
      for cert purchases, and zeroes `InterviewEntitlement.interviews_remaining`.
- [x] **Only on FULL refund** — a goodwill credit or price adjustment must not
      strip access that was partly paid for.
- [x] Never raises (a gateway refund already succeeded), but logs at ERROR with the
      transaction and user id so a mismatch is reconcilable. 5 tests, including that
      revocation **cannot leak across users**.
- [x] FAQ copy corrected: manual path, realistic turnaround, and it now states that
      a full refund ends access — true only as of this change.
- [ ] Still open: `RazorpayRefundView` has **no frontend caller**, so every refund
      is a manual gateway/shell operation.

### §Z1-9 — interview certificates: a paid feature enforced nowhere
- [x] `certificate_enabled` is seeded False on Free / True on Pro+Premium, exposed
      in the entitlement payload and shown in pricing — and **nothing checked it**.
      `_finalize_campaign` called `issue_certificate()` unconditionally, so Free
      tier received the artefact Premium (₹2,499) is partly sold on. Grepping the
      flag returned only serializers, admin, seeds and the payload: no enforcement
      site existed.
- [x] Now gated, and **fails closed** on lookup error — withholding is recoverable,
      over-issuing the paid artefact is not. Idempotency preserved so a plan
      downgrade does not retroactively void an earned certificate. 5 tests; full
      interviews suite (82) green.

### §Z5-2 — a database write per keystroke-line — **and a correction to this document**
- [x] **The audit overstated this.** It called the snapshot "multi-hundred-KB".
      Measured: **15,121 bytes fresh, 15,446 after eight commands** — it barely
      grows. The problem was never per-write size, it was **frequency**.
- [x] Real numbers at 60 concurrent labs × ~20 commands/min:

      | | writes/min | volume | per hour |
      |---|---|---|---|
      | before | 1,200 | 17.3 MB/min | **1.01 GB/hour** |
      | after | 240 | 3.5 MB/min | 0.20 GB/hour |

      **5× fewer** full-row JSONB rewrites and dead tuples. (Not 30× — the debounce
      is per-session and there are 60 sessions.)
- [x] 15s debounce **plus an unconditional flush in `disconnect()`**, so debouncing
      cannot lose work even if the last command lands inside the window. The
      snapshot is a durability backstop — the authoritative engine is in memory and
      the snapshot exists for cross-process team-bot actions and restart recovery —
      so a slightly stale backstop is acceptable; a lost session is not.
- [x] 7 tests. **These are the first tests `apps/terminal` has ever had** — zero
      coverage is how a per-keystroke database write survived this long.

## Verification
Local full suite: **1,710 tests, OK, 52 skipped** (baseline was 1,677; the delta is
the tests added in sessions 4–5). CI on PR #161: frontend, CodeQL, all three
Analyze jobs and **Grader integrity (17m)** green; `backend` still running.

## Corrections made to this document by measurement
| Claim | Reality |
|---|---|
| §Z5-2 snapshot is "multi-hundred-KB" | **15 KB**; frequency was the problem |
| §Y2e IDE credentials are a security hole | **Simulation flavour** across 14 consoles; deleting would strip intended UX |
| §S2 "add generic PASSWORD= patterns" | Would have produced **14+ false positives** and muted the scanner |
| `apps.tutorials` test error blamed on §C2 | **Isolation artefact** — does not reproduce in the full suite |

## Still open — the single largest operational risk
- [ ] **§Z5-1 `_SIM_SESSIONS` cross-process leak.** A process-local dict across 4
      uvicorn workers + celery, populated in one and freed from one, no TTL, no
      bound. Uvicorn workers never recycle, so D2's 5 GB cgroup OOM-kills all four
      and every in-flight lab dies. **The fix pattern is already in the repo** — all
      22 `apps/vmware_sim/*_engine.py` modules are cache-backed with
      `SESSION_TTL=7200`. Porting `UnifiedSimulationEngine` to the same shape also
      fixes §Z5-3 (sim side) and the reconnect-lands-on-wrong-engine bug.
      *Interim mitigation available today: set `UVICORN_WORKERS=2` (halves the
      fan-out, matches the 2 vCPU box) and export `len(_SIM_SESSIONS)` so the leak
      is at least observable.*
