/**
 * Simulated stateful Linux guest shell for the VMware console / SSH labs.
 *
 * This is a pure client-side simulation (no backend round-trip). It is backed by
 * a real in-memory virtual file system (VFS) so file edits, mkdir/rm/cp/mv, and
 * the vi/vim/nano editors persist for the life of the console session.
 *
 * Public surface (extends, does not break, the original createLinuxShell(vm)):
 *   const shell = createLinuxShell(vm)
 *   shell.run(line)               -> { lines, prompt, sideEffect?, clear?, exit?, editor? }
 *   shell.prompt()                -> current prompt string
 *   shell.history                 -> array of entered commands
 *   shell.saveFile(path, content) -> persist an editor buffer back into the VFS
 *   shell.readFile(path)          -> read raw VFS content (or null)
 *   shell.pkgManager()            -> 'apt' | 'yum'
 *
 * Editor handshake with VmwareConsole.jsx:
 *   When the user runs `vi/vim/nano <file>`, run() returns
 *     { editor: { tool, path, content }, lines: [], prompt }
 *   The console renders an editable overlay seeded with `content`, and on save
 *   calls shell.saveFile(path, newContent). On quit-without-save it does nothing.
 */

const HUMAN_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function guestOsFamily(vm) {
  const g = (vm?.guest_os || vm?.guest_os_version || '').toLowerCase()
  if (g.includes('red hat') || g.includes('rhel') || g.includes('centos') || g.includes('rocky') || g.includes('alma') || g.includes('fedora')) return 'rhel'
  if (g.includes('debian') || g.includes('ubuntu')) return 'debian'
  return 'rhel'
}

function pkgManager(vm) {
  return guestOsFamily(vm) === 'debian' ? 'apt' : 'dnf'
}

/* ------------------------------------------------------------------ *
 * Virtual file system
 * ------------------------------------------------------------------ *
 * Representation:
 *   dir   = { type: 'dir',  mode, uid, gid, mtime, children: { name: node } }
 *   file  = { type: 'file', mode, uid, gid, mtime, content: string }
 *   link  = { type: 'link', mode, uid, gid, mtime, target: string }
 */

function nowStamp() {
  const d = new Date()
  return `${HUMAN_MONTHS[d.getMonth()]} ${String(d.getDate()).padStart(2, ' ')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function mkdir(mode = '0755', uid = 0, gid = 0) {
  return { type: 'dir', mode, uid, gid, mtime: nowStamp(), children: {} }
}
function mkfile(content = '', mode = '0644', uid = 0, gid = 0) {
  return { type: 'file', mode, uid, gid, mtime: nowStamp(), content }
}
function mklink(target, mode = '0777') {
  return { type: 'link', mode, uid: 0, gid: 0, mtime: nowStamp(), target }
}

function normalizePath(cwd, p) {
  if (!p) return cwd
  let abs = p.startsWith('/') ? p : `${cwd}/${p}`
  abs = abs.replace(/~(?=\/|$)/, '/root')
  const parts = abs.split('/')
  const stack = []
  for (const part of parts) {
    if (part === '' || part === '.') continue
    if (part === '..') { stack.pop(); continue }
    stack.push(part)
  }
  return '/' + stack.join('/')
}

function dirname(p) {
  const norm = p.replace(/\/+$/, '')
  const idx = norm.lastIndexOf('/')
  return idx <= 0 ? '/' : norm.slice(0, idx)
}
function basename(p) {
  const norm = p.replace(/\/+$/, '')
  return norm.slice(norm.lastIndexOf('/') + 1) || '/'
}

function createVFS(seedFn) {
  const root = mkdir()

  const resolveNode = (path, { followLink = true } = {}) => {
    if (path === '/') return root
    const parts = path.split('/').filter(Boolean)
    let node = root
    let curPath = ''
    for (let i = 0; i < parts.length; i++) {
      if (node.type === 'link' && followLink) {
        const tgt = resolveNode(node.target)
        if (!tgt) return null
        node = tgt
      }
      if (node.type !== 'dir') return null
      curPath += '/' + parts[i]
      const child = node.children[parts[i]]
      if (!child) return null
      node = child
    }
    if (node && node.type === 'link' && followLink) {
      return resolveNode(node.target)
    }
    return node
  }

  const lresolve = (path) => resolveNode(path, { followLink: false })

  const ensureDir = (path) => {
    const parts = path.split('/').filter(Boolean)
    let node = root
    for (const part of parts) {
      if (!node.children[part]) node.children[part] = mkdir()
      node = node.children[part]
      if (node.type !== 'dir') throw new Error(`Not a directory: ${path}`)
    }
    return node
  }

  const writeFile = (path, content, mode, uid, gid) => {
    const parent = ensureDir(dirname(path))
    const name = basename(path)
    const existing = parent.children[name]
    if (existing && existing.type === 'file') {
      existing.content = content
      existing.mtime = nowStamp()
      if (mode) existing.mode = mode
    } else {
      parent.children[name] = mkfile(content, mode, uid, gid)
    }
    return parent.children[name]
  }

  const api = { root, resolveNode, lresolve, ensureDir, writeFile, mkfile, mkdir, mklink }
  seedFn(api)
  return api
}

/* ------------------------------------------------------------------ *
 * Seed a realistic filesystem (60-100 files), distro-aware.
 * ------------------------------------------------------------------ */
function seedFilesystem(vm, fs) {
  const family = guestOsFamily(vm)
  const isRhel = family === 'rhel'
  const hostname = vm?.hostname || vm?.name || (isRhel ? 'rhel-app01' : 'ubuntu-app01')
  const ip = vm?.ip || '10.20.30.41'
  const gw = ip.split('.').slice(0, 3).join('.') + '.1'
  const cidr = ip.split('.').slice(0, 3).join('.')
  const cpu = vm?.cpu || 2
  const memMb = vm?.memory_mb || 4096
  const memKb = memMb * 1024
  const fqdn = `${hostname}.lab.fixitlab.local`

  // Top-level directory skeleton
  const dirs = [
    '/bin', '/sbin', '/lib', '/lib64', '/usr/bin', '/usr/sbin', '/usr/lib', '/usr/local/bin',
    '/usr/local/sbin', '/usr/share', '/usr/include', '/boot/grub2', '/dev', '/dev/disk/by-uuid',
    '/etc', '/etc/ssh', '/etc/nginx/conf.d', '/etc/nginx/sites-enabled', '/etc/systemd/system',
    '/etc/systemd/system/multi-user.target.wants', '/etc/security', '/etc/pam.d', '/etc/cron.d',
    '/etc/cron.daily', '/etc/logrotate.d', '/etc/sudoers.d', '/etc/profile.d', '/etc/skel',
    '/etc/default', '/home', '/home/devops', '/home/devops/.ssh', '/media', '/mnt', '/opt',
    '/opt/app', '/proc', '/proc/sys/kernel', '/proc/sys/net/ipv4', '/proc/sys/vm', '/root',
    '/root/.ssh', '/run', '/srv', '/sys', '/tmp', '/var', '/var/cache', '/var/lib',
    '/var/lib/docker', '/var/lib/mysql', '/var/log', '/var/log/nginx', '/var/log/journal',
    '/var/spool/cron', '/var/spool/mail', '/var/www/html', '/var/tmp',
  ]
  if (isRhel) {
    dirs.push('/etc/yum.repos.d', '/etc/sysconfig', '/etc/sysconfig/network-scripts',
      '/etc/selinux', '/etc/dnf', '/etc/httpd/conf', '/etc/httpd/conf.d')
  } else {
    dirs.push('/etc/apt', '/etc/apt/sources.list.d', '/etc/network', '/etc/netplan',
      '/etc/apache2/sites-enabled')
  }
  dirs.forEach(d => fs.ensureDir(d))

  const W = (p, c, mode, uid, gid) => fs.writeFile(p, c, mode, uid, gid)

  // ---- /etc identity & release ----
  W('/etc/hostname', `${hostname}\n`)
  if (isRhel) {
    W('/etc/os-release',
`NAME="Red Hat Enterprise Linux"
VERSION="9.3 (Plow)"
ID="rhel"
ID_LIKE="fedora"
VERSION_ID="9.3"
PLATFORM_ID="platform:el9"
PRETTY_NAME="Red Hat Enterprise Linux 9.3 (Plow)"
ANSI_COLOR="0;31"
CPE_NAME="cpe:/o:redhat:enterprise_linux:9::baseos"
HOME_URL="https://www.redhat.com/"
`)
    W('/etc/redhat-release', 'Red Hat Enterprise Linux release 9.3 (Plow)\n')
    W('/etc/system-release', 'Red Hat Enterprise Linux release 9.3 (Plow)\n')
  } else {
    W('/etc/os-release',
`NAME="Ubuntu"
VERSION="22.04.4 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 22.04.4 LTS"
VERSION_ID="22.04"
VERSION_CODENAME=jammy
UBUNTU_CODENAME=jammy
HOME_URL="https://www.ubuntu.com/"
`)
    W('/etc/lsb-release',
`DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=22.04
DISTRIB_CODENAME=jammy
DISTRIB_DESCRIPTION="Ubuntu 22.04.4 LTS"
`)
    W('/etc/debian_version', 'bookworm/sid\n')
  }
  W('/etc/machine-id', 'a1b2c3d4e5f60718293a4b5c6d7e8f90\n')

  // ---- hosts / networking ----
  W('/etc/hosts',
`127.0.0.1   localhost localhost.localdomain localhost4
::1         localhost localhost.localdomain localhost6
${ip}   ${fqdn} ${hostname}
${cidr}.10   db01.lab.fixitlab.local db01
${cidr}.20   web01.lab.fixitlab.local web01
`)
  W('/etc/resolv.conf',
`# Generated by NetworkManager
search lab.fixitlab.local
nameserver ${cidr}.2
nameserver 8.8.8.8
options edns0 trust-ad
`)
  W('/etc/hosts.allow', '# hosts.allow\nsshd: 10.0.0.0/8\n')
  W('/etc/hosts.deny', '# hosts.deny\nALL: ALL\n')
  W('/etc/nsswitch.conf', 'passwd:     files sss\ngroup:      files sss\nhosts:      files dns\nnetworks:   files\n')

  if (isRhel) {
    W('/etc/sysconfig/network', 'NETWORKING=yes\nHOSTNAME=' + hostname + '\nGATEWAY=' + gw + '\n')
    W('/etc/sysconfig/network-scripts/ifcfg-eth0',
`TYPE=Ethernet
BOOTPROTO=none
NAME=eth0
DEVICE=eth0
ONBOOT=yes
IPADDR=${ip}
PREFIX=24
GATEWAY=${gw}
DNS1=${cidr}.2
`)
    W('/etc/sysconfig/selinux', 'SELINUX=enforcing\nSELINUXTYPE=targeted\n')
  } else {
    W('/etc/network/interfaces',
`# interfaces(5) file
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
    address ${ip}
    netmask 255.255.255.0
    gateway ${gw}
    dns-nameservers ${cidr}.2 8.8.8.8
`)
    W('/etc/netplan/00-installer-config.yaml',
`network:
  version: 2
  ethernets:
    eth0:
      addresses: [${ip}/24]
      routes:
        - to: default
          via: ${gw}
      nameservers:
        addresses: [${cidr}.2, 8.8.8.8]
`)
  }

  // ---- fstab / mtab ----
  W('/etc/fstab',
`# /etc/fstab
UUID=8f3b2c1a-0e4d-4c6b-9a7f-1d2e3f4a5b6c  /          xfs     defaults        0 0
UUID=1a2b3c4d-5e6f-7081-92a3-b4c5d6e7f809  /boot      xfs     defaults        0 0
UUID=c0ffee00-dead-beef-cafe-0123456789ab  swap       swap    defaults        0 0
tmpfs                                       /dev/shm   tmpfs   defaults        0 0
`)
  W('/etc/mtab', '/dev/sda1 / xfs rw,relatime 0 0\n')
  W('/dev/disk/by-uuid/8f3b2c1a-0e4d-4c6b-9a7f-1d2e3f4a5b6c', '', '0777')

  // ---- users / groups ----
  W('/etc/passwd',
`root:x:0:0:root:/root:/bin/bash
bin:x:1:1:bin:/bin:/sbin/nologin
daemon:x:2:2:daemon:/sbin:/sbin/nologin
adm:x:3:4:adm:/var/adm:/sbin/nologin
sync:x:5:0:sync:/sbin:/bin/sync
shutdown:x:6:0:shutdown:/sbin:/sbin/shutdown
halt:x:7:0:halt:/sbin:/sbin/halt
mail:x:8:12:mail:/var/spool/mail:/sbin/nologin
nobody:x:65534:65534:Kernel Overflow User:/:/sbin/nologin
sshd:x:74:74:Privilege-separated SSH:/var/empty/sshd:/sbin/nologin
nginx:x:990:990:Nginx web server:/var/lib/nginx:/sbin/nologin
mysql:x:27:27:MySQL Server:/var/lib/mysql:/sbin/nologin
chrony:x:993:992:chrony:/var/lib/chrony:/sbin/nologin
devops:x:1000:1000:DevOps Engineer:/home/devops:/bin/bash
`)
  W('/etc/group',
`root:x:0:
bin:x:1:
daemon:x:2:
sys:x:3:
adm:x:4:devops
wheel:x:10:devops
sshd:x:74:
nginx:x:990:
mysql:x:27:
sudo:x:27:devops
devops:x:1000:
`)
  W('/etc/shadow',
`root:$6$Xy9Lk2/QpR$jT0HqW.bK7sZ1m8nO3pVcdeFgHiJ.kLmNoPqRsTuVwXyZ012345aBcDeFg/:19800:0:99999:7:::
bin:*:19800:0:99999:7:::
daemon:*:19800:0:99999:7:::
sshd:!!:19800::::::
nginx:!!:19800::::::
mysql:!!:19800::::::
devops:$6$aBcDeF$gHiJkLmNoPqRsTuVwXyZ0123456789.AbCdEfGhIjKlMnOpQrStUvWx/:19800:0:99999:7:::
`, '0000')
  W('/etc/gshadow', 'root:::\nwheel:::devops\nsudo:!::devops\n', '0000')
  W('/etc/login.defs', 'PASS_MAX_DAYS\t99999\nPASS_MIN_DAYS\t0\nUID_MIN\t\t1000\nGID_MIN\t\t1000\nUMASK\t\t022\n')
  W('/etc/subuid', 'devops:100000:65536\n')
  W('/etc/subgid', 'devops:100000:65536\n')
  W('/etc/sudoers',
`## sudoers
Defaults    env_reset
Defaults    secure_path = /sbin:/bin:/usr/sbin:/usr/bin
root    ALL=(ALL)       ALL
%wheel  ALL=(ALL)       ALL
%sudo   ALL=(ALL:ALL)   ALL
#includedir /etc/sudoers.d
`, '0440')
  W('/etc/sudoers.d/devops', 'devops ALL=(ALL) NOPASSWD: /bin/systemctl\n', '0440')

  // ---- shells & profile ----
  W('/etc/shells', '/bin/sh\n/bin/bash\n/usr/bin/bash\n/bin/nologin\n/sbin/nologin\n')
  W('/etc/profile', '# /etc/profile\nexport PATH\numask 022\nfor i in /etc/profile.d/*.sh ; do\n  [ -r "$i" ] && . "$i"\ndone\n')
  W('/etc/bashrc', '# /etc/bashrc\nif [ "$PS1" ]; then\n  PS1="[\\u@\\h \\W]\\$ "\nfi\n')
  W('/etc/profile.d/lang.sh', 'export LANG=en_US.UTF-8\n')
  W('/etc/environment', 'LANG=en_US.UTF-8\nPATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n')
  W('/etc/inputrc', 'set bell-style none\nset show-all-if-ambiguous on\n')
  W('/etc/vimrc', 'syntax on\nset hlsearch\nset background=dark\n')
  W('/etc/issue', `\\S\nKernel \\r on an \\m\n`)
  W('/etc/motd', `Welcome to ${hostname} — FixitLab managed host. Authorized use only.\n`)
  W('/etc/timezone', 'UTC\n')
  W('/etc/localtime', '', '0777')

  // ---- SSH ----
  W('/etc/ssh/sshd_config',
`# OpenSSH server configuration
Port 22
#AddressFamily any
ListenAddress 0.0.0.0
HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_ed25519_key
PermitRootLogin yes
PasswordAuthentication yes
PubkeyAuthentication yes
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding no
ClientAliveInterval 300
Subsystem sftp /usr/lib/openssh/sftp-server
`)
  W('/etc/ssh/ssh_config', 'Host *\n    SendEnv LANG LC_*\n    HashKnownHosts yes\n    GSSAPIAuthentication yes\n')
  W('/etc/ssh/ssh_host_ed25519_key.pub',
    'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK7Q9f2mF3sZ1vY8nQwErTyUiOpAsDfGhJkLzXcVbNm root@' + hostname + '\n')
  W('/root/.ssh/authorized_keys',
    'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDexampleadminkeyfixitlab... admin@bastion\n', '0600')
  W('/root/.ssh/known_hosts', `${cidr}.10 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA...\n`, '0644')
  W('/home/devops/.ssh/authorized_keys', 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5devopskey... devops@laptop\n', '0600', 1000, 1000)

  // ---- web servers ----
  W('/etc/nginx/nginx.conf',
`user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log notice;
pid /run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;
    include /etc/nginx/conf.d/*.conf;
}
`)
  W('/etc/nginx/conf.d/default.conf',
`server {
    listen 80 default_server;
    server_name _;
    root /var/www/html;
    location / {
        try_files $uri $uri/ =404;
    }
}
`)
  W('/etc/nginx/mime.types', 'types {\n    text/html  html htm;\n    text/css   css;\n    application/javascript js;\n}\n')
  W('/var/www/html/index.html', '<!DOCTYPE html>\n<html><head><title>Welcome</title></head>\n<body><h1>It works! — ' + hostname + '</h1></body></html>\n')
  if (isRhel) {
    W('/etc/httpd/conf/httpd.conf', 'ServerRoot "/etc/httpd"\nListen 80\nInclude conf.d/*.conf\nUser apache\nGroup apache\n')
  } else {
    W('/etc/apache2/apache2.conf', 'ServerRoot "/etc/apache2"\nInclude ports.conf\nUser www-data\nGroup www-data\n')
  }

  // ---- databases / app ----
  W('/etc/my.cnf', '[mysqld]\ndatadir=/var/lib/mysql\nsocket=/var/lib/mysql/mysql.sock\nbind-address=127.0.0.1\nport=3306\n[client]\nsocket=/var/lib/mysql/mysql.sock\n')
  W('/opt/app/config.yml', 'app:\n  name: fixit-api\n  port: 8080\n  log_level: info\ndatabase:\n  host: 127.0.0.1\n  port: 3306\n  name: appdb\n')
  W('/opt/app/.env', 'NODE_ENV=production\nDB_PASSWORD=changeme\nSECRET_KEY=s3cr3t\n', '0600')

  // ---- kernel & sysctl & limits ----
  W('/etc/sysctl.conf',
`# sysctl settings
net.ipv4.ip_forward = 0
net.ipv4.conf.all.rp_filter = 1
kernel.sysrq = 16
kernel.pid_max = 4194304
vm.swappiness = 30
fs.file-max = 2097152
`)
  W('/etc/sysctl.d/99-tuning.conf', 'net.core.somaxconn = 1024\nnet.ipv4.tcp_tw_reuse = 1\n')
  W('/etc/security/limits.conf', '*    soft    nofile    65536\n*    hard    nofile    65536\nroot soft    nofile    65536\n')
  W('/etc/modules-load.d/extra.conf', 'br_netfilter\noverlay\n')

  // ---- SELinux (rhel) ----
  if (isRhel) {
    W('/etc/selinux/config',
`# This file controls the state of SELinux on the system.
# SELINUX= can take one of these three values:
#     enforcing - SELinux security policy is enforced.
#     permissive - SELinux prints warnings instead of enforcing.
#     disabled - No SELinux policy is loaded.
SELINUX=enforcing
SELINUXTYPE=targeted
`)
  }

  // ---- package repos ----
  if (isRhel) {
    W('/etc/yum.repos.d/redhat.repo', '[rhel-9-baseos]\nname=RHEL 9 BaseOS\nenabled=1\ngpgcheck=1\n')
    W('/etc/yum.repos.d/epel.repo', '[epel]\nname=Extra Packages for Enterprise Linux 9\nbaseurl=https://download.example/epel/9/\nenabled=1\ngpgcheck=1\n')
    W('/etc/dnf/dnf.conf', '[main]\ngpgcheck=1\ninstallonly_limit=3\nclean_requirements_on_remove=True\nbest=True\n')
  } else {
    W('/etc/apt/sources.list',
`deb http://archive.ubuntu.com/ubuntu jammy main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse
deb http://security.ubuntu.com/ubuntu jammy-security main restricted universe multiverse
`)
    W('/etc/apt/sources.list.d/docker.list', 'deb [arch=amd64] https://download.docker.com/linux/ubuntu jammy stable\n')
  }

  // ---- cron ----
  W('/etc/crontab',
`SHELL=/bin/bash
PATH=/sbin:/bin:/usr/sbin:/usr/bin
MAILTO=root

# m h dom mon dow user  command
17 *    * * *   root    cd / && run-parts --report /etc/cron.hourly
25 6    * * *   root    test -x /usr/sbin/anacron || run-parts --report /etc/cron.daily
`)
  W('/etc/cron.d/sysstat', '*/10 * * * * root /usr/lib/sa/sa1 1 1\n')
  W('/etc/cron.daily/logrotate', '#!/bin/sh\n/usr/sbin/logrotate /etc/logrotate.conf\n', '0755')
  W('/var/spool/cron/root', '0 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1\n', '0600')
  W('/etc/logrotate.conf', 'weekly\nrotate 4\ncreate\ninclude /etc/logrotate.d\n')
  W('/etc/logrotate.d/nginx', '/var/log/nginx/*.log {\n    daily\n    rotate 14\n    compress\n}\n')

  // ---- systemd unit files ----
  W('/etc/systemd/system/app.service',
`[Unit]
Description=FixitLab API service
After=network.target mysqld.service

[Service]
Type=simple
User=devops
WorkingDirectory=/opt/app
ExecStart=/usr/bin/node /opt/app/server.js
Restart=on-failure

[Install]
WantedBy=multi-user.target
`)
  W('/usr/lib/systemd/system/sshd.service', '[Unit]\nDescription=OpenSSH server daemon\n[Service]\nExecStart=/usr/sbin/sshd -D\n[Install]\nWantedBy=multi-user.target\n')

  // ---- PAM ----
  W('/etc/pam.d/sshd', 'auth       substack     password-auth\naccount    required     pam_nologin.so\nsession    required     pam_loginuid.so\n')
  W('/etc/pam.d/system-auth', 'auth        required      pam_unix.so\naccount     required      pam_unix.so\npassword    required      pam_pwquality.so\n')

  // ---- chrony / time ----
  W('/etc/chrony.conf', 'pool 2.pool.ntp.org iburst\ndriftfile /var/lib/chrony/drift\nmakestep 1.0 3\nrtcsync\n')

  // ---- skeleton dotfiles ----
  W('/etc/skel/.bashrc', '# .bashrc\nalias ll=\'ls -l\'\nalias la=\'ls -A\'\n')
  W('/root/.bashrc', '# .bashrc\nalias ll=\'ls -lh\'\nalias grep=\'grep --color=auto\'\nexport EDITOR=vi\n')
  W('/root/.bash_profile', '# .bash_profile\n[ -f ~/.bashrc ] && . ~/.bashrc\n')
  W('/root/.bash_history',
`uptime
df -h
systemctl status nginx
journalctl -u nginx --no-pager
free -m
ip addr
`)
  W('/root/.vimrc', 'set number\nset expandtab\nset tabstop=4\nsyntax on\n')
  W('/root/anaconda-ks.cfg', '# Kickstart file (generated)\nlang en_US.UTF-8\nkeyboard us\ntimezone UTC\nrootpw --iscrypted $6$...\nbootloader --location=mbr\n')
  W('/home/devops/.bashrc', '# .bashrc\nalias ll=\'ls -l\'\nexport PS1=\'[\\u@\\h \\W]\\$ \'\n', '0644', 1000, 1000)
  W('/home/devops/README.txt', 'Lab host. Use sudo for privileged commands.\n', '0644', 1000, 1000)

  // ---- /proc (basics, runtime-ish) ----
  W('/proc/version', `Linux version 5.15.0-91-generic (build@fixitlab) (gcc 11.4.0) #101-Ubuntu SMP\n`, '0444')
  W('/proc/cmdline', 'BOOT_IMAGE=/boot/vmlinuz-5.15.0-91-generic root=UUID=8f3b2c1a-0e4d-4c6b-9a7f-1d2e3f4a5b6c ro quiet\n', '0444')
  W('/proc/uptime', '1216843.55 4827361.20\n', '0444')
  W('/proc/loadavg', '0.08 0.12 0.09 1/482 18342\n', '0444')
  W('/proc/cpuinfo', Array.from({ length: cpu }).map((_, i) =>
    `processor\t: ${i}\nvendor_id\t: GenuineIntel\nmodel name\t: Intel(R) Xeon(R) Gold 6248 CPU @ 2.50GHz\ncpu MHz\t\t: 2500.000\ncache size\t: 28160 KB\n`).join('\n'), '0444')
  W('/proc/meminfo',
`MemTotal:       ${memKb} kB
MemFree:        ${Math.round(memKb * 0.34)} kB
MemAvailable:   ${Math.round(memKb * 0.55)} kB
Buffers:        ${Math.round(memKb * 0.02)} kB
Cached:         ${Math.round(memKb * 0.20)} kB
SwapTotal:      2097148 kB
SwapFree:       2097148 kB
`, '0444')
  W('/proc/mounts', '/dev/sda1 / xfs rw,relatime 0 0\nproc /proc proc rw,nosuid,nodev,noexec 0 0\ntmpfs /dev/shm tmpfs rw,nosuid,nodev 0 0\n', '0444')
  W('/proc/sys/kernel/hostname', `${hostname}\n`)
  W('/proc/sys/net/ipv4/ip_forward', '0\n')
  W('/proc/sys/vm/swappiness', '30\n')
  W('/sys/class/net/eth0/address', '00:50:56:a1:b2:c3\n')

  // ---- boot ----
  W('/boot/grub2/grub.cfg', '# GRUB config (generated)\nset default="0"\nset timeout=5\nmenuentry "Red Hat Enterprise Linux" { linux /vmlinuz root=UUID=8f3b... }\n', '0600')
  W('/boot/config-5.15.0-91-generic', 'CONFIG_LOCALVERSION=""\nCONFIG_SMP=y\nCONFIG_X86_64=y\n')

  // ---- logs ----
  const today = new Date()
  const ds = `${HUMAN_MONTHS[today.getMonth()]} ${String(today.getDate()).padStart(2, ' ')}`
  W('/var/log/messages',
`${ds} 00:00:01 ${hostname} systemd[1]: Started Daily Cleanup of Temporary Directories.
${ds} 02:00:11 ${hostname} CROND[1842]: (root) CMD (/usr/local/bin/backup.sh)
${ds} 06:25:30 ${hostname} run-parts(/etc/cron.daily)[2010]: starting logrotate
${ds} 09:14:22 ${hostname} kernel: [1216000.1] eth0: link up, 10000 Mbps, full duplex
${ds} 11:02:48 ${hostname} systemd[1]: nginx.service: Failed with result 'exit-code'.
${ds} 11:02:48 ${hostname} nginx[3122]: nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)
`)
  W('/var/log/secure',
`${ds} 08:01:12 ${hostname} sshd[1201]: Accepted password for root from ${gw} port 51022 ssh2
${ds} 08:01:12 ${hostname} sshd[1201]: pam_unix(sshd:session): session opened for user root(uid=0)
${ds} 08:44:55 ${hostname} sudo: devops : TTY=pts/1 ; PWD=/home/devops ; USER=root ; COMMAND=/bin/systemctl restart nginx
${ds} 09:15:02 ${hostname} sshd[1450]: Failed password for invalid user admin from 203.0.113.7 port 40122 ssh2
`)
  W('/var/log/auth.log', `${ds} 08:01:12 ${hostname} sshd[1201]: Accepted publickey for devops from ${gw} port 50122 ssh2\n`)
  W('/var/log/syslog', `${ds} 00:00:01 ${hostname} systemd[1]: Starting Daily apt download activities...\n`)
  W('/var/log/dmesg', '[    0.000000] Linux version 5.15.0-91-generic\n[    1.234567] systemd[1]: Reached target Multi-User System.\n')
  W('/var/log/boot.log', '[  OK  ] Reached target Multi-User System.\n[  OK  ] Started OpenSSH server daemon.\n')
  W('/var/log/cron', `${ds} 02:00:01 ${hostname} CROND[1842]: (root) CMD (/usr/local/bin/backup.sh)\n`)
  W('/var/log/nginx/access.log', `${gw} - - [${String(today.getDate()).padStart(2, '0')}/${HUMAN_MONTHS[today.getMonth()]}/${today.getFullYear()}:09:14:01 +0000] "GET / HTTP/1.1" 200 612 "-" "curl/7.76.1"\n`)
  W('/var/log/nginx/error.log', `${today.getFullYear()}/06/18 11:02:48 [emerg] 3122#3122: bind() to 0.0.0.0:80 failed (98: Address already in use)\n`)
  W('/var/log/wtmp', '', '0664')
  W('/var/log/lastlog', '', '0644')
}

/* ------------------------------------------------------------------ *
 * Service & runtime state (per session)
 * ------------------------------------------------------------------ */
function seedServices() {
  return {
    sshd: { active: 'active', enabled: 'enabled', desc: 'OpenSSH server daemon', pid: 1201, since: '8h ago' },
    nginx: { active: 'failed', enabled: 'enabled', desc: 'The nginx HTTP and reverse proxy server', pid: null, since: 'failed' },
    httpd: { active: 'inactive', enabled: 'disabled', desc: 'The Apache HTTP Server', pid: null, since: 'dead' },
    mysqld: { active: 'active', enabled: 'enabled', desc: 'MySQL Server', pid: 1502, since: '8h ago' },
    docker: { active: 'active', enabled: 'enabled', desc: 'Docker Application Container Engine', pid: 1610, since: '8h ago' },
    crond: { active: 'active', enabled: 'enabled', desc: 'Command Scheduler', pid: 1188, since: '8h ago' },
    firewalld: { active: 'active', enabled: 'enabled', desc: 'firewalld - dynamic firewall daemon', pid: 1170, since: '8h ago' },
    NetworkManager: { active: 'active', enabled: 'enabled', desc: 'Network Manager', pid: 1090, since: '8h ago' },
    chronyd: { active: 'active', enabled: 'enabled', desc: 'NTP client/server', pid: 1140, since: '8h ago' },
    'app': { active: 'active', enabled: 'enabled', desc: 'FixitLab API service', pid: 1820, since: '7h ago' },
  }
}

/* ------------------------------------------------------------------ *
 * Output helpers
 * ------------------------------------------------------------------ */
function permString(node) {
  const t = node.type === 'dir' ? 'd' : node.type === 'link' ? 'l' : '-'
  const m = (node.mode || '0644').slice(-3)
  const map = ['---', '--x', '-w-', '-wx', 'r--', 'r-x', 'rw-', 'rwx']
  const bits = m.split('').map(c => map[parseInt(c, 10)] || '---').join('')
  return t + bits
}
function userName(uid) {
  return ({ 0: 'root', 27: 'mysql', 74: 'sshd', 990: 'nginx', 1000: 'devops' })[uid] || String(uid)
}
function groupName(gid) {
  return ({ 0: 'root', 12: 'mail', 27: 'mysql', 74: 'sshd', 990: 'nginx', 1000: 'devops' })[gid] || String(gid)
}

export function createLinuxShell(vm) {
  const family = guestOsFamily(vm)
  const isRhel = family === 'rhel'
  const hostname = vm?.hostname || vm?.name || (isRhel ? 'rhel-app01' : 'ubuntu-app01')
  const ip = vm?.ip || '10.20.30.41'
  const gw = ip.split('.').slice(0, 3).join('.') + '.1'
  const diskGb = vm?.disk_gb || 40
  const memMb = vm?.memory_mb || 4096
  const cpu = vm?.cpu || 2

  const cwd = { path: '/root' }
  const env = {
    USER: 'root', LOGNAME: 'root', HOME: '/root', SHELL: '/bin/bash',
    PATH: '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    LANG: 'en_US.UTF-8', TERM: 'xterm-256color', PWD: '/root', HOSTNAME: hostname,
  }
  const history = []
  const vfs = createVFS((api) => seedFilesystem(vm, api))
  const services = seedServices()
  let selinuxMode = isRhel ? 'Enforcing' : 'Disabled'
  let nextPid = 19000

  // Guest-repair side-effect state (preserved integration)
  let diskRescanned = !vm?.guest_disk_hidden
  let diskFormatted = !!vm?.guest_disk_formatted
  let diskMounted = !!vm?.guest_disk_mounted
  let moduleLoaded = !vm?.kernel_module_missing

  const prompt = () => `[root@${hostname.split('.')[0]} ${cwd.path === '/root' ? '~' : basename(cwd.path)}]# `
  const abs = (p) => normalizePath(cwd.path, p)

  /* ----- editor save hook (used by VmwareConsole overlay) ----- */
  const saveFile = (path, content) => {
    const p = abs(path)
    vfs.writeFile(p, content.endsWith('\n') || content === '' ? content : content + '\n')
    return true
  }
  const readFile = (path) => {
    const node = vfs.resolveNode(abs(path))
    return node && node.type === 'file' ? node.content : null
  }

  /* ----- argument parsing ----- */
  const parseArgs = (args) => {
    const flags = new Set()
    const positional = []
    for (const a of args) {
      if (a.startsWith('--')) flags.add(a)
      else if (a.startsWith('-') && a.length > 1) a.slice(1).split('').forEach(f => flags.add('-' + f))
      else positional.push(a)
    }
    return { flags, positional, has: (f) => flags.has(f) }
  }

  const run = (raw) => {
    const line = raw.trim()
    if (!line) return { lines: [''], prompt: prompt() }
    history.push(line)

    // Handle redirection: cmd > file  /  cmd >> file
    let redirect = null
    let work = line
    const redirMatch = line.match(/\s(>>?)\s*(\S+)\s*$/)
    if (redirMatch) {
      redirect = { append: redirMatch[1] === '>>', path: redirMatch[2] }
      work = line.slice(0, redirMatch.index).trim()
    }

    const parts = work.split(/\s+/)
    const cmd = parts[0]
    const lc = cmd.toLowerCase()
    const args = parts.slice(1)
    const { flags, positional, has } = parseArgs(args)
    const out = []
    let sideEffect = null
    let editor = null

    const notFound = () => out.push(`bash: ${cmd}: command not found`)
    const emit = (s) => { if (Array.isArray(s)) out.push(...s); else String(s).split('\n').forEach(l => out.push(l)) }

    /* =================== file system =================== */
    if (lc === 'pwd') emit(cwd.path)
    else if (lc === 'cd') {
      const dest = abs(positional[0] || '/root')
      const node = vfs.resolveNode(dest)
      if (!node) emit(`bash: cd: ${positional[0]}: No such file or directory`)
      else if (node.type !== 'dir') emit(`bash: cd: ${positional[0]}: Not a directory`)
      else { cwd.path = dest; env.PWD = dest }
    }
    else if (lc === 'ls' || lc === 'll' || lc === 'dir' || lc === 'vdir') {
      const long = lc === 'll' || has('-l') || has('-la') || has('-al')
      const allF = has('-a') || has('-la') || has('-al') || has('-A')
      const targets = positional.length ? positional : [cwd.path]
      targets.forEach((t, ti) => {
        const p = abs(t)
        const node = vfs.resolveNode(p)
        if (!node) { emit(`ls: cannot access '${t}': No such file or directory`); return }
        if (targets.length > 1) out.push(`${t}:`)
        if (node.type === 'dir') {
          let names = Object.keys(node.children).sort()
          if (allF) names = ['.', '..', ...names]
          if (!long) {
            emit(names.length ? names.join('  ') : '')
          } else {
            out.push(`total ${Math.max(4, names.length * 4)}`)
            names.forEach(n => {
              const child = n === '.' ? node : n === '..' ? (vfs.resolveNode(dirname(p)) || node) : node.children[n]
              const linkSuffix = child.type === 'link' ? ` -> ${child.target}` : ''
              const sz = child.type === 'dir' ? 4096 : (child.content?.length || 0)
              out.push(`${permString(child)} ${child.type === 'dir' ? 2 : 1} ${userName(child.uid).padEnd(8)} ${groupName(child.gid).padEnd(8)} ${String(sz).padStart(6)} ${child.mtime || nowStamp()} ${n}${linkSuffix}`)
            })
          }
        } else {
          if (long) out.push(`${permString(node)} 1 ${userName(node.uid)} ${groupName(node.gid)} ${node.content?.length || 0} ${node.mtime} ${basename(p)}`)
          else emit(basename(p))
        }
        if (targets.length > 1 && ti < targets.length - 1) out.push('')
      })
    }
    else if (lc === 'cat' || lc === 'more' || lc === 'less' || lc === 'bat') {
      if (!positional.length) emit('')
      else positional.forEach(f => {
        const node = vfs.resolveNode(abs(f))
        if (!node) emit(`${lc}: ${f}: No such file or directory`)
        else if (node.type === 'dir') emit(`${lc}: ${f}: Is a directory`)
        else emit(node.content.replace(/\n$/, '') || '')
      })
    }
    else if (lc === 'head' || lc === 'tail') {
      const nFlag = args.find(a => /^-\d+$/.test(a) || a === '-n')
      let count = 10
      const nIdx = args.indexOf('-n')
      if (nIdx >= 0 && args[nIdx + 1]) count = parseInt(args[nIdx + 1], 10)
      else if (nFlag && /^-\d+$/.test(nFlag)) count = parseInt(nFlag.slice(1), 10)
      const file = positional[0]
      const node = file ? vfs.resolveNode(abs(file)) : null
      if (!node || node.type !== 'file') emit(`${lc}: cannot open '${file || ''}' for reading: No such file or directory`)
      else {
        const all = node.content.replace(/\n$/, '').split('\n')
        const sel = lc === 'head' ? all.slice(0, count) : all.slice(-count)
        emit(sel)
      }
    }
    else if (lc === 'echo') {
      // guest disk rescan side-effect: echo "- - -" > /sys/class/scsi_host/.../scan
      if (line.includes('scsi_host') && line.includes('scan')) {
        if (vm?.guest_disk_hidden && !diskRescanned) {
          diskRescanned = true
          sideEffect = { action: 'guest_rescan_scsi', vm_id: vm?.id }
        }
        out.push('')
      } else {
        const interpret = has('-e')
        const noNl = has('-n')
        let text = args.filter(a => a !== '-e' && a !== '-n').join(' ').replace(/^["']|["']$/g, '')
        if (interpret) text = text.replace(/\\n/g, '\n').replace(/\\t/g, '\t')
        // simple $VAR / ${VAR} expansion
        text = text.replace(/\$\{?(\w+)\}?/g, (m, k) => (env[k] !== undefined ? env[k] : m))
        emit(noNl && !text.includes('\n') ? text : text)
      }
    }
    else if (lc === 'touch') {
      if (!positional.length) emit('touch: missing file operand')
      else positional.forEach(f => {
        const p = abs(f)
        const node = vfs.resolveNode(p)
        if (node) node.mtime = nowStamp()
        else vfs.writeFile(p, '')
      })
    }
    else if (lc === 'mkdir') {
      if (!positional.length) emit('mkdir: missing operand')
      else positional.forEach(d => {
        const p = abs(d)
        if (has('-p')) { try { vfs.ensureDir(p) } catch (e) { emit(`mkdir: ${e.message}`) } }
        else {
          const parent = vfs.resolveNode(dirname(p))
          if (!parent || parent.type !== 'dir') emit(`mkdir: cannot create directory '${d}': No such file or directory`)
          else if (parent.children[basename(p)]) emit(`mkdir: cannot create directory '${d}': File exists`)
          else parent.children[basename(p)] = vfs.mkdir()
        }
      })
    }
    else if (lc === 'rmdir') {
      positional.forEach(d => {
        const p = abs(d); const node = vfs.resolveNode(p)
        if (!node) emit(`rmdir: failed to remove '${d}': No such file or directory`)
        else if (node.type !== 'dir') emit(`rmdir: failed to remove '${d}': Not a directory`)
        else if (Object.keys(node.children).length) emit(`rmdir: failed to remove '${d}': Directory not empty`)
        else { const par = vfs.resolveNode(dirname(p)); delete par.children[basename(p)] }
      })
    }
    else if (lc === 'rm') {
      const recursive = has('-r') || has('-R') || has('-rf') || has('-fr')
      const force = has('-f') || has('-rf') || has('-fr')
      if (!positional.length) { if (!force) emit('rm: missing operand') }
      else positional.forEach(f => {
        const p = abs(f); const node = vfs.lresolve(p)
        if (!node) { if (!force) emit(`rm: cannot remove '${f}': No such file or directory`) }
        else if (node.type === 'dir' && !recursive) emit(`rm: cannot remove '${f}': Is a directory`)
        else { const par = vfs.resolveNode(dirname(p)); if (par) delete par.children[basename(p)] }
      })
    }
    else if (lc === 'cp') {
      const recursive = has('-r') || has('-R') || has('-a')
      if (positional.length < 2) emit('cp: missing destination file operand')
      else {
        const dest = positional[positional.length - 1]
        const srcs = positional.slice(0, -1)
        const destNode = vfs.resolveNode(abs(dest))
        const destIsDir = destNode && destNode.type === 'dir'
        srcs.forEach(src => {
          const sp = abs(src); const sNode = vfs.resolveNode(sp)
          if (!sNode) { emit(`cp: cannot stat '${src}': No such file or directory`); return }
          if (sNode.type === 'dir' && !recursive) { emit(`cp: -r not specified; omitting directory '${src}'`); return }
          const target = destIsDir ? `${abs(dest)}/${basename(sp)}` : abs(dest)
          const clone = (node, tgt) => {
            if (node.type === 'dir') {
              vfs.ensureDir(tgt)
              Object.entries(node.children).forEach(([n, c]) => clone(c, `${tgt}/${n}`))
            } else if (node.type === 'file') vfs.writeFile(tgt, node.content, node.mode)
          }
          clone(sNode, target)
        })
      }
    }
    else if (lc === 'mv') {
      if (positional.length < 2) emit('mv: missing destination file operand')
      else {
        const dest = positional[positional.length - 1]
        const srcs = positional.slice(0, -1)
        const destNode = vfs.resolveNode(abs(dest))
        const destIsDir = destNode && destNode.type === 'dir'
        srcs.forEach(src => {
          const sp = abs(src); const sNode = vfs.lresolve(sp)
          if (!sNode) { emit(`mv: cannot stat '${src}': No such file or directory`); return }
          const target = destIsDir ? `${abs(dest)}/${basename(sp)}` : abs(dest)
          const tParent = vfs.ensureDir(dirname(target))
          tParent.children[basename(target)] = sNode
          const sParent = vfs.resolveNode(dirname(sp))
          if (sParent) delete sParent.children[basename(sp)]
        })
      }
    }
    else if (lc === 'find') {
      const startPath = abs(positional[0] || '.')
      const nameIdx = args.indexOf('-name')
      const typeIdx = args.indexOf('-type')
      const pat = nameIdx >= 0 ? args[nameIdx + 1]?.replace(/['"]/g, '') : null
      const typeF = typeIdx >= 0 ? args[typeIdx + 1] : null
      const re = pat ? new RegExp('^' + pat.replace(/\./g, '\\.').replace(/\*/g, '.*').replace(/\?/g, '.') + '$') : null
      const results = []
      const walk = (node, p) => {
        const matchType = !typeF || (typeF === 'd' && node.type === 'dir') || (typeF === 'f' && node.type === 'file') || (typeF === 'l' && node.type === 'link')
        if ((!re || re.test(basename(p) || '/')) && matchType) results.push(p)
        if (node.type === 'dir') Object.entries(node.children).forEach(([n, c]) => walk(c, p === '/' ? `/${n}` : `${p}/${n}`))
      }
      const startNode = vfs.resolveNode(startPath)
      if (!startNode) emit(`find: '${positional[0]}': No such file or directory`)
      else { walk(startNode, startPath); emit(results.length ? results : []) }
    }
    else if (lc === 'grep' || lc === 'egrep' || lc === 'fgrep') {
      const recursive = has('-r') || has('-R')
      const ignore = has('-i')
      const invert = has('-v')
      const showNum = has('-n')
      const countOnly = has('-c')
      const pat = positional[0]
      const files = positional.slice(1)
      if (!pat) emit('Usage: grep [OPTION]... PATTERN [FILE]...')
      else {
        let re
        try { re = new RegExp(pat.replace(/^["']|["']$/g, ''), ignore ? 'i' : '') } catch { re = new RegExp(pat.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), ignore ? 'i' : '') }
        const collect = []
        const grepFile = (path, node) => {
          if (node.type !== 'file') return
          const lines = node.content.replace(/\n$/, '').split('\n')
          let cnt = 0
          lines.forEach((l, i) => {
            const m = re.test(l)
            if (m !== invert) {
              cnt++
              const prefix = (files.length > 1 || recursive) ? `${path}:` : ''
              collect.push(`${prefix}${showNum ? (i + 1) + ':' : ''}${l}`)
            }
          })
          if (countOnly) collect.push(`${(files.length > 1 || recursive) ? path + ':' : ''}${cnt}`)
        }
        const walkGrep = (node, p) => {
          if (node.type === 'file') grepFile(p, node)
          else if (node.type === 'dir') Object.entries(node.children).forEach(([n, c]) => walkGrep(c, p === '/' ? `/${n}` : `${p}/${n}`))
        }
        if (recursive) {
          (files.length ? files : [cwd.path]).forEach(f => { const node = vfs.resolveNode(abs(f)); if (node) walkGrep(node, abs(f)) })
        } else {
          files.forEach(f => { const node = vfs.resolveNode(abs(f)); if (!node) collect.push(`grep: ${f}: No such file or directory`); else grepFile(f, node) })
        }
        if (countOnly && !collect.length) emit('0')
        else emit(collect)
      }
    }
    else if (lc === 'wc') {
      const file = positional[0]
      const node = file ? vfs.resolveNode(abs(file)) : null
      if (!node || node.type !== 'file') emit(`wc: ${file || ''}: No such file or directory`)
      else {
        const c = node.content
        const lines = c === '' ? 0 : c.replace(/\n$/, '').split('\n').length
        const words = c.trim() ? c.trim().split(/\s+/).length : 0
        if (has('-l')) emit(`${lines} ${file}`)
        else if (has('-w')) emit(`${words} ${file}`)
        else if (has('-c')) emit(`${c.length} ${file}`)
        else emit(`${String(lines).padStart(7)} ${String(words).padStart(7)} ${String(c.length).padStart(7)} ${file}`)
      }
    }
    else if (lc === 'chmod') {
      const mode = positional[0]
      positional.slice(1).forEach(f => {
        const node = vfs.lresolve(abs(f))
        if (!node) emit(`chmod: cannot access '${f}': No such file or directory`)
        else if (/^[0-7]{3,4}$/.test(mode)) node.mode = mode.length === 3 ? '0' + mode : mode
      })
      if (!positional.length) emit('chmod: missing operand')
    }
    else if (lc === 'chown' || lc === 'chgrp') {
      const spec = positional[0] || ''
      const [u, g] = spec.split(':')
      positional.slice(1).forEach(f => {
        const node = vfs.lresolve(abs(f))
        if (!node) emit(`${lc}: cannot access '${f}': No such file or directory`)
        else {
          if (lc === 'chgrp') node.gid = isNaN(+spec) ? node.gid : +spec
          else { if (u && !isNaN(+u)) node.uid = +u; if (g && !isNaN(+g)) node.gid = +g }
        }
      })
    }
    else if (lc === 'ln') {
      if (has('-s')) {
        const target = positional[0]; const linkName = positional[1] || basename(target)
        const p = abs(linkName)
        const parent = vfs.ensureDir(dirname(p))
        parent.children[basename(p)] = vfs.mklink(target)
        emit('')
      } else emit('ln: hard links simulated (use -s for symlink)')
    }
    else if (lc === 'stat') {
      const f = positional[0]; const node = f ? vfs.lresolve(abs(f)) : null
      if (!node) emit(`stat: cannot statx '${f}': No such file or directory`)
      else {
        const sz = node.type === 'dir' ? 4096 : (node.content?.length || 0)
        const octal = (node.mode || '0644').slice(-4).padStart(4, '0')
        emit([
          `  File: ${f}${node.type === 'link' ? ' -> ' + node.target : ''}`,
          `  Size: ${sz}\tBlocks: ${Math.ceil(sz / 512)}        IO Block: 4096   ${node.type === 'dir' ? 'directory' : node.type === 'link' ? 'symbolic link' : 'regular file'}`,
          `Access: (${octal}/${permString(node)})  Uid: (${String(node.uid).padStart(5)}/${userName(node.uid).padEnd(8)})   Gid: (${String(node.gid).padStart(5)}/${groupName(node.gid).padEnd(8)})`,
          `Modify: ${node.mtime}`,
        ])
      }
    }
    else if (lc === 'file') {
      const f = positional[0]; const node = f ? vfs.resolveNode(abs(f)) : null
      if (!node) emit(`${f}: cannot open (No such file or directory)`)
      else if (node.type === 'dir') emit(`${f}: directory`)
      else if (node.type === 'link') emit(`${f}: symbolic link to ${node.target}`)
      else if (node.content.startsWith('#!')) emit(`${f}: a ${node.content.split('\n')[0].slice(2)} script, ASCII text executable`)
      else emit(`${f}: ASCII text`)
    }
    else if (lc === 'tree') {
      const startP = abs(positional[0] || '.')
      const startNode = vfs.resolveNode(startP)
      if (!startNode) emit(`${positional[0]} [error opening dir]`)
      else {
        let dirCount = 0, fileCount = 0
        emit(startP)
        const walk = (node, prefix) => {
          const entries = Object.entries(node.children).sort()
          entries.forEach(([n, c], i) => {
            const last = i === entries.length - 1
            out.push(`${prefix}${last ? '└── ' : '├── '}${n}${c.type === 'link' ? ' -> ' + c.target : ''}`)
            if (c.type === 'dir') { dirCount++; walk(c, prefix + (last ? '    ' : '│   ')) }
            else fileCount++
          })
        }
        if (startNode.type === 'dir') walk(startNode, '')
        out.push('', `${dirCount} directories, ${fileCount} files`)
      }
    }
    else if (lc === 'du') {
      const target = abs(positional[0] || '.')
      const node = vfs.resolveNode(target)
      if (!node) emit(`du: cannot access '${positional[0]}': No such file or directory`)
      else emit(`${has('-h') ? '4.0K' : '4'}\t${positional[0] || '.'}`)
    }
    else if (lc === 'df') {
      const h = has('-h') || has('-H')
      const used = Math.round(diskGb * 0.31)
      const avail = diskGb - used
      if (h) emit([
        'Filesystem      Size  Used Avail Use% Mounted on',
        `/dev/sda1        ${diskGb}G  ${used}G   ${avail}G  31% /`,
        'tmpfs           ' + Math.round(memMb / 2) + 'M     0  ' + Math.round(memMb / 2) + 'M   0% /dev/shm',
        ...(diskMounted ? ['/dev/sdb1         20G  1.2G   19G   6% /data'] : []),
      ])
      else emit([
        'Filesystem     1K-blocks    Used Available Use% Mounted on',
        `/dev/sda1      ${diskGb * 1024 * 1024} ${used * 1024 * 1024} ${avail * 1024 * 1024}  31% /`,
        ...(diskMounted ? [`/dev/sdb1       20971520 1258291  19713229   6% /data`] : []),
      ])
    }

    /* =================== editors =================== */
    else if (lc === 'vi' || lc === 'vim' || lc === 'view' || lc === 'nano' || lc === 'ex') {
      const f = positional[0]
      if (!f) {
        // open scratch buffer
        editor = { tool: lc === 'nano' ? 'nano' : 'vi', path: null, content: '' }
      } else {
        const p = abs(f)
        const node = vfs.resolveNode(p)
        if (node && node.type === 'dir') emit(`${lc}: ${f}: Is a directory`)
        else editor = { tool: lc === 'nano' ? 'nano' : 'vi', path: p, content: node && node.type === 'file' ? node.content : '' }
      }
    }

    /* =================== system info =================== */
    else if (lc === 'whoami') emit('root')
    else if (lc === 'id') {
      if (positional[0] && positional[0] !== 'root') emit(`uid=1000(${positional[0]}) gid=1000(${positional[0]}) groups=1000(${positional[0]})`)
      else emit('uid=0(root) gid=0(root) groups=0(root)')
    }
    else if (lc === 'groups') emit(positional[0] ? `${positional[0] === 'root' ? 'root' : positional[0] + ' : ' + positional[0]}` : 'root')
    else if (lc === 'hostname') {
      if (positional[0]) { emit('') } else emit(has('-f') || has('--fqdn') ? `${hostname}.lab.fixitlab.local` : hostname.split('.')[0])
    }
    else if (lc === 'hostnamectl') emit([
      `   Static hostname: ${hostname}`,
      `         Icon name: computer-vm`,
      `           Chassis: vm`,
      `        Machine ID: a1b2c3d4e5f60718293a4b5c6d7e8f90`,
      `  Operating System: ${isRhel ? 'Red Hat Enterprise Linux 9.3 (Plow)' : 'Ubuntu 22.04.4 LTS'}`,
      `            Kernel: Linux 5.15.0-91-generic`,
      `      Architecture: x86-64`,
    ])
    else if (lc === 'uname') {
      if (has('-a')) emit(`Linux ${hostname.split('.')[0]} 5.15.0-91-generic #101-Ubuntu SMP Tue Nov 14 18:10:51 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux`)
      else if (has('-r')) emit('5.15.0-91-generic')
      else if (has('-n')) emit(hostname.split('.')[0])
      else if (has('-m')) emit('x86_64')
      else emit('Linux')
    }
    else if (lc === 'arch') emit('x86_64')
    else if (lc === 'uptime') {
      if (has('-p')) emit('up 14 days, 3 hours, 22 minutes')
      else emit(' 14:22:01 up 14 days,  3:22,  1 user,  load average: 0.08, 0.12, 0.09')
    }
    else if (lc === 'date') {
      if (positional[0]?.startsWith('+')) emit(new Date().toISOString())
      else emit(new Date().toUTCString().replace('GMT', 'UTC'))
    }
    else if (lc === 'cal') emit(`     ${HUMAN_MONTHS[new Date().getMonth()]} ${new Date().getFullYear()}\nSu Mo Tu We Th Fr Sa`)
    else if (lc === 'lscpu') emit([
      'Architecture:            x86_64', '  CPU op-mode(s):         32-bit, 64-bit',
      `CPU(s):                  ${cpu}`, '  On-line CPU(s) list:   0-' + (cpu - 1),
      'Vendor ID:               GenuineIntel', '  Model name:            Intel(R) Xeon(R) Gold 6248 CPU @ 2.50GHz',
      'Virtualization:          VT-x', 'Hypervisor vendor:       VMware', 'Virtualization type:     full',
    ])
    else if (lc === 'lsmem') emit(`Memory block size:       128M\nTotal online memory:     ${Math.round(memMb / 1024)}G`)
    else if (lc === 'nproc') emit(String(cpu))

    /* =================== process & memory =================== */
    else if (lc === 'ps') {
      const wide = has('-e') || has('-ef') || has('-aux') || has('aux') || has('-A')
      if (wide && (has('-ef') || has('ef'))) {
        emit([
          'UID          PID    PPID  C STIME TTY          TIME CMD',
          'root           1       0  0 Jun04 ?        00:00:14 /usr/lib/systemd/systemd --system',
          'root         890       1  0 Jun04 ?        00:00:01 /usr/sbin/sshd -D',
          'root        1201     890  0 08:01 ?        00:00:00 sshd: root@pts/0',
          'mysql       1502       1  0 Jun04 ?        00:01:42 /usr/sbin/mysqld',
          'root        1610       1  0 Jun04 ?        00:02:11 /usr/bin/dockerd',
          'devops      1820       1  0 Jun04 ?        00:00:53 node /opt/app/server.js',
          'root       18342    1201  0 14:22 pts/0    00:00:00 ps -ef',
        ])
      } else if (wide) {
        emit([
          'USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND',
          'root           1  0.0  0.1 169324 12876 ?        Ss   Jun04   0:14 /usr/lib/systemd/systemd',
          'root         890  0.0  0.1  15852  9012 ?        Ss   Jun04   0:01 sshd: /usr/sbin/sshd -D',
          'mysql       1502  0.3  4.2 1820544 ' + Math.round(memMb * 42) + ' ?      Sl   Jun04   1:42 /usr/sbin/mysqld',
          'devops      1820  0.1  1.8 998244 ' + Math.round(memMb * 18) + ' ?       Ssl  Jun04   0:53 node /opt/app/server.js',
        ])
      } else {
        emit(['    PID TTY          TIME CMD', '   1201 pts/0    00:00:00 bash', `  ${nextPid++} pts/0    00:00:00 ps`])
      }
    }
    else if (lc === 'top' || lc === 'htop' || lc === 'atop') {
      const usedPct = 62
      emit([
        `top - 14:22:01 up 14 days,  3:22,  1 user,  load average: 0.08, 0.12, 0.09`,
        `Tasks: 142 total,   1 running, 141 sleeping,   0 stopped,   0 zombie`,
        `%Cpu(s):  2.1 us,  0.8 sy,  0.0 ni, 96.8 id,  0.2 wa,  0.0 hi,  0.1 si,  0.0 st`,
        `MiB Mem :  ${memMb}.0 total,  ${Math.round(memMb * 0.34)}.0 free,  ${Math.round(memMb * usedPct / 100)}.0 used,  ${Math.round(memMb * 0.20)}.0 buff/cache`,
        ``,
        `    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND`,
        `   1502 mysql     20   0 1820544 ${Math.round(memMb * 42)}  18024 S   1.3   4.2   1:42.31 mysqld`,
        `   1820 devops    20   0  998244 ${Math.round(memMb * 18)}  12012 S   0.7   1.8   0:53.10 node`,
        `      1 root      20   0  169324  12876   8420 S   0.0   0.3   0:14.02 systemd`,
        `(press q to quit)`,
      ])
    }
    else if (lc === 'free') {
      const h = has('-h')
      const total = memMb, used = Math.round(memMb * 0.62), free = Math.round(memMb * 0.34), buff = Math.round(memMb * 0.20)
      const fmt = (mb) => h ? (mb >= 1024 ? (mb / 1024).toFixed(1) + 'Gi' : mb + 'Mi') : String(mb * 1024)
      emit([
        `               total        used        free      shared  buff/cache   available`,
        `Mem:    ${String(fmt(total)).padStart(12)}${String(fmt(used)).padStart(12)}${String(fmt(free)).padStart(12)}${String(fmt(Math.round(memMb * 0.01))).padStart(12)}${String(fmt(buff)).padStart(12)}${String(fmt(Math.round(memMb * 0.34))).padStart(12)}`,
        `Swap:   ${String(fmt(2048)).padStart(12)}${String(fmt(0)).padStart(12)}${String(fmt(2048)).padStart(12)}`,
      ])
    }
    else if (lc === 'vmstat') emit(['procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----', ' r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st', ` 1  0      0 ${Math.round(memMb * 348)}  20480 ${Math.round(memMb * 205)}    0    0    12    34   89  142  2  1 97  0  0`])
    else if (lc === 'kill' || lc === 'pkill' || lc === 'killall') {
      if (!positional.length && !args.length) emit(`${lc}: usage: ${lc} [-s sigspec | -n signum | -sigspec] pid | jobspec ...`)
      else emit('')
    }
    else if (lc === 'pidof') emit(positional[0] === 'sshd' ? '890' : positional[0] === 'mysqld' ? '1502' : '')
    else if (lc === 'pgrep') emit(positional[0] === 'sshd' ? '890\n1201' : positional[0] === 'node' ? '1820' : '')
    else if (lc === 'nice' || lc === 'renice' || lc === 'nohup') emit(lc === 'nohup' ? 'nohup: ignoring input and appending output to \'nohup.out\'' : '')
    else if (lc === 'jobs') emit('')

    /* =================== networking =================== */
    else if (lc === 'ip') {
      const sub = positional[0]
      if (sub === 'addr' || sub === 'a' || sub === 'address' || !sub) {
        emit([
          '1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000',
          '    inet 127.0.0.1/8 scope host lo',
          '2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000',
          '    link/ether 00:50:56:a1:b2:c3 brd ff:ff:ff:ff:ff:ff',
          `    inet ${ip}/24 brd ${ip.split('.').slice(0, 3).join('.')}.255 scope global noprefixroute eth0`,
        ])
      } else if (sub === 'route' || sub === 'r') {
        emit([`default via ${gw} dev eth0 proto static metric 100`, `${ip.split('.').slice(0, 3).join('.')}.0/24 dev eth0 proto kernel scope link src ${ip}`])
      } else if (sub === 'link') {
        emit(['1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536', '2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500', '    link/ether 00:50:56:a1:b2:c3 brd ff:ff:ff:ff:ff:ff'])
      } else if (sub === 'neigh' || sub === 'n') {
        emit(`${gw} dev eth0 lladdr 00:50:56:fe:00:01 REACHABLE`)
      } else emit('Object "' + sub + '" is unknown, try "ip help".')
    }
    else if (lc === 'ifconfig') {
      emit([
        `eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500`,
        `        inet ${ip}  netmask 255.255.255.0  broadcast ${ip.split('.').slice(0, 3).join('.')}.255`,
        `        ether 00:50:56:a1:b2:c3  txqueuelen 1000  (Ethernet)`,
        `        RX packets 1284411  bytes 982734411 (937.2 MiB)`,
        `        TX packets 884102  bytes 122874410 (117.1 MiB)`,
        ``,
        `lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536`,
        `        inet 127.0.0.1  netmask 255.0.0.0`,
      ])
    }
    else if (lc === 'ping' || lc === 'ping6') {
      const host = positional[0] || '8.8.8.8'
      const resolved = host === 'localhost' ? '127.0.0.1' : /^\d/.test(host) ? host : gw
      emit([
        `PING ${host} (${resolved}) 56(84) bytes of data.`,
        `64 bytes from ${resolved}: icmp_seq=1 ttl=64 time=0.412 ms`,
        `64 bytes from ${resolved}: icmp_seq=2 ttl=64 time=0.388 ms`,
        `64 bytes from ${resolved}: icmp_seq=3 ttl=64 time=0.401 ms`,
        ``,
        `--- ${host} ping statistics ---`,
        `3 packets transmitted, 3 received, 0% packet loss, time 2003ms`,
        `rtt min/avg/max/mdev = 0.388/0.400/0.412/0.012 ms`,
      ])
    }
    else if (lc === 'ss' || lc === 'netstat') {
      emit([
        'Netid State  Recv-Q Send-Q  Local Address:Port   Peer Address:Port Process',
        'tcp   LISTEN 0      128           0.0.0.0:22          0.0.0.0:*     users:(("sshd",pid=890))',
        'tcp   LISTEN 0      128         127.0.0.1:3306        0.0.0.0:*     users:(("mysqld",pid=1502))',
        `tcp   ESTAB  0      0            ${ip}:22         ${gw}:51022   users:(("sshd",pid=1201))`,
        ...(services.nginx.active === 'active' ? ['tcp   LISTEN 0      511           0.0.0.0:80          0.0.0.0:*     users:(("nginx",pid=3300))'] : []),
      ])
    }
    else if (lc === 'curl' || lc === 'wget') {
      const url = positional.find(a => a.startsWith('http')) || positional[positional.length - 1] || ''
      if (lc === 'wget') emit([`--${new Date().toISOString()}--  ${url}`, `Resolving host... ${gw}`, `Connecting... connected.`, `HTTP request sent, awaiting response... 200 OK`, `Saving to: '${basename(url) || 'index.html'}'`, `'${basename(url) || 'index.html'}' saved`])
      else if (has('-I')) emit(['HTTP/1.1 200 OK', 'Server: nginx/1.20.1', 'Content-Type: text/html', 'Content-Length: 612'])
      else emit('<!DOCTYPE html>\n<html><head><title>Welcome</title></head><body><h1>It works!</h1></body></html>')
    }
    else if (lc === 'nslookup' || lc === 'host' || lc === 'dig') {
      const q = positional[0] || hostname
      if (lc === 'dig') emit([`; <<>> DiG 9.16 <<>> ${q}`, ';; ANSWER SECTION:', `${q}.\t\t300\tIN\tA\t${ip}`])
      else emit([`Server:\t\t${ip.split('.').slice(0, 3).join('.')}.2`, `Address:\t${ip.split('.').slice(0, 3).join('.')}.2#53`, ``, `Name:\t${q}`, `Address: ${ip}`])
    }
    else if (lc === 'traceroute' || lc === 'tracepath' || lc === 'mtr') {
      emit([`traceroute to ${positional[0] || '8.8.8.8'} (8.8.8.8), 30 hops max, 60 byte packets`, ` 1  ${gw} (${gw})  0.412 ms  0.388 ms  0.401 ms`, ` 2  10.0.0.1 (10.0.0.1)  1.204 ms  1.180 ms  1.190 ms`])
    }
    else if (lc === 'nc' || lc === 'ncat' || lc === 'telnet') emit(`Connected to ${positional[0] || 'host'}.`)
    else if (lc === 'nmcli') {
      const sub = positional[0]
      if (sub === 'device' || sub === 'dev') emit(['DEVICE  TYPE      STATE      CONNECTION', 'eth0    ethernet  connected  eth0', 'lo      loopback  unmanaged  --'])
      else if (sub === 'connection' || sub === 'con' || sub === 'c') emit(['NAME  UUID                                  TYPE      DEVICE', 'eth0  5fb06bd0-0bb0-7ffb-45f1-d6edd65f3e03  ethernet  eth0'])
      else if (sub === 'general' || sub === 'g') emit('STATE      CONNECTIVITY  WIFI-HW  WIFI     WWAN-HW  WWAN\nconnected  full          enabled  enabled  enabled  enabled')
      else emit(`eth0: connected to eth0\n\t"Intel 82540EM"\n\tinet4 ${ip}/24`)
    }
    else if (lc === 'nmtui' || lc === 'ethtool' || lc === 'arp' || lc === 'route') {
      if (lc === 'route') emit(['Kernel IP routing table', 'Destination     Gateway         Genmask         Flags Metric Ref    Use Iface', `0.0.0.0         ${gw}     0.0.0.0         UG    100    0        0 eth0`])
      else if (lc === 'arp') emit(['Address                  HWtype  HWaddress           Flags Mask            Iface', `${gw}              ether   00:50:56:fe:00:01   C                     eth0`])
      else if (lc === 'ethtool') emit(`Settings for eth0:\n\tSpeed: 10000Mb/s\n\tDuplex: Full\n\tLink detected: yes`)
      else emit('')
    }
    else if (lc === 'ssh') {
      if (positional[0]) emit(`ssh: connect to host ${positional[0].replace(/.*@/, '')} port 22: (simulated — use the SSH lab terminal for an interactive session)`)
      else emit('usage: ssh [user@]hostname [command]')
    }
    else if (lc === 'scp' || lc === 'rsync' || lc === 'sftp') emit(`${lc}: transfer simulated`)

    /* =================== services (systemd) =================== */
    else if (lc === 'systemctl') {
      const sub = positional[0]
      const rawSvc = positional[1] || ''
      const svc = rawSvc.replace(/\.service$/, '')
      const s = services[svc]
      if (!sub || sub === 'list-units') {
        emit(['  UNIT                LOAD   ACTIVE   SUB     DESCRIPTION',
          ...Object.entries(services).map(([n, v]) => `  ${(n + '.service').padEnd(20)}loaded ${v.active.padEnd(8)}${v.active === 'active' ? 'running' : 'dead   '} ${v.desc}`)])
      } else if (sub === 'status') {
        if (!s) emit(`Unit ${rawSvc || svc}.service could not be found.`)
        else {
          const dot = s.active === 'active' ? '●' : s.active === 'failed' ? '×' : '○'
          emit([
            `${dot} ${svc}.service - ${s.desc}`,
            `     Loaded: loaded (/usr/lib/systemd/system/${svc}.service; ${s.enabled}; preset: enabled)`,
            `     Active: ${s.active} (${s.active === 'active' ? 'running' : s.active === 'failed' ? 'failed' : 'dead'}) since ${s.since}`,
            ...(s.pid ? [`   Main PID: ${s.pid} (${svc})`, `      Tasks: 3 (limit: 4915)`, `     Memory: 12.4M`] : []),
            ...(s.active === 'failed' ? [`    Process: 3122 ExecStart=/usr/sbin/${svc} (code=exited, status=1/FAILURE)`,
              `${svc}[3122]: nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)`] : []),
          ])
        }
      } else if (['start', 'stop', 'restart', 'reload', 'enable', 'disable', 'mask', 'unmask'].includes(sub)) {
        if (!s) emit(`Failed to ${sub} ${svc}.service: Unit ${svc}.service not found.`)
        else {
          if (sub === 'start' || sub === 'restart' || sub === 'reload') { s.active = 'active'; s.pid = s.pid || nextPid++; s.since = 'now' }
          else if (sub === 'stop') { s.active = 'inactive'; s.pid = null; s.since = 'now' }
          else if (sub === 'enable') s.enabled = 'enabled'
          else if (sub === 'disable') s.enabled = 'disabled'
          emit('')
        }
      } else if (sub === 'is-active') emit(s ? s.active : 'unknown')
      else if (sub === 'is-enabled') emit(s ? s.enabled : 'unknown')
      else if (sub === 'is-failed') emit(s && s.active === 'failed' ? 'failed' : 'active')
      else if (sub === 'daemon-reload' || sub === 'reset-failed') emit('')
      else if (sub === 'list-unit-files') emit(['UNIT FILE              STATE', ...Object.entries(services).map(([n, v]) => `${(n + '.service').padEnd(22)} ${v.enabled}`)])
      else if (sub === 'get-default') emit('multi-user.target')
      else emit(`Unknown operation '${sub}'.`)
    }
    else if (lc === 'service') {
      const svc = positional[0]; const sub = positional[1]
      const s = services[svc] || services[svc?.replace(/d$/, '')]
      if (!s) emit(`Redirecting to /bin/systemctl ${sub} ${svc}.service\nUnit ${svc}.service could not be found.`)
      else if (sub === 'status') emit(`● ${svc}.service - ${s.desc}\n     Active: ${s.active}`)
      else { if (sub === 'start' || sub === 'restart') s.active = 'active'; else if (sub === 'stop') s.active = 'inactive'; emit(`Redirecting to /bin/systemctl ${sub} ${svc}.service`) }
    }
    else if (lc === 'journalctl') {
      const ds = nowStamp()
      if (has('-u') || args.includes('-u')) {
        const uIdx = args.indexOf('-u'); const u = (args[uIdx + 1] || 'nginx').replace(/\.service$/, '')
        const s = services[u]
        emit([
          `-- Logs begin at Tue 2026-06-04 08:00:01 UTC, end at ${ds} UTC. --`,
          ...(s && s.active === 'failed'
            ? [`${ds} ${hostname} systemd[1]: Starting ${s.desc}...`,
              `${ds} ${hostname} ${u}[3122]: nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)`,
              `${ds} ${hostname} systemd[1]: ${u}.service: Main process exited, code=exited, status=1/FAILURE`,
              `${ds} ${hostname} systemd[1]: ${u}.service: Failed with result 'exit-code'.`]
            : [`${ds} ${hostname} systemd[1]: Started ${(s && s.desc) || u}.`]),
        ])
      } else if (has('-b') || args.includes('-b')) {
        emit([`-- Boot a1b2c3d4 --`, `${ds} ${hostname} kernel: Linux version 5.15.0-91-generic`, `${ds} ${hostname} systemd[1]: Reached target Multi-User System.`])
      } else if (has('-k')) {
        emit([`${ds} ${hostname} kernel: eth0: link up, 10000 Mbps, full duplex`])
      } else {
        emit([`-- Logs begin at Tue 2026-06-04 08:00:01 UTC. --`, `${ds} ${hostname} systemd[1]: Started Daily Cleanup of Temporary Directories.`, `${ds} ${hostname} sshd[1201]: Accepted password for root from ${gw} port 51022 ssh2`])
      }
    }
    else if (lc === 'dmesg') {
      emit([
        '[    0.000000] Linux version 5.15.0-91-generic (build@fixitlab) #101 SMP',
        '[    0.000000] Command line: BOOT_IMAGE=/boot/vmlinuz root=UUID=8f3b... ro quiet',
        '[    1.234567] systemd[1]: Reached target Multi-User System.',
        '[    2.100000] sd 2:0:0:0: [sda] Attached SCSI disk',
        ...(diskRescanned && vm?.guest_disk_hidden ? ['[ 1284.55] sd 2:0:1:0: [sdb] Attached SCSI disk'] : []),
        '[    8.442000] IPv6: ADDRCONF(NETDEV_CHANGE): eth0: link becomes ready',
      ])
    }

    /* =================== packages =================== */
    else if (lc === 'dnf' || lc === 'yum') {
      const sub = positional[0]
      const pkg = positional[1] || 'package'
      if (sub === 'install') emit(['Last metadata expiration check: 0:12:33 ago.', 'Dependencies resolved.', '========================================', ` Installing: ${pkg}`, '========================================', 'Downloading Packages:', 'Running transaction', `  Installing : ${pkg}-1.0-1.el9.x86_64`, 'Complete!'])
      else if (sub === 'remove' || sub === 'erase') emit(['Dependencies resolved.', `  Removing: ${pkg}`, 'Complete!'])
      else if (sub === 'update' || sub === 'upgrade') emit(['Last metadata expiration check: 0:05:01 ago.', 'Dependencies resolved.', 'Nothing to do.', 'Complete!'])
      else if (sub === 'list') emit(['Installed Packages', 'bash.x86_64          5.1.8-6.el9       @anaconda', `nginx.x86_64         1:1.20.1-14.el9   @epel`])
      else if (sub === 'search') emit([`========== Name Matched: ${pkg} ==========`, `${pkg}.x86_64 : The ${pkg} package`])
      else if (sub === 'info') emit([`Name         : ${pkg}`, `Version      : 1.20.1`, `Repository   : epel`, `Summary      : ${pkg} package`])
      else if (sub === 'repolist') emit(['repo id            repo name', 'rhel-9-baseos      RHEL 9 BaseOS', 'epel               Extra Packages for Enterprise Linux 9'])
      else if (sub === 'clean') emit('0 files removed')
      else if (sub === 'makecache') emit('Metadata cache created.')
      else emit('Loaded plugins: builddep, changelog, config-manager')
    }
    else if (lc === 'apt' || lc === 'apt-get') {
      const sub = positional[0]
      const pkg = positional[1] || 'package'
      if (sub === 'update') emit(['Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease', 'Get:2 http://security.ubuntu.com/ubuntu jammy-security InRelease', 'Reading package lists... Done'])
      else if (sub === 'install') emit(['Reading package lists... Done', 'Building dependency tree... Done', `The following NEW packages will be installed:`, `  ${pkg}`, `Setting up ${pkg} (1.20.1-1ubuntu1) ...`, 'Processing triggers for man-db (2.10.2-1) ...'])
      else if (sub === 'remove' || sub === 'purge') emit(['Reading package lists... Done', `The following packages will be REMOVED:`, `  ${pkg}`, `Removing ${pkg} (1.20.1-1ubuntu1) ...`])
      else if (sub === 'upgrade' || sub === 'dist-upgrade' || sub === 'full-upgrade') emit(['Reading package lists... Done', 'Calculating upgrade... Done', '0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.'])
      else if (sub === 'list') emit(['Listing... Done', `nginx/jammy,now 1.18.0-6ubuntu14 amd64 [installed]`])
      else if (sub === 'search') emit([`${pkg}/jammy 1.20.1 amd64`, `  ${pkg} package`])
      else if (sub === 'show') emit([`Package: ${pkg}`, `Version: 1.20.1`, `Priority: optional`])
      else emit('E: Invalid operation ' + (sub || ''))
    }
    else if (lc === 'apt-cache') emit(`${positional[1] || 'package'} - simulated package description`)
    else if (lc === 'rpm') {
      if (has('-qa') || (has('-q') && has('-a'))) emit(['kernel-5.14.0-362.el9.x86_64', 'bash-5.1.8-6.el9.x86_64', 'systemd-252-14.el9.x86_64', 'openssh-server-8.7p1-34.el9.x86_64', 'nginx-1.20.1-14.el9.x86_64', 'firewalld-1.2.5-1.el9.noarch'])
      else if (has('-q')) emit(`${positional[0] || 'package'}-1.20.1-14.el9.x86_64`)
      else if (has('-V')) emit('')
      else emit('RPM version 4.16.1.3')
    }
    else if (lc === 'dpkg') {
      if (has('-l')) emit(['Desired=Unknown/Install/Remove/Purge/Hold', '||/ Name           Version      Architecture Description', 'ii  bash           5.1-6ubuntu1 amd64        GNU Bourne Again SHell', 'ii  openssh-server 8.9p1-3      amd64        secure shell (SSH) server'])
      else if (has('-L')) emit('/usr/bin/' + (positional[0] || 'pkg'))
      else emit("Debian 'dpkg' package management program version 1.21.1")
    }
    else if (lc === 'snap' || lc === 'flatpak') emit(`${lc}: no ${lc} packages installed`)

    /* =================== users =================== */
    else if (lc === 'useradd' || lc === 'adduser') {
      const u = positional[0]
      if (!u) emit('Usage: useradd [options] LOGIN')
      else {
        const passwd = vfs.resolveNode('/etc/passwd')
        if (passwd && !passwd.content.includes(`\n${u}:`)) passwd.content += `${u}:x:1001:1001::/home/${u}:/bin/bash\n`
        vfs.ensureDir(`/home/${u}`)
        emit('')
      }
    }
    else if (lc === 'userdel' || lc === 'deluser') emit('')
    else if (lc === 'usermod' || lc === 'groupmod') emit('')
    else if (lc === 'groupadd' || lc === 'groupdel') emit('')
    else if (lc === 'passwd') {
      if (positional[0] && positional[0] !== 'root') emit(`Changing password for user ${positional[0]}.\npasswd: all authentication tokens updated successfully.`)
      else emit('Changing password for user root.\npasswd: all authentication tokens updated successfully.')
    }
    else if (lc === 'su') emit('')
    else if (lc === 'sudo') {
      const rest = positional.join(' ')
      if (!rest) emit('usage: sudo command')
      else { const r = run(rest); return { lines: r.lines, prompt: prompt(), sideEffect: r.sideEffect, editor: r.editor } }
    }
    else if (lc === 'last' || lc === 'lastlog' || lc === 'who' || lc === 'w') {
      if (lc === 'w') emit(['14:22:01 up 14 days,  3:22,  1 user,  load average: 0.08, 0.12, 0.09', 'USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT', `root     pts/0    ${gw}      08:01    0.00s  0.04s  0.00s w`])
      else if (lc === 'who') emit(`root     pts/0        ${new Date().toISOString().slice(0, 16).replace('T', ' ')} (${gw})`)
      else emit([`root     pts/0        ${gw}    ${nowStamp()}   still logged in`, '', `wtmp begins ${nowStamp()}`])
    }

    /* =================== storage =================== */
    else if (lc === 'lsblk') {
      emit([
        'NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS',
        `sda      8:0    0   ${diskGb}G  0 disk`,
        `├─sda1   8:1    0    1G  0 part /boot`,
        `└─sda2   8:2    0  ${diskGb - 1}G  0 part /`,
        ...((diskRescanned || !vm?.guest_disk_hidden) && vm?.guest_disk_hidden ? [
          `sdb      8:16   0   20G  0 disk`,
          ...(diskMounted ? ['└─sdb1   8:17   0   20G  0 part /data'] : []),
        ] : []),
        'sr0     11:0    1 1024M  0 rom',
      ])
    }
    else if (lc === 'blkid') {
      emit([
        '/dev/sda1: UUID="1a2b3c4d-5e6f-7081-92a3-b4c5d6e7f809" TYPE="xfs" PARTUUID="000a1b2c-01"',
        '/dev/sda2: UUID="8f3b2c1a-0e4d-4c6b-9a7f-1d2e3f4a5b6c" TYPE="xfs" PARTUUID="000a1b2c-02"',
        ...(diskFormatted ? ['/dev/sdb1: UUID="deadc0de-1234-5678-9abc-def012345678" TYPE="ext4"'] : []),
      ])
    }
    else if (lc === 'fdisk' || lc === 'parted' || lc === 'sfdisk' || lc === 'gdisk') {
      if (has('-l') || lc === 'parted') {
        emit([
          `Disk /dev/sda: ${diskGb} GiB, ${diskGb * 1024 * 1024 * 1024} bytes, ${diskGb * 2 * 1024 * 1024} sectors`,
          'Units: sectors of 1 * 512 = 512 bytes',
          'Device     Boot   Start      End  Sectors Size Type',
          '/dev/sda1  *       2048  2099199  2097152   1G Linux filesystem',
          `/dev/sda2       2099200 ${diskGb * 2 * 1024 * 1024} ... ${diskGb - 1}G Linux filesystem`,
          ...(diskRescanned && vm?.guest_disk_hidden ? ['', `Disk /dev/sdb: 20 GiB, 21474836480 bytes`, diskFormatted ? '/dev/sdb1       2048  41943039  41940992  20G Linux filesystem' : 'Disk /dev/sdb doesn\'t contain a valid partition table'] : []),
        ])
      } else emit(`Welcome to fdisk (util-linux 2.37.4).\nCommand (m for help): (simulated — use 'fdisk -l' to list, or mkfs to format /dev/sdb)`)
    }
    else if (lc === 'mkfs' || lc.startsWith('mkfs.') || lc === 'mke2fs' || lc === 'mkswap') {
      const dev = positional.find(a => a.includes('/dev/')) || positional[0] || ''
      if (dev.includes('sdb') && diskRescanned && !diskFormatted) {
        diskFormatted = true
        emit([`mke2fs 1.46.5 (30-Dec-2021)`, `Creating filesystem with 5242880 4k blocks and 1310720 inodes`, `Filesystem UUID: deadc0de-1234-5678-9abc-def012345678`, `Writing superblocks and filesystem accounting information: done`])
        sideEffect = { action: 'guest_format_disk', vm_id: vm?.id }
      } else if (dev.includes('sdb') && diskFormatted) {
        emit(`mke2fs 1.46.5 (30-Dec-2021)\n/dev/sdb contains a ext4 file system\nProceed anyway? (y,N) (simulated — already formatted)`)
      } else if (!dev.includes('sdb') && dev.includes('sd')) emit(`mkfs.ext4: will not make a filesystem on '${dev}' — it is mounted`)
      else emit('Usage: mkfs.ext4 /dev/sdb')
    }
    else if (lc === 'mount') {
      const dev = positional[0] || ''
      const mnt = positional[1] || '/data'
      if (!positional.length) {
        emit(['/dev/sda2 on / type xfs (rw,relatime,seclabel)', '/dev/sda1 on /boot type xfs (rw,relatime)', 'proc on /proc type proc (rw,nosuid,nodev,noexec)', 'tmpfs on /dev/shm type tmpfs (rw,nosuid,nodev)',
          ...(diskMounted ? ['/dev/sdb1 on /data type ext4 (rw,relatime)'] : [])])
      } else if (dev.includes('sdb') && diskFormatted && !diskMounted) {
        diskMounted = true
        vfs.ensureDir(mnt.startsWith('/') ? mnt : '/data')
        emit('')
        sideEffect = { action: 'guest_mount_disk', vm_id: vm?.id }
      } else if (dev.includes('sdb') && !diskFormatted) emit(`mount: ${mnt}: wrong fs type, bad option, bad superblock on ${dev}. (run mkfs.ext4 ${dev} first)`)
      else if (dev.includes('sdb') && diskMounted) emit(`mount: ${dev} already mounted on /data.`)
      else emit('')
    }
    else if (lc === 'umount') emit('')
    else if (lc === 'swapon' || lc === 'swapoff') emit(lc === 'swapon' ? 'NAME      TYPE      SIZE USED PRIO\n/dev/sda3 partition   2G   0B   -2' : '')
    else if (lc === 'pvs' || lc === 'pvdisplay') emit(['  PV         VG     Fmt  Attr PSize   PFree', `  /dev/sda2  rootvg lvm2 a--  <${diskGb - 1}.00g  0`])
    else if (lc === 'vgs' || lc === 'vgdisplay') emit(['  VG     #PV #LV #SN Attr   VSize   VFree', `  rootvg   1   2   0 wz--n- <${diskGb - 1}.00g    0`])
    else if (lc === 'lvs' || lc === 'lvdisplay') emit(['  LV     VG     Attr       LSize   Pool Origin', `  root   rootvg -wi-ao---- <${diskGb - 5}.00g`, '  swap   rootvg -wi-ao----   2.00g'])
    else if (lc === 'pvcreate' || lc === 'vgcreate' || lc === 'lvcreate' || lc === 'lvextend' || lc === 'vgextend' || lc === 'resize2fs' || lc === 'xfs_growfs') emit(`${lc}: simulated — operation completed`)

    /* =================== kernel modules =================== */
    else if (lc === 'lsmod') {
      emit([
        'Module                  Size  Used by',
        'xfs                   987136  2',
        'overlay               151552  1',
        ...(moduleLoaded ? ['nf_conntrack          172032  2 nf_nat,xt_state', 'br_netfilter           32768  0'] : []),
        'vmw_balloon            24576  0',
        'vmxnet3                65536  0',
      ])
    }
    else if (lc === 'modprobe' || lc === 'insmod' || lc === 'modinfo') {
      const mod = positional[0] || ''
      if (lc === 'modinfo') emit(`filename:       /lib/modules/5.15.0-91/kernel/net/${mod}.ko\nlicense:        GPL\ndescription:    ${mod} kernel module`)
      else if (vm?.kernel_module_missing && !moduleLoaded && (mod.includes('nf_conntrack') || mod.includes('br_netfilter') || mod.includes('bridge') || mod.includes('overlay'))) {
        moduleLoaded = true
        emit('')
        sideEffect = { action: 'guest_load_module', vm_id: vm?.id, module: mod }
      } else emit('')
    }
    else if (lc === 'rmmod' || lc === 'depmod') emit('')
    else if (lc === 'sysctl') {
      if (has('-a')) emit(['kernel.hostname = ' + hostname, 'net.ipv4.ip_forward = 0', 'vm.swappiness = 30', 'fs.file-max = 2097152'])
      else if (has('-p')) emit(['net.ipv4.ip_forward = 0', 'vm.swappiness = 30'])
      else if (positional[0]?.includes('=')) emit(positional[0].replace('=', ' = '))
      else if (positional[0] === 'net.ipv4.ip_forward') emit('net.ipv4.ip_forward = 0')
      else if (positional[0] === 'vm.swappiness') emit('vm.swappiness = 30')
      else if (positional[0]) emit(`${positional[0]} = 0`)
      else emit('usage: sysctl [options] [variable[=value]]')
    }

    /* =================== security / SELinux / firewall =================== */
    else if (lc === 'getenforce') emit(selinuxMode)
    else if (lc === 'setenforce') {
      const v = positional[0]
      if (v === '0' || /permissive/i.test(v)) selinuxMode = 'Permissive'
      else if (v === '1' || /enforcing/i.test(v)) selinuxMode = 'Enforcing'
      emit('')
    }
    else if (lc === 'sestatus') emit([
      'SELinux status:                 enabled',
      'SELinuxfs mount:                /sys/fs/selinux',
      'SELinux root directory:         /etc/selinux',
      'Loaded policy name:             targeted',
      `Current mode:                   ${selinuxMode.toLowerCase()}`,
      'Mode from config file:          enforcing',
      'Policy MLS status:              enabled',
    ])
    else if (lc === 'getsebool' || lc === 'setsebool' || lc === 'semanage' || lc === 'restorecon' || lc === 'chcon') emit(lc === 'getsebool' ? `${positional[0] || 'httpd_can_network_connect'} --> off` : '')
    else if (lc === 'firewall-cmd') {
      if (has('--list-all') || args.includes('--list-all')) emit(['public (active)', '  target: default', '  interfaces: eth0', '  services: ssh dhcpv6-client', '  ports: ', '  masquerade: no'])
      else if (has('--state')) emit('running')
      else if (has('--reload')) emit('success')
      else if (args.some(a => a.startsWith('--add') || a.startsWith('--remove') || a.startsWith('--permanent'))) emit('success')
      else emit('usage: see firewall-cmd --help')
    }
    else if (lc === 'ufw') {
      if (positional[0] === 'status') emit(['Status: active', '', 'To                         Action      From', '--                         ------      ----', '22/tcp                     ALLOW       Anywhere'])
      else emit('Firewall reloaded')
    }
    else if (lc === 'iptables' || lc === 'ip6tables' || lc === 'nft') {
      if (lc === 'nft') emit('table inet filter {\n\tchain input {\n\t\ttype filter hook input priority 0;\n\t}\n}')
      else emit(['Chain INPUT (policy ACCEPT)', 'target     prot opt source               destination', 'ACCEPT     tcp  --  anywhere             anywhere             tcp dpt:ssh', 'Chain FORWARD (policy ACCEPT)', 'Chain OUTPUT (policy ACCEPT)'])
    }
    else if (lc === 'fail2ban-client') emit('Status\n|- Number of jail:\t1\n`- Jail list:\tsshd')

    /* =================== cron =================== */
    else if (lc === 'crontab') {
      if (has('-l')) {
        const node = vfs.resolveNode('/var/spool/cron/root')
        emit(node && node.content ? node.content.replace(/\n$/, '') : 'no crontab for root')
      } else if (has('-e')) emit('crontab: installing new crontab (use vi /var/spool/cron/root to edit)')
      else if (has('-r')) { const node = vfs.resolveNode('/var/spool/cron/root'); if (node) node.content = ''; emit('') }
      else emit('usage: crontab [-u user] file\n       crontab [ -e | -l | -r ]')
    }

    /* =================== shell builtins & misc =================== */
    else if (lc === 'help' || lc === '?') emit(buildHelp(isRhel))
    else if (lc === 'clear') return { lines: [], clear: true, prompt: prompt() }
    else if (lc === 'exit' || lc === 'logout') return { lines: ['logout'], exit: true, prompt: prompt() }
    else if (lc === 'history') {
      if (has('-c')) { history.length = 0; emit('') }
      else history.forEach((h, i) => out.push(`${String(i + 1).padStart(5)}  ${h}`))
    }
    else if (lc === 'env' || lc === 'printenv') {
      if (positional[0] && lc === 'printenv') emit(env[positional[0]] || '')
      else Object.entries(env).forEach(([k, v]) => out.push(`${k}=${v}`))
    }
    else if (lc === 'export') {
      if (positional[0]?.includes('=')) { const [k, ...rest] = positional[0].split('='); env[k] = rest.join('=').replace(/^["']|["']$/g, ''); emit('') }
      else if (positional[0]) emit('')
      else Object.entries(env).forEach(([k, v]) => out.push(`declare -x ${k}="${v}"`))
    }
    else if (lc === 'unset') { if (positional[0]) delete env[positional[0]]; emit('') }
    else if (lc === 'alias') emit(["alias ll='ls -lh'", "alias grep='grep --color=auto'", "alias la='ls -A'"])
    else if (lc === 'unalias' || lc === 'set' || lc === 'shopt' || lc === 'ulimit' || lc === 'umask') {
      if (lc === 'ulimit') emit(has('-n') ? '65536' : 'unlimited')
      else if (lc === 'umask') emit('0022')
      else emit('')
    }
    else if (lc === 'source' || lc === '.') emit('')
    else if (lc === 'which' || lc === 'whereis' || lc === 'type' || lc === 'command') {
      const t = positional[0]
      if (!t) emit('')
      else if (lc === 'whereis') emit(`${t}: /usr/bin/${t} /usr/share/man/man1/${t}.1.gz`)
      else if (lc === 'type') emit(`${t} is /usr/bin/${t}`)
      else emit(`/usr/bin/${t}`)
    }
    else if (lc === 'man' || lc === 'info' || lc === 'apropos') emit(`What manual page do you want?\n(simulated — try '${positional[0] || 'command'} --help')`)
    else if (lc === 'tldr') emit(`# ${positional[0] || 'command'}\n(simulated tldr page)`)
    else if (lc === 'sleep' || lc === 'true' || lc === ':' ) emit('')
    else if (lc === 'false') return { lines: [''], prompt: prompt() }
    else if (lc === 'test' || lc === '[') emit('')
    else if (lc === 'seq') { const n = parseInt(positional[0], 10) || 5; emit(Array.from({ length: Math.min(n, 50) }, (_, i) => String(i + 1))) }
    else if (lc === 'yes') emit('y')
    else if (lc === 'basename') emit(basename(positional[0] || ''))
    else if (lc === 'dirname') emit(dirname(positional[0] || ''))
    else if (lc === 'readlink' || lc === 'realpath') { const node = vfs.lresolve(abs(positional[0] || '')); emit(node && node.type === 'link' ? node.target : abs(positional[0] || '')) }
    else if (lc === 'tee') { if (redirect === null && positional[0]) { vfs.writeFile(abs(positional[0]), '') } emit('') }

    /* =================== text processing =================== */
    else if (['awk', 'gawk', 'sed', 'cut', 'sort', 'uniq', 'tr', 'xargs', 'paste', 'join', 'comm', 'fold', 'column', 'nl', 'rev', 'jq', 'diff', 'cmp'].includes(lc)) {
      // best-effort: if a real file is the last arg, echo its content lightly transformed
      const file = positional.find(a => vfs.resolveNode(abs(a))?.type === 'file')
      if (file) {
        const content = vfs.resolveNode(abs(file)).content.replace(/\n$/, '').split('\n')
        if (lc === 'sort') emit([...content].sort())
        else if (lc === 'uniq') emit(content.filter((l, i) => l !== content[i - 1]))
        else if (lc === 'rev') emit(content.map(l => l.split('').reverse().join('')))
        else if (lc === 'nl') emit(content.map((l, i) => `     ${i + 1}\t${l}`))
        else if (lc === 'tac') emit([...content].reverse())
        else emit(content)
      } else emit('')
    }
    else if (lc === 'tac') emit('')

    /* =================== archives =================== */
    else if (['tar', 'gzip', 'gunzip', 'bzip2', 'xz', 'zip', 'unzip', 'cpio', 'zcat'].includes(lc)) {
      if (lc === 'tar' && (has('-t') || args.some(a => a.includes('t')))) emit(['./', './etc/', './etc/config'])
      else emit('')
    }

    /* =================== interpreters / containers / IaC =================== */
    else if (lc === 'python' || lc === 'python3') emit(positional.length ? '' : 'Python 3.9.18 (main, Jan 24 2024, 00:00:00)\n[GCC 11.4.0] on linux\nType "help", "copyright", "credits" or "license" for more information.\n(simulated — non-interactive)')
    else if (lc === 'node') emit(positional.length ? '' : 'Welcome to Node.js v18.19.0.\nType ".help" for more information. (simulated)')
    else if (['perl', 'ruby', 'php', 'go', 'java', 'gcc', 'make', 'cc', 'javac'].includes(lc)) emit(positional.length ? '' : `${lc}: simulated interpreter/compiler`)
    else if (lc === 'pip' || lc === 'pip3' || lc === 'npm' || lc === 'yarn' || lc === 'gem' || lc === 'cargo') emit(positional[0] === 'install' ? `Successfully installed ${positional[1] || 'package'}` : `${lc} ${positional[0] || ''} (simulated)`)
    else if (lc === 'docker') {
      const sub = positional[0]
      if (sub === 'ps') emit(['CONTAINER ID   IMAGE          COMMAND                  CREATED       STATUS       PORTS                  NAMES', 'a1b2c3d4e5f6   nginx:1.25     "/docker-entrypoint.…"   2 hours ago   Up 2 hours   0.0.0.0:8080->80/tcp   web', 'f6e5d4c3b2a1   mysql:8.0      "docker-entrypoint.s…"   2 hours ago   Up 2 hours   3306/tcp               db'])
      else if (sub === 'images') emit(['REPOSITORY   TAG       IMAGE ID       CREATED       SIZE', 'nginx        1.25      a1b2c3d4e5f6   3 weeks ago   142MB', 'mysql        8.0       f6e5d4c3b2a1   3 weeks ago   621MB'])
      else if (sub === 'version') emit('Client: Docker Engine - Community\n Version:           24.0.7')
      else if (sub === 'info') emit('Containers: 2\n Running: 2\nImages: 5\nServer Version: 24.0.7')
      else if (sub === 'pull') emit(`Using default tag: latest\nlatest: Pulling from library/${positional[1] || 'image'}\nStatus: Downloaded newer image`)
      else emit('Usage:  docker [OPTIONS] COMMAND')
    }
    else if (lc === 'podman') emit('CONTAINER ID  IMAGE   COMMAND  CREATED  STATUS  PORTS  NAMES')
    else if (lc === 'kubectl' || lc === 'k') {
      const sub = positional[0]
      if (sub === 'get') {
        const res = positional[1]
        if (res === 'nodes') emit(['NAME            STATUS   ROLES           AGE   VERSION', 'node01          Ready    control-plane   14d   v1.29.2', 'node02          Ready    <none>          14d   v1.29.2'])
        else if (res === 'pods' || res === 'po') emit(['NAME                    READY   STATUS    RESTARTS   AGE', 'web-7d9f8c6b5-x2k9p     1/1     Running   0          2h', 'db-0                    1/1     Running   0          2h'])
        else emit(`No resources found in default namespace.`)
      } else if (sub === 'version') emit('Client Version: v1.29.2\nServer Version: v1.29.2')
      else if (sub === 'cluster-info') emit('Kubernetes control plane is running at https://10.0.0.1:6443')
      else emit('kubectl controls the Kubernetes cluster manager.')
    }
    else if (lc === 'helm') emit('NAME\tNAMESPACE\tREVISION\tSTATUS\tCHART')
    else if (['ansible', 'ansible-playbook', 'terraform', 'packer', 'vagrant', 'git'].includes(lc)) {
      if (lc === 'git' && positional[0] === 'status') emit('On branch main\nnothing to commit, working tree clean')
      else if (lc === 'terraform' && positional[0] === 'version') emit('Terraform v1.7.4\non linux_amd64')
      else emit(`${lc}: simulated (${positional.join(' ') || 'no args'})`)
    }

    /* =================== power =================== */
    else if (['reboot', 'shutdown', 'poweroff', 'halt'].includes(lc)) emit('Connection to host closed by remote host. (simulated reboot — reopen console)')
    else if (lc === 'systemd-analyze') emit('Startup finished in 1.842s (kernel) + 4.221s (userspace) = 6.063s\nmulti-user.target reached after 4.118s in userspace.')
    else if (lc === 'init' || lc === 'telinit' || lc === 'runlevel') emit(lc === 'runlevel' ? 'N 5' : '')
    else if (lc === 'chroot') emit('')

    else notFound()

    /* ---- apply output redirection back into the VFS ---- */
    if (redirect && !editor) {
      const target = abs(redirect.path)
      const node = vfs.resolveNode(target)
      const existing = node && node.type === 'file' ? node.content : ''
      const payload = out.join('\n')
      vfs.writeFile(target, redirect.append ? existing + payload + '\n' : payload + (payload ? '\n' : ''))
      out.length = 0
      out.push('')
    }

    if (editor) return { lines: [], prompt: prompt(), editor }
    return { lines: out.length ? out : [''], prompt: prompt(), sideEffect }
  }

  return {
    run,
    prompt,
    history,
    saveFile,
    readFile,
    pkgManager: () => pkgManager(vm),
  }
}

function buildHelp(isRhel) {
  return `Simulated ${isRhel ? 'RHEL 9' : 'Ubuntu 22.04'} shell — backed by a real in-memory filesystem.
  Files     ls (-l -a) cd pwd cat head tail echo (> >>) touch mkdir (-p) rm (-rf) cp (-r) mv
            find grep (-r -i -v -n) wc chmod chown ln -s stat file tree du df ln readlink
  Editors   vi / vim / nano  (open, edit, and SAVE files back to the filesystem)
  System    uname -a uptime date id whoami hostnamectl lscpu lsmem free top ps vmstat dmesg
  Services  systemctl (start|stop|restart|status|enable) service journalctl -u <unit>
  Network   ip addr/route/link  ifconfig  ping  ss  netstat  nmcli  ss  dig  traceroute  ssh
  Packages  ${isRhel ? 'dnf / yum / rpm' : 'apt / apt-get / dpkg'}  (install update remove list)
  Users     useradd usermod passwd id groups su sudo who w last
  Storage   lsblk blkid fdisk -l mkfs.ext4 mount umount  pvs vgs lvs  swapon
  Kernel    lsmod modprobe modinfo sysctl (-a -p)
  Security  getenforce setenforce sestatus  firewall-cmd  iptables  ufw  crontab -l
  Other     env export history clear exit help  — 180+ commands recognized`.split('\n')
}

export const BOOT_SEQUENCE = [
  '[    0.000000] Linux version 5.15.0-91-generic (build@fixitlab) #101 SMP',
  '[    0.342891] BIOS-provided physical RAM map:',
  '[    0.891234] systemd[1]: systemd 249 running in system mode (+PAM)',
  '[    1.234567] systemd[1]: Reached target Local File Systems.',
  '[    2.100000] cloud-init: Cloud-init v. 23.1.1 running init-local',
  '[    3.445000] Loading initial ramdisk ...',
  '[    4.120000] Begin: Loading essential drivers ... done.',
  '[    5.890000] Begin: Mounting root file system ... done.',
  '[    6.234000] systemd[1]: Started FixitLab simulated guest.',
  '[    7.001000] Started Network Manager.',
  '[    8.442000] Started OpenSSH server.',
]

export const GRUB_ENTRIES = [
  'Ubuntu, with Linux 5.15.0-91-generic',
  'Ubuntu, with Linux 5.15.0-91-generic (recovery mode)',
  'Ubuntu, with Linux 5.15.0-88-generic',
  'Advanced options for Ubuntu',
  'UEFI Firmware Settings',
]
