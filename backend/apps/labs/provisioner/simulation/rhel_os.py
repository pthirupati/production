"""Virtual RHEL 9 OS state — filesystem, users, services, processes."""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field


@dataclass
class SimUser:
    username: str
    uid: int
    gid: int
    home: str
    shell: str = "/bin/bash"
    gecos: str = ""
    locked: bool = False


@dataclass
class SimService:
    name: str
    active: str = "inactive"  # active | inactive | failed
    enabled: str = "disabled"
    description: str = ""
    loaded: str = "loaded"
    sub_state: str = "dead"
    unit_file: str = ""


@dataclass
class SimProcess:
    pid: int
    user: str
    cpu: float
    mem: float
    command: str


@dataclass
class PackageSpec:
    """Everything a dnf/apt install of a package should materialise on the box.

    Installing a package via the catalog (RHELOSState.install_package) resolves
    deps recursively, records the real catalog version in installed_packages,
    writes each config_file to the sim FS, registers the systemd unit(s) it
    ships, creates its log files, and records its binaries so which/command -v/
    PATH resolve. This is what makes a fresh install honestly reflected in every
    subsequent query the way a real RHEL box behaves.
    """
    version: str = "1.0.0"
    release: str = "1.el9"
    arch: str = "x86_64"
    summary: str = ""
    binaries: list[tuple[str, str]] = field(default_factory=list)     # (name, path)
    units: list[tuple[str, str]] = field(default_factory=list)        # (unit, description)
    config_files: dict[str, str] = field(default_factory=dict)        # path -> content
    log_files: list[str] = field(default_factory=list)                # paths to touch
    deps: list[str] = field(default_factory=list)                     # package names
    size_kb: int = 512                                                # download size


# ── Package catalog ──────────────────────────────────────────────────────────
# Installing any of these via `dnf install`, `yum install`, `apt install`, or
# `rpm -i` materialises the package for real (see RHELOSState.install_package).
# Dependencies list catalog package names and are resolved recursively; leaf
# deps (openssl-libs, pcre2, apr, …) carry no unit and just record a version so
# `rpm -q` and the dep table are honest. Common teaching packages are covered.
PACKAGE_CATALOG: dict[str, PackageSpec] = {
    # ── leaf / library dependencies (no service, no config) ──
    "nginx-filesystem": PackageSpec(version="1.20.1", release="14.el9", arch="noarch",
                                    summary="The basic directory layout for the nginx server"),
    "openssl-libs": PackageSpec(version="3.0.7", release="24.el9",
                                summary="A general purpose cryptography library", size_kb=2100),
    "pcre2": PackageSpec(version="10.40", release="2.el9", summary="Perl-compatible regular expression library"),
    "apr": PackageSpec(version="1.7.0", release="11.el9", summary="Apache Portable Runtime library"),
    "apr-util": PackageSpec(version="1.6.1", release="23.el9", summary="Apache Portable Runtime Utility library",
                            deps=["apr"]),
    "mariadb-common": PackageSpec(version="10.5.22", release="1.el9", arch="noarch",
                                  summary="MariaDB common files for both server and client"),
    "postgresql-private-libs": PackageSpec(version="13.14", release="1.el9",
                                           summary="The shared libraries required for PostgreSQL clients"),
    "containerd.io": PackageSpec(version="1.6.28", release="3.1.el9",
                                 summary="An industry-standard container runtime", size_kb=35000),
    "docker-ce-cli": PackageSpec(version="25.0.3", release="1.el9",
                                 summary="The open-source application container engine CLI", size_kb=15000),
    "conmon": PackageSpec(version="2.1.10", release="1.el9", summary="OCI container runtime monitor"),
    "criu": PackageSpec(version="3.18", release="4.el9", summary="Tool for Checkpoint/Restore in User-space"),

    # ── web / proxy ──
    "nginx": PackageSpec(
        version="1.20.1", release="14.el9",
        summary="A high performance web server and reverse proxy server",
        binaries=[("nginx", "/usr/sbin/nginx")],
        units=[("nginx", "The nginx HTTP and reverse proxy server")],
        config_files={
            "/etc/nginx/nginx.conf": (
                "user nginx;\nworker_processes auto;\n"
                "error_log /var/log/nginx/error.log;\npid /run/nginx.pid;\n"
                "events {\n    worker_connections 1024;\n}\n"
                "http {\n    include /etc/nginx/mime.types;\n"
                "    default_type application/octet-stream;\n"
                "    access_log /var/log/nginx/access.log;\n"
                "    sendfile on;\n    keepalive_timeout 65;\n"
                "    include /etc/nginx/conf.d/*.conf;\n"
                "    server {\n        listen 80;\n        server_name localhost;\n"
                "        root /usr/share/nginx/html;\n        index index.html;\n    }\n}\n"
            ),
        },
        log_files=["/var/log/nginx/access.log", "/var/log/nginx/error.log"],
        deps=["nginx-filesystem", "openssl-libs", "pcre2"], size_kb=580,
    ),
    "httpd": PackageSpec(
        version="2.4.57", release="8.el9",
        summary="Apache HTTP Server",
        binaries=[("httpd", "/usr/sbin/httpd"), ("apachectl", "/usr/sbin/apachectl")],
        units=[("httpd", "The Apache HTTP Server")],
        config_files={
            "/etc/httpd/conf/httpd.conf": (
                "ServerRoot \"/etc/httpd\"\nListen 80\n"
                "Include conf.modules.d/*.conf\nUser apache\nGroup apache\n"
                "ServerAdmin root@localhost\nDocumentRoot \"/var/www/html\"\n"
                "ErrorLog \"logs/error_log\"\nLogLevel warn\n"
                "IncludeOptional conf.d/*.conf\n"
            ),
        },
        log_files=["/var/log/httpd/access_log", "/var/log/httpd/error_log"],
        deps=["httpd-tools", "apr", "apr-util"], size_kb=1470,
    ),
    "httpd-tools": PackageSpec(version="2.4.57", release="8.el9",
                               summary="Tools for use with the Apache HTTP Server",
                               binaries=[("ab", "/usr/bin/ab"), ("htpasswd", "/usr/bin/htpasswd")],
                               deps=["apr", "apr-util"], size_kb=90),
    "haproxy": PackageSpec(
        version="2.4.22", release="3.el9",
        summary="HAProxy reverse proxy for high availability environments",
        binaries=[("haproxy", "/usr/sbin/haproxy")],
        units=[("haproxy", "HAProxy Load Balancer")],
        config_files={
            "/etc/haproxy/haproxy.cfg": (
                "global\n    log /dev/log local0\n    maxconn 4000\n"
                "defaults\n    mode http\n    timeout connect 5s\n"
                "    timeout client 30s\n    timeout server 30s\n"
                "frontend main\n    bind *:80\n    default_backend app\n"
                "backend app\n    server app1 127.0.0.1:8080 check\n"
            ),
        },
        log_files=["/var/log/haproxy.log"],
        deps=["openssl-libs", "pcre2"], size_kb=2100,
    ),

    # ── databases ──
    "mariadb-server": PackageSpec(
        version="10.5.22", release="1.el9",
        summary="The MariaDB server and related files",
        binaries=[("mariadbd", "/usr/sbin/mariadbd"), ("mysqld", "/usr/sbin/mariadbd"),
                  ("mariadb-admin", "/usr/bin/mariadb-admin")],
        units=[("mariadb", "MariaDB 10.5 database server")],
        config_files={
            "/etc/my.cnf.d/mariadb-server.cnf": (
                "[mysqld]\ndatadir=/var/lib/mysql\nsocket=/var/lib/mysql/mysql.sock\n"
                "log-error=/var/log/mariadb/mariadb.log\npid-file=/run/mariadb/mariadb.pid\n"
            ),
        },
        log_files=["/var/log/mariadb/mariadb.log"],
        deps=["mariadb", "mariadb-common"], size_kb=9800,
    ),
    "mariadb": PackageSpec(version="10.5.22", release="1.el9",
                           summary="A very fast and robust SQL database server (client)",
                           binaries=[("mariadb", "/usr/bin/mariadb"), ("mysql", "/usr/bin/mariadb")],
                           deps=["mariadb-common"], size_kb=1600),
    "postgresql-server": PackageSpec(
        version="13.14", release="1.el9",
        summary="The programs needed to create and run a PostgreSQL server",
        binaries=[("postgres", "/usr/bin/postgres"), ("initdb", "/usr/bin/initdb"),
                  ("pg_ctl", "/usr/bin/pg_ctl")],
        units=[("postgresql", "PostgreSQL database server")],
        config_files={
            "/var/lib/pgsql/data/postgresql.conf": (
                "listen_addresses = 'localhost'\nport = 5432\nmax_connections = 100\n"
                "logging_collector = on\nlog_directory = 'log'\n"
            ),
        },
        log_files=["/var/lib/pgsql/data/log/postgresql.log"],
        deps=["postgresql", "postgresql-private-libs"], size_kb=5600,
    ),
    "postgresql": PackageSpec(version="13.14", release="1.el9",
                              summary="PostgreSQL client programs",
                              binaries=[("psql", "/usr/bin/psql"), ("pg_dump", "/usr/bin/pg_dump")],
                              deps=["postgresql-private-libs"], size_kb=1600),
    "redis": PackageSpec(
        version="6.2.7", release="1.el9",
        summary="A persistent key-value database",
        binaries=[("redis-server", "/usr/bin/redis-server"), ("redis-cli", "/usr/bin/redis-cli")],
        units=[("redis", "Redis persistent key-value database")],
        config_files={
            "/etc/redis/redis.conf": (
                "bind 127.0.0.1 -::1\nport 6379\ndaemonize no\n"
                "pidfile /run/redis/redis.pid\nlogfile /var/log/redis/redis.log\n"
                "dir /var/lib/redis\n"
            ),
        },
        log_files=["/var/log/redis/redis.log"],
        deps=[], size_kb=1100,
    ),
    "memcached": PackageSpec(
        version="1.6.9", release="4.el9",
        summary="High Performance, Distributed Memory Object Cache",
        binaries=[("memcached", "/usr/bin/memcached")],
        units=[("memcached", "memcached daemon")],
        config_files={"/etc/sysconfig/memcached": (
            "PORT=\"11211\"\nUSER=\"memcached\"\nMAXCONN=\"1024\"\nCACHESIZE=\"64\"\n")},
        log_files=[], deps=[], size_kb=120,
    ),

    # ── containers ──
    "docker": PackageSpec(
        version="25.0.3", release="1.el9",
        summary="The open-source application container engine",
        binaries=[("docker", "/usr/bin/docker"), ("dockerd", "/usr/bin/dockerd")],
        units=[("docker", "Docker Application Container Engine")],
        config_files={"/etc/docker/daemon.json": "{\n  \"log-driver\": \"json-file\"\n}\n"},
        log_files=[], deps=["containerd.io", "docker-ce-cli"], size_kb=42000,
    ),
    "podman": PackageSpec(
        version="4.9.4", release="1.el9",
        summary="Manage Pods, Containers and Container Images",
        binaries=[("podman", "/usr/bin/podman")],
        units=[("podman", "Podman API Service")],
        config_files={"/etc/containers/registries.conf":
                      "unqualified-search-registries = [\"registry.access.redhat.com\", \"docker.io\"]\n"},
        log_files=[], deps=["conmon", "criu"], size_kb=15000,
    ),

    # ── services / daemons ──
    "chrony": PackageSpec(
        version="4.3", release="1.el9",
        summary="An NTP client/server",
        binaries=[("chronyd", "/usr/sbin/chronyd"), ("chronyc", "/usr/bin/chronyc")],
        units=[("chronyd", "NTP client/server")],
        config_files={"/etc/chrony.conf":
                      "pool 2.rhel.pool.ntp.org iburst\ndriftfile /var/lib/chrony/drift\n"
                      "makestep 1.0 3\nrtcsync\nlogdir /var/log/chrony\n"},
        log_files=[], deps=[], size_kb=340,
    ),
    "firewalld": PackageSpec(
        version="1.2.5", release="1.el9", arch="noarch",
        summary="A firewall daemon with D-Bus interface providing a dynamic firewall",
        binaries=[("firewall-cmd", "/usr/bin/firewall-cmd"),
                  ("firewall-offline-cmd", "/usr/bin/firewall-offline-cmd")],
        units=[("firewalld", "firewalld - dynamic firewall daemon")],
        config_files={"/etc/firewalld/firewalld.conf":
                      "DefaultZone=public\nCleanupOnExit=yes\nFirewallBackend=nftables\n"},
        log_files=["/var/log/firewalld"], deps=[], size_kb=430,
    ),
    "vsftpd": PackageSpec(
        version="3.0.5", release="5.el9",
        summary="Very Secure Ftp Daemon",
        binaries=[("vsftpd", "/usr/sbin/vsftpd")],
        units=[("vsftpd", "Vsftpd ftp daemon")],
        config_files={"/etc/vsftpd/vsftpd.conf":
                      "anonymous_enable=NO\nlocal_enable=YES\nwrite_enable=YES\n"
                      "listen=YES\nlisten_ipv6=NO\npam_service_name=vsftpd\n"},
        log_files=["/var/log/vsftpd.log"], deps=[], size_kb=180,
    ),
    "bind": PackageSpec(
        version="9.16.23", release="18.el9",
        summary="The Berkeley Internet Name Domain (BIND) DNS server",
        binaries=[("named", "/usr/sbin/named"), ("rndc", "/usr/sbin/rndc")],
        units=[("named", "Berkeley Internet Name Domain (DNS)")],
        config_files={"/etc/named.conf":
                      "options {\n    listen-on port 53 { 127.0.0.1; };\n"
                      "    directory \"/var/named\";\n    allow-query { localhost; };\n"
                      "    recursion yes;\n};\nzone \".\" IN {\n    type hint;\n"
                      "    file \"named.ca\";\n};\n"},
        log_files=["/var/named/data/named.run"], deps=["openssl-libs"], size_kb=2200,
    ),
    "nfs-utils": PackageSpec(
        version="2.5.4", release="20.el9",
        summary="NFS utilities and supporting clients and daemons for the kernel NFS server",
        binaries=[("exportfs", "/usr/sbin/exportfs"), ("showmount", "/usr/sbin/showmount"),
                  ("mount.nfs", "/usr/sbin/mount.nfs")],
        units=[("nfs-server", "NFS server and services")],
        config_files={"/etc/exports": "# /srv/nfs 192.168.0.0/24(rw,sync,no_root_squash)\n"},
        log_files=[], deps=[], size_kb=520,
    ),

    # ── developer / cli tools (no service) ──
    "git": PackageSpec(version="2.43.5", release="1.el9",
                       summary="Fast Version Control System",
                       binaries=[("git", "/usr/bin/git")], deps=[], size_kb=4600),
    "curl": PackageSpec(version="7.76.1", release="29.el9",
                        summary="A utility for getting files from remote servers (FTP, HTTP, and others)",
                        binaries=[("curl", "/usr/bin/curl")], deps=["openssl-libs"], size_kb=300),
    "wget": PackageSpec(version="1.21.1", release="8.el9",
                        summary="A utility for retrieving files using the HTTP or FTP protocols",
                        binaries=[("wget", "/usr/bin/wget")], deps=["openssl-libs"], size_kb=780),
    "vim": PackageSpec(version="8.2.2637", release="20.el9",
                       summary="The VIM version 8.2 editor (vim-enhanced)",
                       binaries=[("vim", "/usr/bin/vim"), ("vi", "/usr/bin/vim")],
                       config_files={"/etc/vimrc": "set nocompatible\nsyntax on\nset backspace=2\n"},
                       deps=[], size_kb=1900),
    "net-tools": PackageSpec(version="2.0", release="0.62.20160912git.el9",
                             summary="Basic networking tools",
                             binaries=[("netstat", "/usr/bin/netstat"), ("ifconfig", "/usr/sbin/ifconfig"),
                                       ("route", "/usr/sbin/route"), ("arp", "/usr/sbin/arp")],
                             deps=[], size_kb=310),
    "tcpdump": PackageSpec(version="4.99.0", release="9.el9",
                           summary="A network traffic monitoring tool",
                           binaries=[("tcpdump", "/usr/sbin/tcpdump")],
                           deps=[], size_kb=490),
}

# Aliases: alternate/legacy package names that map to a canonical catalog entry.
# Includes Debian/Ubuntu names so the apt path shares the same catalog.
PACKAGE_ALIASES: dict[str, str] = {
    # RHEL-side alternates
    "docker-ce": "docker",
    "mariadb-server-utils": "mariadb-server",
    "named": "bind",
    "bind9": "bind",
    "vim-enhanced": "vim",
    # Debian / Ubuntu names -> catalog canonical
    "apache2": "httpd",
    "apache2-bin": "httpd",
    "docker.io": "docker",
    "redis-server": "redis",
    "postgresql": "postgresql-server",
    "postgresql-server": "postgresql-server",
    "bind9utils": "bind",
    "chrony": "chrony",
    "nfs-common": "nfs-utils",
    "nfs-kernel-server": "nfs-utils",
    "vim-tiny": "vim",
}


def resolve_package_name(name: str) -> str:
    """Map an alias (or Debian name) to its canonical catalog key; else itself."""
    return PACKAGE_ALIASES.get(name, name)


# Commands that ship with a base RHEL install (coreutils, bash, systemd,
# openssh, sudo, python3, dnf, rpm, …) and therefore always resolve via
# which/command -v/type/PATH regardless of what has been installed. Anything
# NOT here must be installed via a package before it resolves.
BASE_BINARIES: dict[str, str] = {
    "bash": "/usr/bin/bash", "sh": "/usr/bin/sh", "ls": "/usr/bin/ls",
    "cat": "/usr/bin/cat", "echo": "/usr/bin/echo", "cp": "/usr/bin/cp",
    "mv": "/usr/bin/mv", "rm": "/usr/bin/rm", "mkdir": "/usr/bin/mkdir",
    "touch": "/usr/bin/touch", "chmod": "/usr/bin/chmod", "chown": "/usr/bin/chown",
    "grep": "/usr/bin/grep", "sed": "/usr/bin/sed", "awk": "/usr/bin/awk",
    "find": "/usr/bin/find", "tar": "/usr/bin/tar", "head": "/usr/bin/head",
    "tail": "/usr/bin/tail", "wc": "/usr/bin/wc", "sort": "/usr/bin/sort",
    "cut": "/usr/bin/cut", "tr": "/usr/bin/tr", "tee": "/usr/bin/tee",
    "ps": "/usr/bin/ps", "kill": "/usr/bin/kill", "df": "/usr/bin/df",
    "du": "/usr/bin/du", "free": "/usr/bin/free", "id": "/usr/bin/id",
    "whoami": "/usr/bin/whoami", "hostname": "/usr/bin/hostname",
    "uname": "/usr/bin/uname", "date": "/usr/bin/date", "which": "/usr/bin/which",
    "env": "/usr/bin/env", "su": "/usr/bin/su", "sudo": "/usr/bin/sudo",
    "systemctl": "/usr/bin/systemctl", "journalctl": "/usr/bin/journalctl",
    "useradd": "/usr/sbin/useradd", "userdel": "/usr/sbin/userdel",
    "usermod": "/usr/sbin/usermod", "groupadd": "/usr/sbin/groupadd",
    "passwd": "/usr/bin/passwd", "getent": "/usr/bin/getent",
    "python3": "/usr/bin/python3", "python": "/usr/bin/python3",
    "dnf": "/usr/bin/dnf", "yum": "/usr/bin/yum", "rpm": "/usr/bin/rpm",
    "ssh": "/usr/bin/ssh", "scp": "/usr/bin/scp", "ping": "/usr/bin/ping",
    "ip": "/usr/sbin/ip", "ss": "/usr/sbin/ss", "mount": "/usr/bin/mount",
    "umount": "/usr/bin/umount", "lsblk": "/usr/bin/lsblk", "blkid": "/usr/sbin/blkid",
    "dmesg": "/usr/bin/dmesg", "uptime": "/usr/bin/uptime",
    # util-linux / procps-ng / coreutils tools present on a stock RHEL box.
    "top": "/usr/bin/top", "pidof": "/usr/sbin/pidof", "pgrep": "/usr/bin/pgrep",
    "pkill": "/usr/bin/pkill", "killall": "/usr/bin/killall", "pstree": "/usr/bin/pstree",
    "vmstat": "/usr/bin/vmstat", "nice": "/usr/bin/nice", "renice": "/usr/bin/renice",
    "uniq": "/usr/bin/uniq", "findmnt": "/usr/bin/findmnt", "lscpu": "/usr/bin/lscpu",
    "lsmod": "/usr/sbin/lsmod", "file": "/usr/bin/file", "who": "/usr/bin/who",
    "w": "/usr/bin/w", "last": "/usr/bin/last", "chage": "/usr/bin/chage",
    "ethtool": "/usr/sbin/ethtool", "hostnamectl": "/usr/bin/hostnamectl",
    "timedatectl": "/usr/bin/timedatectl", "nmcli": "/usr/bin/nmcli",
    "lsof": "/usr/bin/lsof", "stat": "/usr/bin/stat", "nproc": "/usr/bin/nproc",
}


# Backward-compatible view: package -> [(unit, description)] derived from the
# catalog. register_package_service (grading contract) reads this, so existing
# behaviour is preserved while the catalog stays the single source of truth.
PACKAGE_SERVICES: dict[str, list[tuple[str, str]]] = {
    name: list(spec.units) for name, spec in PACKAGE_CATALOG.items()
}
# Retain legacy entries the catalog does not (yet) model so any older caller of
# register_package_service still registers the expected unit.
PACKAGE_SERVICES.update({
    "mysql-server": [("mysqld", "MySQL Server")],
    "docker-ce": [("docker", "Docker Application Container Engine")],
    "php-fpm": [("php-fpm", "The PHP FastCGI Process Manager")],
    "mongodb-org": [("mongod", "MongoDB Database Server")],
    "mongodb": [("mongod", "MongoDB Database Server")],
    "tomcat": [("tomcat", "Apache Tomcat Web Application Container")],
    "named": [("named", "Berkeley Internet Name Domain (DNS)")],
    "dovecot": [("dovecot", "Dovecot IMAP/POP3 email server")],
    "postfix": [("postfix", "Postfix Mail Transport Agent")],
    "samba": [("smb", "Samba SMB Daemon")],
    "rabbitmq-server": [("rabbitmq-server", "RabbitMQ broker")],
    "elasticsearch": [("elasticsearch", "Elasticsearch")],
    "grafana": [("grafana-server", "Grafana instance")],
    "prometheus": [("prometheus", "Prometheus monitoring system")],
})


@dataclass
class SimBlockDevice:
    """A whole disk, partition, or LV as seen by lsblk/blkid/mkfs/mount."""
    name: str                       # /dev/sdb, /dev/sdb1, /dev/mapper/rhel-data
    size: str = "50G"
    dev_type: str = "disk"          # disk | part | lvm
    parent: str = ""                # parent device name for partitions
    fstype: str = ""                # xfs | ext4 | swap | "" (unformatted)
    uuid: str = ""                  # populated when formatted
    mountpoint: str = ""            # current mount target ("" = unmounted)
    present: bool = True            # False until a SCSI rescan reveals it
    removable: bool = False
    needs_reboot: bool = False      # hidden disk a rescan won't reveal — needs reboot


class RHELOSState:
    """Mutable in-memory RHEL-like system state."""

    def __init__(self, hostname: str = "rhel-sim", scenario_slug: str = ""):
        self.hostname = hostname
        self.scenario_slug = scenario_slug
        self.kernel = "5.14.0-362.el9.x86_64"
        self.os_release = "Red Hat Enterprise Linux 9.3 (Plow)"
        self.current_user = "root"
        self.cwd = "/root"
        self.uid_counter = 1000
        self.pid_counter = 2000
        self.last_exit_code = 0
        self.boot_time = time.time() - 3600
        # Hardware profile. Defaults match the historical hardcoded RHEL box so
        # pure-Linux labs are byte-for-byte unchanged; for a unified-server VMware
        # lab these are re-seeded from the VM template (see set_hardware). nproc,
        # lscpu, free and /proc/{cpuinfo,meminfo} all read these two fields.
        self.cpu_count = 4
        self.mem_mb = 16384
        self.vfs: dict[str, str | dict] = {}
        self.users: dict[str, SimUser] = {}
        self.groups: dict[str, list[int]] = {"root": [0]}
        self.services: dict[str, SimService] = {}
        self.processes: list[SimProcess] = []
        self.env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/root",
            "SHELL": "/bin/bash",
            "USER": "root",
            "HOSTNAME": hostname,
        }
        self.dmesg_extra: list[str] = []
        self.gpu_healthy: bool = True
        self.initramfs_fixed: bool = False
        self.grub_fixed: bool = False
        self.mbr_fixed: bool = False
        self.kernel_fixed: bool = False
        self.patching_done: bool = False
        self.precheck_ran: bool = False
        self.postcheck_ran: bool = False
        self.rebooted_after_patch: bool = False
        self.emergency_mode: bool = False
        self.fstab_valid: bool = True
        # Jira-coordinated change management
        self.ops_backup_taken: bool = False
        self.ops_db_stopped: bool = False
        self.ops_app_stopped: bool = False
        self.ops_db_started: bool = True
        self.ops_app_started: bool = True
        self.ops_services_restarted: bool = False
        self.ops_security_approved: bool = False
        self.mount_issue_after_reboot: bool = False
        self.mount_filesystems_fixed: bool = False
        self.pending_storage_device: str = "/dev/sdb"
        self.storage_disk_provisioned: bool = True
        self.pending_nic_config: str = "10.0.0.20/24"
        self.network_nic_provisioned: bool = True
        # SELinux: mode round-trips via getenforce/setenforce; ports/fcontexts
        # are state that semanage mutates and restorecon/chcon read.
        self.selinux_mode: str = "Enforcing"  # Enforcing | Permissive | Disabled
        self.selinux_ports: dict[str, list[int]] = {}   # type -> [ports]
        self.selinux_fcontexts: list[dict] = []          # {path, type}
        self.file_contexts: dict[str, str] = {}          # path -> selinux context
        # Block-device model for storage/filesystem scenarios.
        self.block_devices: dict[str, SimBlockDevice] = {}
        self.hidden_block_devices: dict[str, SimBlockDevice] = {}  # revealed by SCSI rescan
        self.swaps: dict[str, dict] = {}  # device -> {"size": kb, "used": kb}
        self.mounts: dict[str, dict] = {}  # mountpoint -> {"device", "fstype", "size_kb"}
        self.disk_rescanned: bool = False
        # Cross-technology bridge (VMware ⇄ this terminal). session_id keys the
        # shared cache; server_hung models a guest hung until reset from VMware.
        self.session_id: str = ""
        self.server_hung: bool = False
        self.editor = None  # EditorSession when nano/vi active
        self.network_ifs: dict[str, dict] = {
            "lo": {"up": True, "addrs": ["127.0.0.1/8"]},
            "eth0": {"up": True, "addrs": ["10.0.0.10/24"]},
        }
        # Git simulation — repos, branches, commits (lazy; see git_state.py)
        from .git_state import GitSimState
        self.git = GitSimState()
        from .lvm_state import LVMState
        from .firewall_state import FirewallState
        self.lvm = LVMState()
        self.firewall = FirewallState()
        # Stateful rpm DB: name -> "name-version-release.arch". `dnf/yum install`
        # adds, remove deletes, and `rpm -q`/`rpm -qa` read from it so an install
        # is reflected in subsequent queries.
        self.installed_packages: dict[str, str] = {
            "kernel": f"kernel-{self.kernel}",
            "glibc": "glibc-2.34-100.el9.x86_64",
            "bash": "bash-5.1.8-9.el9.x86_64",
            "systemd": "systemd-252-13.el9.x86_64",
            "openssh-server": "openssh-server-8.7p1-34.el9.x86_64",
            "openssh-clients": "openssh-clients-8.7p1-34.el9.x86_64",
            "sudo": "sudo-1.9.5p2-9.el9.x86_64",
            "python3": "python3-3.9.18-1.el9.x86_64",
            "dnf": "dnf-4.14.0-8.el9.noarch",
            "rpm": "rpm-4.16.1.3-22.el9.x86_64",
            "firewalld": "firewalld-1.2.5-1.el9.noarch",
            "chrony": "chrony-4.3-1.el9.x86_64",
            "coreutils": "coreutils-8.32-34.el9.x86_64",
        }
        # Binary registry: command name -> absolute path. `which`, `command -v`,
        # `type` and PATH resolution consult this on top of the base coreutils
        # already present, so only genuinely-installed binaries resolve. A
        # catalog install (install_package) records the package's binaries here.
        self.installed_binaries: dict[str, str] = {}
        # Interactive confirm state: when a package manager prints "Is this ok
        # [y/N]:" (no -y), it stashes a callback here and the next input line
        # (y/n) resolves it. None when nothing is pending. See RHELShell.run.
        self.pending_confirm = None
        self._init_base_system()
        self._init_block_devices()

    def _init_base_system(self) -> None:
        self.users["root"] = SimUser("root", 0, 0, "/root", "/bin/bash", "root")
        self._write_file("/etc/hostname", self.hostname + "\n")
        self._write_file("/etc/os-release",
                         f'NAME="Red Hat Enterprise Linux"\n'
                         f'VERSION="9.3 (Plow)"\nID="rhel"\nID_LIKE="fedora"\n'
                         f'VERSION_ID="9.3"\n'
                         f'PRETTY_NAME="{self.os_release}"\n'
                         f'ANSI_COLOR="0;31"\nCPE_NAME="cpe:/o:redhat:enterprise_linux:9::baseos"\n')
        self._write_file("/etc/redhat-release", self.os_release + "\n")
        self._write_file("/etc/system-release", self.os_release + "\n")
        self._write_file("/etc/passwd", "root:x:0:0:root:/root:/bin/bash\n")
        self._write_file("/etc/group", "root:x:0:\n")
        self._write_file("/etc/shadow", "root:*:19000:0:99999:7:::\n")
        self._write_file("/etc/shells", "/bin/sh\n/bin/bash\n")
        self._write_file("/etc/resolv.conf", "nameserver 8.8.8.8\nnameserver 1.1.1.1\n")
        self._write_file("/etc/hosts", f"127.0.0.1 localhost localhost.localdomain\n::1 localhost\n127.0.1.1 {self.hostname}\n")
        # A few /proc pseudo-files learners routinely cat.
        self._write_file("/proc/cpuinfo", self._proc_cpuinfo())
        self._write_file("/proc/meminfo", self._proc_meminfo())
        self._write_file("/proc/loadavg", "0.08 0.04 0.01 1/234 900\n")
        self._write_file("/proc/version",
                         f"Linux version {self.kernel} (mockbuild@rhel) "
                         f"(gcc 11.4.1) #1 SMP PREEMPT_DYNAMIC\n")
        self._write_file("/proc/uptime", "3600.00 3550.00\n")
        self._mkdir("/root")
        self._mkdir("/home")
        self._mkdir("/etc/systemd/system")
        self._mkdir("/var/log")
        self._mkdir("/var/log/journal")
        self._mkdir("/opt/fixitlab")
        self._write_file("/opt/fixitlab/check.sh", "#!/bin/bash\nexit 0\n")

        # Only the daemons a stock RHEL minimal install actually ships belong to
        # the base system. nginx is NOT one of them — it is registered only when
        # its package is installed (dnf/apt/rpm) or when a web/nginx scenario
        # preset pre-installs it (see _preseed_scenario_services below), so an
        # un-installed nginx honestly reports "command not found" / unknown unit.
        for svc, desc in (
            ("sshd", "OpenSSH server daemon"),
            ("crond", "Command Scheduler"),
            ("chronyd", "NTP client/server"),
            ("rsyslog", "System Logging Service"),
        ):
            self.services[svc] = SimService(
                svc, active="active", enabled="enabled", description=desc,
                sub_state="running",
                unit_file=f"[Unit]\nDescription={desc}\n",
            )

        self.processes = [
            SimProcess(1, "root", 0.0, 0.1, "systemd"),
            SimProcess(412, "root", 0.1, 0.5, "/usr/sbin/sshd -D"),
        ]
        self.pid_counter = 900
        self._register_base_installed_binaries()
        self._preseed_scenario_services()

    def _register_base_installed_binaries(self) -> None:
        """Packages pre-installed on the seed image (firewalld, chrony, …) ship
        real binaries and units — record them so `which firewall-cmd`,
        `which chronyc`, and `systemctl status firewalld` behave as they would on
        a box where those RPMs are genuinely present. chronyd's unit is already
        registered as an active base daemon in _init_base_system."""
        for pkg in list(self.installed_packages):
            spec = PACKAGE_CATALOG.get(resolve_package_name(pkg))
            if not spec:
                continue
            for bname, bpath in spec.binaries:
                self.installed_binaries.setdefault(bname, bpath)
            for unit, desc in spec.units:
                if unit not in self.services:
                    self.services[unit] = SimService(
                        unit, active="inactive", enabled="disabled",
                        description=desc, loaded="loaded", sub_state="dead",
                        unit_file=f"[Unit]\nDescription={desc}\n",
                    )

    def _preseed_scenario_services(self) -> None:
        """Some web/nginx scenario presets (in scenario_presets.py) mutate
        state.services["nginx"].active directly and assume the unit already
        exists — they represent a machine where nginx IS installed. Since those
        presets are applied AFTER __init__ and cannot be edited here, pre-register
        the nginx unit (active/enabled, as before) and its worker processes when
        this state's scenario_slug routes to such a preset. This keeps existing
        grading and tests working; every other scenario boots without nginx.
        """
        slug = (self.scenario_slug or "").lower()
        nginx_scenarios = (
            "nginx" in slug
            or "firewalld" in slug
            or "selinux-httpd-port" in slug
            or "server-hung" in slug
        )
        if not nginx_scenarios:
            return
        desc = "The nginx HTTP and reverse proxy server"
        self.services["nginx"] = SimService(
            "nginx", active="active", enabled="enabled", description=desc,
            sub_state="running", unit_file=f"[Unit]\nDescription={desc}\n",
        )
        self.installed_packages.setdefault("nginx", "nginx-1.20.1-14.el9.x86_64")
        self.installed_binaries.setdefault("nginx", "/usr/sbin/nginx")
        self.processes.extend([
            SimProcess(891, "nginx", 0.0, 0.3, "nginx: master process /usr/sbin/nginx"),
            SimProcess(892, "nginx", 0.0, 0.2, "nginx: worker process"),
        ])

    def _init_block_devices(self) -> None:
        """Seed the boot disk layout (sda + LVM). Extra disks come from scenario presets or VMware hot-add."""
        self.block_devices = {
            "/dev/sda": SimBlockDevice("/dev/sda", "50G", "disk"),
            "/dev/sda1": SimBlockDevice("/dev/sda1", "1G", "part", parent="/dev/sda",
                                        fstype="xfs", uuid="aaaa1111-boot", mountpoint="/boot"),
            "/dev/sda2": SimBlockDevice("/dev/sda2", "49G", "part", parent="/dev/sda",
                                        fstype="LVM2_member", uuid="bbbb2222-pv"),
        }
        # Root + swap LVs exposed as device-mapper block devices.
        self.block_devices["/dev/mapper/rhel-root"] = SimBlockDevice(
            "/dev/mapper/rhel-root", "40G", "lvm", parent="/dev/sda2",
            fstype="xfs", uuid="cccc3333-root", mountpoint="/")
        self.block_devices["/dev/mapper/rhel-swap"] = SimBlockDevice(
            "/dev/mapper/rhel-swap", "8G", "lvm", parent="/dev/sda2",
            fstype="swap", uuid="dddd4444-swap", mountpoint="[SWAP]")
        self.swaps["/dev/mapper/rhel-swap"] = {"size": 8 * 1024 * 1024, "used": 0}

    def _proc_cpuinfo(self, cores: int | None = None) -> str:
        cores = self.cpu_count if cores is None else cores
        blocks = []
        for i in range(cores):
            blocks.append(
                f"processor\t: {i}\n"
                "vendor_id\t: GenuineIntel\n"
                "cpu family\t: 6\nmodel\t\t: 85\n"
                "model name\t: Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz\n"
                "stepping\t: 7\nmicrocode\t: 0x1\n"
                "cpu MHz\t\t: 2500.000\ncache size\t: 36608 KB\n"
                f"physical id\t: 0\nsiblings\t: {cores}\ncore id\t\t: {i}\n"
                f"cpu cores\t: {cores}\napicid\t\t: {i}\n"
                "flags\t\t: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr sse sse2 ss ht\n"
                "bogomips\t: 5000.00\n"
            )
        return "\n".join(blocks)

    def _proc_meminfo(self) -> str:
        total = self.mem_mb * 1024
        free = int(total * 0.704)
        avail = int(total * 0.832)
        cached = int(total * 0.181)
        swap = self.swaps.get("/dev/mapper/rhel-swap", {}).get("size", 8 * 1024 * 1024)
        return (
            f"MemTotal:       {total:>8} kB\n"
            f"MemFree:        {free:>8} kB\n"
            f"MemAvailable:   {avail:>8} kB\n"
            "Buffers:          131072 kB\n"
            f"Cached:         {cached:>9} kB\n"
            "SwapCached:            0 kB\n"
            "Active:          2097152 kB\n"
            "Inactive:        1048576 kB\n"
            f"SwapTotal:      {swap:>9} kB\n"
            f"SwapFree:       {swap:>9} kB\n"
        )

    def gen_uuid(self) -> str:
        import uuid as _uuid
        return str(_uuid.uuid4())

    def add_block_device(self, name: str, size: str = "50G", dev_type: str = "disk",
                         present: bool = True, **kw) -> "SimBlockDevice":
        """Register a disk/partition; when present=False it is hidden until a
        SCSI rescan reveals it (the classic disk-missing workflow)."""
        dev = SimBlockDevice(name, size, dev_type, present=present, **kw)
        if present:
            self.block_devices[name] = dev
        else:
            dev.present = False
            self.hidden_block_devices[name] = dev
        return dev

    def reveal_hidden_disks(self, after_reboot: bool = False) -> list[str]:
        """A SCSI rescan / rescan-scsi-bus.sh makes pending disks appear.

        Two sources are drained: (1) locally pre-seeded hidden_block_devices (the
        classic single-engine disk-missing flow), and (2) the cross-technology
        VMware bridge — disks hot-added in the VMware simulator for THIS lab
        session. Bridge disks flagged requires_reboot stay invisible to a plain
        rescan and only appear once `after_reboot` is True (Scenario B)."""
        revealed = []
        self.disk_rescanned = True
        for name, dev in list(self.hidden_block_devices.items()):
            if getattr(dev, "needs_reboot", False) and not after_reboot:
                continue
            dev.present = True
            self.block_devices[name] = dev
            del self.hidden_block_devices[name]
            revealed.append(name)
        revealed.extend(self._reveal_bridge_disks(after_reboot=after_reboot))
        return revealed

    def _reveal_bridge_disks(self, after_reboot: bool = False) -> list[str]:
        """Pull disks hot-added in the VMware simulator for this lab session."""
        if not self.session_id:
            return []
        try:
            from .vmware_bridge import consume_revealed_disks
        except Exception:
            return []
        revealed = []
        for disk in consume_revealed_disks(self.session_id, after_reboot=after_reboot):
            dev = disk.get("dev") or "/dev/sdc"
            size = f"{int(disk.get('size_gb', 50))}G"
            # The disk arrives bare (no partition table / no LVM metadata) — the
            # operator must pvcreate/vgextend/lvextend to actually use it.
            self.block_devices[dev] = SimBlockDevice(dev, size, "disk", present=True)
            self.hidden_block_devices.pop(dev, None)
            revealed.append(dev)
        revealed.extend(self._reveal_aws_bridge_volumes())
        return revealed

    def _reveal_aws_bridge_volumes(self) -> list[str]:
        """Pull EBS volumes attached in the AWS console for this lab session
        (AWS console → Linux terminal chain, mirrors the VMware disk train)."""
        if not self.session_id:
            return []
        try:
            from .aws_bridge import consume_volume_events
        except Exception:
            return []
        revealed = []
        for event in consume_volume_events(self.session_id):
            dev = event.get("device") or "/dev/sdf"
            size = f"{int(event.get('size_gb', 20))}G"
            self.block_devices[dev] = SimBlockDevice(dev, size, "disk", present=True)
            self.hidden_block_devices.pop(dev, None)
            revealed.append(dev)
        return revealed

    def reveal_bridge_nic(self) -> bool:
        """A rescan / ifup surfaces a NIC hot-added in VMware for this session."""
        if not self.session_id:
            return False
        try:
            from .vmware_bridge import consume_pending_nic
        except Exception:
            return False
        nic = consume_pending_nic(self.session_id)
        if not nic:
            return False
        ip = nic.get("ip", "10.0.0.30/24")
        name = f"eth{len(self.network_ifs) - 1}"  # lo + eth0 already present → eth1
        self.network_ifs[name] = {"up": True, "addrs": [ip]}
        return True

    def reveal_ansible_services(self) -> list[str]:
        """Cross-tech read: fold in services an AWX playbook configured for this
        lab session (ANSIBLE(AWX) → LINUX chain). Drains the shared bridge and,
        for each service the playbook ran to success, installs its package
        (so `rpm -q` sees it and its config lands on disk), registers the unit,
        and starts/enables it per the recorded intent — so the terminal's
        `systemctl is-active <svc>` reports `active` after (and only after) the
        playbook has run in AWX. Additive + fail-closed: with nothing recorded
        this is a no-op and the service stays inactive/unknown. Returns the list
        of service names revealed (newly converged) this call."""
        if not self.session_id:
            return []
        try:
            from .vmware_bridge import consume_ansible_results
        except Exception:
            return []
        revealed: list[str] = []
        for result in consume_ansible_results(self.session_id):
            service = result.get("service")
            if not service:
                continue
            # 1) Install the package the playbook installed (idempotent) so the
            #    config file + binaries + unit exist just as a real install would.
            if result.get("installed", True):
                pkg = result.get("package") or service
                if not self.is_package_installed(pkg):
                    try:
                        self.install_package(pkg)
                    except Exception:
                        pass
                # Unknown-to-catalog service still needs a queryable unit.
                if service not in self.services:
                    self.register_package_service(service)
            # 2) Write the config the playbook rendered, if it supplied one and
            #    the install did not already lay one down.
            cfg_path = result.get("config_path")
            if cfg_path:
                content = result.get("config_content") or ""
                if content or not self.file_exists(cfg_path):
                    self.write_file(cfg_path, content)
            # 3) Converge the unit's runtime state to what the playbook asserts.
            svc = self.services.get(service)
            if svc is None:
                svc = SimService(service, description=f"{service} (configured by Ansible)")
                self.services[service] = svc
            if result.get("started", True):
                svc.active = "active"
                svc.sub_state = "running"
            if result.get("enabled", True):
                svc.enabled = "enabled"
            revealed.append(service)
        return revealed

    def publish_workload_to_monitoring(self, service: str, *, port: int = 9100,
                                       job: str = "node") -> bool:
        """Cross-tech write: expose a Linux service as a Prometheus scrape target
        for the monitoring engine (WORKLOAD → MONITORING chain). The workload's
        `up` value is read from the REAL service state — active → up=1, otherwise
        up=0 — so a stopped service correctly scrapes DOWN and monitoring never
        fabricates a healthy target. Returns True if a record was published.
        Fail-closed: an unknown unit is not published at all (no target)."""
        if not self.session_id:
            return False
        svc = self.services.get(service)
        if svc is None:
            return False
        try:
            from .vmware_bridge import record_workload
        except Exception:
            return False
        instance = f"{self.hostname}:{port}"
        record_workload(self.session_id, {
            "name": service,
            "up": svc.active == "active",
            "job": job,
            "instance": instance,
            "port": port,
        })
        return True

    def recover_from_vmware_reset(self) -> bool:
        """If the guest was hung and VMware reset it for this session, recover."""
        if not self.server_hung or not self.session_id:
            return False
        try:
            from .vmware_bridge import was_vm_reset
        except Exception:
            return False
        if was_vm_reset(self.session_id):
            self.server_hung = False
            return True
        return False

    def find_block_device(self, ref: str) -> "SimBlockDevice | None":
        """Resolve a device by /dev path, UUID=, or bare UUID."""
        if not ref:
            return None
        if ref.startswith("UUID="):
            ref = ref.split("=", 1)[1].strip('"')
        if ref in self.block_devices:
            return self.block_devices[ref]
        for dev in self.block_devices.values():
            if dev.uuid and dev.uuid == ref:
                return dev
        return None

    def _mkdir(self, path: str) -> None:
        self.vfs[path] = {"type": "dir", "entries": {}}

    def _write_file(self, path: str, content: str, mode: str = "644") -> None:
        self.vfs[path] = {"type": "file", "content": content, "mode": mode, "owner": "root", "group": "root"}

    def resolve_path(self, path: str) -> str:
        if not path:
            return self.cwd
        if path.startswith("/"):
            base = path
        else:
            base = self.cwd.rstrip("/") + "/" + path if self.cwd != "/" else "/" + path
        parts = []
        for p in base.split("/"):
            if p == "" or p == ".":
                continue
            if p == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        return "/" + "/".join(parts) if parts else "/"

    def read_file(self, path: str) -> str | None:
        ap = self.resolve_path(path)
        node = self.vfs.get(ap)
        if isinstance(node, dict) and node.get("type") == "file":
            return node.get("content", "")
        return None

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        ap = self.resolve_path(path)
        parent = "/".join(ap.split("/")[:-1]) or "/"
        name = ap.split("/")[-1]
        if parent not in self.vfs:
            self._mkdir(parent)
        parent_node = self.vfs.get(parent)
        if isinstance(parent_node, dict) and parent_node.get("type") == "dir":
            parent_node.setdefault("entries", {})[name] = ap
        existing = self.vfs.get(ap)
        if append and isinstance(existing, dict) and existing.get("type") == "file":
            content = existing.get("content", "") + content
        self._write_file(ap, content)

    def list_dir(self, path: str) -> list[str] | None:
        ap = self.resolve_path(path)
        node = self.vfs.get(ap)
        if isinstance(node, dict) and node.get("type") == "dir":
            entries = list(node.get("entries", {}).keys())
            if ap == "/":
                return sorted(set(entries + [k.split("/")[-1] for k in self.vfs if k.count("/") == 1 and k != "/"]))
            return sorted(entries)
        if isinstance(node, dict) and node.get("type") == "file":
            return None
        # implicit dirs from file paths
        prefix = ap.rstrip("/") + "/"
        found = set()
        for p in self.vfs:
            if p.startswith(prefix):
                rest = p[len(prefix):]
                found.add(rest.split("/")[0])
        return sorted(found) if found else None

    def file_exists(self, path: str) -> bool:
        ap = self.resolve_path(path)
        return ap in self.vfs

    def is_dir(self, path: str) -> bool:
        ap = self.resolve_path(path)
        node = self.vfs.get(ap)
        if isinstance(node, dict):
            return node.get("type") == "dir"
        return self.list_dir(ap) is not None and not self.read_file(ap)

    def sync_passwd_files(self) -> None:
        lines_p = []
        for u in sorted(self.users.values(), key=lambda x: x.uid):
            lines_p.append(f"{u.username}:x:{u.uid}:{u.gid}:{u.gecos}:{u.home}:{u.shell}")
            # Ensure each user has a primary group entry.
            gname = u.username
            if gname not in self.groups:
                self.groups[gname] = [u.gid]
        self._write_file("/etc/passwd", "\n".join(lines_p) + "\n")

        # Build /etc/group from the full group table, listing supplementary
        # member usernames (uid != group's own gid) as real /etc/group does.
        uid_to_name = {u.uid: u.username for u in self.users.values()}
        gid_lines = []
        for gname, gids in self.groups.items():
            primary_gid = gids[0] if gids else 0
            members = []
            for uid in gids[1:] if len(gids) > 1 else []:
                member_name = uid_to_name.get(uid)
                if member_name and member_name != gname:
                    members.append(member_name)
            gid_lines.append((primary_gid, f"{gname}:x:{primary_gid}:{','.join(members)}"))
        gid_lines.sort(key=lambda x: x[0])
        self._write_file("/etc/group", "\n".join(line for _, line in gid_lines) + "\n")

    def register_package_service(self, pkg: str) -> list[str]:
        """When a package is installed, register the systemd unit(s) it ships as
        known (stopped, disabled) so a follow-up systemctl start/enable/status of
        that service works realistically. Returns the unit names registered.

        Existing units are left untouched (an install never stops a running
        service), and packages with no associated unit are a no-op.
        """
        units = PACKAGE_SERVICES.get(pkg)
        if not units:
            return []
        registered = []
        for name, desc in units:
            if name in self.services:
                continue
            self.services[name] = SimService(
                name,
                active="inactive",
                enabled="disabled",
                description=desc,
                loaded="loaded",
                sub_state="dead",
                unit_file=f"[Unit]\nDescription={desc}\n",
            )
            registered.append(name)
        return registered

    def catalog_nvra(self, name: str) -> str:
        """version-release.arch NVRA for a catalog package (or a 1.0.0 stub)."""
        spec = PACKAGE_CATALOG.get(resolve_package_name(name))
        if spec:
            return f"{name}-{spec.version}-{spec.release}.{spec.arch}"
        return f"{name}-1.0.0-1.el9.x86_64"

    def resolve_install_plan(self, pkg: str) -> list[str]:
        """Recursively resolve `pkg` and its deps into an install order (deps
        first), canonicalising aliases and skipping already-installed packages.
        Returns catalog names in the order they should be installed."""
        order: list[str] = []
        seen: set[str] = set()

        def visit(name: str) -> None:
            canon = resolve_package_name(name)
            if canon in seen:
                return
            seen.add(canon)
            spec = PACKAGE_CATALOG.get(canon)
            if spec:
                for dep in spec.deps:
                    visit(dep)
            if canon in self.installed_packages:
                return
            if canon not in order:
                order.append(canon)

        visit(pkg)
        return order

    def install_package(self, pkg: str) -> list[str]:
        """Really install `pkg`: resolve deps recursively (skipping installed
        ones), record the catalog version in installed_packages, write each
        config file to the sim FS, register the systemd unit(s), create the log
        files, and record the binaries so which/command -v/PATH resolve.

        Returns the list of package names newly installed (deps first, target
        last). Packages not in the catalog still get recorded (with a stub
        version + their unit via register_package_service) so unknown installs
        remain queryable, matching the previous best-effort behaviour.
        """
        plan = self.resolve_install_plan(pkg)
        installed: list[str] = []
        for name in plan:
            spec = PACKAGE_CATALOG.get(name)
            self.installed_packages[name] = self.catalog_nvra(name)
            if spec:
                for path, content in spec.config_files.items():
                    if not self.file_exists(path):
                        self.write_file(path, content)
                self.register_package_service(name)
                for bname, bpath in spec.binaries:
                    self.installed_binaries[bname] = bpath
                for logpath in spec.log_files:
                    if not self.file_exists(logpath):
                        self.write_file(logpath, "")
            else:
                # Unknown package: keep the old best-effort unit registration so
                # a follow-up systemctl start/status still works if it ships one.
                self.register_package_service(name)
            installed.append(name)
        return installed

    def is_package_installed(self, pkg: str) -> bool:
        return resolve_package_name(pkg) in self.installed_packages or pkg in self.installed_packages

    def resolve_binary(self, name: str) -> str | None:
        """Absolute path of an installed command, or None. Consults the base
        coreutils/base-system binaries always present plus anything a package
        install recorded. `which`/`command -v`/`type`/PATH share this."""
        binaries = getattr(self, "installed_binaries", None)
        if binaries and name in binaries:
            return binaries[name]
        return BASE_BINARIES.get(name)

    def add_user(self, username: str, home: str | None = None, shell: str = "/bin/bash") -> tuple[bool, str]:
        if username in self.users:
            return False, f"useradd: user '{username}' already exists"
        uid = self.uid_counter
        self.uid_counter += 1
        home = home or f"/home/{username}"
        self.users[username] = SimUser(username, uid, uid, home, shell, username)
        self._mkdir(home)
        self.sync_passwd_files()
        return True, ""

    def set_prompt_user(self, username: str) -> bool:
        if username not in self.users:
            return False
        self.current_user = username
        u = self.users[username]
        self.cwd = u.home
        self.env["USER"] = username
        self.env["HOME"] = u.home
        return True

    def clone_for_host(self, hostname: str) -> RHELOSState:
        """Companion host shares scenario preset but different hostname."""
        other = RHELOSState(hostname=hostname, scenario_slug=self.scenario_slug)
        other.vfs = copy.deepcopy(self.vfs)
        other.users = copy.deepcopy(self.users)
        other.groups = copy.deepcopy(self.groups)
        other.services = copy.deepcopy(self.services)
        other.processes = copy.deepcopy(self.processes)
        other.dmesg_extra = list(self.dmesg_extra)
        other.uid_counter = self.uid_counter
        other.pid_counter = self.pid_counter
        other.lvm = copy.deepcopy(self.lvm)
        other.firewall = copy.deepcopy(self.firewall)
        other.network_ifs = copy.deepcopy(self.network_ifs)
        other.block_devices = copy.deepcopy(self.block_devices)
        other.hidden_block_devices = copy.deepcopy(self.hidden_block_devices)
        other.swaps = copy.deepcopy(self.swaps)
        other.mounts = copy.deepcopy(self.mounts)
        other.selinux_mode = self.selinux_mode
        other.selinux_ports = copy.deepcopy(self.selinux_ports)
        other.selinux_fcontexts = copy.deepcopy(self.selinux_fcontexts)
        other.file_contexts = copy.deepcopy(self.file_contexts)
        other.emergency_mode = self.emergency_mode
        other.fstab_valid = self.fstab_valid
        other.editor = None
        other._write_file("/etc/hostname", hostname + "\n")
        other.env["HOSTNAME"] = hostname
        return other

    def set_hostname(self, hostname: str) -> None:
        """Rewrite the hostname everywhere it surfaces — the shell prompt, the
        HOSTNAME env var, /etc/hostname and /etc/hosts. Used by the unified-server
        model so a VMware VM's console shows that VM's hostname, not 'rhel-sim'."""
        if not hostname:
            return
        short = hostname.split(".")[0]
        self.hostname = short
        self.env["HOSTNAME"] = short
        self._write_file("/etc/hostname", short + "\n")
        self._write_file(
            "/etc/hosts",
            "127.0.0.1 localhost localhost.localdomain\n::1 localhost\n"
            f"127.0.1.1 {hostname} {short}\n",
        )

    def set_hardware(self, cpu: int | None = None, mem_mb: int | None = None) -> None:
        """Seed the CPU count / RAM and refresh the /proc pseudo-files that expose
        them, so nproc/lscpu/free/`cat /proc/{cpuinfo,meminfo}` all agree with the
        VMware VM the learner sees."""
        if cpu:
            try:
                self.cpu_count = max(1, int(cpu))
            except (TypeError, ValueError):
                pass
        if mem_mb:
            try:
                self.mem_mb = max(256, int(mem_mb))
            except (TypeError, ValueError):
                pass
        self._write_file("/proc/cpuinfo", self._proc_cpuinfo())
        self._write_file("/proc/meminfo", self._proc_meminfo())

    def set_host_ip(self, ip: str, iface: str = "eth0") -> None:
        if iface not in self.network_ifs:
            self.network_ifs[iface] = {"up": True, "addrs": []}
        self.network_ifs[iface]["addrs"] = [f"{ip}/24" if "/" not in ip else ip]

    def append_host_ip(self, ip: str, iface: str = "eth0") -> None:
        if iface not in self.network_ifs:
            self.network_ifs[iface] = {"up": True, "addrs": []}
        addr = f"{ip}/24" if "/" not in ip else ip
        if addr not in self.network_ifs[iface]["addrs"]:
            self.network_ifs[iface]["addrs"].append(addr)

    def format_ip_addr(self) -> str:
        lines = []
        for idx, (name, data) in enumerate(self.network_ifs.items(), 1):
            flags = "LOOPBACK,UP" if name == "lo" else "BROADCAST,UP"
            if not data.get("up", True):
                flags = "BROADCAST"
            mtu = 65536 if name == "lo" else 1500
            lines.append(f"{idx}: {name}: <{flags}> mtu {mtu}")
            for addr in data.get("addrs", []):
                if name == "lo":
                    lines.append(f"    inet {addr.split('/')[0]}/8 scope host {name}")
                else:
                    ip, _, prefix = addr.partition("/")
                    lines.append(f"    inet {ip}/{prefix or '24'} brd {ip.rsplit('.', 1)[0]}.255 scope global {name}")
        return "\n".join(lines)
