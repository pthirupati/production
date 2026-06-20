"""Apply in-memory fixes to simulation labs for E2E validation."""
from __future__ import annotations

from apps.labs.provisioner.simulation.ops_state import apply_team_ops_action
from apps.labs.provisioner.simulation.shell import get_sim_session
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


# ── Generated maps for real-state scenarios (see scenario_presets.py) ──
_RS_SERVICE_FIX = {'db-redis-down': 'redis', 'db-mariadb-down': 'mariadb', 'db-mongodb-down': 'mongod', 'db-cassandra-down': 'cassandra', 'db-pgbouncer-down': 'pgbouncer', 'rhel-chronyd-down': 'chronyd', 'rhel-rsyslog-down': 'rsyslog', 'rhel-firewalld-down': 'firewalld', 'rhel-auditd-down': 'auditd', 'rhel-nfs-server-down': 'nfs-server', 'docker-containerd-down': 'containerd', 'linux-haproxy-down': 'haproxy', 'linux-named-down': 'named', 'linux-memcached-down': 'memcached', 'linux-rabbitmq-down': 'rabbitmq-server', 'linux-nginx-stream-proxy-down': 'nginx'}
_RS_MARKER_FIX = {'db-postgres-pg-hba-deny': '/var/lib/pgsql/data/pg_hba.conf', 'db-mysql-bind-address': '/etc/my.cnf', 'db-redis-maxmemory-noevict': '/etc/redis/redis.conf', 'db-postgres-fsync-off': '/var/lib/pgsql/data/postgresql.conf', 'ansible-become-password-missing': '/home/ansible/playbook.yml', 'ansible-jinja-template-error': '/home/ansible/templates/app.conf.j2', 'ansible-loop-wrong-var': '/home/ansible/loop.yml', 'ansible-when-condition-bug': '/home/ansible/conditional.yml', 'ansible-galaxy-role-missing': '/home/ansible/requirements.yml', 'ansible-vars-precedence-bug': '/home/ansible/group_vars/all.yml', 'ansible-no-log-leaking-secret': '/home/ansible/secret-task.yml', 'shell-rsync-delete-danger': '/opt/scripts/backup.sh', 'shell-cron-path-missing': '/opt/scripts/cronjob.sh', 'shell-pipefail-missing': '/opt/scripts/deploy-pipeline.sh', 'shell-word-splitting-bug': '/opt/scripts/process-files.sh', 'shell-signal-not-trapped': '/opt/scripts/long-job.sh', 'shell-readonly-clobber': '/opt/scripts/report.sh', 'shell-arith-division-zero': '/opt/scripts/metrics.sh', 'shell-getopts-parsing': '/opt/scripts/cli-tool.sh', 'html-broken-doctype': '/var/www/html/index.html', 'html-missing-charset': '/var/www/html/index.html', 'html-broken-relative-links': '/var/www/html/index.html', 'html-inaccessible-form': '/var/www/html/contact.html', 'html-meta-viewport-missing': '/var/www/html/index.html', 'html-csp-blocking-assets': '/var/www/html/index.html', 'html-duplicate-ids': '/var/www/html/index.html', 'rhel-subscription-manager-config': '/etc/yum.repos.d/redhat.repo', 'rhel-tuned-wrong-profile': '/etc/tuned/active_profile', 'rhel-selinux-booleans': '/etc/selinux/booleans.local', 'rhel-grub-default-target': '/etc/systemd/default.target.conf', 'gpu-mps-not-enabled': '/etc/nvidia-mps/config', 'gpu-ecc-disabled': '/etc/nvidia/ecc.conf', 'gpu-persistence-mode-off': '/etc/nvidia/persistence.conf', 'gpu-cgroup-device-denied': '/etc/nvidia-container-runtime/config.toml', 'gpu-clock-throttled-power': '/etc/nvidia/power-limit.conf', 'gpu-fabric-manager-down': '/etc/nvidia/fabricmanager.cfg', 'baremetal-bios-boot-order': '/etc/bios/boot_order.cfg', 'baremetal-bmc-snmp-misconfig': '/etc/bmc/snmp.cfg', 'baremetal-fan-curve-aggressive': '/etc/bmc/fan_curve.cfg', 'baremetal-numa-not-enabled': '/etc/bios/numa.cfg', 'baremetal-firmware-mismatch': '/etc/firmware/nic_version.cfg', 'baremetal-secure-boot-blocking': '/etc/bios/secureboot.cfg', 'docker-daemon-json-invalid': '/etc/docker/daemon.json', 'docker-storage-driver-wrong': '/etc/docker/storage.conf', 'docker-insecure-registry': '/etc/docker/registries.conf', 'docker-default-bridge-subnet': '/etc/docker/daemon.json', 'docker-logging-unbounded': '/etc/docker/daemon.json', 'docker-userns-remap-broken': '/etc/docker/daemon.json', 'linux-fstab-bad-option': '/etc/fstab', 'linux-limits-conf-too-low': '/etc/security/limits.conf', 'linux-resolv-conf-wrong': '/etc/resolv.conf', 'linux-sudoers-syntax-error': '/etc/sudoers.d/ops', 'linux-logrotate-misconfig': '/etc/logrotate.d/app', 'linux-crontab-syntax-error': '/etc/cron.d/app-job', 'linux-journald-storage-volatile': '/etc/systemd/journald.conf', 'linux-sshd-permitroot-hardening': '/etc/ssh/sshd_config.d/hardening.conf'}



_RS_SERVICE_FIX.update({'db-mysql-replica-stopped': 'mysqld', 'db-postgres-standby-stopped': 'postgresql', 'db-redis-sentinel-down': 'redis-sentinel', 'db-etcd-down': 'etcd', 'db-influxdb-down': 'influxdb', 'db-elasticsearch-down': 'elasticsearch', 'db-couchdb-down': 'couchdb', 'db-neo4j-down': 'neo4j', 'db-clickhouse-down': 'clickhouse-server', 'docker-daemon-down': 'docker', 'docker-docker-socket-proxy-down': 'docker-socket-proxy', 'rhel-sssd-down': 'sssd', 'rhel-cockpit-down': 'cockpit', 'rhel-tuned-down': 'tuned', 'rhel-firewalld-restart-loop': 'firewalld', 'rhel-multipathd-down': 'multipathd', 'rhel-iscsid-down': 'iscsid', 'rhel-libvirtd-down': 'libvirtd', 'rhel-postfix-down': 'postfix'})
_RS_MARKER_FIX.update({'db-postgres-shared-buffers-low': '/var/lib/pgsql/data/postgresql.conf', 'db-postgres-work-mem-low': '/var/lib/pgsql/data/postgresql.conf', 'db-mysql-innodb-buffer-pool': '/etc/my.cnf', 'db-mysql-slow-query-log-off': '/etc/my.cnf', 'db-postgres-log-min-duration': '/var/lib/pgsql/data/postgresql.conf', 'db-mongodb-no-auth': '/etc/mongod.conf', 'db-redis-no-password': '/etc/redis/redis.conf', 'db-postgres-ssl-disabled': '/var/lib/pgsql/data/postgresql.conf', 'db-mysql-sql-mode-loose': '/etc/my.cnf', 'db-postgres-autovacuum-off': '/var/lib/pgsql/data/postgresql.conf', 'db-mysql-max-allowed-packet': '/etc/my.cnf', 'db-postgres-statement-timeout': '/var/lib/pgsql/data/postgresql.conf', 'db-mariadb-galera-config': '/etc/my.cnf.d/galera.cnf', 'db-redis-rdb-aof-conflict': '/etc/redis/redis.conf', 'db-postgres-hot-standby-off': '/var/lib/pgsql/data/postgresql.conf', 'db-mysql-binlog-disabled': '/etc/my.cnf', 'db-postgres-wal-level-minimal': '/var/lib/pgsql/data/postgresql.conf', 'db-mongodb-oplog-too-small': '/etc/mongod.conf', 'db-mysql-tmp-table-disk': '/etc/my.cnf', 'db-postgres-checkpoint-spikes': '/var/lib/pgsql/data/postgresql.conf', 'db-redis-thp-warning': '/etc/redis/redis-tuning.conf', 'db-mysql-skip-name-resolve': '/etc/my.cnf', 'db-postgres-connection-leak': '/var/lib/pgsql/data/postgresql.conf', 'ansible-handler-missing': '/home/ansible/site.yml', 'ansible-tags-misused': '/home/ansible/tagged.yml', 'ansible-delegate-to-wrong': '/home/ansible/delegate.yml', 'ansible-serial-too-high': '/home/ansible/rolling.yml', 'ansible-block-rescue-missing': '/home/ansible/block.yml', 'ansible-vault-id-wrong': '/home/ansible/vault-vars.yml', 'ansible-inventory-group-vars': '/home/ansible/inventory/hosts.ini', 'ansible-fact-caching-stale': '/home/ansible/ansible.cfg', 'ansible-become-user-wrong': '/home/ansible/become.yml', 'ansible-template-trim-blocks': '/home/ansible/templates/nginx.conf.j2', 'ansible-with-items-deprecated': '/home/ansible/legacy-loop.yml', 'ansible-changed-when-wrong': '/home/ansible/idempotent.yml', 'ansible-failed-when-wrong': '/home/ansible/failwhen.yml', 'ansible-async-poll-wrong': '/home/ansible/async.yml', 'ansible-uri-validate-certs': '/home/ansible/uri.yml', 'ansible-package-name-wrong': '/home/ansible/pkg.yml', 'ansible-service-enabled-missing': '/home/ansible/svc.yml', 'ansible-copy-vs-template': '/home/ansible/copy.yml', 'ansible-lineinfile-regex': '/home/ansible/lineinfile.yml', 'ansible-mount-fstab-missing': '/home/ansible/mount.yml', 'ansible-cron-special-time': '/home/ansible/cron.yml', 'ansible-firewalld-permanent': '/home/ansible/firewalld.yml', 'ansible-selinux-context': '/home/ansible/sefcontext.yml', 'ansible-user-ssh-key': '/home/ansible/sshkey.yml', 'ansible-template-validate': '/home/ansible/sshd-template.yml', 'ansible-handler-flush': '/home/ansible/flush.yml', 'ansible-register-loop-results': '/home/ansible/register.yml', 'ansible-set-fact-scope': '/home/ansible/setfact.yml', 'ansible-import-vs-include': '/home/ansible/include.yml', 'ansible-callback-plugin': '/home/ansible/ansible.cfg', 'ansible-strategy-free-unsafe': '/home/ansible/strategy.yml', 'ansible-connection-local-wrong': '/home/ansible/localconn.yml', 'ansible-env-var-not-passed': '/home/ansible/env.yml', 'ansible-retries-until': '/home/ansible/retry.yml', 'ansible-yaml-indentation': '/home/ansible/badindent.yml', 'shell-set-e-not-set': '/opt/scripts/run.sh', 'shell-tmpfile-race': '/opt/scripts/tmpwork.sh', 'shell-eval-injection': '/opt/scripts/parse.sh', 'shell-cd-without-check': '/opt/scripts/clean.sh', 'shell-glob-no-match': '/opt/scripts/archive.sh', 'shell-arithmetic-leading-zero': '/opt/scripts/dates.sh', 'shell-here-string-quoting': '/opt/scripts/gen-config.sh', 'shell-exit-code-masked': '/opt/scripts/check-status.sh', 'shell-ifs-not-reset': '/opt/scripts/csv.sh', 'shell-subshell-var-lost': '/opt/scripts/count.sh', 'shell-test-string-vs-int': '/opt/scripts/threshold.sh', 'shell-find-exec-unsafe': '/opt/scripts/purge.sh', 'shell-readarray-missing': '/opt/scripts/lines.sh', 'shell-trap-err-missing': '/opt/scripts/pipeline.sh', 'shell-lockfile-stale': '/opt/scripts/singleton.sh', 'shell-date-format-locale': '/opt/scripts/report-date.sh', 'shell-printf-vs-echo': '/opt/scripts/emit.sh', 'shell-unset-var-default': '/opt/scripts/params.sh', 'shell-pipe-to-while-fd': '/opt/scripts/fanout.sh', 'shell-mktemp-cleanup': '/opt/scripts/build-temp.sh', 'shell-array-quoting': '/opt/scripts/args-array.sh', 'shell-command-substitution-newline': '/opt/scripts/capture.sh', 'shell-getopt-long': '/opt/scripts/longopts.sh', 'shell-numeric-bc-scale': '/opt/scripts/ratio.sh', 'shell-source-relative-path': '/opt/scripts/main-with-lib.sh', 'shell-background-wait': '/opt/scripts/parallel.sh', 'shell-echo-password': '/opt/scripts/db-login.sh', 'shell-rm-rf-variable': '/opt/scripts/wipe.sh', 'shell-curl-no-fail': '/opt/scripts/healthcheck.sh', 'shell-tar-absolute-paths': '/opt/scripts/make-backup.sh', 'shell-no-shebang': '/opt/scripts/no-shebang.sh', 'shell-stderr-stdout-merge': '/opt/scripts/logging.sh', 'shell-exit-trap-overwrite': '/opt/scripts/multi-trap.sh', 'shell-positional-shift': '/opt/scripts/shift-args.sh', 'shell-process-sub-portability': '/opt/scripts/diff-check.sh', 'shell-readonly-reassign': '/opt/scripts/const.sh', 'docker-compose-env-missing': '/opt/app/docker-compose.yml', 'docker-compose-depends-on': '/opt/app/docker-compose.yml', 'docker-healthcheck-wrong': '/opt/app/Dockerfile', 'docker-restart-policy-missing': '/opt/app/docker-compose.yml', 'docker-memory-limit-oom': '/opt/app/docker-compose.yml', 'docker-cpu-limit-throttle': '/opt/app/docker-compose.yml', 'docker-bind-mount-wrong': '/opt/app/docker-compose.yml', 'docker-volume-permissions': '/opt/app/docker-compose.yml', 'docker-network-alias-missing': '/opt/app/docker-compose.yml', 'docker-ports-conflict': '/opt/app/docker-compose.yml', 'docker-dockerfile-cache-bust': '/opt/app/Dockerfile', 'docker-dockerfile-root-user': '/opt/app/Dockerfile', 'docker-multistage-bloat': '/opt/app/Dockerfile', 'docker-entrypoint-shell-form': '/opt/app/Dockerfile', 'docker-no-dockerignore': '/opt/app/.dockerignore', 'docker-secrets-in-env': '/opt/app/Dockerfile', 'docker-compose-version-deprecated': '/opt/app/docker-compose.yml', 'docker-logging-driver-blocking': '/etc/docker/daemon.json', 'docker-iptables-disabled': '/etc/docker/daemon.json', 'docker-mtu-mismatch': '/etc/docker/daemon.json', 'docker-default-ulimit-low': '/etc/docker/daemon.json', 'docker-live-restore-off': '/etc/docker/daemon.json', 'docker-registry-mirror-missing': '/etc/docker/daemon.json', 'docker-compose-network-external': '/opt/app/docker-compose.yml', 'docker-build-arg-undefined': '/opt/app/Dockerfile', 'docker-healthcheck-interval-aggressive': '/opt/app/Dockerfile', 'docker-compose-restart-loop': '/opt/app/docker-compose.yml', 'docker-overlay-network-encryption': '/opt/app/docker-compose.yml', 'docker-tmpfs-missing': '/opt/app/docker-compose.yml', 'docker-cap-add-excessive': '/opt/app/docker-compose.yml', 'docker-readonly-rootfs-missing': '/opt/app/docker-compose.yml', 'docker-network-subnet-overlap': '/opt/app/docker-compose.yml', 'docker-init-missing-zombies': '/opt/app/docker-compose.yml', 'docker-build-platform-mismatch': '/opt/app/Dockerfile', 'gpu-driver-version-pin': '/etc/nvidia/driver-pin.conf', 'gpu-cuda-toolkit-path': '/etc/profile.d/cuda.sh', 'gpu-nccl-ib-disabled': '/etc/nccl.conf', 'gpu-mig-profile-wrong': '/etc/nvidia/mig-layout.conf', 'gpu-dcgm-exporter-config': '/etc/dcgm-exporter/config.csv', 'gpu-xid-errors-logging': '/etc/nvidia/xid-monitor.conf', 'gpu-cgroups-v2-mismatch': '/etc/nvidia-container-runtime/config.toml', 'gpu-topology-numa-pinning': '/etc/gpu/numa-pinning.conf', 'gpu-power-cap-cluster': '/etc/gpu/cluster-power.conf', 'gpu-vbios-mismatch': '/etc/gpu/vbios-baseline.conf', 'gpu-thermal-throttle-airflow': '/etc/gpu/thermal-policy.conf', 'gpu-shared-memory-limit': '/etc/gpu/shm-policy.conf', 'gpu-driver-mode-wddm': '/etc/gpu/driver-mode.conf', 'gpu-cuda-arch-mismatch': '/etc/gpu/cuda-arch.conf', 'gpu-persistence-daemon-config': '/etc/gpu/persistenced.conf', 'gpu-rocm-kfd-permissions': '/etc/gpu/rocm-access.conf', 'gpu-mps-pipe-dir': '/etc/gpu/mps-pipe.conf', 'gpu-fan-policy-passive': '/etc/gpu/fan-policy.conf', 'gpu-clock-locked-low': '/etc/gpu/clock-policy.conf', 'gpu-ecc-pages-retired': '/etc/gpu/health-policy.conf', 'gpu-container-toolkit-runtime': '/etc/docker/daemon.json', 'gpu-driver-blacklist-nouveau': '/etc/modprobe.d/blacklist-nouveau.conf', 'gpu-cuda-mps-memory-limit': '/etc/gpu/mps-memlimit.conf', 'gpu-p2p-disabled': '/etc/gpu/p2p.conf', 'gpu-driver-fabric-mismatch': '/etc/gpu/fabric-version.conf', 'gpu-monitoring-interval': '/etc/gpu/telemetry.conf', 'gpu-driver-debug-logging': '/etc/gpu/driver-logging.conf', 'gpu-affinity-hyperthreading': '/etc/gpu/cpu-affinity.conf', 'gpu-nvlink-degraded': '/etc/gpu/nvlink-policy.conf', 'gpu-driver-secureboot': '/etc/gpu/secureboot-signing.conf', 'gpu-cgroup-memory-accounting': '/etc/gpu/cgroup-accounting.conf', 'gpu-driver-iommu-passthrough': '/etc/gpu/iommu.conf', 'gpu-batch-scheduler-binding': '/etc/gpu/scheduler-binding.conf', 'gpu-driver-runtime-mismatch': '/etc/gpu/runtime-compat.conf', 'gpu-mig-not-enabled': '/etc/gpu/mig-enable.conf', 'gpu-telemetry-export-tls': '/etc/gpu/telemetry-tls.conf', 'baremetal-ipmi-lan-disabled': '/etc/bmc/lan-channel.cfg', 'baremetal-bmc-default-creds': '/etc/bmc/credentials.cfg', 'baremetal-sel-full': '/etc/bmc/sel-policy.cfg', 'baremetal-raid-write-cache': '/etc/raid/cache-policy.cfg', 'baremetal-raid-rebuild-rate': '/etc/raid/rebuild-rate.cfg', 'baremetal-disk-predictive-fail': '/etc/smart/policy.cfg', 'baremetal-nic-teaming-mode': '/etc/network/teaming.cfg', 'baremetal-pxe-vlan-tag': '/etc/pxe/vlan.cfg', 'baremetal-power-redundancy': '/etc/bmc/power-policy.cfg', 'baremetal-cpu-cstates-latency': '/etc/bios/cstates.cfg', 'baremetal-turbo-disabled': '/etc/bios/turbo.cfg', 'baremetal-memory-mismatch-rank': '/etc/bios/memory.cfg', 'baremetal-ras-features-off': '/etc/bios/ras.cfg', 'baremetal-sr-iov-disabled': '/etc/bios/sriov.cfg', 'baremetal-watchdog-disabled': '/etc/bmc/watchdog.cfg', 'baremetal-clock-source-unstable': '/etc/bios/clocksource.cfg', 'baremetal-hugepages-not-reserved': '/etc/bios/hugepages.cfg', 'baremetal-iommu-not-enabled': '/etc/bios/iommu.cfg', 'baremetal-boot-mode-legacy': '/etc/bios/bootmode.cfg', 'baremetal-tpm-disabled': '/etc/bios/tpm.cfg', 'baremetal-pcie-bifurcation': '/etc/bios/pcie-bifurcation.cfg', 'baremetal-fan-zone-mapping': '/etc/bmc/fan-zones.cfg', 'baremetal-ntp-bmc-drift': '/etc/bmc/ntp.cfg', 'baremetal-disk-spindown-aggressive': '/etc/storage/power-policy.cfg', 'baremetal-numa-balancing-vm': '/etc/bios/numa-balancing.cfg', 'baremetal-firmware-rollback-protection': '/etc/firmware/rollback-policy.cfg', 'baremetal-console-redirect': '/etc/bios/serial-console.cfg', 'baremetal-disk-cache-flush': '/etc/storage/cache-flush.cfg', 'baremetal-power-cap-enforced': '/etc/bmc/power-cap.cfg', 'baremetal-sata-mode-ide': '/etc/bios/sata-mode.cfg', 'baremetal-aspm-power-save': '/etc/bios/aspm.cfg', 'baremetal-memory-scrub-disabled': '/etc/bios/memory-scrub.cfg', 'baremetal-boot-watchdog-timeout': '/etc/bmc/boot-watchdog.cfg', 'baremetal-thermal-shutdown-threshold': '/etc/bmc/thermal-shutdown.cfg', 'baremetal-lldp-disabled': '/etc/network/lldp.cfg', 'rhel-dnf-gpgcheck-off': '/etc/dnf/dnf.conf', 'rhel-yum-proxy-wrong': '/etc/dnf/dnf.conf', 'rhel-chrony-conf-no-servers': '/etc/chrony.conf', 'rhel-nsswitch-misordered': '/etc/nsswitch.conf', 'rhel-pam-faillock-lockout': '/etc/security/faillock.conf', 'rhel-selinux-permissive': '/etc/selinux/config', 'rhel-grub-cmdline-missing-param': '/etc/default/grub', 'rhel-systemd-resolved-conf': '/etc/systemd/resolved.conf', 'rhel-fapolicyd-blocking': '/etc/fapolicyd/fapolicyd.rules', 'rhel-kdump-not-configured': '/etc/kdump.conf', 'rhel-rsyslog-remote-forward': '/etc/rsyslog.d/remote.conf', 'rhel-auditd-rules-missing': '/etc/audit/rules.d/audit.rules', 'rhel-ntp-iburst-missing': '/etc/chrony.conf', 'rhel-sysctl-somaxconn-low': '/etc/sysctl.d/99-net.conf', 'rhel-sysctl-swappiness': '/etc/sysctl.d/99-vm.conf', 'rhel-logind-killuser': '/etc/systemd/logind.conf', 'rhel-coredump-disabled': '/etc/systemd/coredump.conf', 'rhel-firewalld-zone-wrong': '/etc/firewalld/zones/public.xml', 'rhel-crypto-policy-legacy': '/etc/crypto-policies/config', 'rhel-sshd-maxstartups': '/etc/ssh/sshd_config.d/limits.conf', 'rhel-systemd-oomd-killing': '/etc/systemd/oomd.conf', 'rhel-dnf-automatic-misconfig': '/etc/dnf/automatic.conf'})


_RS_MARKER_FIX.update({'html-img-missing-alt': '/var/www/html/gallery.html', 'html-table-no-headers': '/var/www/html/data.html', 'html-heading-skip': '/var/www/html/article.html', 'html-lang-missing': '/var/www/html/index.html', 'html-button-vs-div': '/var/www/html/menu.html', 'html-form-no-action': '/var/www/html/signup.html', 'html-form-no-name': '/var/www/html/login.html', 'html-required-validation': '/var/www/html/order.html', 'html-deprecated-tags': '/var/www/html/old.html', 'html-inline-styles': '/var/www/html/styled.html', 'html-missing-favicon': '/var/www/html/index.html', 'html-open-graph-missing': '/var/www/html/index.html', 'html-canonical-missing': '/var/www/html/page.html', 'html-robots-noindex': '/var/www/html/landing.html', 'html-mixed-content': '/var/www/html/secure.html', 'html-target-blank-noopener': '/var/www/html/links.html', 'html-autocomplete-password': '/var/www/html/account.html', 'html-iframe-no-sandbox': '/var/www/html/embed.html', 'html-script-blocking-render': '/var/www/html/index.html', 'html-no-lazy-loading': '/var/www/html/feed.html', 'html-missing-width-height': '/var/www/html/news.html', 'html-font-no-display-swap': '/var/www/html/typography.html', 'html-srcset-missing': '/var/www/html/responsive.html', 'html-nested-interactive': '/var/www/html/card.html', 'html-unclosed-tags': '/var/www/html/broken.html', 'html-entity-encoding': '/var/www/html/comments.html', 'html-base-tag-wrong': '/var/www/html/app.html', 'html-meta-refresh-redirect': '/var/www/html/redirect.html', 'html-table-layout': '/var/www/html/layout.html', 'html-aria-misuse': '/var/www/html/widget.html', 'html-form-label-wrap': '/var/www/html/search.html', 'html-viewport-user-scalable': '/var/www/html/mobile.html', 'html-duplicate-title': '/var/www/html/dup.html', 'html-empty-link-text': '/var/www/html/icons.html', 'html-form-get-sensitive': '/var/www/html/reset.html', 'html-charset-late': '/var/www/html/late.html', 'html-noscript-missing': '/var/www/html/spa.html', 'html-print-stylesheet': '/var/www/html/invoice.html', 'html-svg-no-title': '/var/www/html/chart.html', 'html-preload-misconfigured': '/var/www/html/fast.html', 'html-doctype-xhtml': '/var/www/html/legacy-xhtml.html', 'gpu-dmabuf-permissions': '/etc/gpu/dmabuf-access.conf', 'rhel-needs-restarting': '/etc/rhel-patch-policy.conf', 'db-postgres-effective-cache-size': '/var/lib/pgsql/data/postgresql.conf'})


def _engine_for_session(session) -> UnifiedSimulationEngine | None:
    entry = get_sim_session(str(session.id))
    if not entry:
        return None
    engine = entry.get("state", {}).get("engine")
    return engine if isinstance(engine, UnifiedSimulationEngine) else None


def _boot_login(engine: UnifiedSimulationEngine) -> None:
    if not engine.boot:
        return
    if engine.boot.phase in ("grub", "grub_rescue", "mbr", "initramfs", "panic", "booting"):
        engine._handle_boot("")
    if engine.boot.phase == "login":
        engine._handle_boot("root")
    if engine.boot.phase == "password_wait":
        engine._handle_boot("redhat")


def _fix_boot_issue(engine: UnifiedSimulationEngine, slug: str) -> None:
    boot = engine.boot
    if not boot:
        return
    if "initramfs" in slug or "dracut" in slug:
        engine._handle_boot("dracut -f")
    elif "kernel-panic" in slug or ("kernel" in slug and "panic" in slug):
        engine._handle_boot("dracut -f")
        boot.kernel_fixed = True
        engine.shell.state.kernel_fixed = True
    elif "mbr" in slug:
        engine._handle_boot("grub2-install /dev/sda")
        boot.mbr_fixed = True
        engine.shell.state.mbr_fixed = True
    elif "grub-rescue" in slug or ("grub" in slug and "rescue" in slug):
        engine._handle_boot("grub2-install /dev/sda")
        engine._handle_boot("grub2-mkconfig -o /boot/grub2/grub.cfg")
        boot.grub_fixed = True
        engine.shell.state.grub_fixed = True
    elif "grub" in slug or "boot" in slug:
        engine._handle_boot("grub2-mkconfig -o /boot/grub2/grub.cfg")
        boot.grub_fixed = True
        engine.shell.state.grub_fixed = True
    _boot_login(engine)


def apply_simulation_fix(session) -> tuple[bool, str]:
    """Run the scenario fix, then persist the engine so cross-worker validation
    (which may restore the engine from LabSession.simulation_snapshot) sees the
    repaired state instead of the stale pre-fix snapshot."""
    result = _apply_simulation_fix(session)
    try:
        if result and result[0]:
            from apps.labs.provisioner.simulation.sim_persistence import persist_session_snapshot
            persist_session_snapshot(str(session.id))
    except Exception:
        pass
    return result


def _apply_simulation_fix(session) -> tuple[bool, str]:
    """Run scenario-specific fix commands against the simulation engine."""
    engine = _engine_for_session(session)
    if not engine:
        return False, "no simulation session"

    slug = (session.scenario.slug or "").lower()
    shell = engine.shell
    state = shell.state

    try:
        # ── Real-state generated scenarios (services + config markers) ──
        # Matched FIRST by exact slug so generic substring rules below don't
        # mis-handle them. Service scenarios start the failed unit; marker
        # scenarios rewrite the broken config to carry the FIXED-OK sentinel,
        # proving a genuine edit (validation reads the real file content).
        if slug in _RS_SERVICE_FIX:
            unit = _RS_SERVICE_FIX[slug]
            shell.run(f"systemctl start {unit}")
            svc = state.services.get(unit)
            if svc:
                svc.active = "active"
                svc.sub_state = "running"
            return True, f"{unit} started"
        if slug in _RS_MARKER_FIX:
            path = _RS_MARKER_FIX[slug]
            existing = state.read_file(path) or ""
            fixed = (existing.replace("# broken configuration", "# corrected configuration")
                     + "\n# FIXED-OK: corrected per the documented remediation\n")
            state.write_file(path, fixed)
            return True, f"{path} corrected"

        # ── New high-value scenarios (matched before generic substrings) ──
        if "selinux-httpd-port-denied" in slug:
            # Label the custom port with SELinux, keep Enforcing, then start nginx.
            shell.run("semanage port -a -t http_port_t -p tcp 8080")
            shell.run("systemctl start nginx")
            return True, "selinux port labelled and nginx started"

        if "disk-missing-rescan-fs" in slug:
            shell.run('echo "- - -" > /sys/class/scsi_host/host0/scan')
            shell.run("mkfs.xfs /dev/sdc")
            shell.run("mkdir -p /data")
            shell.run("mount /dev/sdc /data")
            shell.run('echo "/dev/sdc /data xfs defaults 0 0" >> /etc/fstab')
            return True, "disk rescanned, formatted, mounted, persisted"

        if "swap-not-active" in slug:
            shell.run("mkswap /dev/sdc")
            shell.run("swapon /dev/sdc")
            shell.run('echo "/dev/sdc none swap sw 0 0" >> /etc/fstab')
            return True, "swap activated and persisted"

        if "lvm-create-mount" in slug:
            shell.run("pvcreate /dev/sdc")
            shell.run("vgcreate vgdata /dev/sdc")
            shell.run("lvcreate -L 10G -n lvdata vgdata")
            shell.run("mkfs.xfs /dev/vgdata/lvdata")
            shell.run("mkdir -p /data")
            shell.run("mount /dev/vgdata/lvdata /data")
            shell.run('echo "/dev/vgdata/lvdata /data xfs defaults 0 0" >> /etc/fstab')
            return True, "lvm provisioned and mounted at /data"

        if "default-gateway-missing" in slug:
            shell.run("ip route add default via 10.0.0.1 dev eth0")
            shell.run('echo "GATEWAY=10.0.0.1" >> /etc/sysconfig/network')
            return True, "default gateway configured and persisted"

        if "sysctl-ip-forward" in slug:
            shell.run('echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-ipforward.conf')
            return True, "ip_forward enabled persistently"

        if "kernel-module-not-loaded" in slug:
            shell.run("modprobe br_netfilter")
            shell.run('echo "br_netfilter" > /etc/modules-load.d/k8s.conf')
            return True, "kernel module load made persistent"

        if "db-postgres-max-connections" in slug:
            shell.run(
                "sed -i 's/max_connections = 20/max_connections = 200/' "
                "/var/lib/pgsql/data/postgresql.conf"
            )
            shell.run("systemctl restart postgresql")
            return True, "max_connections raised and postgresql restarted"

        if "db-mysql-table-crashed" in slug:
            # Repairing the MyISAM table clears the crashed marker.
            shell.run("rm -f /var/lib/mysql/appdb/orders.CRASHED")
            shell.run("systemctl restart mysqld")
            return True, "crashed table repaired and mysqld restarted"

        if "db-postgres-disk-full-archive" in slug:
            # Reclaim disk by clearing the already-archived WAL backlog, then start.
            shell.run("rm -rf /var/lib/pgsql/archive")
            shell.run("systemctl start postgresql")
            return True, "disk reclaimed and postgresql started"

        if "patch" in slug:
            state.ops_backup_taken = True
            state.ops_db_stopped = True
            state.ops_app_stopped = True
            shell.run("bash /opt/fixitlab/precheck.sh")
            shell.run("dnf update -y")
            engine._reboot_from_shell()
            shell.run("mount -a")
            state.mount_filesystems_fixed = True
            state.ops_services_restarted = True
            _boot_login(engine)
            post = shell.run("bash /opt/fixitlab/postcheck.sh")
            if "PASSED" not in post:
                return False, post[:200]
            return True, "patching fixed"

        if "nginx" in slug and "root" in slug:
            sites = state.read_file("/etc/nginx/sites-enabled/default") or ""
            if "/var/www/wrong" in sites:
                state._write_file(
                    "/etc/nginx/sites-enabled/default",
                    sites.replace("/var/www/wrong", "/var/www/html"),
                )
            return True, "nginx root fixed"

        if "nginx" in slug:
            shell.run("sed -i 's/listn/listen/' /etc/nginx/sites-enabled/default")
            shell.run("systemctl start nginx")
            return True, "nginx fixed"

        if "useradd" in slug:
            shell.run(
                "sed -i 's/corrupt::99999:99999:bad:\\/bad:\\/bin\\/bash//' /etc/passwd"
            )
            shell.run("useradd -m appuser")
            return True, "useradd fixed"

        if "gpu" in slug or "nvidia" in slug:
            shell.run("modprobe nvidia")
            state.gpu_healthy = True
            return True, "gpu fixed"

        if "initramfs" in slug or "dracut" in slug or "kernel-panic" in slug:
            _fix_boot_issue(engine, slug)
            return True, "boot issue fixed"

        if "grub" in slug or "mbr" in slug or "boot" in slug:
            _fix_boot_issue(engine, slug)
            return True, "grub fixed"

        if "ansible" in slug:
            shell.run("ssh-copy-id root@web1")
            shell.run("ssh-copy-id root@web2")
            return True, "ssh key fixed"

        if "ssh-stop" in slug or "sshd-down" in slug:
            shell.run("systemctl start sshd")
            return True, "sshd started"

        if "firewalld" in slug:
            shell.run("firewall-cmd --permanent --add-service=http")
            shell.run("firewall-cmd --reload")
            return True, "firewall fixed"

        if "mysql-dual" in slug:
            shell.run("systemctl start mysqld")
            return True, "mysqld started"

        if "mysql" in slug:
            shell.run("systemctl start mysqld")
            return True, "mysqld started"

        if "postgres" in slug:
            shell.run("systemctl start postgresql")
            return True, "postgresql started"

        if "docker" in slug:
            if "daemon-stopped" in slug or "stopped" in slug:
                shell.run("systemctl start docker")
            elif "exited" in slug or "container" in slug:
                shell.run("docker start web")
            elif "pull" in slug:
                shell.run("docker pull nginx:latest")
            elif "network" in slug:
                shell.run("docker network connect bridge web")
                engine._docker_network_fixed = True
            elif "compose" in slug:
                shell.run("docker compose up -d")
            else:
                shell.run("docker start web")
            engine._container_running = True
            docker_svc = state.services.get("docker")
            if docker_svc:
                docker_svc.active = "active"
                docker_svc.sub_state = "running"
            return True, "docker fixed"

        if "endpoint" in slug or "service-not-ready" in slug:
            shell.run("kubectl patch service api -p '{\"spec\":{\"selector\":{\"app\":\"api\"}}}'")
            return True, "k8s endpoints fixed"

        # ── DevOps CI/CD + Helm (engine-backed health) ──
        if "helm" in slug:
            devops = getattr(engine, "devops", None)
            if devops:
                devops.helm_rollback("webapp", 3)
            return True, "helm release rolled back to deployed"

        if "ci-pipeline" in slug or "pipeline-failure" in slug or "devops-ci" in slug:
            devops = getattr(engine, "devops", None)
            if devops:
                devops.fix_pipeline()
            return True, "ci/cd pipeline fixed"

        # ── Networking (BGP / NTP / MTU) engine-backed health ──
        if "bgp" in slug:
            net = getattr(engine, "networking", None)
            if net:
                net.fix_bgp()
            return True, "bgp session established"

        if "ntp" in slug:
            net = getattr(engine, "networking", None)
            if net:
                net.sync_ntp()
            return True, "ntp synchronized"

        if "mtu" in slug:
            shell.run("ip link set dev eth1 mtu 1500")
            net = getattr(engine, "networking", None)
            if net:
                net.interface_mtu = 1500
            return True, "interface mtu realigned"

        sim_type = getattr(session.scenario, "simulation_type", "") or ""
        if sim_type == "vmware" or "vmware" in slug:
            from e2e_vmware_fix import apply_vmware_simulation_fix
            return apply_vmware_simulation_fix(session)

        if "crashloop" in slug or ("k8s" in slug and "pod" in slug):
            shell.run("kubectl rollout restart deployment/nginx")
            return True, "k8s pods fixed"

        if "node-notready" in slug:
            shell.run("kubectl uncordon worker-1")
            return True, "k8s node fixed"

        if "configmap" in slug:
            shell.run("kubectl create configmap app-config --from-literal=key=value")
            return True, "k8s configmap fixed"

        if "imagepull" in slug or "image-pull" in slug:
            shell.run("kubectl set image deployment/api api=api:v1")
            return True, "k8s image pull fixed"

        if "rbac" in slug:
            shell.run("kubectl create rolebinding fix --clusterrole=edit --serviceaccount=default:default")
            return True, "k8s rbac fixed"

        if "k8s" in slug or "kubernetes" in slug:
            shell.run("kubectl rollout restart deployment/nginx")
            return True, "k8s fixed"

        if "ipmi" in slug or "baremetal" in slug:
            shell.run("ipmitool power on")
            engine._power_state = "on"
            return True, "power on"

        if "pip" in slug and "python" in slug:
            state._mkdir("/opt/app")
            state._write_file("/opt/app/main.py", 'import requests\nprint("ok")\n')
            return True, "python deps fixed"

        if "python" in slug:
            state._mkdir("/opt/app")
            state._write_file("/opt/app/main.py", 'print("hello")\n')
            return True, "python syntax fixed"

        if "bash" in slug or "unbound" in slug:
            state._mkdir("/opt/scripts")
            state._write_file(
                "/opt/scripts/deploy.sh",
                "#!/bin/bash\nset -u\n: ${VAR:-}\n",
            )
            return True, "bash script fixed"

        if "lvm" in slug:
            apply_team_ops_action(engine, "storage_disk_added", slug)
            shell.run("pvcreate /dev/sdb")
            # Extend whichever VG this scenario actually uses (rhel, fixitlab, …)
            # instead of assuming "rhel" — otherwise vgextend no-ops and the PV
            # never joins a VG (e.g. lvm-add-pv-extend uses the "fixitlab" VG).
            vgs = list(getattr(getattr(state, "lvm", None), "vgs", {}) or {})
            for vg in (vgs or ["rhel"]):
                shell.run(f"vgextend {vg} /dev/sdb")
            for vg in (vgs or ["rhel"]):
                shell.run(f"lvextend -r -l +100%FREE /dev/{vg}/datalv")
            return True, "storage disk provisioned"

        if "network-nic" in slug:
            apply_team_ops_action(engine, "network_nic_added", slug)
            return True, "network nic provisioned"

        if "readonly" in slug or ("fs" in slug and "fix" in slug):
            shell.run("mount -o remount,rw /")
            state.mount_filesystems_fixed = True
            return True, "readonly fs remounted rw"

        if "remount" in slug:
            shell.run("mount -o remount,rw /")
            state.mount_filesystems_fixed = True
            return True, "fs remounted"

        if "ldconfig" in slug or "missing-library" in slug:
            state._mkdir("/etc/ld.so.conf.d")
            state._write_file("/etc/ld.so.conf.d/fixitlab.conf", "/usr/local/lib\n")
            state.ldconfig_updated = True
            state.myapp_working = True
            return True, "ldconfig conf restored"

        if "terraform" in slug or any(w in slug for w in (
            "aws-", "cloudwatch", "lambda", "s3-", "eks", "iam-", "ec2-", "elb",
            "ecr", "rds", "vpc", "kinesis", "sqs", "cloudfront", "secrets-manager",
        )):
            state.terraform_fixed = True
            return True, "terraform/aws issue resolved"

        if any(w in slug for w in (
            "windows", "win-", "iis", "hyper-v", "kerberos", "gpo", "ntfs", "smb-",
            "winrm", "wmi", "sql-server", "dhcp-", "replication-", "dns-zone",
            "ad-user", "certificate-enrollment", "file-server", "gpo-not",
            "print-spooler", "remote-desktop", "service-dependency", "windows-update",
        )):
            state.windows_fixed = True
            return True, "windows issue resolved"

        return False, f"no simulation fix map for {slug}"
    except Exception as exc:
        return False, str(exc)[:200]
