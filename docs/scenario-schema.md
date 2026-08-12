# Scenario authoring schema (Phase 3.1)

Learner-facing labs are defined as `scenarios/<technology>/<slug>/scenario.yaml`.
Every lab session owns its own **Lab Servers** — there is no platform-global host.

## Required fields

| Field | Purpose |
|---|---|
| `title` | Specific ticket-style title (concrete resource names) |
| `slug` | Unique id |
| `technology` | Tech pack slug |
| `description` | Company ticket prose with CONTEXT / ENVIRONMENT / OBJECTIVE (+ IMPACT recommended) |
| `objectives` | ≥2 concrete acceptance steps |
| `hints` | ≥3 progressive hints with non-decreasing `cost` (0 → near-answer) |

## Strongly recommended (required for hero labs)

| Field | Purpose |
|---|---|
| `consoles` | List of tools to open (`terminal`, `vmware`, `aws`, `commvault`, `datacenter`, `soc`, …) |
| `lab_servers` | Scenario-scoped hosts the terminal/consoles share |
| `summary` | One-line outcome |
| `what_you_will_learn` | Skill bullets |
| `environment` | Nodes / credentials for the ticket |
| `tasks[].validation` | Machine-checkable check (usually `check.sh`) |

### `lab_servers` shape

```yaml
lab_servers:
  - id: primary
    role: primary
    hostname: db01
    persona: linux          # linux|windows|gpu|kubernetes|…
    appears_in: [terminal, vmware, commvault]
  - id: esxi-host
    role: hypervisor
    hostname: esxi-01
    persona: baremetal
    physical_location: { room: "Data Hall A", rack: "R12", u_position: 10 }
    appears_in: [vmware, datacenter]
```

Cross-tech means multiple consoles in **this** scenario share these Lab Servers.
AWS EC2 never appears in a physical rack; racked servers never appear as EC2.

## `coding_spec` — choosing `language`

`language` names the runtime that **grades** the lab, which is not always the
language the learner types. `apps/labs/code_exec.py` can auto-grade
`python`, `javascript` and `sql`; `bash`/`shell`/`sh` are `NEEDS_REVIEW` and every
other value returns `needs_review`, which by design **never auto-passes**. Setting
`language:` to something the grader cannot run does not "label the lab correctly" —
it makes the lab unsolvable.

| Lab shape | `language` | Entry file | Why |
|---|---|---|---|
| Repair/complete a **query**, graded on the rows it returns | `python` | `solution.py` exposing `solution(conn)` | Lets the test seed its own dataset and assert exact tuples — `language: sql` cannot invoke the learner's query against test-chosen data |
| Build a **schema**: DDL, indexes, constraints, migrations | `sql` | `solution.sql` | Harness applies the script to in-memory sqlite3, then asserts with `rows` / `scalar` / `tables` / `columns` / `indexes` / `explain` |
| Author **markup/styles** with a live preview | `javascript` | readonly `solution.js` harness + writable `index.html` / `styles.css` | `PAGE_HTML` / `PAGE_CSS` are injected server-side so JS tests can assert on markup without a DOM; the editor still highlights each file by extension and the IDE opens `index.html` |

So a `postgresql` lab on `language: python`, or an `html` lab on
`language: javascript`, is usually **correct** — check the grading shape before
"fixing" it. See `scenarios/postgresql/pg-fix-having-aggregate-filter` (query
repair) and `scenarios/html/academy-html-001-learn-semantic-html` (markup) for the
canonical examples of each.

SQL test helpers, all scoped to a **fresh** database per test (so a test that
mutates cannot change the next one's verdict):

```yaml
coding_spec:
  language: sql
  entrypoint: solution.sql
  hidden_tests:
    - name: index_is_used
      code: assert "idx_orders_customer" in explain("SELECT * FROM orders WHERE customer_id = 10")
    - name: row_count
      code: assert scalar("SELECT COUNT(*) FROM orders") == 3
```

## Banned learner-facing words

Do not use in `title`, `description`, `hints`, `objectives`, `summary`, etc.:

Simulation, Simulator, Simulated, Demo, Mock, Fake, Practice Environment

Internal fields (`lab_mode: simulation`, code, tests, docs) may keep those terms.

## Linter

```bash
python scripts/lint_scenarios.py --strict-heroes
python scripts/lint_scenarios.py --all --max-failures 999   # report-only catalog sweep
```
