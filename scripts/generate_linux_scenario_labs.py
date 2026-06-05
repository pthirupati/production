#!/usr/bin/env python3
"""Generate Linux troubleshooting scenario lab files from curated topic map."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "scenarios" / "linux"
SHARED = Path(__file__).resolve().parent.parent / "scenarios" / "shared"

BASE_DOCKER = """FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y {packages} && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab
{extra_run}
COPY check.sh /opt/fixitlab/check.sh
{setup_copy}RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "{cmd}"]
"""

SCENARIOS = [
    {
        "slug": "fs-readonly-remount",
        "title": "Filesystem Stuck Read-Only",
        "category": "Storage",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q4 readonly FS — remount rw, dmesg, fs errors",
        "packages": "vim nano less procps python3 util-linux",
        "extra_run": "RUN mkdir /data && echo test > /data/file.txt && mount -o remount,ro / 2>/dev/null || touch /data/.ro && chmod 555 /data",
        "setup_copy": "",
        "cmd": "mount -o remount,ro /data 2>/dev/null || true; exec /bin/bash",
        "check": """#!/bin/bash
mount | grep ' /data ' | grep -q rw && test -w /data/file.txt && echo PASS && exit 0
echo FAIL: remount /data read-write: mount -o remount,rw /data
exit 1""",
        "description": "Applications fail with 'Read-only file system'. /data was remounted read-only after errors. Remount read-write and verify writes work.",
        "objectives": ["Identify read-only mount with mount/findmnt", "Remount rw safely", "Verify application can write"],
        "hints": [
            (1, 10, "Run `findmnt /data` and `dmesg | tail`"),
            (2, 20, "`mount -o remount,rw /data` then `touch /data/test`"),
        ],
    },
    {
        "slug": "inode-exhausted",
        "title": "Inode Exhaustion on /var/cache",
        "category": "Storage",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q8 inodes — df -i, delete tiny files",
        "packages": "vim nano less procps python3 e2fsprogs",
        "extra_run": """RUN mkdir -p /var/cache/app && for i in $(seq 1 800); do touch /var/cache/app/f$i; done""",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
AVAIL=$(df -i /var/cache 2>/dev/null | tail -1 | awk '{print $4}')
[ "${AVAIL:-0}" -gt 50 ] && echo PASS && exit 0
echo FAIL: free inodes on /var/cache (need >50). Delete unused files under /var/cache/app
exit 1""",
        "description": "Cannot create new files though df shows space available. Inodes on /var/cache are exhausted.",
        "objectives": ["Check inode usage with df -i", "Find directories with many small files", "Delete unneeded files to free inodes"],
        "hints": [
            (1, 10, "`df -i /var/cache` — look at IUse%"),
            (2, 20, "`find /var/cache/app -type f | wc -l` — remove old cache files"),
        ],
    },
    {
        "slug": "disk-full-open-deleted-file",
        "title": "Disk Full — Deleted File Still Open",
        "category": "Storage",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q6 df vs du — lsof /proc/fd, restart process",
        "packages": "vim nano less procps python3 lsof",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh; exec /bin/bash",
        "check": """#!/bin/bash
USE=$(df /var/log | tail -1 | awk '{print $5}' | tr -d '%')
[ "$USE" -lt 85 ] && echo PASS && exit 0
echo FAIL: /var/log still full — find deleted-but-open files: lsof +L1 /var/log
exit 1""",
        "description": "df shows /var/log 100% full but du sums to much less. A process holds a deleted log file open.",
        "objectives": ["Compare df vs du", "Find open deleted files with lsof", "Stop process or truncate via /proc/PID/fd"],
        "hints": [
            (1, 15, "`lsof +L1 /var/log` or `lsof | grep deleted`"),
            (2, 25, "Kill the holder PID or `>: /proc/PID/fd/N`"),
        ],
        "setup_sh": """#!/bin/bash
mkdir -p /var/log
fallocate -l 80M /var/log/app.log 2>/dev/null || dd if=/dev/zero of=/var/log/app.log bs=1M count=80
tail -f /var/log/app.log >/dev/null 2>&1 &
echo $! >/var/run/logholder.pid
rm -f /var/log/app.log
""",
    },
    {
        "slug": "cron-access-denied",
        "title": "User Not Allowed to Run Cron",
        "category": "Scheduling",
        "difficulty": "easy",
        "time_limit": 600,
        "topics": "Q193 cron.allow/deny",
        "packages": "vim nano less cron procps python3",
        "extra_run": "RUN echo 'appuser' >> /etc/cron.deny && useradd -m appuser",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! grep -q '^appuser$' /etc/cron.deny 2>/dev/null && echo PASS && exit 0
echo FAIL: remove appuser from /etc/cron.deny or add to /etc/cron.allow
exit 1""",
        "description": "appuser gets 'You are not allowed to run crontab' when scheduling jobs.",
        "objectives": ["Check /etc/cron.deny and cron.allow", "Allow appuser to use cron"],
        "hints": [(1, 10, "Remove appuser from /etc/cron.deny")],
    },
    {
        "slug": "ssh-key-permissions",
        "title": "SSH Key Auth Fails — Bad .ssh Permissions",
        "category": "SSH / Security",
        "difficulty": "easy",
        "time_limit": 600,
        "topics": "Q42 key auth — chmod 700 ~/.ssh 600 authorized_keys",
        "packages": "openssh-client vim nano less procps python3",
        "extra_run": """RUN useradd -m dev && mkdir -p /home/dev/.ssh && echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC test' > /home/dev/.ssh/authorized_keys && chmod 777 /home/dev/.ssh && chmod 644 /home/dev/.ssh/authorized_keys && chown -R dev:dev /home/dev/.ssh""",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
P1=$(stat -c %a /home/dev/.ssh)
P2=$(stat -c %a /home/dev/.ssh/authorized_keys)
[ "$P1" = "700" ] && [ "$P2" = "600" ] && echo PASS && exit 0
echo FAIL: fix ~/.ssh to 700 and authorized_keys to 600
exit 1""",
        "description": "Key-based SSH rejected for dev. Permissions on ~/.ssh are too open.",
        "objectives": ["Fix .ssh directory to 700", "Fix authorized_keys to 600"],
        "hints": [(1, 15, "`chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys`")],
    },
    {
        "slug": "home-directory-ssh-denied",
        "title": "SSH Rejects Writable Home Directory",
        "category": "SSH / Security",
        "difficulty": "easy",
        "time_limit": 600,
        "topics": "Q38 home dir perms — must not be group/world writable",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN useradd -m ops && chmod 777 /home/ops",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
P=$(stat -c %a /home/ops)
[ "$P" = "755" ] || [ "$P" = "750" ] || [ "$P" = "700" ] && echo PASS && exit 0
echo FAIL: chmod 755 /home/ops (remove world-writable)
exit 1""",
        "description": "User ops cannot SSH. Home directory is world-writable which OpenSSH rejects.",
        "objectives": ["Check home permissions", "Set safe mode 755 or 750"],
        "hints": [(1, 10, "`chmod 755 /home/ops`")],
    },
    {
        "slug": "nsswitch-login-delay",
        "title": "Slow SSH Login — NSS/DNS Delay",
        "category": "Authentication",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q169 login delay — nsswitch, UseDNS no",
        "packages": "vim nano less procps python3 libnss-myhostname2 2>/dev/null || true",
        "extra_run": "RUN sed -i 's/^hosts:.*/hosts: files myhostname dns/' /etc/nsswitch.conf 2>/dev/null || echo 'hosts: files dns' > /etc/nsswitch.conf",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
grep -q '^hosts:.*files' /etc/nsswitch.conf && ! grep -q 'myhostname' /etc/nsswitch.conf && echo PASS && exit 0
echo FAIL: fix /etc/nsswitch.conf hosts line to: hosts: files dns
exit 1""",
        "description": "SSH password prompt takes 30+ seconds. Misconfigured nsswitch causes lookup timeouts.",
        "objectives": ["Inspect /etc/nsswitch.conf", "Fix hosts line order", "Optionally set UseDNS no in sshd_config"],
        "hints": [(1, 15, "Set `hosts: files dns` in /etc/nsswitch.conf")],
    },
    {
        "slug": "suid-binary-broken",
        "title": "SUID Binary Not Working",
        "category": "Permissions",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q19 SUID — chmod u+s",
        "packages": "vim nano less procps python3",
        "extra_run": """RUN echo '#!/bin/bash\ncat /etc/shadow' > /usr/local/bin/reads-shadow && chmod 755 /usr/local/bin/reads-shadow && chown root:root /usr/local/bin/reads-shadow""",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
PERM=$(stat -c %a /usr/local/bin/reads-shadow)
[[ "$PERM" == *4* ]] || stat -c %A /usr/local/bin/reads-shadow | grep -q s && echo PASS && exit 0
echo FAIL: chmod u+s /usr/local/bin/reads-shadow (SUID bit)
exit 1""",
        "description": "A custom privileged helper lost its SUID bit and no longer runs with elevated privileges.",
        "objectives": ["Understand SUID with ls -l", "Restore chmod u+s on the binary"],
        "hints": [(1, 15, "`chmod u+s /usr/local/bin/reads-shadow`")],
    },
    {
        "slug": "broken-symlink-chain",
        "title": "Broken Symbolic Link Chain",
        "category": "Filesystem",
        "difficulty": "easy",
        "time_limit": 600,
        "topics": "Q17 soft links — readlink, ln -sf",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN mkdir -p /opt/app/bin && echo '#!/bin/bash\necho ok' > /opt/app/bin/real.sh && chmod +x /opt/app/bin/real.sh && ln -sf /opt/app/bin/wrong.sh /usr/local/bin/apptool",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
/usr/local/bin/apptool >/dev/null 2>&1 && echo PASS && exit 0
echo FAIL: fix symlink: ln -sf /opt/app/bin/real.sh /usr/local/bin/apptool
exit 1""",
        "description": "Application launcher /usr/local/bin/apptool is a broken symlink.",
        "objectives": ["Use readlink -f to trace links", "Recreate symlink to correct target"],
        "hints": [(1, 10, "`readlink /usr/local/bin/apptool`")],
    },
    {
        "slug": "etc-hosts-breaks-app",
        "title": "/etc/hosts Breaks Application",
        "category": "Networking",
        "difficulty": "easy",
        "time_limit": 600,
        "topics": "Q62 /etc/hosts vs resolv.conf",
        "packages": "vim nano less procps python3 curl",
        "extra_run": "RUN echo '127.0.0.1 api.internal.wrong' >> /etc/hosts",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! grep -q 'api.internal.wrong' /etc/hosts && echo PASS && exit 0
echo FAIL: remove or fix wrong api.internal entry in /etc/hosts
exit 1""",
        "description": "App cannot reach api.internal — /etc/hosts overrides DNS with wrong address.",
        "objectives": ["Compare /etc/hosts and getent hosts", "Fix or remove bad entry"],
        "hints": [(1, 10, "`getent hosts api.internal`")],
    },
    {
        "slug": "chrony-not-syncing",
        "title": "NTP/Chrony Not Synchronizing",
        "category": "Services",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q49 NTP port 123 — chrony sources",
        "packages": "chrony vim nano less procps python3",
        "extra_run": "RUN echo 'pool invalid.ntp.example iburst' >> /etc/chrony/chrony.conf",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! grep -q 'invalid.ntp.example' /etc/chrony/chrony.conf && echo PASS && exit 0
echo FAIL: remove invalid pool from /etc/chrony/chrony.conf and restart chrony
exit 1""",
        "description": "System clock drifts. chrony configured with invalid time server.",
        "objectives": ["Check chronyc sources", "Fix chrony.conf pool/server", "Restart chrony"],
        "hints": [(1, 15, "Use `pool pool.ntp.org iburst`")],
    },
    {
        "slug": "dpkg-interrupted",
        "title": "APT/DPKG Database Interrupted",
        "category": "Package Management",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q117 package DB — dpkg --configure -a, rm /var/lib/dpkg/lock*",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN touch /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! [ -f /var/lib/dpkg/lock-frontend ] && dpkg --audit 2>/dev/null | grep -qv . && echo PASS && exit 0
! [ -f /var/lib/dpkg/lock-frontend ] && echo PASS && exit 0
echo FAIL: rm /var/lib/dpkg/lock* && dpkg --configure -a
exit 1""",
        "description": "apt/dpkg fails with lock errors after interrupted upgrade.",
        "objectives": ["Remove stale dpkg locks", "Run dpkg --configure -a", "Verify apt works"],
        "hints": [(1, 20, "`rm /var/lib/dpkg/lock* && dpkg --configure -a`")],
    },
    {
        "slug": "user-invalid-primary-group",
        "title": "User Has Invalid Primary Group",
        "category": "User Management",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q21 primary group — usermod -g",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN groupadd devteam && useradd -m -g 99999 baduser 2>/dev/null || useradd -m baduser && sed -i 's/:99999:/:99999:/' /etc/passwd || sed -i '/^baduser:/s/:[0-9]*:/:99999:/' /etc/passwd",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
GID=$(getent passwd baduser | cut -d: -f4)
getent group "$GID" >/dev/null && echo PASS && exit 0
echo FAIL: usermod -g devteam baduser (or create missing group)
exit 1""",
        "description": "User baduser cannot login — GID in /etc/passwd does not exist in /etc/group.",
        "objectives": ["Compare passwd and group entries", "Fix primary group with usermod -g"],
        "hints": [(1, 15, "`getent passwd baduser` vs `getent group GID`")],
    },
    {
        "slug": "account-locked-faillock",
        "title": "Account Locked After Failed Logins",
        "category": "Authentication",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q33 faillock — faillock --user --reset",
        "packages": "libpam-modules libpam-modules-bin vim nano less procps python3",
        "extra_run": "RUN useradd -m lockeduser && faillock --user lockeduser --deny 2>/dev/null || passwd -l lockeduser",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
passwd -S lockeduser 2>/dev/null | grep -q P && echo PASS && exit 0
faillock --user lockeduser 2>/dev/null | grep -q 'when' && { echo FAIL: faillock --user lockeduser --reset; exit 1; }
passwd -u lockeduser 2>/dev/null; passwd -S lockeduser | grep -q P && echo PASS && exit 0
echo FAIL: unlock with faillock --reset or passwd -u
exit 1""",
        "description": "lockeduser account disabled after brute-force lockout (faillock/passwd -l).",
        "objectives": ["Check faillock/passwd -S", "Reset lockout and unlock account"],
        "hints": [(1, 15, "`faillock --user lockeduser --reset` or `passwd -u lockeduser`")],
    },
    {
        "slug": "fstab-nfs-hung-mount",
        "title": "fstab NFS Entry Causes df Hang",
        "category": "Storage / NFS",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q10 df hang — noserver, nobootwait, fix fstab",
        "packages": "vim nano less procps python3 nfs-common",
        "extra_run": "RUN mkdir -p /mnt/nfs && echo '192.0.2.99:/export /mnt/nfs nfs defaults,_netdev 0 0' >> /etc/fstab",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
grep '/mnt/nfs' /etc/fstab | grep -qE 'nobootwait|nofail' && echo PASS && exit 0
! grep -q '192.0.2.99' /etc/fstab && echo PASS && exit 0
echo FAIL: comment out bad NFS line or add nfs nobootwait,nofail,soft,timeo=5
exit 1""",
        "description": "df and ls hang on /mnt/nfs. Unreachable NFS server in /etc/fstab blocks mount lookups.",
        "objectives": ["Identify stale NFS in fstab", "Add nofail/nobootwait or remove entry", "Use timeout mount options"],
        "hints": [(1, 20, "Comment bad line or use `nofail,nobootwait,soft,timeo=5`")],
    },
    {
        "slug": "acl-permission-denied",
        "title": "ACL Required for Shared Directory",
        "category": "Permissions / ACL",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q19 ACL — setfacl -m u:user:rx",
        "packages": "acl vim nano less procps python3",
        "extra_run": "RUN groupadd shared && useradd -m -G shared alice && useradd -m -G shared bob && mkdir -p /srv/shared && chown root:shared /srv/shared && chmod 770 /srv/shared",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
getfacl /srv/shared 2>/dev/null | grep -q 'user:alice' && echo PASS && exit 0
echo FAIL: setfacl -m u:alice:rwx /srv/shared
exit 1""",
        "description": "User alice cannot access /srv/shared despite group membership. ACL entry missing.",
        "objectives": ["Check getfacl output", "Grant ACL with setfacl", "Verify access as alice"],
        "hints": [(1, 15, "`setfacl -m u:alice:rwx /srv/shared`")],
    },
    {
        "slug": "swap-disabled",
        "title": "Swap Disabled — Memory Pressure",
        "category": "Memory",
        "difficulty": "easy",
        "time_limit": 600,
        "topics": "Q147-Q148 swap — swapon, /etc/fstab",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN fallocate -l 256M /swapfile && chmod 600 /swapfile && mkswap /swapfile",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
swapon --show | grep -q swapfile && echo PASS && exit 0
echo FAIL: swapon /swapfile and add to /etc/fstab
exit 1""",
        "description": "OOM kills occurring. Swap file exists but is not activated.",
        "objectives": ["Check free -h and swapon --show", "Enable swap with swapon", "Persist in fstab"],
        "hints": [(1, 10, "`swapon /swapfile`")],
    },
    {
        "slug": "ssh-allowusers-block",
        "title": "AllowUsers Blocks SSH Login",
        "category": "SSH",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q39 Q40 AllowUsers/DenyUsers",
        "packages": "openssh-server vim nano less procps python3",
        "extra_run": "RUN useradd -m deploy && mkdir -p /var/run/sshd && echo 'AllowUsers adminonly' >> /etc/ssh/sshd_config.d/99-fixitlab.conf",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
grep -q 'AllowUsers.*deploy' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/* 2>/dev/null && echo PASS && exit 0
! grep -q 'AllowUsers adminonly' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/* 2>/dev/null && echo PASS && exit 0
echo FAIL: add deploy to AllowUsers or remove restrictive AllowUsers line
exit 1""",
        "description": "deploy user cannot SSH. AllowUsers directive permits only adminonly.",
        "objectives": ["grep AllowUsers in sshd_config", "Add deploy or fix directive", "sshd -t to validate"],
        "hints": [(1, 15, "Change to `AllowUsers adminonly deploy` or remove file")],
    },
    {
        "slug": "ext4-superblock-corrupt",
        "title": "ext4 Filesystem Needs fsck",
        "category": "Storage",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q7 ext fsck — e2fsck -y",
        "packages": "e2fsprogs vim nano less procps python3",
        "extra_run": "RUN mkdir -p /data && dd if=/dev/zero of=/data.img bs=1M count=100 && mkfs.ext4 /data.img && mount -o loop /data.img /data && echo corrupt > /data/.marker",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
mount /data 2>/dev/null
[ -f /data/.marker ] && echo PASS && exit 0
echo FAIL: umount /data; fsck.ext4 -y /data.img; mount /data.img /data
exit 1""",
        "description": "ext4 volume on /data fails to mount cleanly after unclean shutdown.",
        "objectives": ["Unmount filesystem", "Run fsck.ext4", "Remount and verify data"],
        "hints": [(1, 20, "`umount /data && fsck.ext4 -y /data.img`")],
        "setup_sh": """#!/bin/bash
umount /data 2>/dev/null || true
# Simulate dirty filesystem
tune2fs -c 1 /data.img 2>/dev/null || true
""",
    },
    {
        "slug": "umask-wrong-newfiles",
        "title": "Wrong umask — Insecure New Files",
        "category": "Permissions",
        "difficulty": "easy",
        "time_limit": 600,
        "topics": "Q24 umask — /etc/profile.d",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN echo 'umask 000' > /etc/profile.d/99-bad-umask.sh",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! grep -q 'umask 000' /etc/profile.d/99-bad-umask.sh 2>/dev/null && echo PASS && exit 0
echo FAIL: set umask 022 in /etc/profile.d/99-bad-umask.sh
exit 1""",
        "description": "New files created world-writable. Global umask set to 000 in profile.d.",
        "objectives": ["Check umask command", "Fix system umask to 022", "Verify new file permissions"],
        "hints": [(1, 10, "Change to `umask 022`")],
    },
    {
        "slug": "limits-nproc-exceeded",
        "title": "nproc Limit Prevents Forking",
        "category": "Performance",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q140 limits.conf — ulimit -u",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN echo '* soft nproc 5' > /etc/security/limits.d/99-nproc.conf && echo '* hard nproc 10' >> /etc/security/limits.d/99-nproc.conf",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! grep -q 'nproc 5' /etc/security/limits.d/99-nproc.conf 2>/dev/null && echo PASS && exit 0
grep -q 'nproc 1024' /etc/security/limits.d/99-nproc.conf 2>/dev/null && echo PASS && exit 0
echo FAIL: raise nproc limits in /etc/security/limits.d/99-nproc.conf
exit 1""",
        "description": "Applications fail with 'cannot fork' or 'resource temporarily unavailable'. nproc limit too low.",
        "objectives": ["Check ulimit -u", "Fix /etc/security/limits.d/", "Verify new shell limits"],
        "hints": [(1, 15, "Set nproc soft/hard to 1024 or remove restrictive file")],
    },
    {
        "slug": "sticky-bit-tmp-issue",
        "title": "Sticky Bit Missing on Shared /tmp/app",
        "category": "Permissions",
        "difficulty": "easy",
        "time_limit": 600,
        "topics": "Q19 sticky bit — chmod +t",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN mkdir -p /tmp/app && chmod 777 /tmp/app && useradd -m u1 && useradd -m u2",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
stat -c %a /tmp/app | grep -q 1777 && echo PASS && exit 0
[ "$(stat -c %a /tmp/app)" = "1777" ] && echo PASS && exit 0
PERM=$(stat -c %A /tmp/app)
echo "$PERM" | grep -q 't' && echo PASS && exit 0
echo FAIL: chmod 1777 /tmp/app (sticky bit)
exit 1""",
        "description": "Users delete each other's files in shared /tmp/app. Sticky bit not set.",
        "objectives": ["Understand sticky bit on world-writable dirs", "Apply chmod +t or 1777"],
        "hints": [(1, 10, "`chmod 1777 /tmp/app` or `chmod +t /tmp/app`")],
    },
]

# Advanced multi-step labs (LVM, PAM, bind mounts, repair, networking)
COMPLEX_SCENARIOS = [
    {
        "slug": "lvm-add-pv-extend",
        "title": "LVM Full — Add New PV and Extend LV",
        "category": "Storage / LVM",
        "difficulty": "hard",
        "time_limit": 1800,
        "docker_privileged": True,
        "topics": "Q11-Q14 LVM — pvcreate, vgextend, lvextend, xfs_growfs",
        "packages": "lvm2 xfsprogs e2fsprogs util-linux parted kmod vim nano less procps python3",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
FAILED=0
pvs /dev/loop*p2 2>/dev/null | grep -q fixitlab || { echo "FAIL: add second disk to VG (pvcreate + vgextend)"; FAILED=1; }
SIZE=$(lvs --noheadings -o lv_size --units m --nosuffix fixitlab/datalv 2>/dev/null | tr -d ' ')
[ -n "$SIZE" ] && [ "${SIZE%%.*}" -ge 450 ] || { echo "FAIL: extend datalv to use new PV space (need >=450M)"; FAILED=1; }
mountpoint -q /data || mount /data 2>/dev/null || true
AVAIL=$(df -BM /data 2>/dev/null | tail -1 | awk '{print $4}' | tr -d M)
[ "${AVAIL:-0}" -ge 80 ] || { echo "FAIL: grow XFS on /data after lvextend (xfs_growfs)"; FAILED=1; }
[ $FAILED -eq 0 ] && echo PASS && exit 0
exit 1""",
        "description": "/data is 100% full. Volume group fixitlab has no free extents, but a new empty disk was attached and is not yet in the VG.",
        "objectives": ["Confirm VG is full with vgs/pvs", "Initialize new disk with pvcreate", "vgextend and lvextend datalv", "Run xfs_growfs /data"],
        "hints": [
            (1, 15, "`pvs` and `vgs` — second loop disk exists but is not a PV"),
            (2, 30, "`pvcreate /dev/loopXp2 && vgextend fixitlab /dev/loopXp2`"),
            (3, 45, "`lvextend -l +100%FREE /dev/fixitlab/datalv && xfs_growfs /data`"),
        ],
        "setup_sh": """#!/bin/bash
set -e
dd if=/dev/zero of=/var/disk1.img bs=1M count=400 status=none
dd if=/dev/zero of=/var/disk2.img bs=1M count=350 status=none
D1=$(losetup -f --show /var/disk1.img)
D2=$(losetup -f --show /var/disk2.img)
parted -s "$D1" mklabel gpt && parted -s "$D1" mkpart primary 1MiB 100%
parted -s "$D2" mklabel gpt && parted -s "$D2" mkpart primary 1MiB 100%
sleep 1
P1="${D1}p1"; [ -b "$P1" ] || P1="${D1}1"
P2="${D2}p1"; [ -b "$P2" ] || P2="${D2}1"
pvcreate -y "$P1"
vgcreate fixitlab "$P1"
lvcreate -y -l 100%FREE -n datalv fixitlab
mkfs.xfs /dev/fixitlab/datalv
mkdir -p /data && mount /dev/fixitlab/datalv /data
dd if=/dev/zero of=/data/fill bs=1M count=360 status=none
echo "Disk2 $P2 is unused — add to VG and extend datalv"
""",
    },
    {
        "slug": "lvm-pvmove-evacuate",
        "title": "LVM — Evacuate PV Before Disk Removal",
        "category": "Storage / LVM",
        "difficulty": "hard",
        "time_limit": 1800,
        "docker_privileged": True,
        "topics": "Q14 pvmove — migrate extents off failing PV",
        "packages": "lvm2 xfsprogs e2fsprogs util-linux parted kmod vim nano less procps python3",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
FAILED=0
# Old PV should have zero used extents after pvmove
USED=$(pvs --noheadings -o pv_used --units m --nosuffix 2>/dev/null | head -1 | tr -d ' ')
[ -z "$USED" ] || [ "${USED%%.*}" -le 4 ] || { echo "FAIL: pvmove data off old PV first (pv_used should be ~0)"; FAILED=1; }
mountpoint -q /data || mount /data 2>/dev/null || true
[ -f /data/important.db ] || { echo "FAIL: /data must remain mounted with data intact"; FAILED=1; }
vgdisplay fixitlab 2>/dev/null | grep -q 'PV Name' && echo "OK: VG healthy"
[ $FAILED -eq 0 ] && echo PASS && exit 0
exit 1""",
        "description": "Operations must retire /dev/loop disk1. LV datalv spans two PVs; evacuate all extents to disk2 with pvmove before vgreduce.",
        "objectives": ["Inspect pvs/lvs extent layout", "Run pvmove for old PV", "Verify PV is empty and data intact", "vgreduce old PV (optional)"],
        "hints": [
            (1, 20, "`pvs -o+pv_used,vg_name` — datalv uses both PVs"),
            (2, 40, "`pvmove /dev/loop0p1` (use actual old PV path from pvs)"),
            (3, 55, "`vgreduce fixitlab /dev/loop0p1` after pvmove completes"),
        ],
        "setup_sh": """#!/bin/bash
set -e
dd if=/dev/zero of=/var/old.img bs=1M count=200 status=none
dd if=/dev/zero of=/var/new.img bs=1M count=200 status=none
OLD=$(losetup -f --show /var/old.img)
NEW=$(losetup -f --show /var/new.img)
for D in "$OLD" "$NEW"; do
  parted -s "$D" mklabel gpt && parted -s "$D" mkpart primary 1MiB 100%
done
sleep 1
OP="${OLD}p1"; [ -b "$OP" ] || OP="${OLD}1"
NP="${NEW}p1"; [ -b "$NP" ] || NP="${NEW}1"
pvcreate -y "$OP" "$NP"
vgcreate fixitlab "$OP" "$NP"
lvcreate -y -l 100%FREE -n datalv fixitlab
mkfs.xfs /dev/fixitlab/datalv
mkdir -p /data && mount /dev/fixitlab/datalv /data
echo "production data" > /data/important.db
echo "Evacuate $OP before removal — use pvmove"
""",
    },
    {
        "slug": "xfs-repair-damage",
        "title": "XFS Filesystem Requires xfs_repair",
        "category": "Storage / XFS",
        "difficulty": "hard",
        "time_limit": 1500,
        "topics": "Q7 XFS repair — xfs_repair, mount after clean log",
        "packages": "xfsprogs e2fsprogs util-linux vim nano less procps python3",
        "extra_run": "RUN mkdir -p /data",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
DEV=$(cat /etc/fixitlab-xfs-dev 2>/dev/null)
[ -z "$DEV" ] && DEV=$(losetup -j /var/xfs.img 2>/dev/null | cut -d: -f1 | head -1)
mount /data 2>/dev/null || true
mountpoint -q /data && [ -f /data/app.conf ] && echo PASS && exit 0
[ -n "$DEV" ] && xfs_repair -n "$DEV" 2>/dev/null | grep -qi clean && mount "$DEV" /data && [ -f /data/app.conf ] && echo PASS && exit 0
echo FAIL: umount /data; xfs_repair on loop device; mount /data and verify /data/app.conf
exit 1""",
        "description": "/data fails to mount after unclean shutdown. xfs_repair is required before the application config can be read.",
        "objectives": ["Read mount/dmesg errors", "Unmount broken mountpoint", "Run xfs_repair", "Remount and verify data"],
        "hints": [
            (1, 15, "`dmesg | tail` and `xfs_repair -n /dev/loop0`"),
            (2, 30, "`umount /data && xfs_repair /dev/loop0 && mount /data`"),
        ],
        "setup_sh": """#!/bin/bash
set -e
dd if=/dev/zero of=/var/xfs.img bs=1M count=120 status=none
DEV=$(losetup -f --show /var/xfs.img)
mkfs.xfs -f "$DEV"
mkdir -p /data && mount "$DEV" /data
echo "enabled=true" > /data/app.conf
sync
umount /data
# Corrupt primary superblock copy (offset 0) — repair restores from secondary
dd if=/dev/zero of="$DEV" bs=512 count=8 conv=notrunc status=none
echo "$DEV" > /etc/fixitlab-xfs-dev
echo "XFS on $DEV needs xfs_repair before mount"
""",
    },
    {
        "slug": "bind-mount-hides-data",
        "title": "Bind Mount Hides Production Web Root",
        "category": "Storage / Mounts",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q5 bind mounts — findmnt, umount overlay, restore content",
        "packages": "vim nano less procps python3 util-linux",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
[ -f /var/www/html/index.html ] && grep -q 'FixitLab Production' /var/www/html/index.html && echo PASS && exit 0
mount | grep -q '/var/www/html' && echo "FAIL: empty bind mount still covers /var/www/html — umount it" && exit 1
echo FAIL: umount /var/www/html bind mount so real site files are visible
exit 1""",
        "description": "Nginx serves a blank page. Real site files exist on disk but an empty directory is bind-mounted over /var/www/html.",
        "objectives": ["Compare ls vs findmnt", "Identify bind mount", "Unmount overlay", "Verify index.html content"],
        "hints": [
            (1, 15, "`findmnt /var/www/html` shows a bind mount"),
            (2, 25, "`umount /var/www/html` — do not delete files under /var/www"),
        ],
        "setup_sh": """#!/bin/bash
set -e
mkdir -p /var/www/html /var/empty-overlay
echo '<h1>FixitLab Production</h1>' > /var/www/html/index.html
mount --bind /var/empty-overlay /var/www/html
echo "Bind mount hides real web root"
""",
    },
    {
        "slug": "hosts-deny-blocks-ssh",
        "title": "TCP Wrappers hosts.deny Blocks SSH",
        "category": "Security / SSH",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q39 hosts.allow/deny — sshd tcp wrappers",
        "packages": "openssh-server libwrap0 vim nano less procps python3",
        "extra_run": "RUN useradd -m remote && mkdir -p /var/run/sshd && echo 'sshd: ALL' > /etc/hosts.deny",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! grep -qE '^sshd:\\s*ALL' /etc/hosts.deny 2>/dev/null && echo PASS && exit 0
grep -qE '^sshd:\\s*ALL' /etc/hosts.allow 2>/dev/null && echo PASS && exit 0
echo FAIL: remove sshd: ALL from /etc/hosts.deny or allow in /etc/hosts.allow
exit 1""",
        "description": "All SSH connections refused immediately. /etc/hosts.deny blocks sshd via TCP wrappers.",
        "objectives": ["Check /etc/hosts.deny and hosts.allow", "Fix sshd access rule", "Validate with sshd -t"],
        "hints": [(1, 20, "Remove `sshd: ALL` from hosts.deny or add `sshd: ALL` to hosts.allow")],
    },
    {
        "slug": "systemd-unit-wont-start",
        "title": "Broken systemd Unit — App Won't Start",
        "category": "Services / systemd",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q180 systemd — systemctl status, journalctl, unit syntax",
        "packages": "vim nano less procps python3",
        "extra_run": """RUN mkdir -p /opt/myapp && echo '#!/bin/bash\\nwhile true; do echo running; sleep 5; done' > /opt/myapp/run.sh && chmod +x /opt/myapp/run.sh && echo -e '[Unit]\\nDescription=MyApp\\n[Service]\\nType=simple\\nExecStart=/opt/myapp/nope.sh\\nRestart=on-failure\\n[Install]\\nWantedBy=multi-user.target' > /etc/systemd/system/myapp.service""",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
grep -q 'ExecStart=/opt/myapp/run.sh' /etc/systemd/system/myapp.service && echo PASS && exit 0
echo FAIL: fix ExecStart in /etc/systemd/system/myapp.service to /opt/myapp/run.sh
exit 1""",
        "description": "myapp.service fails on every start. ExecStart points to a non-existent script path.",
        "objectives": ["systemctl status myapp", "Read journalctl -u myapp", "Fix unit file ExecStart", "Reload and start service"],
        "hints": [
            (1, 15, "`systemctl status myapp` and `journalctl -u myapp -n 20`"),
            (2, 25, "Change ExecStart to `/opt/myapp/run.sh` then `systemctl daemon-reload`"),
        ],
    },
    {
        "slug": "pam-access-blocks-user",
        "title": "PAM access.conf Denies Console Login",
        "category": "Authentication / PAM",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q33 PAM access — /etc/security/access.conf",
        "packages": "libpam-modules libpam-modules-bin vim nano less procps python3",
        "extra_run": "RUN useradd -m opsuser && echo '- : opsuser : ALL' >> /etc/security/access.conf",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! grep -qE '^- : opsuser :' /etc/security/access.conf 2>/dev/null && echo PASS && exit 0
grep -qE '^\\+ : opsuser :' /etc/security/access.conf 2>/dev/null && echo PASS && exit 0
echo FAIL: remove deny rule for opsuser in /etc/security/access.conf or add explicit allow
exit 1""",
        "description": "opsuser receives 'access denied' on login. PAM access.conf contains a negative rule for this account.",
        "objectives": ["Inspect /etc/security/access.conf", "Understand +/- PAM access syntax", "Restore opsuser login"],
        "hints": [(1, 20, "Remove `- : opsuser : ALL` or add `+ : opsuser : LOCAL`")],
    },
    {
        "slug": "chattr-immutable-config",
        "title": "Immutable Flag Blocks Config Edit",
        "category": "Filesystem / Attributes",
        "difficulty": "hard",
        "time_limit": 900,
        "topics": "Q4 chattr +i — lsattr, remove immutable",
        "packages": "e2fsprogs vim nano less procps python3",
        "extra_run": "RUN mkdir -p /etc/myapp && echo 'PORT=8080' > /etc/myapp/config.env && chattr +i /etc/myapp/config.env",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
lsattr /etc/myapp/config.env 2>/dev/null | grep -q '\\-i\\-' && grep -q 'PORT=9090' /etc/myapp/config.env && echo PASS && exit 0
lsattr /etc/myapp/config.env 2>/dev/null | grep -q 'i' && echo "FAIL: remove immutable flag first (chattr -i)" && exit 1
echo FAIL: chattr -i /etc/myapp/config.env then set PORT=9090
exit 1""",
        "description": "Config change for PORT=9090 fails with 'Operation not permitted'. File has immutable attribute set.",
        "objectives": ["Use lsattr to see 'i' flag", "chattr -i to clear immutable", "Apply required config change"],
        "hints": [(1, 15, "`lsattr /etc/myapp/config.env` then `chattr -i` before editing")],
    },
    {
        "slug": "ldconfig-missing-library",
        "title": "Application Fails — Shared Library Not Found",
        "category": "Libraries",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q156 ldconfig — /etc/ld.so.conf.d, ldd",
        "packages": "gcc libc6-dev vim nano less procps python3",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
/usr/local/bin/myapp 2>/dev/null && echo PASS && exit 0
ldconfig -p 2>/dev/null | grep -q libfixit && /usr/local/bin/myapp && echo PASS && exit 0
echo FAIL: restore /etc/ld.so.conf.d/fixitlab.conf and run ldconfig
exit 1""",
        "description": "/usr/local/bin/myapp exits with 'error while loading shared libraries'. Custom library path was removed from ld.so.conf.d.",
        "objectives": ["Run ldd on myapp", "Inspect /etc/ld.so.conf.d", "Restore library path and ldconfig"],
        "hints": [
            (1, 15, "`ldd /usr/local/bin/myapp` shows libfixit.so not found"),
            (2, 25, "Recreate `/etc/ld.so.conf.d/fixitlab.conf` with `/usr/local/lib` and `ldconfig`"),
        ],
        "setup_sh": """#!/bin/bash
set -e
mkdir -p /usr/local/lib
cat > /tmp/libfixit.c <<'CEOF'
#include <stdio.h>
void fixit_greet(void) { printf("FixitLab app OK\\n"); }
CEOF
gcc -shared -fPIC -o /usr/local/lib/libfixit.so /tmp/libfixit.c 2>/dev/null || \
  cc -shared -fPIC -o /usr/local/lib/libfixit.so /tmp/libfixit.c
cat > /tmp/myapp.c <<'CEOF'
#include <stdio.h>
void fixit_greet(void);
int main(void) { fixit_greet(); return 0; }
CEOF
gcc -o /usr/local/bin/myapp /tmp/myapp.c -L/usr/local/lib -lfixit -Wl,-rpath,/usr/local/lib 2>/dev/null || \
  cc -o /usr/local/bin/myapp /tmp/myapp.c -L/usr/local/lib -lfixit
echo '/usr/local/lib' > /etc/ld.so.conf.d/fixitlab.conf
ldconfig
rm -f /etc/ld.so.conf.d/fixitlab.conf
ldconfig
echo "Library path config removed — myapp broken until ldconfig fixed"
""",
    },
    {
        "slug": "fstab-bad-uuid",
        "title": "fstab Wrong UUID — /mnt/data Won't Mount",
        "category": "Storage / fstab",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q9 fstab UUID — blkid, fix mount entry",
        "packages": "e2fsprogs util-linux vim nano less procps python3",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
DEV=$(cat /etc/fixitlab-data-dev 2>/dev/null)
[ -z "$DEV" ] && DEV=$(losetup -j /var/data.img 2>/dev/null | cut -d: -f1 | head -1)
mount /mnt/data 2>/dev/null || true
mountpoint -q /mnt/data && [ -f /mnt/data/production.dat ] && echo PASS && exit 0
REAL=$(blkid -s UUID -o value "$DEV" 2>/dev/null)
[ -n "$REAL" ] && grep -q "$REAL" /etc/fstab 2>/dev/null && mount -a 2>/dev/null && mountpoint -q /mnt/data && echo PASS && exit 0
echo FAIL: fix UUID in /etc/fstab for /mnt/data (use blkid) then mount -a
exit 1""",
        "description": "After reboot /mnt/data is empty. /etc/fstab references the wrong UUID for the data volume.",
        "objectives": ["Compare blkid vs fstab", "Fix UUID entry", "mount -a and verify production.dat"],
        "hints": [(1, 20, "`blkid` then replace bad UUID in /etc/fstab for /mnt/data")],
        "setup_sh": """#!/bin/bash
set -e
dd if=/dev/zero of=/var/data.img bs=1M count=80 status=none
DEV=$(losetup -f --show /var/data.img)
mkfs.ext4 -F "$DEV"
mkdir -p /mnt/data
REAL_UUID=$(blkid -s UUID -o value "$DEV")
echo "critical" > /tmp/production.dat
mount "$DEV" /mnt/data && mv /tmp/production.dat /mnt/data/ && umount /mnt/data
echo "$DEV" > /etc/fixitlab-data-dev
echo "UUID=00000000-0000-0000-0000-000000000000 /mnt/data ext4 defaults 0 2" >> /etc/fstab
echo "Real UUID is $REAL_UUID but fstab has wrong value"
""",
    },
    {
        "slug": "noexec-tmp-blocked",
        "title": "/tmp Mounted noexec — Installer Fails",
        "category": "Storage / Mounts",
        "difficulty": "hard",
        "time_limit": 900,
        "topics": "Q5 mount options — noexec, findmnt, remount exec",
        "packages": "vim nano less procps python3 util-linux",
        "extra_run": "RUN mkdir -p /opt/install && echo '#!/bin/sh\\necho installed' > /opt/install/run.sh && chmod +x /opt/install/run.sh",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
findmnt -n /tmp -o OPTIONS 2>/dev/null | grep -q noexec && echo "FAIL: /tmp still noexec — remount with exec" && exit 1
cp /opt/install/run.sh /tmp/run.sh && chmod +x /tmp/run.sh && /tmp/run.sh | grep -q installed && echo PASS && exit 0
echo FAIL: mount -o remount,exec /tmp (or remove noexec from fstab)
exit 1""",
        "description": "Installer script copied to /tmp fails with 'Permission denied' when executed. /tmp was remounted with noexec.",
        "objectives": ["findmnt /tmp for noexec", "Remount /tmp with exec", "Run installer successfully"],
        "hints": [(1, 15, "`mount -o remount,exec /tmp`")],
        "setup_sh": """#!/bin/bash
mount -o remount,noexec /tmp 2>/dev/null || mount --bind /tmp /tmp && mount -o remount,noexec,bind /tmp
echo "/tmp is noexec"
""",
    },
    {
        "slug": "resolv-dead-nameserver",
        "title": "DNS Resolution Broken — Dead nameserver",
        "category": "Networking / DNS",
        "difficulty": "hard",
        "time_limit": 900,
        "topics": "Q95 resolv.conf — fix nameserver, getent hosts",
        "packages": "dnsmasq vim nano less procps python3 dnsutils iproute2",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
getent hosts app.fixitlab.local >/dev/null 2>&1 && echo PASS && exit 0
echo FAIL: point nameserver to 127.0.0.1 in /etc/resolv.conf (local dnsmasq serves app.fixitlab.local)
exit 1""",
        "description": "DNS lookups fail for internal host app.fixitlab.local. resolv.conf points to dead 192.0.2.1; local dnsmasq on 127.0.0.1 is running.",
        "objectives": ["Test with getent hosts app.fixitlab.local", "Fix nameserver in resolv.conf", "Verify local DNS resolves"],
        "hints": [(1, 15, "Set `nameserver 127.0.0.1` — dnsmasq is already running")],
        "setup_sh": """#!/bin/bash
set -e
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
address=/app.fixitlab.local/10.20.0.5
EOF
dnsmasq
echo 'nameserver 192.0.2.1' > /etc/resolv.conf
echo "dnsmasq on 127.0.0.1 — fix resolv.conf to use it"
""",
    },
    {
        "slug": "cron-missing-path",
        "title": "Cron Job Fails — PATH Not Set",
        "category": "Scheduling",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q193 cron environment — PATH in crontab",
        "packages": "cron vim nano less procps python3",
        "extra_run": """RUN mkdir -p /usr/local/bin && echo '#!/bin/bash\\necho ok > /var/run/cron-ok' > /usr/local/bin/backup.sh && chmod +x /usr/local/bin/backup.sh && echo '* * * * * backup.sh' | crontab -""",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
[ -f /var/run/cron-ok ] && echo PASS && exit 0
crontab -l 2>/dev/null | grep -qE 'PATH=.*usr/local' && echo PASS && exit 0
crontab -l 2>/dev/null | grep -q '/usr/local/bin/backup.sh' && echo PASS && exit 0
echo FAIL: add PATH=/usr/local/bin:/bin:/usr/bin to crontab or use full path to backup.sh
exit 1""",
        "description": "Minute cron job never creates /var/run/cron-ok. Crontab calls backup.sh without PATH or full path.",
        "objectives": ["Check /var/log/syslog for cron errors", "Fix crontab PATH or use absolute path", "Wait for job or run manually"],
        "hints": [(1, 20, "Use `* * * * * /usr/local/bin/backup.sh` or set PATH in crontab")],
    },
    {
        "slug": "user-nologin-shell",
        "title": "User Shell Set to /usr/sbin/nologin",
        "category": "Users / Groups",
        "difficulty": "medium",
        "time_limit": 900,
        "topics": "Q21 nologin shell — usermod -s /bin/bash",
        "packages": "vim nano less procps python3",
        "extra_run": "RUN useradd -m -s /usr/sbin/nologin deploy",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
SHELL=$(getent passwd deploy | cut -d: -f7)
[ "$SHELL" = "/bin/bash" ] || [ "$SHELL" = "/bin/sh" ] && echo PASS && exit 0
echo FAIL: usermod -s /bin/bash deploy
exit 1""",
        "description": "deploy user exists but interactive login immediately closes. Shell is /usr/sbin/nologin.",
        "objectives": ["Check /etc/passwd shell field", "Change shell with usermod -s", "Verify login works"],
        "hints": [(1, 10, "`usermod -s /bin/bash deploy`")],
    },
    {
        "slug": "sudo-secure-path-broken",
        "title": "sudo secure_path Blocks Admin Commands",
        "category": "Sudo / Security",
        "difficulty": "hard",
        "time_limit": 1200,
        "topics": "Q32 sudoers secure_path — visudo",
        "packages": "sudo vim nano less procps python3 iproute2",
        "extra_run": "RUN useradd -m -G sudo admin && echo 'Defaults secure_path=\"/usr/bin\"' > /etc/sudoers.d/99-bad-path && chmod 440 /etc/sudoers.d/99-bad-path",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
! grep -q 'secure_path="/usr/bin"' /etc/sudoers.d/99-bad-path 2>/dev/null && echo PASS && exit 0
grep -q '/usr/sbin' /etc/sudoers.d/99-bad-path 2>/dev/null && echo PASS && exit 0
echo FAIL: fix secure_path to include /usr/sbin and /sbin in /etc/sudoers.d/99-bad-path
exit 1""",
        "description": "sudo ip or sudo systemctl fail with 'command not found'. secure_path in sudoers omits /usr/sbin and /sbin.",
        "objectives": ["sudo -l as admin", "Inspect /etc/sudoers.d/", "Fix secure_path to standard paths"],
        "hints": [(1, 20, "Set `Defaults secure_path=\"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"`")],
    },
    {
        "slug": "capabilities-ping-fails",
        "title": "ping Fails — Missing CAP_NET_RAW",
        "category": "Capabilities / Security",
        "difficulty": "hard",
        "time_limit": 900,
        "topics": "Q41 capabilities — setcap cap_net_raw+ep",
        "packages": "vim nano less procps python3 iputils-ping libcap2-bin",
        "extra_run": "RUN setcap -r /bin/ping 2>/dev/null || setcap -r /usr/bin/ping 2>/dev/null || true",
        "setup_copy": "",
        "cmd": "exec /bin/bash",
        "check": """#!/bin/bash
PING=$(command -v ping)
getcap "$PING" 2>/dev/null | grep -q cap_net_raw && echo PASS && exit 0
echo FAIL: setcap cap_net_raw+ep $PING
exit 1""",
        "description": "ping 127.0.0.1 fails with 'Operation not permitted'. File capability cap_net_raw was removed from ping binary.",
        "objectives": ["Run getcap on ping binary", "Restore cap_net_raw with setcap", "Verify ping works"],
        "hints": [(1, 15, "`setcap cap_net_raw+ep $(command -v ping)`")],
    },
    {
        "slug": "journald-var-log-full",
        "title": "journald Cannot Write — /var/log Full",
        "category": "Logging / Disk",
        "difficulty": "hard",
        "time_limit": 1500,
        "topics": "Q6 journal vacuum — journalctl --vacuum-size",
        "packages": "vim nano less procps python3 systemd",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
USE=$(df /var/log 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
[ "${USE:-100}" -lt 90 ] && echo PASS && exit 0
journalctl --disk-usage 2>/dev/null | grep -q journal
echo FAIL: free /var/log space — journalctl --vacuum-size=50M or delete /var/log/big/*.log
exit 1""",
        "description": "journalctl and apps logging to /var/log fail. /var/log is full from oversized application logs.",
        "objectives": ["df -h /var/log", "Find large files under /var/log", "Vacuum journal or delete stale logs"],
        "hints": [
            (1, 15, "`du -sh /var/log/* | sort -h`"),
            (2, 25, "`journalctl --vacuum-size=50M` and remove /var/log/big/*.log"),
        ],
        "setup_sh": """#!/bin/bash
set -e
mkdir -p /var/log/big
for i in $(seq 1 40); do dd if=/dev/zero of=/var/log/big/app$i.log bs=1M count=8 status=none; done
echo "/var/log filled with large app logs"
""",
    },
    {
        "slug": "mdadm-degraded-array",
        "title": "Software RAID1 Degraded — Missing Disk",
        "category": "Storage / RAID",
        "difficulty": "hard",
        "time_limit": 1800,
        "docker_privileged": True,
        "topics": "Q15 mdadm — cat /proc/mdstat, add disk, rebuild",
        "packages": "mdadm e2fsprogs util-linux vim nano less procps python3",
        "extra_run": "",
        "setup_copy": "COPY setup.sh /opt/fixitlab/setup.sh\nRUN chmod +x /opt/fixitlab/setup.sh\n",
        "cmd": "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash",
        "check": """#!/bin/bash
cat /proc/mdstat 2>/dev/null | grep -qE 'md0.*active.*raid1.*\\[UU\\]' && echo PASS && exit 0
cat /proc/mdstat 2>/dev/null | grep -qE '\\[U_\\]|\\[_U\\]' && echo "FAIL: RAID still degraded — add missing device to md0" && exit 1
echo FAIL: rebuild RAID1 — mdadm --manage /dev/md0 --add /dev/loopXp2 then wait for [UU]
exit 1""",
        "description": "/dev/md0 RAID1 array is degraded (missing disk). Data is on surviving mirror; add replacement disk and rebuild.",
        "objectives": ["Check /proc/mdstat", "Identify failed/missing slot", "mdadm --add replacement device", "Monitor rebuild to [UU]"],
        "hints": [
            (1, 20, "`cat /proc/mdstat` and `mdadm --detail /dev/md0`"),
            (2, 40, "`mdadm --manage /dev/md0 --add /dev/loopXp2` (use spare loop partition)"),
        ],
        "setup_sh": """#!/bin/bash
set -e
dd if=/dev/zero of=/var/raid1.img bs=1M count=120 status=none
dd if=/dev/zero of=/var/raid2.img bs=1M count=120 status=none
D1=$(losetup -f --show /var/raid1.img)
D2=$(losetup -f --show /var/raid2.img)
echo yes | mdadm --create /dev/md0 --level=1 --raid-devices=2 "$D1" "$D2"
sleep 2
mkfs.ext4 /dev/md0
mkdir -p /data && mount /dev/md0 /data
echo "raid data" > /data/important.txt
# Fail and remove second device — leaves degraded array
mdadm /dev/md0 --fail "$D2" 2>/dev/null || true
mdadm /dev/md0 --remove "$D2" 2>/dev/null || true
echo "$D2" > /etc/fixitlab-raid-spare
echo "RAID degraded — add $D2 back with mdadm --manage /dev/md0 --add"
""",
    },
]

ALL_SCENARIOS = SCENARIOS + COMPLEX_SCENARIOS


def write_scenario(s):
    d = ROOT / s["slug"]
    d.mkdir(parents=True, exist_ok=True)
    for f in ("systemctl.py", "service.sh"):
        src = SHARED / f
        if src.exists():
            (d / f).write_text(src.read_text())
    setup_copy = s.get("setup_copy", "")
    docker = BASE_DOCKER.format(
        packages=s["packages"],
        extra_run=s.get("extra_run", ""),
        setup_copy=setup_copy,
        cmd=s["cmd"],
    )
    (d / "Dockerfile").write_text(docker)
    (d / "check.sh").write_text(s["check"] + "\n")
    if s.get("setup_sh"):
        (d / "setup.sh").write_text(s["setup_sh"] + "\n")
    hints_yaml = "\n".join(
        f'  - order: {o}\n    cost: {c}\n    content: "{h}"' for o, c, h in s.get("hints", [])
    )
    yaml = f"""title: "{s['title']}"
slug: "{s['slug']}"
technology: "Linux"
category: "{s['category']}"
difficulty: "{s['difficulty']}"
time_limit: {s['time_limit']}
max_score: 100
infrastructure_type: "docker"
docker_privileged: {str(s.get('docker_privileged', False)).lower()}
jira_priority: "Medium"
topics_covered: "{s['topics']}"

description: |
  {s['description']}

objectives:
{chr(10).join('  - ' + o for o in s['objectives'])}

initial_state: |
  Ubuntu 22.04 lab container with a realistic misconfiguration.

hints:
{hints_yaml}
"""
    (d / "scenario.yaml").write_text(yaml)
    print(f"  wrote {s['slug']}")


def main():
    for s in ALL_SCENARIOS:
        write_scenario(s)
    print(f"Generated {len(ALL_SCENARIOS)} Linux scenarios ({len(COMPLEX_SCENARIOS)} complex) in {ROOT}")


if __name__ == "__main__":
    main()
