#!/usr/bin/env python3
"""DEPRECATED: shallow single-page tutorials — use course_catalog.py instead.

Regenerating this file is no longer recommended. Full 10-module courses with
19 sections each are built programmatically via seed_tutorials → course_catalog.
"""
import json
import os

OUT = os.path.join(
    os.path.dirname(__file__),
    "..",
    "backend",
    "apps",
    "tutorials",
    "management",
    "commands",
    "data",
    "tutorials_e3_batch3.json",
)

SPECS = [
    ("vmware-zero-to-hero", "VMware vSphere: Zero to Hero", "VMware", "intermediate", 55, "vmware", 310, [
        ("vSphere architecture", "ESXi hosts run VMs; vCenter is the management plane. Clusters enable HA/DRS; datastores hold VMDKs; port groups connect VMs to VLANs.", "", "text", ""),
        ("Inventory navigation", "Datacenter → cluster → host → VM. Use the simulator inventory tree to power VMs, open consoles, and run wizards.", "", "text", "Open VMware from the lab toolbar."),
        ("Create a VM", "New Virtual Machine wizard: name, compute, storage, guest OS, hardware. Finish and verify in inventory.", "", "text", ""),
        ("Networking", "Standard vSwitch vs distributed switch. VMkernel ports for management/vMotion. MTU 9000 for storage.", "", "text", ""),
        ("Storage and snapshots", "Thin vs thick provisioning. Snapshots are not backups — consolidate chains regularly.", "", "text", ""),
        ("HA and DRS", "Admission control prevents overcommit. DRS balances load; affinity rules pin GPU workloads.", "", "text", ""),
        ("Troubleshooting", "Host disconnected → check management network. VM question pending → answer in vCenter. Tools outdated → upgrade open-vm-tools.", "", "text", ""),
    ]),
    ("grafana-zero-to-hero", "Grafana Observability: Zero to Hero", "Grafana", "beginner", 45, "grafana", 311, [
        ("Observability stack", "Metrics (Prometheus), logs (Loki), traces (Tempo). Grafana unifies visualization and alerting.", "", "text", ""),
        ("Datasources", "Prometheus is the default metrics backend. Verify URL, auth, and scrape health before building dashboards.", "", "text", ""),
        ("Dashboards and panels", "Time series, gauges, stat panels. Template variables filter by job, instance, or cluster.", "", "text", ""),
        ("Explore and PromQL", "Ad-hoc queries in Explore. rate(), histogram_quantile(), and label matchers are daily tools.", "rate(http_requests_total[5m])", "bash", ""),
        ("Alerting", "Alert rules → contact points → notification policies. Reduce noise with grouping and inhibition.", "", "text", ""),
        ("On-call workflow", "Silences for maintenance. Runbooks linked from annotations. FixitLab sim grades via terminal markers.", "", "text", ""),
    ]),
    ("prometheus-zero-to-hero", "Prometheus Monitoring: Zero to Hero", "Prometheus", "intermediate", 50, "prometheus", 312, [
        ("Pull model", "Prometheus scrapes /metrics on an interval. Pushgateway is for batch jobs only.", "", "text", ""),
        ("Targets and SD", "Targets page shows UP/DOWN. relabel_configs drop high-cardinality labels.", "", "text", ""),
        ("PromQL essentials", "Instant vs range vectors. rate() for counters; increase() for spikes.", "up{job=\"node\"}", "bash", ""),
        ("Recording rules", "Pre-aggregate expensive queries. alert rules fire on thresholds.", "", "text", ""),
        ("Alertmanager", "Routes by severity/team. inhibit_rules suppress duplicates.", "", "text", ""),
        ("Cross-tech scraping", "VMware-created hosts appear as node targets when lab_hosts is wired.", "", "text", ""),
    ]),
    ("terraform-aws-zero-to-hero", "Terraform & AWS CLI: Zero to Hero", "Terraform", "intermediate", 50, "terraform", 313, [
        ("IaC workflow", "Write HCL → terraform init → plan → apply. State tracks real infrastructure.", "", "text", ""),
        ("Providers and modules", "Pin provider versions. Modules encapsulate VPC, EKS, S3 patterns.", "", "text", ""),
        ("AWS CLI basics", "aws sts get-caller-identity, aws s3 ls, aws ec2 describe-instances for verification.", "aws sts get-caller-identity", "bash", ""),
        ("State and locking", "S3 backend + DynamoDB lock. force-unlock only when no active apply.", "", "text", ""),
        ("Drift and import", "terraform plan shows drift. import brings existing resources under management.", "", "text", ""),
        ("FixitLab simulator", "Open Terraform from the lab toolbar for init/plan/apply and AWS CLI mock.", "", "text", ""),
    ]),
    ("ansible-awx-zero-to-hero", "Ansible AWX / Tower: Zero to Hero", "Ansible", "intermediate", 45, "ansible", 314, [
        ("AWX vs Ansible CLI", "AWX adds RBAC, schedules, surveys, and centralized credentials over ansible-playbook.", "", "text", ""),
        ("Projects and SCM", "Git projects sync playbooks. Failed sync blocks templates.", "", "text", ""),
        ("Inventories", "Static, constructed, or sourced from cloud. Groups and host vars drive targeting.", "", "text", ""),
        ("Job templates", "Link playbook + inventory + credentials + limits. Launch with extra vars.", "", "text", ""),
        ("Credentials", "Machine, Vault, cloud credentials. Never commit secrets to Git.", "", "text", ""),
        ("Operator install", "AWX operator on Kubernetes. Verify web UI and run first template.", "", "text", ""),
    ]),
    ("nmap-security-zero-to-hero", "Nmap Network Scanning: Zero to Hero", "Nmap", "beginner", 40, "nmap", 315, [
        ("Scan types", "SYN (-sS), connect (-sT), UDP (-sU). Privileged SYN is default on Linux.", "nmap -sS -p 22,80,443 target", "bash", ""),
        ("Service detection", "-sV fingerprints versions. -O guesses OS (noisy).", "nmap -sV -p 80 target", "bash", ""),
        ("Scripts (NSE)", "--script vuln,default,safe. Understand legal scope before scanning.", "nmap --script http-title target", "bash", ""),
        ("Output", "-oN normal, -oX XML, -oG grepable. Parse with ndiff for baselines.", "", "text", ""),
        ("Firewall evasion", "Fragmentation, decoys, timing (-T0..T5). Lab sim models filtered ports.", "", "text", ""),
        ("Reporting", "Document open ports, service versions, and remediation priority.", "", "text", ""),
    ]),
    ("wireshark-zero-to-hero", "Wireshark Packet Analysis: Zero to Hero", "Wireshark", "intermediate", 45, "wireshark", 316, [
        ("Capture basics", "Promiscuous mode, snaplen, ring buffer. Filter during capture to reduce noise.", "", "text", ""),
        ("Display filters", "tcp.port == 443 and ip.addr == 10.0.0.5 — not the same as capture filters.", "tcp.flags.syn == 1", "bash", ""),
        ("Follow streams", "TCP/HTTP/TLS follow reconstructs conversations. Export objects from HTTP.", "", "text", ""),
        ("TLS", "Decrypt with pre-master secret or key log from browser. Without keys, see only metadata.", "", "text", ""),
        ("Troubleshooting", "Retransmissions, zero window, DNS failures. io.stat and Expert Info guide triage.", "", "text", ""),
        ("Lab simulator", "Open Wireshark from the lab toolbar for display filters and follow-stream drills.", "", "text", ""),
    ]),
    ("windows-server-zero-to-hero", "Windows Server: Zero to Hero", "Windows", "intermediate", 50, "windows", 317, [
        ("Server Manager", "Roles and features, local server summary, remote management.", "", "text", ""),
        ("Active Directory", "DC promotion, DNS integration, OU structure, GPO basics.", "", "text", ""),
        ("Services and updates", "Windows Update policies. Critical services: DNS, DHCP, AD DS.", "", "text", ""),
        ("PowerShell remoting", "WinRM, Enter-PSSession, Invoke-Command for automation.", "Get-Service | Where Status -eq Stopped", "bash", ""),
        ("GUI sim labs", "win-gui-* scenarios open Server Manager simulator from the lab toolbar.", "", "text", ""),
        ("Hybrid with Linux", "Cross-tech labs pair Windows GUI steps with Linux terminal fixes.", "", "text", ""),
    ]),
    ("rhel-linux-zero-to-hero", "RHEL Linux Administration: Zero to Hero", "RHEL", "beginner", 50, "rhel-linux", 318, [
        ("Systemd", "systemctl start/stop/enable. journalctl -u service for logs.", "systemctl status sshd", "bash", ""),
        ("Package management", "dnf install, dnf history rollback, subscription-manager for RHEL.", "dnf install -y httpd", "bash", ""),
        ("SELinux", "getenforce, setsebool, audit2allow. Most 'permission denied' on RHEL is SELinux.", "getenforce", "bash", ""),
        ("Firewalld", "firewall-cmd --add-service --permanent. Zones map to interfaces.", "", "text", ""),
        ("LVM and storage", "pvcreate, vgcreate, lvcreate, xfs_growfs for online expand.", "", "text", ""),
        ("Boot and rescue", "dracut, grubby, single-user mode, initramfs rebuild after driver changes.", "", "text", ""),
    ]),
    ("java-zero-to-hero", "Java Development: Zero to Hero", "Java", "beginner", 45, "java", 319, [
        ("JDK vs JRE", "JDK compiles; JRE runs. Use LTS releases (17, 21) in production.", "", "text", ""),
        ("Build tools", "Maven pom.xml lifecycle; Gradle for flexible builds.", "mvn -q test", "bash", ""),
        ("Spring Boot", "Auto-configuration, actuator health, embedded Tomcat.", "", "text", ""),
        ("JVM tuning", "-Xms/-Xmx, G1GC, heap dumps with jcmd/jmap.", "", "text", ""),
        ("Containers", "Distroless or slim JRE images. Respect cgroup memory limits.", "", "text", ""),
        ("Coding labs", "FixitLab Java scenarios use the browser IDE with server-side grading.", "", "text", ""),
    ]),
    ("javascript-zero-to-hero", "JavaScript & Node.js: Zero to Hero", "JavaScript", "beginner", 45, "javascript", 320, [
        ("Language core", "let/const, async/await, modules ESM vs CJS.", "", "text", ""),
        ("Node.js runtime", "event loop, fs/promises, npm scripts, npx.", "node --version", "bash", ""),
        ("Express APIs", "Routing, middleware, error handlers, JSON body parser.", "", "text", ""),
        ("Testing", "Jest or Vitest unit tests; supertest for HTTP.", "npm test", "bash", ""),
        ("Security", "Validate input, helmet, rate limits, never eval user data.", "", "text", ""),
        ("Browser IDE", "JS coding labs run in a Web Worker sandbox with visible + hidden tests.", "", "text", ""),
    ]),
    ("html-css-zero-to-hero", "HTML & Web Frontend: Zero to Hero", "HTML", "beginner", 40, "html", 321, [
        ("Semantic HTML", "header, nav, main, article improve a11y and SEO.", "", "text", ""),
        ("Forms and validation", "required, pattern, accessible labels.", "", "text", ""),
        ("CSS layout", "Flexbox for components; Grid for page layout.", "", "text", ""),
        ("Responsive design", "Mobile-first media queries; rem units.", "", "text", ""),
        ("React bridge", "Components, props, state, hooks — see React tutorial for SPA depth.", "", "text", ""),
        ("Lab scenarios", "Fix broken pages in simulation labs using curl and browser devtools.", "", "text", ""),
    ]),
    ("peoplesoft-zero-to-hero", "PeopleSoft Administration: Zero to Hero", "PeopleSoft", "advanced", 55, "peoplesoft", 322, [
        ("PIA and app server", "Web profile, Jolt pool, domain connection. Open PeopleSoft from lab toolbar.", "", "text", ""),
        ("Process Scheduler", "Jobs, job sets, distribution lists, recurrence.", "", "text", ""),
        ("Security", "Roles, permission lists, row-level security, sign-on PeopleCode.", "", "text", ""),
        ("Integration Broker", "Service operations, REST/SOAP, handling errors.", "", "text", ""),
        ("Troubleshooting", "Check App Server logs, clear cache, bounce PIA domain.", "", "text", ""),
        ("Upgrades", "Image copy, compare reports, data mover scripts.", "", "text", ""),
    ]),
    ("prompt-engineering-zero-to-hero", "Prompt Engineering: Zero to Hero", "AI", "beginner", 40, "prompt-engineering", 323, [
        ("Prompt structure", "Role, task, context, format, constraints. Few-shot examples beat vague instructions.", "", "text", ""),
        ("Chain of thought", "Ask the model to reason step-by-step for math and logic.", "", "text", ""),
        ("Tool use", "Function calling and JSON mode for structured outputs.", "", "text", ""),
        ("Evaluation", "Golden sets, rubrics, regression on prompt changes.", "", "text", ""),
        ("Safety", "System prompts, output filters, PII redaction.", "", "text", ""),
        ("Playground labs", "Prompt engineering scenarios open the Prompt Playground surface.", "", "text", ""),
    ]),
    ("database-sql-zero-to-hero", "Database Engineering: Zero to Hero", "Database", "intermediate", 50, "postgresql", 324, [
        ("Relational model", "Normalization, keys, indexes, transactions ACID.", "", "text", ""),
        ("PostgreSQL", "EXPLAIN ANALYZE, vacuum, connection pooling with PgBouncer.", "EXPLAIN ANALYZE SELECT ...", "bash", ""),
        ("MySQL", "InnoDB, replication, slow query log.", "", "text", ""),
        ("SQLite", "Embedded, WAL mode, single-writer limits.", "", "text", ""),
        ("Backups", "pg_dump, PITR, restore drills.", "", "text", ""),
        ("Lab paths", "Dedicated mysql, postgresql, sqlite technology labs with Docker sim.", "", "text", ""),
    ]),
    ("simulation-engine-zero-to-hero", "FixitLab Simulation Engine: Zero to Hero", "Simulation", "beginner", 35, "simulation", 325, [
        ("What is simulated", "RHEL personas, file markers, and GUI overlays replace real cloud for training.", "", "text", ""),
        ("Terminal vs GUI", "Some labs use terminal only; others open VMware, Grafana, AWX, or Terraform UIs.", "", "text", ""),
        ("Validation", "check.sh greps FIXED-OK markers — fixes must match scenario recipe.", "", "text", ""),
        ("Cross-technology", "vmware_link scenarios share session state across terminal and GUI.", "", "text", ""),
        ("Hints and scoring", "Hints cost points. Check validates server-side.", "", "text", ""),
        ("Best practices", "Read objectives, use Open * toolbar buttons, then verify with Check.", "", "text", ""),
    ]),
]


def main():
    tutorials = []
    for slug, title, topic, diff, mins, pg, order, sections in SPECS:
        tutorials.append({
            "slug": slug,
            "title": title,
            "summary": title.split(": ", 1)[-1] + " — complete training path from fundamentals to production.",
            "topic": topic,
            "difficulty": diff,
            "estimated_minutes": mins,
            "playground_slug": pg,
            "order": order,
            "sections": sections,
        })
    path = os.path.abspath(OUT)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(tutorials, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote {len(tutorials)} tutorials to {path}")


if __name__ == "__main__":
    main()
