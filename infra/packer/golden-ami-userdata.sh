#!/bin/bash
###############################################################################
# FixitLab Golden AMI — user-data setup script
#
# Pre-installs everything a lab instance needs so cloud-init on actual labs
# only takes ~5-10 seconds (just scenario setup) instead of 2-3 minutes.
###############################################################################
set -e
export DEBIAN_FRONTEND=noninteractive

echo "=== FixitLab Golden AMI Build Started ===" | tee /var/log/fixitlab-ami-build.log

# ── 1. System updates ──
apt-get update -qq
apt-get upgrade -y -qq

# ── 2. Base packages every lab needs ──
apt-get install -y -qq \
  vim nano less procps net-tools curl wget htop \
  iproute2 iputils-ping dnsutils traceroute \
  strace lsof tree ncdu jq \
  bash-completion man-db sudo \
  openssh-server \
  python3 python3-pip \
  ca-certificates gnupg \
  cron at logrotate rsyslog \
  passwd login adduser \
  lvm2 parted fdisk \
  nginx \
  apt-transport-https software-properties-common

# ── 3. Pre-configure SSH for fast startup ──
# Generate host keys now so sshd doesn't regenerate them on each boot
ssh-keygen -A

# Optimize sshd config for fast connections
cat >> /etc/ssh/sshd_config << 'EOF'

# FixitLab optimizations — reduce connection delay
UseDNS no
GSSAPIAuthentication no
ClientAliveInterval 30
ClientAliveCountMax 3
MaxStartups 10:30:60
LoginGraceTime 30
EOF

# ── 4. Pre-configure cloud-init to be minimal ──
# Disable modules we don't need on lab instances — speeds up boot by ~20s
cat > /etc/cloud/cloud.cfg.d/99-fixitlab.cfg << 'EOF'
# FixitLab: minimal cloud-init for fast boot
cloud_init_modules:
  - bootcmd
  - write-files
  - users-groups
  - ssh

cloud_config_modules:
  - runcmd
  - scripts-user

cloud_final_modules:
  - final-message

# Disable unnecessary cloud-init features
apt:
  preserve_sources_list: true
EOF

# ── 5. Pre-create FixitLab directories ──
mkdir -p /opt/fixitlab
mkdir -p /var/log/fixitlab

# ── 6. Create lab helper utilities ──
cat > /opt/fixitlab/status.sh << 'STATUSEOF'
#!/bin/bash
# Show lab session info
if [ -f /opt/fixitlab_env ]; then
    source /opt/fixitlab_env
    echo "Session:  ${FIXITLAB_SESSION_ID:-unknown}"
    echo "Scenario: ${FIXITLAB_SCENARIO:-unknown}"
fi
if [ -f /opt/fixitlab/.ready ]; then
    echo "Status:   READY"
else
    echo "Status:   SETUP IN PROGRESS"
fi
STATUSEOF
chmod +x /opt/fixitlab/status.sh

# ── 7. Clean up package cache to reduce AMI size ──
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ── 8. Signal that AMI build is complete ──
touch /opt/fixitlab/.ami-ready
echo "=== FixitLab Golden AMI Build Complete ===" | tee -a /var/log/fixitlab-ami-build.log
