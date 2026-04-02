#!/usr/bin/env python
"""
Seed script — creates essential data for FixitLab to work:
- Billing plans (free, pro, enterprise)
- Technologies (Linux, Docker, Networking, Web Servers, Databases)
- Tags
- Sample scenarios with validation scripts
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.billing.models import Plan
from apps.question_bank.models import Technology, Tag, Scenario
from apps.hints.models import Hint


def seed_plans():
    """Create billing plans."""
    plans = [
        {"code": "free", "name": "Free", "price": 0, "max_labs_per_day": 5, "max_lab_duration_minutes": 30},
        {"code": "pro", "name": "Pro", "price": 9.99, "max_labs_per_day": 50, "max_lab_duration_minutes": 120},
        {"code": "enterprise", "name": "Enterprise", "price": 49.99, "max_labs_per_day": 999, "max_lab_duration_minutes": 240},
    ]
    for p in plans:
        plan, created = Plan.objects.get_or_create(code=p["code"], defaults=p)
        if created:
            print(f"  ✅ Plan: {plan.name}")
        else:
            print(f"  ℹ️  Plan exists: {plan.name}")


def seed_technologies():
    """Create technology categories."""
    techs = [
        {"name": "Linux", "slug": "linux", "icon": "terminal", "color": "cyan", "order": 1,
         "description": "Linux system administration, shell scripting, and troubleshooting"},
        {"name": "Docker", "slug": "docker", "icon": "container", "color": "blue", "order": 2,
         "description": "Container management, Docker networking, and orchestration"},
        {"name": "Networking", "slug": "networking", "icon": "network", "color": "green", "order": 3,
         "description": "TCP/IP, DNS, firewall rules, and network troubleshooting"},
        {"name": "Web Servers", "slug": "web-servers", "icon": "globe", "color": "amber", "order": 4,
         "description": "Nginx, Apache, reverse proxies, and SSL/TLS configuration"},
        {"name": "Databases", "slug": "databases", "icon": "database", "color": "purple", "order": 5,
         "description": "PostgreSQL, MySQL, Redis — queries, replication, and recovery"},
    ]
    for t in techs:
        tech, created = Technology.objects.get_or_create(slug=t["slug"], defaults=t)
        if created:
            print(f"  ✅ Technology: {tech.name}")
        else:
            print(f"  ℹ️  Technology exists: {tech.name}")


def seed_tags():
    """Create scenario tags."""
    tag_names = [
        "nginx", "apache", "systemd", "bash", "ssh", "dns", "firewall",
        "permissions", "disk", "memory", "process", "cron", "docker",
        "networking", "postgresql", "mysql", "redis", "ssl", "logs",
        "debugging", "useradd", "passwd", "filesystem", "fstab", "mount",
        "lvm", "storage", "iptables", "security",
    ]
    for name in tag_names:
        tag, created = Tag.objects.get_or_create(name=name)
        if created:
            print(f"  ✅ Tag: {tag.name}")


def seed_scenarios():
    """Create sample scenarios with validation scripts."""
    linux = Technology.objects.get(slug="linux")
    webservers = Technology.objects.get(slug="web-servers")
    networking = Technology.objects.get(slug="networking")
    docker_tech = Technology.objects.get(slug="docker")
    databases = Technology.objects.get(slug="databases")

    # Common dangerous commands blocked in every scenario
    GLOBAL_BLOCKED = [
        "reboot",
        "shutdown",
        "halt",
        "poweroff",
        "^init\\s+[06]",           # init 0 / init 6
        "^rm\\s+-rf\\s+/",         # rm -rf /
        "^rm\\s+-fr\\s+/",         # rm -fr /
        "mkfs",                     # format disks
        "^dd\\s+if=",              # raw disk writes
        ":(){ :|:& };:",           # fork bomb
    ]

    scenarios_data = [
        {
            "technology": webservers,
            "slug": "broken-nginx",
            "title": "Fix the Broken Nginx",
            "subtitle": "The web server is down",
            "category": "Web Server",
            "difficulty": "easy",
            "scenario_type": "fix",
            "description": "A production web server has suddenly stopped responding to requests. Users are reporting 'connection refused' errors when trying to access the website. Your task is to investigate the Nginx web server, identify why it refuses to start, fix the configuration error, and ensure that the server is serving the default page on port 80. This is a common real-world scenario that sysadmins encounter regularly.",
            "objectives": [
                "Check the Nginx service status and identify the error",
                "Locate and fix the configuration syntax error",
                "Validate the configuration with 'nginx -t'",
                "Start the Nginx service and ensure it serves content on port 80"
            ],
            "initial_state": "An Ubuntu 22.04 server with Nginx installed. The nginx configuration file (/etc/nginx/sites-available/default) contains a syntax error that prevents the service from starting. The default HTML page exists at /var/www/html/index.html.",
            "validation_script": "#!/bin/bash\ncurl -s http://localhost:80 | grep -qi 'welcome\\|nginx' && echo 'PASS: Nginx is serving' && exit 0 || echo 'FAIL: Nginx not serving on port 80' && exit 1",
            "solution_explanation": "The nginx configuration at /etc/nginx/sites-enabled/default had a syntax error (missing semicolon). Fix it with: sudo nano /etc/nginx/sites-enabled/default, fix the error, then run: sudo nginx -t && sudo systemctl restart nginx",
            "time_limit": 900,
            "is_free": True,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["nginx", "systemd", "debugging"],
            "hints": [
                {"content": "Check if nginx is running: systemctl status nginx", "penalty": 5},
                {"content": "Test the nginx configuration: nginx -t", "penalty": 10},
                {"content": "Look for syntax errors in /etc/nginx/sites-enabled/default", "penalty": 15},
            ],
        },
        {
            "technology": linux,
            "slug": "disk-full",
            "title": "Disk Space Full",
            "subtitle": "Find and remove the space hog",
            "category": "System Administration",
            "difficulty": "easy",
            "scenario_type": "fix",
            "description": "A critical production server is running out of disk space on the root partition. Services are starting to fail, and you need to urgently identify what is consuming all the storage and free up space. You'll need to use Linux disk analysis tools to find large files, hidden caches, and runaway log generators, then clean them up to bring disk usage below 80%.",
            "objectives": [
                "Use 'df -h' to verify disk usage on the root partition",
                "Find large files using 'du' and 'find' commands",
                "Check for hidden files and directories that may be consuming space",
                "Remove or compress unnecessary large files",
                "Verify disk usage is below 80% after cleanup"
            ],
            "initial_state": "An Ubuntu 22.04 server with the root partition nearly full. Large junk files have been placed in various locations across the filesystem, including hidden directories. A log generator script may also be actively growing log files.",
            "validation_script": "#!/bin/bash\nUSAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')\nif [ \"$USAGE\" -lt 80 ]; then echo 'PASS: Disk usage is under 80%' && exit 0; else echo \"FAIL: Disk usage is ${USAGE}%\" && exit 1; fi",
            "solution_explanation": "Use 'du -sh /* 2>/dev/null | sort -rh | head' to find the large file, then 'find / -size +100M -type f' to locate specific large files. Remove the junk file with rm.",
            "time_limit": 600,
            "is_free": True,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["disk", "bash", "debugging"],
            "hints": [
                {"content": "Check disk usage with: df -h", "penalty": 5},
                {"content": "Find large files: find / -size +100M -type f 2>/dev/null", "penalty": 10},
            ],
        },
        {
            "technology": linux,
            "slug": "ssh-lockout",
            "title": "SSH Lockout Recovery",
            "subtitle": "The keys don't work anymore",
            "category": "Security",
            "difficulty": "medium",
            "scenario_type": "fix",
            "description": "SSH key-based authentication has suddenly stopped working on a server. The admin can still access the machine via the console, but remote SSH logins using keys are being rejected. Password authentication is disabled in the SSH config, so fixing key-based auth is critical. Investigate and fix the SSH configuration and file permissions to restore remote access.",
            "objectives": [
                "Check SSH daemon logs for authentication errors",
                "Identify incorrect file permissions on ~/.ssh directory and authorized_keys",
                "Fix the permission settings to match SSH requirements",
                "Verify that key-based authentication works again"
            ],
            "initial_state": "An Ubuntu 22.04 server with OpenSSH installed. The permissions on /root/.ssh directory and authorized_keys file have been changed to insecure values. SSH daemon refuses key authentication when permissions are too open.",
            "validation_script": "#!/bin/bash\nPERM=$(stat -c '%a' /root/.ssh 2>/dev/null)\nKEYPERM=$(stat -c '%a' /root/.ssh/authorized_keys 2>/dev/null)\nif [ \"$PERM\" = \"700\" ] && [ \"$KEYPERM\" = \"600\" ]; then echo 'PASS' && exit 0; else echo 'FAIL: Wrong permissions' && exit 1; fi",
            "solution_explanation": "SSH requires strict permissions: chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys. The SSH daemon checks these permissions and refuses key auth if they're too open.",
            "time_limit": 900,
            "is_free": True,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["ssh", "permissions", "debugging"],
            "hints": [
                {"content": "Check SSH service logs: journalctl -u sshd -n 50", "penalty": 5},
                {"content": "SSH is strict about permissions on ~/.ssh and authorized_keys", "penalty": 10},
                {"content": "Required: ~/.ssh (700), authorized_keys (600)", "penalty": 20},
            ],
        },
        {
            "technology": linux,
            "slug": "zombie-process",
            "title": "Kill the Zombie Process",
            "subtitle": "Something is eating all the CPU",
            "category": "Process Management",
            "difficulty": "easy",
            "scenario_type": "fix",
            "description": "A runaway process is consuming all available CPU cycles on a production server, causing other services to become unresponsive. Your task is to identify the offending process using system monitoring tools, safely terminate it, and verify that CPU usage returns to normal levels. This simulates a common production incident where a rogue script or process needs to be killed.",
            "objectives": [
                "Use 'top', 'htop', or 'ps' to identify the process consuming excessive CPU",
                "Determine the PID of the runaway process",
                "Safely terminate the process using 'kill' command",
                "Verify that CPU usage has returned to normal (below 50%)"
            ],
            "initial_state": "An Ubuntu 22.04 server with a CPU-intensive rogue process running in the background. The process is an infinite loop script consuming near 100% of one CPU core.",
            "validation_script": "#!/bin/bash\nCPU=$(top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d. -f1)\nif [ \"$CPU\" -lt 50 ]; then echo 'PASS: CPU usage normal' && exit 0; else echo \"FAIL: CPU at ${CPU}%\" && exit 1; fi",
            "solution_explanation": "Use 'top' or 'ps aux --sort=-%cpu' to find the runaway process, then 'kill <PID>' or 'kill -9 <PID>' to terminate it.",
            "time_limit": 600,
            "is_free": True,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["process", "bash", "debugging"],
            "hints": [
                {"content": "Use 'top' or 'htop' to see which process is using the most CPU", "penalty": 5},
                {"content": "Use 'kill <PID>' to terminate the process", "penalty": 10},
            ],
        },
        {
            "technology": networking,
            "slug": "dns-resolution-broken",
            "title": "DNS Resolution Broken",
            "subtitle": "Can't resolve any hostnames",
            "category": "DNS",
            "difficulty": "medium",
            "scenario_type": "fix",
            "description": "A production server has completely lost the ability to resolve domain names. All DNS queries fail, making it impossible to reach external services, pull packages, or make API calls. The /etc/resolv.conf file has been corrupted with invalid nameserver addresses. Your task is to diagnose the issue and restore DNS resolution by configuring valid nameservers.",
            "objectives": [
                "Verify that DNS resolution is failing using 'nslookup' or 'dig'",
                "Inspect the current DNS configuration in /etc/resolv.conf",
                "Replace invalid nameservers with working ones (e.g., 8.8.8.8)",
                "Verify that DNS resolution works correctly after the fix"
            ],
            "initial_state": "An Ubuntu 22.04 server with DNS resolution completely broken. The /etc/resolv.conf file contains invalid nameserver entries (192.0.2.1 and 198.51.100.1 — reserved documentation IPs that don't respond to DNS queries).",
            "validation_script": "#!/bin/bash\nnslookup google.com > /dev/null 2>&1 && echo 'PASS: DNS resolution works' && exit 0 || echo 'FAIL: Cannot resolve domains' && exit 1",
            "solution_explanation": "Fix /etc/resolv.conf by adding a valid nameserver: echo 'nameserver 8.8.8.8' > /etc/resolv.conf. You can also add 'nameserver 8.8.4.4' as a backup.",
            "time_limit": 600,
            "is_free": True,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["dns", "networking", "debugging"],
            "hints": [
                {"content": "Check the DNS config: cat /etc/resolv.conf", "penalty": 5},
                {"content": "A common public DNS server is 8.8.8.8 (Google)", "penalty": 10},
            ],
        },
        {
            "technology": linux,
            "slug": "broken-cron",
            "title": "Fix the Broken Cron Job",
            "subtitle": "The backup stopped running",
            "category": "Automation",
            "difficulty": "medium",
            "scenario_type": "fix",
            "description": "A critical backup cron job that runs nightly at 2 AM has mysteriously stopped producing backup files. The cron entry exists in the crontab, and the backup script is present at /opt/backup.sh, but no new backups are being created. Investigate the backup automation setup, identify what's preventing the backup from running, and fix it so the job executes correctly.",
            "objectives": [
                "Examine the backup script at /opt/backup.sh for issues",
                "Check file permissions on the backup script",
                "Verify the cron entry syntax is correct",
                "Ensure the cron job can execute the backup script successfully"
            ],
            "initial_state": "An Ubuntu 22.04 server with a backup script at /opt/backup.sh that has incorrect permissions (644 instead of 755, making it non-executable). The cron entry exists but the job fails silently because the script cannot be executed.",
            "validation_script": "#!/bin/bash\nPERM=$(stat -c '%a' /opt/backup.sh 2>/dev/null)\nCRON=$(crontab -l 2>/dev/null | grep -c backup)\nif [ \"$PERM\" = \"755\" ] && [ \"$CRON\" -gt 0 ]; then echo 'PASS' && exit 0; else echo 'FAIL' && exit 1; fi",
            "solution_explanation": "1. Make the script executable: chmod 755 /opt/backup.sh  2. Fix the cron entry: crontab -e and correct the timing syntax.",
            "time_limit": 900,
            "is_free": True,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["cron", "bash", "permissions"],
            "hints": [
                {"content": "Check if the script is executable: ls -la /opt/backup.sh", "penalty": 5},
                {"content": "Check the cron entry: crontab -l", "penalty": 10},
            ],
        },
        # ─── Cloud-based scenarios (AWS EC2 / DigitalOcean) ──────────
        {
            "technology": linux,
            "slug": "broken-fstab",
            "title": "Fix the Broken /etc/fstab",
            "subtitle": "The filesystem won't mount",
            "category": "Filesystem",
            "difficulty": "hard",
            "scenario_type": "fix",
            "infrastructure_type": "aws_ec2",
            "cloud_setup_script": """#!/bin/bash
# Create a partition and filesystem, then break fstab
fallocate -l 100M /tmp/disk.img
losetup /dev/loop10 /tmp/disk.img
mkfs.ext4 /dev/loop10
mkdir -p /mnt/data
# Add a broken fstab entry (wrong UUID)
echo "UUID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee /mnt/data ext4 defaults 0 2" >> /etc/fstab
# Also break an existing entry
echo "/dev/sdz99 /mnt/backup xfs defaults 0 0" >> /etc/fstab
""",
            "description": "A production server has a broken /etc/fstab configuration that prevents filesystems from mounting properly. After a reboot, critical mount points are failing. You need to fix the fstab entries so mount -a succeeds without errors. This scenario requires a real server with actual block devices and mount operations.",
            "objectives": [
                "Identify which fstab entries are invalid",
                "Find the correct UUID for the loop device filesystem",
                "Remove or fix non-existent device entries",
                "Verify mount -a succeeds without errors"
            ],
            "initial_state": "An Ubuntu 22.04 server with a broken /etc/fstab containing entries for non-existent devices and wrong UUIDs.",
            "validation_script": "#!/bin/bash\nmount -a 2>&1\nif [ $? -eq 0 ]; then\n  echo 'PASS: All fstab entries mount successfully'\n  exit 0\nelse\n  echo 'FAIL: mount -a failed'\n  exit 1\nfi",
            "solution_explanation": "1. Use 'blkid' to find correct UUIDs. 2. Fix or remove entries referencing non-existent devices. 3. Use the correct UUID for /dev/loop10. 4. Run 'mount -a' to verify.",
            "time_limit": 1200,
            "is_free": False,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["filesystem", "fstab", "mount"],
            "hints": [
                {"content": "Use 'blkid' to list all block device UUIDs", "penalty": 5},
                {"content": "Use 'mount -a' to test all fstab entries at once", "penalty": 10},
                {"content": "Non-existent devices in fstab should be removed or commented out", "penalty": 15},
            ],
        },
        {
            "technology": linux,
            "slug": "lvm-recovery",
            "title": "LVM Volume Recovery",
            "subtitle": "The logical volume disappeared",
            "category": "Storage",
            "difficulty": "hard",
            "scenario_type": "fix",
            "infrastructure_type": "aws_ec2",
            "cloud_setup_script": """#!/bin/bash
# Install LVM tools
apt-get install -y -qq lvm2
# Create disk images for LVM
fallocate -l 200M /tmp/pv1.img
fallocate -l 200M /tmp/pv2.img
losetup /dev/loop11 /tmp/pv1.img
losetup /dev/loop12 /tmp/pv2.img
# Create PV, VG, LV
pvcreate /dev/loop11 /dev/loop12
vgcreate datavg /dev/loop11 /dev/loop12
lvcreate -n datalv -L 300M datavg
mkfs.ext4 /dev/datavg/datalv
mkdir -p /data
mount /dev/datavg/datalv /data
echo "important data" > /data/important.txt
umount /data
# Break it: deactivate the LV
lvchange -an /dev/datavg/datalv
# Remove the LV metadata backup
rm -f /etc/lvm/backup/datavg
""",
            "description": "A critical LVM logical volume containing important data has become inactive and won't mount. The LVM configuration has been tampered with. You need to recover the LV, activate it, and mount it properly. This scenario requires real LVM operations on a proper Linux server.",
            "objectives": [
                "Diagnose the LVM state using pvs, vgs, lvs",
                "Activate the logical volume",
                "Mount the filesystem and verify data recovery",
                "Add a persistent fstab entry"
            ],
            "initial_state": "An Ubuntu 22.04 server with a deactivated LVM logical volume. The VG and PVs exist but the LV is inactive.",
            "validation_script": "#!/bin/bash\nif mountpoint -q /data && [ -f /data/important.txt ]; then\n  echo 'PASS: LVM volume recovered and data accessible'\n  exit 0\nelse\n  echo 'FAIL: /data not mounted or data missing'\n  exit 1\nfi",
            "solution_explanation": "1. 'vgscan' to scan for VGs. 2. 'lvchange -ay /dev/datavg/datalv' to activate. 3. 'mount /dev/datavg/datalv /data' to mount.",
            "time_limit": 1200,
            "is_free": False,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["lvm", "storage", "filesystem"],
            "hints": [
                {"content": "Use 'lvs' to list logical volumes and their state", "penalty": 5},
                {"content": "Use 'lvchange -ay <path>' to activate a logical volume", "penalty": 10},
                {"content": "After activating, mount with: mount /dev/datavg/datalv /data", "penalty": 15},
            ],
        },
        {
            "technology": linux,
            "slug": "firewall-lockout",
            "title": "Firewall Lockout Recovery",
            "subtitle": "iptables rules gone wrong",
            "category": "Security",
            "difficulty": "hard",
            "scenario_type": "fix",
            "infrastructure_type": "digitalocean",
            "cloud_setup_script": """#!/bin/bash
# Install iptables
apt-get install -y -qq iptables nginx
# Start nginx on port 80
systemctl start nginx
# Set up broken iptables rules that block HTTP
iptables -A INPUT -p tcp --dport 80 -j DROP
iptables -A INPUT -p tcp --dport 443 -j DROP
# Also add a rule that blocks outgoing DNS
iptables -A OUTPUT -p udp --dport 53 -j DROP
iptables -A OUTPUT -p tcp --dport 53 -j DROP
""",
            "description": "Someone applied iptables firewall rules that are blocking HTTP/HTTPS traffic and DNS resolution on a web server. Nginx is running but unreachable. Outgoing DNS is also blocked. Fix the firewall rules to restore web access and DNS resolution without removing necessary security rules.",
            "objectives": [
                "List current iptables rules to understand the blocking",
                "Remove rules that block HTTP (port 80) and HTTPS (port 443)",
                "Remove rules that block outgoing DNS (port 53)",
                "Verify nginx is accessible and DNS works"
            ],
            "initial_state": "An Ubuntu 22.04 server with nginx running but iptables rules blocking ports 80, 443, and outgoing DNS.",
            "validation_script": "#!/bin/bash\nFAILED=0\ncurl -s http://localhost:80 > /dev/null 2>&1 || FAILED=$((FAILED+1))\nnslookup google.com > /dev/null 2>&1 || FAILED=$((FAILED+1))\nif [ $FAILED -eq 0 ]; then\n  echo 'PASS: HTTP and DNS working'\n  exit 0\nelse\n  echo \"FAIL: $FAILED checks failed\"\n  exit 1\nfi",
            "solution_explanation": "Use 'iptables -L -n --line-numbers' to list rules. Delete blocking rules with 'iptables -D INPUT <number>' or flush with 'iptables -F'. Be careful not to lock yourself out of SSH.",
            "time_limit": 900,
            "is_free": False,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED + ["^iptables\\s+-F"],
            "tags": ["iptables", "firewall", "security", "networking"],
            "hints": [
                {"content": "List all iptables rules: iptables -L -n --line-numbers", "penalty": 5},
                {"content": "Delete a specific rule: iptables -D INPUT <rule-number>", "penalty": 10},
                {"content": "To flush all rules (nuclear option): iptables -F", "penalty": 20},
            ],
        },
        # ─── AWS EC2: Broken User Creation ────────────────────────────────
        {
            "technology": linux,
            "slug": "broken-useradd",
            "title": "Fix Broken User Creation",
            "subtitle": "useradd command is failing",
            "category": "User Management",
            "difficulty": "medium",
            "scenario_type": "fix",
            "infrastructure_type": "aws_ec2",
            "cloud_setup_script": """#!/bin/bash
# ── Break user management on the server ──
# NOTE: Order matters! All file content changes BEFORE permission lockdown.

# 1. Ensure shadow-utils is installed (provides useradd, pwck, grpck)
if command -v dnf &>/dev/null; then
    dnf install -y -q shadow-utils passwd util-linux 2>/dev/null || true
elif command -v yum &>/dev/null; then
    yum install -y -q shadow-utils passwd util-linux 2>/dev/null || true
elif command -v apt-get &>/dev/null; then
    apt-get install -y -qq passwd login 2>/dev/null || true
fi

# 2. Corrupt /etc/passwd by adding a malformed line
echo "CORRUPTED:::ENTRY::INVALID:LINE" >> /etc/passwd

# 3. Add a duplicate GID in /etc/group (BEFORE locking permissions!)
echo "fakegroup:x:0:" >> /etc/group

# 4. Create a lock file that blocks useradd
touch /etc/.pwd.lock

# 5. Leave a breadcrumb for the user
echo "NOTICE: User creation is broken. A new employee 'devops' needs an account urgently." > /root/TICKET.txt
echo "Requirements: home directory, bash shell, able to log in." >> /root/TICKET.txt

# 6. LAST: Break permissions on critical files (after all writes are done)
chmod 444 /etc/passwd
chmod 444 /etc/shadow
chmod 444 /etc/group

echo "Setup complete: user management is broken" >> /var/log/fixitlab-setup.log
""",
            "description": "The system administrator received an urgent ticket: new employees cannot be onboarded because the 'useradd' command is failing with errors. Critical system files have been tampered with — permissions are wrong, /etc/passwd contains corrupted entries, and lock files are blocking user management. Your mission is to diagnose all the issues, repair the user management system, and create the required 'devops' user account with a home directory and bash shell.",
            "objectives": [
                "Investigate why useradd is failing (check error messages carefully)",
                "Fix permissions on /etc/passwd (644), /etc/shadow (640), /etc/group (644)",
                "Remove corrupted/malformed entries from /etc/passwd and /etc/group",
                "Remove any stale lock files blocking user management",
                "Create user 'devops' with home directory (-m) and bash shell (-s /bin/bash)",
            ],
            "initial_state": "An Ubuntu 22.04 EC2 instance where user management is broken. The useradd command fails. Critical files (/etc/passwd, /etc/shadow, /etc/group) have wrong permissions and corrupted entries. A stale lock file exists. You need to fix everything and create the 'devops' user.",
            "validation_script": """#!/bin/bash
SCORE=0
TOTAL=5

# Step 1: Check /etc/passwd is readable and valid
if command -v pwck &>/dev/null; then
    pwck -r -q 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "FAIL: /etc/passwd has integrity errors. Run 'pwck' to check."
        exit 1
    fi
else
    # Fallback: check no obviously corrupted lines exist
    if grep -q 'CORRUPTED:::ENTRY' /etc/passwd 2>/dev/null; then
        echo "FAIL: /etc/passwd contains corrupted entries"
        exit 1
    fi
fi
echo "OK: /etc/passwd integrity check passed"
SCORE=$((SCORE + 1))

# Step 2: Check /etc/group is valid
if command -v grpck &>/dev/null; then
    grpck -r -q 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "FAIL: /etc/group has integrity errors. Run 'grpck' to check."
        exit 1
    fi
else
    if grep -q 'fakegroup' /etc/group 2>/dev/null; then
        echo "FAIL: /etc/group contains invalid entries"
        exit 1
    fi
fi
echo "OK: /etc/group integrity check passed"
SCORE=$((SCORE + 1))

# Step 3: Check permissions on critical files (portable stat)
get_perm() { stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null; }
PASSWD_PERM=$(get_perm /etc/passwd)
SHADOW_PERM=$(get_perm /etc/shadow)
GROUP_PERM=$(get_perm /etc/group)
if [ "$PASSWD_PERM" != "644" ]; then echo "FAIL: /etc/passwd permissions ($PASSWD_PERM, expected 644)"; exit 1; fi
if [ "$SHADOW_PERM" != "640" ] && [ "$SHADOW_PERM" != "600" ]; then echo "FAIL: /etc/shadow permissions ($SHADOW_PERM, expected 640)"; exit 1; fi
if [ "$GROUP_PERM" != "644" ]; then echo "FAIL: /etc/group permissions ($GROUP_PERM, expected 644)"; exit 1; fi
# Check lock file is removed
if [ -f /etc/.pwd.lock ]; then echo "FAIL: /etc/.pwd.lock still exists (blocks useradd)"; exit 1; fi
echo "OK: File permissions are correct and lock file removed"
SCORE=$((SCORE + 1))

# Step 4: Check user 'devops' exists with correct config
if ! id devops &>/dev/null; then echo "FAIL: User 'devops' does not exist"; exit 1; fi
DEVOPS_SHELL=$(getent passwd devops | cut -d: -f7)
DEVOPS_HOME=$(getent passwd devops | cut -d: -f6)
if [ "$DEVOPS_SHELL" != "/bin/bash" ]; then echo "FAIL: devops shell is '$DEVOPS_SHELL' not '/bin/bash'"; exit 1; fi
if [ ! -d "$DEVOPS_HOME" ]; then echo "FAIL: Home directory '$DEVOPS_HOME' missing"; exit 1; fi
echo "OK: User 'devops' exists with bash shell and home directory"
SCORE=$((SCORE + 1))

# Step 5: Verify useradd works now
useradd -m -s /bin/bash fixitlab_testuser 2>/dev/null
if [ $? -ne 0 ]; then echo "FAIL: useradd still broken"; exit 1; fi
userdel -r fixitlab_testuser 2>/dev/null
echo "OK: useradd command is working"
SCORE=$((SCORE + 1))

echo ""
echo "PASS: All checks passed ($SCORE/$TOTAL)"
exit 0
""",
            "solution_explanation": "1. Remove stale lock: rm /etc/.pwd.lock. 2. Fix permissions: chmod 644 /etc/passwd /etc/group && chmod 640 /etc/shadow. 3. Remove corrupted line from /etc/passwd (the 'CORRUPTED:::ENTRY' line). 4. Remove duplicate GID 0 group from /etc/group (the 'fakegroup' line). 5. Create user: useradd -m -s /bin/bash devops.",
            "time_limit": 900,
            "is_free": False,
            "is_active": True,
            "blocked_commands": GLOBAL_BLOCKED,
            "tags": ["useradd", "permissions", "passwd", "debugging"],
            "hints": [
                {"content": "Try running 'useradd testuser' and read the exact error message carefully.", "penalty": 5},
                {"content": "Check permissions: ls -la /etc/passwd /etc/shadow /etc/group — they should be 644, 640, 644.", "penalty": 10},
                {"content": "Use 'pwck' and 'grpck' to find corrupted entries in /etc/passwd and /etc/group.", "penalty": 15},
                {"content": "Fix: rm /etc/.pwd.lock && chmod 644 /etc/passwd /etc/group && chmod 640 /etc/shadow. Remove the CORRUPTED line from /etc/passwd and fakegroup from /etc/group. Then: useradd -m -s /bin/bash devops", "penalty": 25},
            ],
        },
    ]

    for s_data in scenarios_data:
        tags_list = s_data.pop("tags", [])
        hints_list = s_data.pop("hints", [])

        scenario, created = Scenario.objects.get_or_create(
            slug=s_data["slug"],
            defaults=s_data,
        )

        if created:
            print(f"  ✅ Scenario: {scenario.title}")

            # Add tags
            for tag_name in tags_list:
                tag = Tag.objects.filter(name=tag_name).first()
                if tag:
                    scenario.tags.add(tag)

            # Add hints
            for i, hint_data in enumerate(hints_list, 1):
                Hint.objects.create(
                    scenario=scenario,
                    order=i,
                    content=hint_data["content"],
                    penalty=hint_data["penalty"],
                )
        else:
            print(f"  ℹ️  Scenario exists: {scenario.title}")


if __name__ == "__main__":
    print("\n🌱 Seeding FixitLab database...\n")
    print("📋 Plans:")
    seed_plans()
    print("\n🖥️  Technologies:")
    seed_technologies()
    print("\n🏷️  Tags:")
    seed_tags()
    print("\n🎯 Scenarios:")
    seed_scenarios()
    print("\n✅ Seeding complete!\n")
