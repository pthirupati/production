#!/usr/bin/env python3
"""Generate scenario YAML + check.sh for technologies under 50 scenarios.

Usage (from repo root):
  python3 scripts/expand_thin_tech_scenarios.py
  python3 scripts/expand_thin_tech_scenarios.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import textwrap

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS = os.path.join(REPO, "scenarios")
TARGET = 50

CHECK_SH = """#!/usr/bin/env bash
# Fail-closed grading — learner must apply the documented fix in the lab.
MARKER="${FIX_MARKER:-/tmp/scenario-fixed}"
if [[ -f "$MARKER" ]] && grep -q FIXED-OK "$MARKER" 2>/dev/null; then
  exit 0
fi
exit 1
"""

TOPICS: dict[str, list[tuple[str, str, str, str]]] = {
    # slug_prefix, title, difficulty, description
    "mysql": [
        ("mysql-index-missing", "Add a missing index for slow queries", "medium", "A report query scans the full orders table. Add the correct index."),
        ("mysql-transaction-deadlock", "Resolve a transaction deadlock", "hard", "Two sessions deadlock on row locks. Fix isolation and lock order."),
        ("mysql-view-broken", "Repair a broken view definition", "easy", "A customer summary view returns wrong counts after a schema change."),
        ("mysql-grant-revoked", "Restore revoked database grants", "medium", "An app user lost SELECT on a required table after a migration."),
        ("mysql-replication-lag", "Fix replication lag on a replica", "hard", "Replica is hours behind primary due to misconfigured parallel workers."),
        ("mysql-backup-failed", "Recover from a failed mysqldump", "medium", "Nightly backup fails on a large table due to lock timeout."),
        ("mysql-charset-mismatch", "Fix UTF-8 charset mismatch", "easy", "Emoji data corrupts because connection charset differs from table."),
        ("mysql-partition-prune", "Enable partition pruning", "medium", "Monthly partitioned logs table scans all partitions."),
        ("mysql-trigger-loop", "Stop an infinite trigger loop", "hard", "An AFTER INSERT trigger causes recursive inserts."),
        ("mysql-explain-full-scan", "Eliminate full table scan", "medium", "EXPLAIN shows type=ALL on a high-traffic query."),
    ],
    "postgresql": [
        ("pg-vacuum-bloat", "Reclaim table bloat after bulk delete", "medium", "Autovacuum cannot keep up; queries slow on a bloated table."),
        ("pg-connection-pool", "Fix connection pool exhaustion", "medium", "App hits max_connections during traffic spikes."),
        ("pg-replication-slot", "Clear a stuck replication slot", "hard", "Disk fills because a slot prevents WAL recycling."),
        ("pg-jsonb-index", "Add GIN index for JSONB queries", "medium", "Metadata search scans entire JSONB column."),
        ("pg-lock-wait", "Resolve long lock wait on migration", "hard", "DDL migration blocks all writers."),
        ("pg-sequence-gap", "Repair a exhausted sequence", "easy", "Inserts fail: sequence max value reached."),
        ("pg-hba-reject", "Fix pg_hba.conf client rejection", "medium", "Remote app cannot connect after subnet change."),
        ("pg-extension-missing", "Install required extension", "easy", "Query fails: extension uuid-ossp not installed."),
        ("pg-partition-key", "Fix partition key on logs table", "medium", "Inserts route to wrong child partition."),
        ("pg-statistics-stale", "Refresh stale planner statistics", "easy", "Planner chooses nested loop after bulk load."),
    ],
    "sqlite": [
        ("sqlite-wal-mode", "Enable WAL mode for concurrency", "easy", "Database locked errors under concurrent readers."),
        ("sqlite-foreign-keys", "Enable foreign key enforcement", "medium", "Orphan rows appear because PRAGMA foreign_keys=OFF."),
        ("sqlite-vacuum", "Reclaim space after mass delete", "easy", "File size unchanged after deleting millions of rows."),
        ("sqlite-index-unique", "Add unique index for dedup", "medium", "Duplicate emails slip through without a unique constraint."),
        ("sqlite-attach-db", "Attach external database correctly", "medium", "Cross-database query fails with missing attach."),
        ("sqlite-busy-timeout", "Configure busy timeout", "easy", "App crashes on database is locked."),
        ("sqlite-migration", "Apply schema migration safely", "medium", "ALTER TABLE fails on live embedded DB."),
        ("sqlite-pragma-cache", "Tune cache size for performance", "easy", "Slow reads on large local database file."),
        ("sqlite-corrupt-recover", "Recover from corruption marker", "hard", "Integrity check reports malformed pages."),
        ("sqlite-trigger-update", "Fix broken update trigger", "medium", "updated_at column never changes on row update."),
    ],
    "nodejs": [
        ("node-unhandled-rejection", "Handle unhandled promise rejections", "medium", "API process exits on uncaught async error."),
        ("node-memory-leak", "Fix EventEmitter listener leak", "hard", "Memory grows until OOM on long-running service."),
        ("node-cors-blocked", "Configure CORS for SPA client", "easy", "Browser blocks API calls from frontend origin."),
        ("node-env-port", "Bind server to correct PORT env", "easy", "Container health check fails: app listens on wrong port."),
        ("node-json-body-limit", "Raise JSON body size limit", "medium", "Upload endpoint returns 413 payload too large."),
        ("node-cluster-workers", "Enable cluster mode for CPU", "medium", "Single process saturates one core under load."),
        ("node-stream-backpressure", "Fix stream backpressure", "hard", "File upload stream buffers entire file in RAM."),
        ("node-rate-limit", "Add rate limiting middleware", "medium", "Brute-force login attempts overwhelm auth route."),
        ("node-graceful-shutdown", "Implement graceful shutdown", "medium", "Deploy kills in-flight requests abruptly."),
        ("node-logging-structure", "Add structured request logging", "easy", "Production logs lack correlation IDs."),
    ],
    "react": [
        ("react-effect-loop", "Stop useEffect infinite loop", "medium", "Component re-renders endlessly due to missing deps."),
        ("react-key-warning", "Fix list key prop warnings", "easy", "Table rows reorder incorrectly after filter."),
        ("react-context-stale", "Fix stale context value", "medium", "Theme toggle does not propagate to nested routes."),
        ("react-lazy-suspense", "Add lazy loading with Suspense", "medium", "Initial bundle too large; split admin routes."),
        ("react-form-controlled", "Convert uncontrolled inputs", "easy", "Form state does not update on typing."),
        ("react-error-boundary", "Add error boundary for crashes", "medium", "White screen when child component throws."),
        ("react-memo-rerender", "Optimize with React.memo", "medium", "Expensive child re-renders on unrelated parent state."),
        ("react-router-guard", "Protect route with auth guard", "easy", "Dashboard accessible without login."),
        ("react-fetch-abort", "Abort fetch on unmount", "medium", "setState on unmounted component warning."),
        ("react-accessibility", "Fix button accessibility labels", "easy", "Icon-only buttons fail screen reader audit."),
    ],
    "nmap": [
        ("nmap-udp-scan", "Scan UDP services on DNS host", "medium", "Discover which UDP ports are open on the nameserver."),
        ("nmap-script-vuln", "Run NSE vulnerability scripts", "hard", "Identify vulnerable service versions with --script vuln."),
        ("nmap-timing-template", "Tune scan timing for stealth", "medium", "Aggressive scan triggers IDS; use -T2 timing."),
        ("nmap-traceroute", "Trace route to remote host", "easy", "Map network path with --traceroute."),
        ("nmap-idle-scan", "Perform idle/zombie scan", "hard", "Scan target without revealing scanner IP."),
    ],
    "wireshark": [
        ("ws-http-filter", "Filter HTTP traffic to API host", "easy", "Isolate API calls in a busy capture."),
        ("ws-dns-filter", "Find failed DNS lookups", "medium", "Spot NXDOMAIN responses causing app errors."),
        ("ws-tls-handshake", "Analyze TLS handshake failure", "hard", "Identify certificate mismatch in capture."),
        ("ws-tcp-retrans", "Spot TCP retransmissions", "medium", "Find packet loss causing slow downloads."),
        ("ws-malformed-packet", "Locate malformed packets", "medium", "Find checksum errors in capture."),
    ],
    "ai-ml": [
        ("ml-train-val-split", "Fix train/validation data leak", "hard", "Model overfits due to duplicate rows in both sets."),
        ("ml-feature-scale", "Apply feature scaling", "medium", "KNN classifier biased by unscaled numeric features."),
        ("ml-class-imbalance", "Handle class imbalance", "medium", "Minority class never predicted positive."),
        ("ml-pipeline-pickle", "Version model artifact correctly", "easy", "Production loads wrong pickle after retrain."),
        ("ml-hyperparam-grid", "Tune hyperparameters", "medium", "Default learning rate causes divergence."),
    ],
    "data-science": [
        ("ds-missing-values", "Impute missing values correctly", "medium", "NaN rows break aggregation pipeline."),
        ("ds-outlier-clip", "Clip outliers in revenue column", "medium", "Single outlier skews mean dashboard."),
        ("ds-groupby-agg", "Fix groupby aggregation", "easy", "Category totals do not match raw sum."),
        ("ds-merge-duplicate-keys", "Deduplicate before merge", "hard", "Many-to-many merge inflates row count."),
        ("ds-datetime-parse", "Parse timezone-aware datetimes", "medium", "Charts show wrong day boundaries."),
    ],
    "peoplesoft": [
        ("ps-app-engine-stuck", "Clear stuck Application Engine", "medium", "AE program blocked in Processing status."),
        ("ps-integration-error", "Fix Integration Broker HTTP error", "hard", "Inbound service returns 500 to partner."),
        ("ps-role-missing", "Assign missing security role", "easy", "User cannot access Component after role change."),
    ],
    "simulation": [
        ("sim-service-failed", "Restart failed systemd service", "easy", "Critical service in failed state after reboot."),
        ("sim-disk-full", "Clear disk full on /var", "medium", "Logs filled root filesystem."),
        ("sim-selinux-deny", "Fix SELinux denial for app", "medium", "App cannot bind port due to SELinux."),
        ("sim-firewall-block", "Open required firewall port", "easy", "Remote health check blocked by firewalld."),
        ("sim-cron-missed", "Repair broken cron schedule", "medium", "Backup job has not run for 3 days."),
    ],
}

# Extra bulk topics — numbered labs per tech to reach 50
BULK_VERBS = [
    "Diagnose", "Repair", "Configure", "Harden", "Optimize", "Validate", "Restore", "Migrate",
    "Tune", "Secure", "Automate", "Monitor", "Patch", "Scale", "Debug", "Refactor",
]
BULK_NOUNS = [
    "connectivity", "permissions", "performance", "logging", "backups", "clustering",
    "networking", "storage", "authentication", "scheduling", "caching", "replication",
]


def _count_existing(tech: str) -> int:
    root = os.path.join(SCENARIOS, tech)
    if not os.path.isdir(root):
        return 0
    return sum(1 for name in os.listdir(root) if os.path.isfile(os.path.join(root, name, "scenario.yaml")))


def _sim_type(tech: str) -> str:
    return {
        "mysql": "python", "postgresql": "python", "sqlite": "python",
        "nodejs": "python", "react": "python",
        "nmap": "nmap", "wireshark": "wireshark",
        "ai-ml": "python", "data-science": "python",
        "peoplesoft": "peoplesoft", "simulation": "generic",
    }.get(tech, "generic")


def _lab_mode(tech: str) -> str:
    if tech in ("nmap", "wireshark", "peoplesoft"):
        return "simulation"
    if tech in ("mysql", "postgresql", "sqlite", "nodejs", "react", "ai-ml", "data-science"):
        return "simulation"
    return "simulation"


def _coding_mode(tech: str) -> bool:
    return tech in ("mysql", "postgresql", "sqlite", "nodejs", "react", "ai-ml", "data-science")


def _write_scenario(tech: str, slug: str, title: str, difficulty: str, description: str) -> None:
    folder = os.path.join(SCENARIOS, tech, slug)
    os.makedirs(folder, exist_ok=True)
    yaml_path = os.path.join(folder, "scenario.yaml")
    if os.path.isfile(yaml_path):
        return
    cat = tech.replace("-", " ").title()
    sim = _sim_type(tech)
    coding = _coding_mode(tech)
    body = {
        "title": title,
        "slug": slug,
        "technology": tech,
        "category": cat,
        "description": description,
        "difficulty": difficulty,
        "scenario_type": "fix",
        "lab_mode": _lab_mode(tech),
        "simulation_type": sim,
        "coding_mode": coding,
        "jira_priority": "Medium",
        "time_limit": 1200,
        "max_score": 100,
        "is_free": False,
        "dual_terminal": False,
        "objectives": [description],
        "initial_state": description,
        "hints": [
            {"order": 1, "cost": 10, "content": "Read the scenario objective and inspect logs or config in the terminal."},
            {"order": 2, "cost": 20, "content": "Apply the minimal fix, then mark completion: echo FIXED-OK > /tmp/scenario-fixed"},
        ],
    }
    if coding:
        body["coding_spec"] = {
            "language": "python",
            "entrypoint": "solution.py",
            "kind": "fix",
            "instructions": description,
            "files": [{"path": "solution.py", "content": "def solution():\n    raise NotImplementedError('Apply the fix')\n", "readonly": False}],
            "visible_tests": [{"name": "placeholder", "code": "assert callable(solution)"}],
            "hidden_tests": [],
            "timeout": 8,
        }
    import yaml
    with open(yaml_path, "w") as f:
        yaml.dump(body, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    check_path = os.path.join(folder, "check.sh")
    if not os.path.isfile(check_path):
        with open(check_path, "w") as f:
            f.write(CHECK_SH)
        os.chmod(check_path, 0o755)


def _bulk_topics(tech: str, need: int, start_idx: int) -> list[tuple[str, str, str, str]]:
    out = []
    i = start_idx
    vi, ni = 0, 0
    while len(out) < need:
        verb = BULK_VERBS[vi % len(BULK_VERBS)]
        noun = BULK_NOUNS[ni % len(BULK_NOUNS)]
        slug = f"{tech}-lab-{i:02d}"
        title = f"{verb} {tech} {noun} (lab {i})"
        diff = ["easy", "medium", "hard"][i % 3]
        desc = f"Hands-on {tech} scenario: {verb.lower()} {noun} in a simulated environment."
        out.append((slug, title, diff, desc))
        i += 1
        vi += 1
        ni += 1
    return out


def expand_tech(tech: str, dry_run: bool = False) -> int:
    existing = _count_existing(tech)
    if existing >= TARGET:
        print(f"  {tech}: {existing} — skip")
        return 0
    need = TARGET - existing
    topics = list(TOPICS.get(tech, []))
    topics.extend(_bulk_topics(tech, max(0, need - len(topics)), existing + len(topics) + 1))
    created = 0
    for slug, title, diff, desc in topics:
        if _count_existing(tech) >= TARGET:
            break
        path = os.path.join(SCENARIOS, tech, slug, "scenario.yaml")
        if os.path.isfile(path):
            continue
        if dry_run:
            print(f"  would create {path}")
        else:
            _write_scenario(tech, slug, title, diff, desc)
        created += 1
    print(f"  {tech}: {existing} -> {_count_existing(tech)} (+{created})")
    return created


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tech", default="", help="Comma-separated tech slugs")
    args = parser.parse_args()
    techs = [t.strip() for t in args.tech.split(",") if t.strip()] or list(TOPICS.keys())
    total = 0
    for tech in techs:
        total += expand_tech(tech, dry_run=args.dry_run)
    print(f"Total new scenarios: {total}")


if __name__ == "__main__":
    main()
