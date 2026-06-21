#!/usr/bin/env python3
"""
Generator for Grafana + Prometheus simulation scenarios.

Each scenario is INTEGRITY-WIRED via the established fail-closed recipe:
  1. scenario.yaml          — lab_mode: simulation, simulation_type grafana|prometheus
  2. check.sh               — `grep -q FIXED-OK <config>` (recognized by
                              validation.py's generic FIXED-OK branch — NO new
                              validator code)
  3. a preset (emitted)     — writes <config> in a BROKEN state (no FIXED-OK)
  4. an e2e marker (emitted)— _RS_MARKER_FIX[slug] = <config>; the e2e fix
                              rewrites it WITH FIXED-OK so fail-before/pass-after
                              holds.

Running this script (idempotently):
  - writes scenarios/grafana/<slug>/{scenario.yaml,check.sh}
  - writes scenarios/prometheus/<slug>/{scenario.yaml,check.sh}
  - writes backend/.../simulation/monitoring_presets.py (preset module)
  - prints the _RS_MARKER_FIX dict block to add to scripts/e2e_simulation_fix.py
"""
from __future__ import annotations

import os
import stat
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCEN = os.path.join(ROOT, "scenarios")
PRESET_OUT = os.path.join(
    ROOT, "backend", "apps", "labs", "provisioner", "simulation", "monitoring_presets.py"
)

# Config file path each scenario's fix must edit. Grafana provisioning lives
# under /etc/grafana/provisioning, dashboards/alerting as YAML/JSON; Prometheus
# config lives under /etc/prometheus. The path is also the FIXED-OK target.
GRAFANA_DIR = "/etc/grafana"
GRAF_PROV = "/etc/grafana/provisioning"
PROM_DIR = "/etc/prometheus"


def _f(path: str) -> str:
    return path


# ── GRAFANA scenarios: (slug, title, difficulty, config_path, summary) ──
# 50 scenarios spanning datasources, dashboards, panels, variables, alerting,
# contact points, notification policies, provisioning, auth, and Loki.
GRAFANA = [
    ("grafana-datasource-misconfigured-no-data", "Datasource URL wrong — panels show No data", "medium", f"{GRAF_PROV}/datasources/prometheus.yaml", "The Prometheus datasource points at a wrong host so every panel renders 'No data'."),
    ("grafana-datasource-wrong-auth", "Datasource auth header missing", "medium", f"{GRAF_PROV}/datasources/prometheus.yaml", "Datasource returns 401 because the auth header / token is not configured."),
    ("grafana-datasource-tls-skip-verify", "Datasource TLS verification failing", "medium", f"{GRAF_PROV}/datasources/prometheus.yaml", "TLS handshake to Prometheus fails; cert verification misconfigured."),
    ("grafana-datasource-default-missing", "No default datasource set", "easy", f"{GRAF_PROV}/datasources/prometheus.yaml", "No datasource is marked default, so new panels have no source."),
    ("grafana-datasource-duplicate-uid", "Duplicate datasource UID", "medium", f"{GRAF_PROV}/datasources/prometheus.yaml", "Two datasources share a UID; provisioning fails to load."),
    ("grafana-loki-datasource-down", "Loki datasource unreachable", "medium", f"{GRAF_PROV}/datasources/loki.yaml", "Logs panels show errors — the Loki datasource URL is wrong."),
    ("grafana-datasource-scrape-interval-mismatch", "Datasource scrape interval mismatch", "medium", f"{GRAF_PROV}/datasources/prometheus.yaml", "The datasource's scrapeInterval disagrees with Prometheus, skewing rate()."),
    ("grafana-panel-wrong-promql", "Panel query has invalid PromQL", "medium", f"{GRAF_PROV}/dashboards/node-overview.json", "A panel's PromQL expression is malformed and errors."),
    ("grafana-panel-wrong-unit", "Panel unit misconfigured (bytes vs bits)", "easy", f"{GRAF_PROV}/dashboards/node-overview.json", "CPU/memory panel uses the wrong unit, so values look absurd."),
    ("grafana-panel-no-data-state", "Panel No-data state hides outage", "medium", f"{GRAF_PROV}/dashboards/node-overview.json", "Panel's no-data handling masks a real outage."),
    ("grafana-panel-legend-broken", "Panel legend format wrong", "easy", f"{GRAF_PROV}/dashboards/node-overview.json", "Legend template references a missing label."),
    ("grafana-panel-threshold-wrong", "Panel thresholds inverted", "easy", f"{GRAF_PROV}/dashboards/api-slo.json", "Threshold colors are inverted so healthy looks critical."),
    ("grafana-panel-time-range-override", "Panel time-range override stuck", "easy", f"{GRAF_PROV}/dashboards/api-slo.json", "A relative time override pins the panel to stale data."),
    ("grafana-panel-transform-broken", "Panel transform drops series", "medium", f"{GRAF_PROV}/dashboards/api-slo.json", "A transformation filters out all series by mistake."),
    ("grafana-panel-stat-reducer-wrong", "Stat panel reducer wrong (last vs mean)", "easy", f"{GRAF_PROV}/dashboards/node-overview.json", "Stat panel reducer shows the wrong aggregate."),
    ("grafana-dashboard-json-invalid", "Dashboard JSON invalid — fails to load", "medium", f"{GRAF_PROV}/dashboards/node-overview.json", "Dashboard JSON has a syntax error and won't import."),
    ("grafana-dashboard-uid-collision", "Dashboard UID collision", "medium", f"{GRAF_PROV}/dashboards/dashboards.yaml", "Two dashboards share a UID; one silently overwrites the other."),
    ("grafana-dashboard-folder-missing", "Dashboard provisioning folder missing", "easy", f"{GRAF_PROV}/dashboards/dashboards.yaml", "Provisioning points at a folder path that does not exist."),
    ("grafana-dashboard-version-drift", "Provisioned dashboard overwritten by UI edits", "medium", f"{GRAF_PROV}/dashboards/dashboards.yaml", "allowUiUpdates lets UI edits clobber provisioned dashboards."),
    ("grafana-variable-query-wrong", "Template variable query returns nothing", "medium", f"{GRAF_PROV}/dashboards/node-overview.json", "label_values() query is wrong so the $instance variable is empty."),
    ("grafana-variable-regex-filter", "Variable regex filters out all values", "medium", f"{GRAF_PROV}/dashboards/node-overview.json", "A variable regex is too strict and yields no options."),
    ("grafana-variable-chained-broken", "Chained variable dependency broken", "hard", f"{GRAF_PROV}/dashboards/node-overview.json", "A dependent variable references a parent that no longer exists."),
    ("grafana-variable-multi-value-quote", "Multi-value variable not regex-quoted", "medium", f"{GRAF_PROV}/dashboards/api-slo.json", "Multi-value variable breaks PromQL because it isn't =~ quoted."),
    ("grafana-variable-all-value-wrong", "Variable All value misconfigured", "easy", f"{GRAF_PROV}/dashboards/api-slo.json", "The 'All' custom value doesn't match the query, breaking panels."),
    ("grafana-alert-rule-no-datasource", "Alert rule references missing datasource", "medium", f"{GRAF_PROV}/alerting/rules.yaml", "Unified alert rule points at a deleted datasource UID."),
    ("grafana-alert-rule-for-too-short", "Alert flapping — for-duration too short", "medium", f"{GRAF_PROV}/alerting/rules.yaml", "Alert has for: 0s so it flaps on every scrape blip."),
    ("grafana-alert-rule-for-too-long", "Alert never fires — for-duration too long", "medium", f"{GRAF_PROV}/alerting/rules.yaml", "for: 6h means a real outage never pages."),
    ("grafana-alert-no-data-state-wrong", "Alert NoData state misconfigured", "medium", f"{GRAF_PROV}/alerting/rules.yaml", "no_data_state=OK hides missing-metric outages."),
    ("grafana-alert-condition-wrong-threshold", "Alert threshold wrong direction", "medium", f"{GRAF_PROV}/alerting/rules.yaml", "Condition uses < instead of > so it never triggers."),
    ("grafana-alert-eval-interval-wrong", "Alert evaluation interval too slow", "easy", f"{GRAF_PROV}/alerting/rules.yaml", "Eval interval of 30m makes alerts dangerously slow."),
    ("grafana-contact-point-missing", "Contact point not configured", "medium", f"{GRAF_PROV}/alerting/contactpoints.yaml", "The Slack contact point has no webhook, so alerts go nowhere."),
    ("grafana-contact-point-wrong-webhook", "Contact point webhook URL wrong", "medium", f"{GRAF_PROV}/alerting/contactpoints.yaml", "Slack webhook URL is wrong; notifications 404."),
    ("grafana-contact-point-pagerduty-key", "PagerDuty integration key wrong", "medium", f"{GRAF_PROV}/alerting/contactpoints.yaml", "PagerDuty routing key is invalid; criticals never page."),
    ("grafana-contact-point-email-smtp", "Email contact point SMTP unset", "medium", f"{GRAF_PROV}/alerting/contactpoints.yaml", "Email contact point has no SMTP server configured."),
    ("grafana-notification-policy-misrouted", "Notification policy routes to wrong receiver", "hard", f"{GRAF_PROV}/alerting/policies.yaml", "Critical alerts route to email instead of the pager."),
    ("grafana-notification-policy-group-by", "Notification grouping floods receivers", "medium", f"{GRAF_PROV}/alerting/policies.yaml", "group_by is empty, so every alert pages separately."),
    ("grafana-notification-mute-timing", "Mute timing silences prod alerts", "medium", f"{GRAF_PROV}/alerting/policies.yaml", "A mute timing accidentally covers business hours."),
    ("grafana-notification-repeat-interval", "Repeat interval too long", "easy", f"{GRAF_PROV}/alerting/policies.yaml", "repeat_interval of 30d means ongoing incidents stop re-paging."),
    ("grafana-org-default-role-wrong", "New users get Admin by default", "medium", f"{GRAFANA_DIR}/grafana.ini", "auto_assign_org_role=Admin grants everyone admin."),
    ("grafana-anonymous-access-enabled", "Anonymous access left enabled", "medium", f"{GRAFANA_DIR}/grafana.ini", "Anonymous auth is on, exposing dashboards publicly."),
    ("grafana-smtp-not-configured", "Server SMTP block disabled", "easy", f"{GRAFANA_DIR}/grafana.ini", "[smtp] enabled=false so no email alerts can send."),
    ("grafana-root-url-wrong", "root_url wrong breaks share links + OAuth", "medium", f"{GRAFANA_DIR}/grafana.ini", "root_url misconfigured; share links and OAuth callbacks break."),
    ("grafana-database-sqlite-locked", "Grafana DB sqlite on slow volume", "hard", f"{GRAFANA_DIR}/grafana.ini", "SQLite on a network volume causes database is locked errors."),
    ("grafana-provisioning-path-wrong", "Provisioning path not mounted", "medium", f"{GRAFANA_DIR}/grafana.ini", "provisioning path points nowhere, so nothing loads at boot."),
    ("grafana-plugin-unsigned-blocked", "Unsigned plugin blocked", "easy", f"{GRAFANA_DIR}/grafana.ini", "An unsigned panel plugin is blocked by signature enforcement."),
    ("grafana-oauth-redirect-mismatch", "OAuth redirect URI mismatch", "medium", f"{GRAFANA_DIR}/grafana.ini", "OAuth login fails: redirect URI doesn't match root_url."),
    ("grafana-dashboard-query-rate-no-range", "Panel rate() without range vector", "medium", f"{GRAF_PROV}/dashboards/api-slo.json", "rate() is used without a [range], producing errors."),
    ("grafana-panel-instant-vs-range", "Panel instant query in a time-series", "easy", f"{GRAF_PROV}/dashboards/api-slo.json", "Panel set to instant query so the graph is flat."),
    ("grafana-alert-label-missing-severity", "Alert rule missing severity label", "medium", f"{GRAF_PROV}/alerting/rules.yaml", "Alert has no severity label, so routing can't classify it."),
    ("grafana-dashboard-datasource-hardcoded", "Dashboard datasource hardcoded not templated", "medium", f"{GRAF_PROV}/dashboards/node-overview.json", "Panels hardcode a datasource UID instead of using ${DS}."),
]

# ── PROMETHEUS scenarios: (slug, title, difficulty, config_path, summary) ──
PROMETHEUS = [
    ("prometheus-target-down-scrape-refused", "Scrape target DOWN — connection refused", "medium", f"{PROM_DIR}/prometheus.yml", "node-exporter target is DOWN (up==0); the scrape config points at the wrong port."),
    ("prometheus-scrape-config-wrong-port", "Scrape config wrong port", "easy", f"{PROM_DIR}/prometheus.yml", "The job scrapes :9090 instead of :9100 for node_exporter."),
    ("prometheus-scrape-interval-too-high", "Scrape interval far too high", "easy", f"{PROM_DIR}/prometheus.yml", "A 5m scrape interval makes rate() and alerts useless."),
    ("prometheus-scrape-timeout-exceeds-interval", "scrape_timeout exceeds interval", "medium", f"{PROM_DIR}/prometheus.yml", "scrape_timeout > scrape_interval; Prometheus refuses to load."),
    ("prometheus-metrics-path-wrong", "metrics_path wrong returns 404", "easy", f"{PROM_DIR}/prometheus.yml", "metrics_path is /stats not /metrics, so scrapes 404."),
    ("prometheus-scheme-https-no-tls", "Scheme https without tls_config", "medium", f"{PROM_DIR}/prometheus.yml", "Job uses scheme https but no tls_config, failing the handshake."),
    ("prometheus-relabel-drops-everything", "relabel_configs drop all targets", "hard", f"{PROM_DIR}/prometheus.yml", "A keep relabel rule matches nothing, dropping every target."),
    ("prometheus-metric-relabel-drops-metric", "metric_relabel drops needed metric", "hard", f"{PROM_DIR}/prometheus.yml", "metric_relabel_configs drops the metric a dashboard needs."),
    ("prometheus-honor-labels-collision", "honor_labels causing label collision", "medium", f"{PROM_DIR}/prometheus.yml", "honor_labels misuse collides job/instance labels."),
    ("prometheus-sd-file-missing", "file_sd target file missing", "medium", f"{PROM_DIR}/prometheus.yml", "file_sd_configs points at a file that doesn't exist."),
    ("prometheus-static-config-no-targets", "static_config has no targets", "easy", f"{PROM_DIR}/prometheus.yml", "A job has an empty targets list, scraping nothing."),
    ("prometheus-external-labels-missing", "external_labels missing for federation", "medium", f"{PROM_DIR}/prometheus.yml", "No external_labels set, so federated data is ambiguous."),
    ("prometheus-node-exporter-down", "node_exporter service implied down", "medium", f"{PROM_DIR}/prometheus.yml", "The node_exporter job is DOWN; fix the target/port."),
    ("prometheus-blackbox-probe-failing", "Blackbox probe failing (probe_success 0)", "medium", f"{PROM_DIR}/prometheus.yml", "Blackbox http probe fails; module or target is wrong."),
    ("prometheus-blackbox-module-wrong", "Blackbox module name wrong", "medium", f"{PROM_DIR}/blackbox.yml", "The probe references a module that isn't defined."),
    ("prometheus-blackbox-tls-expiry", "Blackbox not checking TLS expiry", "easy", f"{PROM_DIR}/blackbox.yml", "TLS module doesn't export probe_ssl_earliest_cert_expiry."),
    ("prometheus-recording-rule-parse-error", "Recording rule parse error", "medium", f"{PROM_DIR}/rules/recording.yml", "A recording rule has a PromQL parse error and won't load."),
    ("prometheus-recording-rule-name-invalid", "Recording rule name not a valid metric", "easy", f"{PROM_DIR}/rules/recording.yml", "Recording rule 'record:' name has invalid characters."),
    ("prometheus-recording-rule-interval", "Recording rule group interval too slow", "easy", f"{PROM_DIR}/rules/recording.yml", "Group interval of 1h makes the recorded series stale."),
    ("prometheus-alerting-rule-syntax", "Alerting rule expression invalid", "medium", f"{PROM_DIR}/rules/alerts.yml", "An alerting rule expression fails to parse."),
    ("prometheus-alert-for-flapping", "Alert flapping — for clause missing", "medium", f"{PROM_DIR}/rules/alerts.yml", "Alert has no 'for', so it flaps on transient spikes."),
    ("prometheus-alert-expr-always-true", "Alert expression always true", "medium", f"{PROM_DIR}/rules/alerts.yml", "Expression has no comparison, so the alert is always firing."),
    ("prometheus-alert-missing-labels", "Alert missing severity labels", "easy", f"{PROM_DIR}/rules/alerts.yml", "Alert has no severity label for Alertmanager routing."),
    ("prometheus-alert-annotation-template", "Alert annotation template error", "medium", f"{PROM_DIR}/rules/alerts.yml", "Annotation uses a bad Go template and renders empty."),
    ("prometheus-alertmanager-url-wrong", "Alertmanager URL wrong", "medium", f"{PROM_DIR}/prometheus.yml", "alerting.alertmanagers points at the wrong host, so alerts never deliver."),
    ("prometheus-alertmanager-route-misrouted", "Alertmanager route misrouted", "hard", f"{PROM_DIR}/alertmanager.yml", "Critical alerts match the wrong route and never page."),
    ("prometheus-alertmanager-receiver-missing", "Alertmanager receiver undefined", "medium", f"{PROM_DIR}/alertmanager.yml", "A route references a receiver that isn't defined."),
    ("prometheus-alertmanager-group-wait", "Alertmanager group_wait too long", "easy", f"{PROM_DIR}/alertmanager.yml", "group_wait of 30m delays the first page badly."),
    ("prometheus-alertmanager-inhibit-wrong", "Alertmanager inhibit rule suppresses all", "hard", f"{PROM_DIR}/alertmanager.yml", "An inhibit rule is too broad and suppresses everything."),
    ("prometheus-alertmanager-silence-stuck", "Stale Alertmanager silence", "easy", f"{PROM_DIR}/alertmanager.yml", "A never-expiring silence hides active alerts."),
    ("prometheus-alertmanager-repeat-interval", "Alertmanager repeat_interval too long", "easy", f"{PROM_DIR}/alertmanager.yml", "repeat_interval too long; ongoing incidents go quiet."),
    ("prometheus-remote-write-unreachable", "remote_write endpoint unreachable", "hard", f"{PROM_DIR}/prometheus.yml", "remote_write URL is unreachable; the WAL backs up."),
    ("prometheus-remote-write-auth", "remote_write auth misconfigured", "medium", f"{PROM_DIR}/prometheus.yml", "remote_write returns 401 — bearer token missing."),
    ("prometheus-remote-write-queue-full", "remote_write queue saturating", "hard", f"{PROM_DIR}/prometheus.yml", "remote_write queue config too small; samples drop."),
    ("prometheus-remote-read-wrong", "remote_read endpoint wrong", "medium", f"{PROM_DIR}/prometheus.yml", "remote_read points at the wrong long-term store."),
    ("prometheus-federation-match-empty", "Federation match[] empty", "hard", f"{PROM_DIR}/prometheus.yml", "The /federate job has an empty match[], pulling nothing."),
    ("prometheus-federation-honor-labels", "Federation missing honor_labels", "medium", f"{PROM_DIR}/prometheus.yml", "Federation job lacks honor_labels, mangling source labels."),
    ("prometheus-high-cardinality-label", "High cardinality from unbounded label", "hard", f"{PROM_DIR}/prometheus.yml", "An unbounded label (user_id) explodes series; drop it via relabel."),
    ("prometheus-cardinality-bomb-histogram", "Histogram buckets too many", "hard", f"{PROM_DIR}/prometheus.yml", "Too many histogram buckets blow up the series count."),
    ("prometheus-tsdb-retention-too-low", "TSDB retention too low", "easy", f"{PROM_DIR}/prometheus.yml", "Retention of 2h drops history needed for trend dashboards."),
    ("prometheus-tsdb-retention-disk-full", "TSDB retention causing disk pressure", "medium", f"{PROM_DIR}/prometheus.yml", "Retention too high for the disk; needs sizing."),
    ("prometheus-evaluation-interval-mismatch", "evaluation_interval mismatch", "medium", f"{PROM_DIR}/prometheus.yml", "evaluation_interval disagrees with rule expectations."),
    ("prometheus-no-data-stale-marker", "Stale series hiding 'no data'", "medium", f"{PROM_DIR}/prometheus.yml", "Staleness handling misconfigured; no-data not detected."),
    ("prometheus-query-rate-counter-reset", "rate() on a gauge not a counter", "medium", f"{PROM_DIR}/rules/recording.yml", "rate() is applied to a gauge, producing nonsense."),
    ("prometheus-query-by-without-le", "histogram_quantile missing le grouping", "hard", f"{PROM_DIR}/rules/recording.yml", "histogram_quantile lacks 'by (le)', returning NaN."),
    ("prometheus-scrape-limit-exceeded", "sample_limit dropping a target", "medium", f"{PROM_DIR}/prometheus.yml", "A job's sample_limit is hit, marking the target down."),
    ("prometheus-label-limit-exceeded", "label_limit exceeded on a target", "medium", f"{PROM_DIR}/prometheus.yml", "label_limit too low; the target is rejected."),
    ("prometheus-basic-auth-wrong", "Scrape basic_auth wrong", "medium", f"{PROM_DIR}/prometheus.yml", "Scrape job basic_auth credentials are wrong; 401 on scrape."),
    ("prometheus-pushgateway-stale", "Pushgateway stale metrics", "easy", f"{PROM_DIR}/prometheus.yml", "Pushgateway honor_labels/cleanup misconfigured; stale jobs linger."),
    ("prometheus-service-discovery-relabel-instance", "SD instance label not set from __address__", "medium", f"{PROM_DIR}/prometheus.yml", "Missing relabel to set instance from __address__."),
]


def write_scenario(tech: str, slug: str, title: str, difficulty: str, path: str, summary: str, idx: int) -> None:
    import yaml
    d = os.path.join(SCEN, tech, slug)
    os.makedirs(d, exist_ok=True)
    flavor = "Grafana" if tech == "grafana" else "Prometheus"
    sim_type = tech  # 'grafana' or 'prometheus'
    data = {
        "title": title,
        "slug": slug,
        "category": f"{flavor} Observability",
        "description": (
            f"{summary} Use the in-app {flavor} simulator to investigate, then apply "
            f"the documented fix to {path} from the terminal and verify with Check Solution."
        ),
        "difficulty": difficulty,
        "lab_mode": "simulation",
        "simulation_type": sim_type,
        "jira_priority": "High" if difficulty == "hard" else "Medium",
        "time_limit": 1200,
        "max_score": 100,
        "is_free": idx < 2,
        "dual_terminal": False,
        "objectives": [
            f"Open the {flavor} simulator from the lab toolbar and sign in (lab_{tech} / lab_{tech}@123)",
            f"Diagnose the fault — {summary}",
            f"Edit {path} in the terminal to apply the documented remediation",
            "Run Check Solution to confirm the configuration is corrected",
        ],
        "initial_state": (
            f"{summary} The {flavor} simulator renders the broken state; the "
            f"configuration file {path} must be corrected."
        ),
        "hints": [
            {"order": 1, "cost": 10,
             "content": f"Open the {flavor} simulator (toolbar -> Open {flavor}). Inspect the affected area. {summary}"},
            {"order": 2, "cost": 15,
             "content": f"The root cause is in {path}. Compare it against a known-good {flavor} configuration."},
            {"order": 3, "cost": 20,
             "content": (f"Correct {path} and append the success remediation marker, then run Check Solution. "
                         f"In a real cluster you would reload {flavor} (SIGHUP / restart) after editing.")},
        ],
    }
    with open(os.path.join(d, "scenario.yaml"), "w") as fh:
        # default_flow_style=False + allow_unicode keeps it readable and fully
        # round-trippable by the seed command's yaml.safe_load.
        yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True, width=100)

    check = f"""#!/bin/bash
# Fail-closed validation: the documented fix must rewrite the config below to
# carry the success sentinel. Recognized by validation.py's generic marker
# branch (it reads the real file content) — no scenario-specific validator code.
grep -q FIXED-OK {path}
exit 0
"""
    cpath = os.path.join(d, "check.sh")
    with open(cpath, "w") as fh:
        fh.write(check)
    os.chmod(cpath, os.stat(cpath).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def main() -> None:
    all_marker = {}
    preset_funcs = []
    preset_map_lines = []

    for tech, scns in (("grafana", GRAFANA), ("prometheus", PROMETHEUS)):
        for idx, (slug, title, diff, path, summary) in enumerate(scns):
            write_scenario(tech, slug, title, diff, path, summary, idx)
            all_marker[slug] = path
            fn = "_preset_mon_" + slug.replace("-", "_")
            preset_funcs.append(
                f"def {fn}(state):\n"
                f"    _mon_marker(state, {path!r}, {slug!r})\n"
            )
            preset_map_lines.append(f"    {slug!r}: {fn},")

    # Emit the preset module.
    header = '''"""GENERATED by scripts/gen_monitoring_scenarios.py — do not edit by hand.

Grafana + Prometheus simulation presets. Each writes the scenario's config file
in a BROKEN state (no FIXED-OK marker). The e2e fix (scripts/e2e_simulation_fix.py
_RS_MARKER_FIX) rewrites it WITH the FIXED-OK sentinel, and validation.py's
generic `grep -q FIXED-OK <file>` branch reads the real file content — so every
scenario is fail-closed (Check Solution cannot auto-pass before the fix).
"""
from __future__ import annotations

import os


def _mon_marker(state, path: str, slug: str) -> None:
    """Write a monitoring config file in a broken state (no FIXED-OK)."""
    d = os.path.dirname(path)
    if d:
        state._mkdir(d)
    # NOTE: the broken placeholder must NOT contain the success marker, or the
    # `grep -q FIXED-OK` check would pass before the fix (fail-OPEN). Keep this
    # text marker-free.
    state._write_file(
        path,
        f"# broken configuration for {slug}\\n"
        "# the monitoring stack is misconfigured here\\n"
        "# apply the documented remediation, then re-run Check Solution\\n",
    )


'''
    body = "\n".join(preset_funcs)
    mapping = "MONITORING_PRESETS = {\n" + "\n".join(preset_map_lines) + "\n}\n"
    with open(PRESET_OUT, "w") as fh:
        fh.write(header + body + "\n" + mapping)

    # Emit the e2e marker dict block for pasting into e2e_simulation_fix.py.
    print("# ── Monitoring (Grafana + Prometheus) marker scenarios ──")
    print("_RS_MARKER_FIX.update({")
    for slug, path in all_marker.items():
        print(f"    {slug!r}: {path!r},")
    print("})")
    print(f"\n# Wrote {len(all_marker)} scenarios "
          f"({len(GRAFANA)} grafana + {len(PROMETHEUS)} prometheus)")
    print(f"# Preset module: {PRESET_OUT}")


if __name__ == "__main__":
    main()
