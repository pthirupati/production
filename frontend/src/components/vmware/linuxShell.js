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

import { createGitSim } from './gitSim'

const HUMAN_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** Per-VM shared guest state (VFS, packages, disk flags) — all terminal tabs share this. */
const sharedGuestState = new Map()

function guestStateKey(vm) {
  return String(vm?.id || vm?.name || 'default')
}

function formatUptime(ms) {
  const s = Math.floor(ms / 1000)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function getOrCreateGuestShared(vm) {
  const key = guestStateKey(vm)
  if (!sharedGuestState.has(key)) {
    const family = guestOsFamily(vm)
    const isRhel = family === 'rhel'
    const diskGb = vm?.disk_gb || 40
    const vfs = createVFS((api) => seedFilesystem(vm, api))
    sharedGuestState.set(key, {
      vfs,
      services: seedServices(),
      pkgs: createPkgDb(isRhel),
      selinuxMode: isRhel ? 'Enforcing' : 'Disabled',
      diskRescanned: !vm?.guest_disk_hidden,
      diskFormatted: !!vm?.guest_disk_formatted,
      diskMounted: !!vm?.guest_disk_mounted,
      nicRescanned: !vm?.guest_nic_pending,
      moduleLoaded: !vm?.kernel_module_missing,
      lvm: createLvmState(diskGb),
      bootEpoch: Date.now() - (14 * 86400 + 3 * 3600 + 22 * 60) * 1000,
    })
  }
  const shared = sharedGuestState.get(key)
  // Reconcile VMware engine flags when the guest object updates (disk add/rescan flow).
  if (vm?.guest_disk_rescanned || vm?.guest_disk_visible) shared.diskRescanned = true
  if (vm?.guest_disk_formatted) shared.diskFormatted = true
  if (vm?.guest_disk_mounted) shared.diskMounted = true
  if (vm?.guest_nic_pending === false) shared.nicRescanned = true
  if (vm?.kernel_module_missing === false) shared.moduleLoaded = true
  // New hot-added hardware must be rescanned again — reset flags when pending devices appear.
  if (vm?.guest_disk_hidden && (vm?.guest_pending_disks?.length || 0) > 0 && !vm?.guest_disk_rescanned && !vm?.guest_disk_visible) {
    shared.diskRescanned = false
  }
  if (vm?.guest_nic_pending && (vm?.guest_pending_nics?.length || 0) > 0) {
    shared.nicRescanned = false
  }
  return shared
}

function createLvmState(diskGb) {
  const rootPvGb = Math.max(1, diskGb - 1)
  const swapGb = 2
  const rootGb = Math.max(8, diskGb - 5)
  return {
    rootPvGb,
    swapGb,
    rootLvGb: rootGb,
    rootFsGb: rootGb,
    extraPvGb: 20,
    extraPvDevice: null,
    extraPvInVg: false,
    vgFreeGb: 0,
  }
}

function fmtGb(n, opts = {}) {
  const v = Number(n) || 0
  const body = `${v.toFixed(2)}g`
  return opts.lt ? `<${body}` : body
}

/** SCSI unit 1 → sdb, 2 → sdc, … (unit 0 is always the boot disk on sda). */
function scsiUnitToDevLetter(scsiUnit) {
  const unit = Number(scsiUnit) || 0
  if (unit <= 0) return null
  return String.fromCharCode(96 + unit + 1)
}

function scsiUnitToDevPath(scsiUnit) {
  const letter = scsiUnitToDevLetter(scsiUnit)
  return letter ? `/dev/sd${letter}` : null
}

/** Extra (non-boot) disks visible in the guest — mirrors vm.disks[] + hot-add pending state. */
function guestExtraDisks(vm, shared) {
  if (!shared.diskRescanned && vm?.guest_disk_hidden) {
    return []
  }
  const pending = vm?.guest_pending_disks || []
  if (pending.length) {
    return pending.map((d, i) => {
      const unit = d.scsi_unit ?? (i + 1)
      return {
        letter: scsiUnitToDevLetter(unit) || String.fromCharCode(98 + i),
        scsi_unit: unit,
        capacity_gb: d.capacity_gb || d.size_gb || 20,
        scsi_id: d.scsi_id || `0:${unit}`,
      }
    })
  }
  return (vm?.disks || [])
    .filter((d) => (d.scsi_unit ?? 0) > 0)
    .map((d) => ({
      letter: scsiUnitToDevLetter(d.scsi_unit) || 'b',
      scsi_unit: d.scsi_unit,
      capacity_gb: d.capacity_gb || d.size_gb || 20,
      scsi_id: d.scsi_id || `0:${d.scsi_unit}`,
    }))
}

function extraDiskPath(extra) {
  if (!extra) return null
  return `/dev/sd${extra.letter || scsiUnitToDevLetter(extra.scsi_unit) || 'b'}`
}

function extraDiskPartPath(extra) {
  const base = extraDiskPath(extra)
  return base ? `${base}1` : null
}

function devMatchesExtraDisk(dev, vm, shared) {
  const norm = normalizeDevName(dev || '')
  return guestExtraDisks(vm, shared).some((d) => {
    const base = extraDiskPath(d)
    const part = extraDiskPartPath(d)
    return norm === base || norm === part || norm.startsWith(`${base}`)
  })
}

function guestExtraNics(vm, shared) {
  const pending = vm?.guest_pending_nics || []
  if (!shared.nicRescanned && vm?.guest_nic_pending) return []
  if (pending.length) {
    return pending.map((n, i) => ({
      name: n.name || `eth${i + 1}`,
      mac: n.mac || n.mac_address || `00:50:56:${(i + 1).toString(16).padStart(2, '0')}:c3:d4`,
      label: n.label || `Network adapter ${i + 2}`,
    }))
  }
  const nics = vm?.nics || []
  if (nics.length <= 1) return []
  return nics.slice(1).map((n, i) => ({
    name: `eth${i + 1}`,
    mac: n.mac || n.mac_address || `00:50:56:${(i + 1).toString(16).padStart(2, '0')}:c3:d4`,
    label: n.label || `Network adapter ${i + 2}`,
  }))
}

function triggerGuestRescan(vm, shared) {
  shared.diskRescanned = true
  shared.nicRescanned = true
  if (vm?.guest_disk_hidden) {
    return { action: 'guest_rescan_scsi', vm_id: vm?.id }
  }
  if (vm?.guest_nic_pending) {
    return { action: 'guest_rescan_scsi', vm_id: vm?.id }
  }
  return null
}

function normalizeDevName(dev = '') {
  if (!dev) return ''
  if (dev.includes('/mapper/rootvg-root')) return '/dev/rootvg/root'
  if (dev.includes('/rootvg/root')) return '/dev/rootvg/root'
  return dev.replace(/\/+$/, '')
}

function parseSizeGb(args, freeGb) {
  const joined = args.join(' ')
  if (/\+?100%FREE/i.test(joined)) return freeGb
  const m = joined.match(/\+?(\d+(?:\.\d+)?)([gGtTmMkK]?)/)
  if (!m) return freeGb || 0
  const n = Number(m[1]) || 0
  const unit = (m[2] || 'g').toLowerCase()
  if (unit === 't') return n * 1024
  if (unit === 'm') return n / 1024
  if (unit === 'k') return n / (1024 * 1024)
  return n
}

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
  const hostname = vm?.hostname || vm?.name || (isRhel ? 'rhel-server-01' : 'ubuntu-server-01')
  const kernel = isRhel ? '5.14.0-362.8.1.el9_3.x86_64' : '5.15.0-91-generic'
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
    '/etc/default', '/home', '/home/devops', '/home/devops/.ssh',
    '/home/labuser', '/home/labuser/.ssh', '/home/labuser/.config/htop',
    '/home/labuser/projects', '/home/labuser/projects/web-app',
    '/home/labuser/projects/scripts', '/home/labuser/projects/configs',
    '/home/labuser/tmp', '/media', '/mnt', '/mnt/backup', '/mnt/data', '/opt',
    '/opt/app', '/proc', '/proc/sys/kernel', '/proc/sys/net/ipv4', '/proc/sys/vm', '/root',
    '/root/.ssh', '/run', '/srv', '/sys', '/tmp', '/var', '/var/cache', '/var/lib',
    '/var/lib/docker', '/var/lib/mysql', '/var/log', '/var/log/nginx', '/var/log/journal',
    '/var/spool/cron', '/var/spool/mail', '/var/www/html', '/var/tmp',
  ]
  if (isRhel) {
    dirs.push('/etc/yum.repos.d', '/etc/sysconfig', '/etc/sysconfig/network-scripts',
      '/etc/selinux', '/etc/selinux/targeted', '/etc/dnf', '/etc/firewalld',
      '/etc/firewalld/zones', '/etc/firewalld/services', '/etc/httpd/conf', '/etc/httpd/conf.d',
      '/var/log/audit')
  } else {
    dirs.push('/etc/apt', '/etc/apt/sources.list.d', '/etc/network', '/etc/netplan',
      '/etc/apache2/sites-enabled', '/etc/ufw')
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
    W('/etc/rhel-release', 'Red Hat Enterprise Linux release 9.3 (Plow)\n')
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
    W('/etc/NetworkManager/NetworkManager.conf', '[main]\nplugins=keyfile,ifcfg-rh\n\n[ifupdown]\nmanaged=false\n')
    W('/etc/firewalld/firewalld.conf', 'DefaultZone=public\nCleanupOnExit=yes\nLockdown=no\nIPv6_rpfilter=yes\n')
    W('/etc/firewalld/zones/public.xml', '<zone><short>Public</short><service name="ssh"/><service name="http"/></zone>\n')
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
    W('/etc/ufw/ufw.conf', 'ENABLED=yes\nLOGLEVEL=low\n')
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
labuser:x:1001:1001:Lab User:/home/labuser:/bin/bash
jsmith:x:1002:1002:John Smith:/home/jsmith:/bin/bash
deploy:x:1003:1003:Deploy User:/home/deploy:/bin/bash
`)
  W('/etc/group',
`root:x:0:
bin:x:1:
daemon:x:2:
sys:x:3:
adm:x:4:devops,labuser
wheel:x:10:devops,labuser
sshd:x:74:
nginx:x:990:
mysql:x:27:
sudo:x:27:devops,labuser
devops:x:1000:
labuser:x:1001:
jsmith:x:1002:
deploy:x:1003:
`)
  W('/etc/shadow',
`root:$6$Xy9Lk2/QpR$jT0HqW.bK7sZ1m8nO3pVcdeFgHiJ.kLmNoPqRsTuVwXyZ012345aBcDeFg/:19800:0:99999:7:::
bin:*:19800:0:99999:7:::
daemon:*:19800:0:99999:7:::
sshd:!!:19800::::::
nginx:!!:19800::::::
mysql:!!:19800::::::
devops:$6$aBcDeF$gHiJkLmNoPqRsTuVwXyZ0123456789.AbCdEfGhIjKlMnOpQrStUvWx/:19800:0:99999:7:::
labuser:$6$labUsr$labuser.training.hash.placeholder.for.simulation/:19800:0:99999:7:::
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

  // ---- labuser home (primary training account) ----
  W('/home/labuser/.bashrc',
`# ~/.bashrc — labuser
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias grep='grep --color=auto'
export PS1='\\u@\\h:\\w\\$ '
export EDITOR=vim
export VISUAL=vim
`, '0644', 1001, 1001)
  W('/home/labuser/.profile', '# ~/.profile\nif [ -n "$BASH_VERSION" ]; then\n    [ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"\nfi\n', '0644', 1001, 1001)
  W('/home/labuser/.bash_logout', '# ~/.bash_logout\n', '0644', 1001, 1001)
  W('/home/labuser/.vimrc', 'set number\nset expandtab\nset tabstop=4\nsyntax on\n', '0644', 1001, 1001)
  W('/home/labuser/.sudo_as_admin_successful', '', '0644', 1001, 1001)
  W('/home/labuser/.bash_history',
`sudo apt update
systemctl status nginx
df -h
lsblk
cd projects/scripts
./health-check.sh
tail -f /var/log/nginx/access.log
`, '0600', 1001, 1001)
  W('/home/labuser/.ssh/authorized_keys',
`ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7labuser-key-1 labuser@workstation
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIlabuser-deploy-key deploy@ci
`, '0600', 1001, 1001)
  W('/home/labuser/.ssh/config',
`Host *
    StrictHostKeyChecking accept-new
    IdentityFile ~/.ssh/id_rsa
`, '0600', 1001, 1001)
  W('/home/labuser/.config/htop/htoprc', '# htop configuration\nfields=0 48 17 18 38 39 40 2 46 47 49 1\n', '0644', 1001, 1001)
  W('/home/labuser/projects/web-app/app.py',
`#!/usr/bin/env python3
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify(status='ok', version='2.4.1')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
`, '0644', 1001, 1001)
  W('/home/labuser/projects/web-app/requirements.txt', 'flask==3.0.0\ngunicorn==21.2.0\n', '0644', 1001, 1001)
  W('/home/labuser/projects/scripts/health-check.sh',
`#!/bin/bash
# Health check — run from cron every 5 minutes
SERVICES=(nginx mysql redis-server postgresql)
for svc in "\${SERVICES[@]}"; do
  systemctl is-active --quiet "$svc" || echo "WARN: $svc not active"
done
`, '0755', 1001, 1001)
  W('/home/labuser/projects/scripts/backup.sh', '#!/bin/bash\n# Backup script — see /var/log/backup.log\n', '0755', 1001, 1001)
  W('/home/labuser/projects/scripts/deploy.sh', '#!/bin/bash\nset -euo pipefail\necho "Deploying application..."\n', '0755', 1001, 1001)
  W('/home/labuser/projects/configs/nginx-site.conf',
`server {
    listen 80;
    server_name app.lab.local;
    root /var/www/html;
}
`, '0644', 1001, 1001)
  W('/var/spool/cron/labuser',
`# m h  dom mon dow   command
*/5 * * * * /home/labuser/projects/scripts/health-check.sh >> /var/log/healthcheck.log 2>&1
0 2 * * * /home/labuser/projects/scripts/backup.sh
`, '0600', 1001, 1001)

  // ---- /proc (basics, runtime-ish) ----
  W('/proc/version', `Linux version ${kernel} (build@fixitlab) (gcc ${isRhel ? '11.4.1' : '11.4.0'}) #1 SMP PREEMPT_DYNAMIC x86_64\n`, '0444')
  W('/proc/cmdline', `BOOT_IMAGE=/boot/vmlinuz-${kernel} root=UUID=8f3b2c1a-0e4d-4c6b-9a7f-1d2e3f4a5b6c ro quiet\n`, '0444')
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
  W(`/boot/config-${kernel}`, 'CONFIG_LOCALVERSION=""\nCONFIG_SMP=y\nCONFIG_X86_64=y\nCONFIG_BLK_DEV_SD=y\nCONFIG_VMXNET3=m\n')

  // ---- logs ----
  const today = new Date()
  const ds = `${HUMAN_MONTHS[today.getMonth()]} ${String(today.getDate()).padStart(2, ' ')}`
  const systemLines = [
    `${ds} 00:00:01 ${hostname} systemd[1]: Started Daily Cleanup of Temporary Directories.`,
    `${ds} 00:05:01 ${hostname} systemd[1]: Started Run anacron jobs.`,
    `${ds} 02:00:11 ${hostname} CROND[1842]: (root) CMD (/usr/local/bin/backup.sh)`,
    `${ds} 06:25:30 ${hostname} run-parts(/etc/cron.daily)[2010]: starting logrotate`,
    `${ds} 09:14:22 ${hostname} kernel: [1216000.1] eth0: link up, 10000 Mbps, full duplex`,
    `${ds} 09:15:23 ${hostname} sshd[1823]: Server listening on 0.0.0.0 port 22.`,
    `${ds} 10:00:01 ${hostname} kernel: [1234567.123] EXT4-fs (sdb1): mounted filesystem with ordered data mode`,
    `${ds} 11:02:48 ${hostname} systemd[1]: nginx.service: Failed with result 'exit-code'.`,
    `${ds} 11:02:48 ${hostname} nginx[3122]: nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)`,
  ]
  const authLines = [
    `${ds} 08:01:12 ${hostname} sshd[1201]: Accepted password for root from ${gw} port 51022 ssh2`,
    `${ds} 08:01:12 ${hostname} sshd[1201]: pam_unix(sshd:session): session opened for user root(uid=0)`,
    `${ds} 08:44:55 ${hostname} sudo: labuser : TTY=pts/1 ; PWD=/home/labuser ; USER=root ; COMMAND=/usr/bin/systemctl restart nginx`,
    `${ds} 09:15:02 ${hostname} sshd[1450]: Failed password for invalid user admin from 203.0.113.7 port 40122 ssh2`,
    `${ds} 09:15:04 ${hostname} sshd[1450]: Failed password for invalid user root from 203.0.113.7 port 40123 ssh2`,
  ]
  const accessLines = Array.from({ length: 80 }, (_, i) => {
    const minute = String(10 + (i % 50)).padStart(2, '0')
    const status = i % 17 === 0 ? 404 : i % 13 === 0 ? 500 : 200
    const path = status === 404 ? '/wp-admin' : i % 5 === 0 ? '/api/health' : '/'
    return `${gw} - - [${String(today.getDate()).padStart(2, '0')}/${HUMAN_MONTHS[today.getMonth()]}/${today.getFullYear()}:09:${minute}:01 +0000] "GET ${path} HTTP/1.1" ${status} ${status === 200 ? 612 : 162} "-" "curl/7.81.0"`
  })
  W('/var/log/messages', `${systemLines.join('\n')}\n`)
  W('/var/log/secure', `${authLines.join('\n')}\n`)
  W('/var/log/auth.log', `${authLines.join('\n')}\n`)
  W('/var/log/syslog', `${systemLines.join('\n')}\n`)
  W('/var/log/dmesg', `[    0.000000] Linux version ${kernel}\n[    1.234567] systemd[1]: Reached target Multi-User System.\n[    2.100000] sd 2:0:0:0: [sda] Attached SCSI disk\n`)
  W('/var/log/boot.log', '[  OK  ] Reached target Multi-User System.\n[  OK  ] Started OpenSSH server daemon.\n')
  W('/var/log/cron', `${ds} 02:00:01 ${hostname} CROND[1842]: (root) CMD (/usr/local/bin/backup.sh)\n`)
  W('/var/log/nginx/access.log', `${accessLines.join('\n')}\n`)
  W('/var/log/nginx/error.log', `${today.getFullYear()}/06/18 11:02:48 [emerg] 3122#3122: bind() to 0.0.0.0:80 failed (98: Address already in use)\n`)
  W('/var/log/audit/audit.log', `type=AVC msg=audit(${Math.floor(Date.now() / 1000)}.456:4522): avc: denied { write } for pid=901 comm="mysqld" name="mysql" scontext=system_u:system_r:mysqld_t:s0 tcontext=system_u:object_r:var_t:s0 tclass=dir permissive=0\n`)
  W('/var/log/wtmp', '', '0664')
  W('/var/log/lastlog', '', '0644')
}

/* ------------------------------------------------------------------ *
 * Service & runtime state (per session)
 * ------------------------------------------------------------------ */
function seedServices() {
  return {
    sshd: { active: 'active', enabled: 'enabled', desc: 'OpenSSH server daemon', pid: 1201, since: '8h ago' },
    nginx: { active: 'active', enabled: 'enabled', desc: 'The nginx HTTP and reverse proxy server', pid: 3300, since: '8h ago' },
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
  return ({ 0: 'root', 27: 'mysql', 74: 'sshd', 990: 'nginx', 1000: 'devops', 1001: 'labuser', 1002: 'jsmith', 1003: 'deploy' })[uid] || String(uid)
}
function groupName(gid) {
  return ({ 0: 'root', 12: 'mail', 27: 'mysql', 74: 'sshd', 990: 'nginx', 1000: 'devops', 1001: 'labuser', 1002: 'jsmith', 1003: 'deploy' })[gid] || String(gid)
}

/* ------------------------------------------------------------------ *
 * Package-manager simulation (realistic dnf/yum + apt transactions)
 * ------------------------------------------------------------------ *
 * The React console drives the y/N prompt and the timed progress stream,
 * but the *content* of every phase lives here so both the web console and
 * the SSH terminal render byte-identical output.
 */

// A few packages that ship plausible dependencies, sizes, and versions.
const PKG_CATALOG = {
  nginx: { ver: '1:1.20.1', rel: '14.el9', repo: 'epel', sizeK: 36, deps: ['nginx-filesystem', 'nginx-core'] },
  httpd: { ver: '2.4.57', rel: '5.el9', repo: 'rhel-9-appstream', sizeK: 48, deps: ['httpd-core', 'httpd-tools', 'mod_http2'] },
  git: { ver: '2.39.3', rel: '1.el9', repo: 'rhel-9-appstream', sizeK: 54, deps: ['git-core', 'perl-Git'] },
  vim: { ver: '8.2.2637', rel: '20.el9', repo: 'rhel-9-appstream', sizeK: 58, deps: ['vim-common', 'vim-filesystem'] },
  'vim-enhanced': { ver: '8.2.2637', rel: '20.el9', repo: 'rhel-9-appstream', sizeK: 58, deps: ['vim-common', 'vim-filesystem'] },
  htop: { ver: '3.2.1', rel: '1.el9', repo: 'epel', sizeK: 17, deps: [] },
  wget: { ver: '1.21.1', rel: '7.el9', repo: 'rhel-9-baseos', sizeK: 21, deps: [] },
  curl: { ver: '7.76.1', rel: '26.el9', repo: 'rhel-9-baseos', sizeK: 22, deps: ['libcurl'] },
  tmux: { ver: '3.2a', rel: '5.el9', repo: 'rhel-9-appstream', sizeK: 24, deps: [] },
  mysql: { ver: '8.0.36', rel: '1.el9', repo: 'rhel-9-appstream', sizeK: 95, deps: ['mysql-common', 'mysql-libs'] },
  'mysql-server': { ver: '8.0.36', rel: '1.el9', repo: 'rhel-9-appstream', sizeK: 120, deps: ['mysql', 'mysql-common'] },
  docker: { ver: '24.0.7', rel: '1.el9', repo: 'docker-ce', sizeK: 110, deps: ['containerd.io', 'docker-ce-cli'] },
}

function pkgInfo(name) {
  return PKG_CATALOG[name] || { ver: '1.0.0', rel: '1.el9', repo: 'rhel-9-appstream', sizeK: 28, deps: [] }
}

/* ------------------------------------------------------------------ *
 * Stateful package database (the rpm / dpkg DB)
 * ------------------------------------------------------------------ *
 * `yum/dnf install` and `apt install` ADD to it; remove/erase/purge DELETE
 * from it; and `rpm -q`, `rpm -qa`, `dnf list installed`, `yum list installed`,
 * and `dpkg -l` all read FROM it. Without this, an install never showed up in a
 * subsequent rpm query (the original bug). Distribution-aware: RHEL-family hosts
 * report .rpm packages (arch x86_64/noarch, el9 dist tag), Debian/Ubuntu hosts
 * report dpkg packages (amd64, ubuntu version suffix).
 */

// The packages a minimal-but-realistic install ships with, before the learner
// touches anything. Names line up with what `systemctl`/`which` already imply.
const RHEL_BASE_PKGS = [
  ['kernel', '5.14.0', '362.el9', 'x86_64'],
  ['kernel-core', '5.14.0', '362.el9', 'x86_64'],
  ['glibc', '2.34', '83.el9', 'x86_64'],
  ['bash', '5.1.8', '6.el9', 'x86_64'],
  ['coreutils', '8.32', '34.el9', 'x86_64'],
  ['systemd', '252', '14.el9', 'x86_64'],
  ['openssh', '8.7p1', '34.el9', 'x86_64'],
  ['openssh-server', '8.7p1', '34.el9', 'x86_64'],
  ['openssh-clients', '8.7p1', '34.el9', 'x86_64'],
  ['openssl', '3.0.7', '24.el9', 'x86_64'],
  ['sudo', '1.9.5p2', '9.el9', 'x86_64'],
  ['python3', '3.9.18', '1.el9', 'x86_64'],
  ['dnf', '4.14.0', '8.el9', 'noarch'],
  ['yum', '4.14.0', '8.el9', 'noarch'],
  ['rpm', '4.16.1.3', '22.el9', 'x86_64'],
  ['firewalld', '1.2.5', '1.el9', 'noarch'],
  ['NetworkManager', '1.42.2', '1.el9', 'x86_64'],
  ['chrony', '4.3', '1.el9', 'x86_64'],
  ['vim-minimal', '8.2.2637', '20.el9', 'x86_64'],
  ['curl', '7.76.1', '26.el9', 'x86_64'],
  ['tar', '1.34', '6.el9', 'x86_64'],
]
const DEBIAN_BASE_PKGS = [
  ['base-files', '12ubuntu4.6', '', 'amd64'],
  ['bash', '5.1', '6ubuntu1', 'amd64'],
  ['coreutils', '8.32', '4.1ubuntu1', 'amd64'],
  ['libc6', '2.35', '0ubuntu3.6', 'amd64'],
  ['systemd', '249.11', '0ubuntu3.12', 'amd64'],
  ['openssh-server', '8.9p1', '3ubuntu0.6', 'amd64'],
  ['openssh-client', '8.9p1', '3ubuntu0.6', 'amd64'],
  ['openssl', '3.0.2', '0ubuntu1.15', 'amd64'],
  ['sudo', '1.9.9', '1ubuntu2.4', 'amd64'],
  ['python3', '3.10.6', '1~22.04', 'amd64'],
  ['apt', '2.4.11', '', 'amd64'],
  ['dpkg', '1.21.1', 'ubuntu2.3', 'amd64'],
  ['ufw', '0.36.1', '4build1', 'all'],
  ['netplan.io', '0.106.1', '7ubuntu0.22.04.2', 'amd64'],
  ['chrony', '4.2', '2ubuntu2.2', 'amd64'],
  ['vim-tiny', '8.2.3995', '1ubuntu2.15', 'amd64'],
  ['curl', '7.81.0', '1ubuntu1.15', 'amd64'],
  ['tar', '1.34', '1ubuntu0.1.22.04.2', 'amd64'],
]

// Map our PKG_CATALOG version into a per-distro {ver, rel, arch} record.
function pkgRecord(name, isRhel) {
  const i = pkgInfo(name)
  if (isRhel) {
    const arch = /noarch/.test(i.rel) ? 'noarch' : 'x86_64'
    return { name, ver: i.ver, rel: i.rel, arch, repo: i.repo }
  }
  // Debian: strip the rpm-style epoch (e.g. "1:1.20.1" -> "1.20.1") + el tag.
  return { name, ver: i.ver.replace(/^[0-9]+:/, ''), rel: '1ubuntu1', arch: 'amd64', repo: i.repo }
}

function createPkgDb(isRhel) {
  const db = new Map()
  const base = isRhel ? RHEL_BASE_PKGS : DEBIAN_BASE_PKGS
  base.forEach(([name, ver, rel, arch]) => db.set(name, { name, ver, rel, arch }))

  const add = (name) => {
    const rec = db.get(name) || pkgRecord(name, isRhel)
    db.set(name, rec)
  }
  // install a package plus the dependencies the catalog declares for it
  const install = (names) => {
    names.forEach((n) => {
      add(n)
      pkgInfo(n).deps.forEach((d) => add(d))
    })
  }
  const remove = (names) => {
    let removed = 0
    names.forEach((n) => { if (db.delete(n)) removed += 1 })
    return removed
  }
  const has = (name) => db.has(name)
  const get = (name) => db.get(name) || null
  // rpm -qa NVRA, sorted like rpm prints them
  const rpmList = () => [...db.values()]
    .map((r) => `${r.name}-${r.ver}-${r.rel}.${r.arch}`)
    .sort()
  // `name-version-release.arch` for a single installed package, or null
  const rpmNvra = (name) => {
    const r = db.get(name)
    return r ? `${r.name}-${r.ver}-${r.rel}.${r.arch}` : null
  }
  // dnf/yum "list installed" rows: "name.arch   version-release   @repo"
  const dnfRows = () => [...db.values()]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((r) => `${(r.name + '.' + r.arch).padEnd(34)}${(r.ver + '-' + r.rel).padEnd(24)}@${r.repo || 'anaconda'}`)
  // dpkg -l rows: "ii  name  version  arch  description"
  const dpkgRows = () => [...db.values()]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((r) => `ii  ${r.name.padEnd(28)} ${(r.ver + (r.rel ? '-' + r.rel : '')).padEnd(24)} ${r.arch.padEnd(12)} ${r.name} package`)
  return { db, install, remove, has, get, rpmList, rpmNvra, dnfRows, dpkgRows }
}

// dnf/yum: "Dependencies resolved" + the table + transaction summary (shown BEFORE the y/N prompt).
function dnfResolveLines(mgr, pkgs, action = 'install') {
  const lines = ['Last metadata expiration check: 0:14:22 ago on ' + new Date().toUTCString().replace('GMT', 'UTC') + '.']
  if (action === 'remove') {
    lines.push('Dependencies resolved.', '================================================================================',
      ' Package            Arch        Version              Repository           Size',
      '================================================================================', 'Removing:')
    pkgs.forEach(p => { const i = pkgInfo(p); lines.push(` ${p.padEnd(18)} x86_64      ${(i.ver + '-' + i.rel).padEnd(20)} @${i.repo.padEnd(18)} ${i.sizeK} k`) })
    lines.push('', 'Transaction Summary',
      '================================================================================',
      `Remove  ${pkgs.length} Package${pkgs.length > 1 ? 's' : ''}`, '', 'Freed space: ' + (pkgs.length * 1.2).toFixed(1) + ' M')
    return lines
  }
  // install/upgrade
  const all = []
  pkgs.forEach(p => { all.push({ name: p, dep: false, ...pkgInfo(p) }); pkgInfo(p).deps.forEach(d => all.push({ name: d, dep: true, ...pkgInfo(d) })) })
  lines.push('Dependencies resolved.',
    '================================================================================',
    ' Package            Arch        Version              Repository           Size',
    '================================================================================', 'Installing:')
  all.filter(p => !p.dep).forEach(p => lines.push(` ${p.name.padEnd(18)} x86_64      ${(p.ver + '-' + p.rel).padEnd(20)} ${p.repo.padEnd(20)} ${p.sizeK} k`))
  const deps = all.filter(p => p.dep)
  if (deps.length) {
    lines.push('Installing dependencies:')
    deps.forEach(p => lines.push(` ${p.name.padEnd(18)} x86_64      ${(p.ver + '-' + p.rel).padEnd(20)} ${p.repo.padEnd(20)} ${p.sizeK} k`))
  }
  const total = all.reduce((s, p) => s + p.sizeK, 0)
  lines.push('', 'Transaction Summary',
    '================================================================================',
    `Install  ${all.length} Package${all.length > 1 ? 's' : ''}`, '',
    `Total download size: ${total} k`, `Installed size: ${(total * 3.4 / 1024).toFixed(1)} M`)
  return lines
}

// dnf/yum: the streamed download + transaction phases (shown AFTER 'y', one chunk per tick).
function dnfProgressChunks(pkgs, action = 'install') {
  const all = []
  if (action === 'remove') {
    const chunks = [['Running transaction check', 'Running transaction test', 'Transaction test succeeded', 'Running transaction']]
    pkgs.forEach((p, i) => chunks.push([`  Erasing          : ${p}-${pkgInfo(p).ver}-${pkgInfo(p).rel}.x86_64    ${i + 1}/${pkgs.length}`,
      `  Verifying        : ${p}-${pkgInfo(p).ver}-${pkgInfo(p).rel}.x86_64    ${i + 1}/${pkgs.length}`]))
    chunks.push(['', 'Removed:', ...pkgs.map(p => `  ${p}-${pkgInfo(p).ver}-${pkgInfo(p).rel}.x86_64`), '', 'Complete!'])
    return chunks
  }
  pkgs.forEach(p => { all.push(p); pkgInfo(p).deps.forEach(d => all.push(d)) })
  const chunks = [['Downloading Packages:']]
  all.forEach(p => { const i = pkgInfo(p); chunks.push([`(${all.indexOf(p) + 1}/${all.length}): ${p}-${i.ver}-${i.rel}.x86_64.rpm        ${i.sizeK} kB/s | ${i.sizeK} kB     00:00`]) })
  chunks.push(['--------------------------------------------------------------------------------',
    `Total                                           ${all.reduce((s, p) => s + pkgInfo(p).sizeK, 0)} kB/s | ${all.reduce((s, p) => s + pkgInfo(p).sizeK, 0)} kB     00:01`,
    'Running transaction check', 'Transaction check succeeded.', 'Running transaction test', 'Transaction test succeeded.', 'Running transaction'])
  all.forEach((p, i) => chunks.push([`  Installing       : ${p}-${pkgInfo(p).ver}-${pkgInfo(p).rel}.x86_64    ${i + 1}/${all.length}`]))
  all.forEach((p, i) => chunks.push([`  Verifying        : ${p}-${pkgInfo(p).ver}-${pkgInfo(p).rel}.x86_64    ${i + 1}/${all.length}`]))
  chunks.push(['', 'Installed:', ...all.map(p => `  ${p}-${pkgInfo(p).ver}-${pkgInfo(p).rel}.x86_64`), '', 'Complete!'])
  return chunks
}

// apt: the resolution block shown BEFORE the "Do you want to continue? [Y/n]" prompt.
function aptResolveLines(pkgs, action = 'install') {
  const lines = ['Reading package lists... Done', 'Building dependency tree... Done', 'Reading state information... Done']
  if (action === 'remove' || action === 'purge') {
    lines.push('The following packages will be REMOVED:', '  ' + pkgs.join(' '), '',
      `0 upgraded, 0 newly installed, ${pkgs.length} to remove and 0 not upgraded.`,
      `After this operation, ${(pkgs.length * 1.4).toFixed(1)} MB disk space will be freed.`)
    return lines
  }
  const deps = []
  pkgs.forEach(p => pkgInfo(p).deps.forEach(d => deps.push(d)))
  if (deps.length) lines.push('The following additional packages will be installed:', '  ' + deps.join(' '))
  lines.push('The following NEW packages will be installed:', '  ' + [...pkgs, ...deps].join(' '), '',
    `0 upgraded, ${pkgs.length + deps.length} newly installed, 0 to remove and 0 not upgraded.`,
    `Need to get ${((pkgs.length + deps.length) * 1.1).toFixed(1)} MB of archives.`,
    `After this operation, ${((pkgs.length + deps.length) * 4.2).toFixed(1)} MB of additional disk space will be used.`)
  return lines
}

// apt: streamed Get/Unpacking/Setting up phases (shown AFTER 'Y').
function aptProgressChunks(pkgs, action = 'install') {
  const all = []
  pkgs.forEach(p => { all.push(p); pkgInfo(p).deps.forEach(d => all.push(d)) })
  if (action === 'remove' || action === 'purge') {
    const chunks = [['(Reading database ... 184221 files and directories currently installed.)']]
    pkgs.forEach(p => chunks.push([`Removing ${p} (${pkgInfo(p).ver.replace(/^[0-9]+:/, '')}-1ubuntu1) ...`]))
    chunks.push(['Processing triggers for man-db (2.10.2-1) ...'])
    return chunks
  }
  const chunks = []
  all.forEach((p, i) => chunks.push([`Get:${i + 1} http://archive.ubuntu.com/ubuntu jammy/main amd64 ${p} amd64 ${pkgInfo(p).ver.replace(/^[0-9]+:/, '')}-1ubuntu1 [${pkgInfo(p).sizeK} kB]`]))
  chunks.push([`Fetched ${all.reduce((s, p) => s + pkgInfo(p).sizeK, 0)} kB in 1s (${all.reduce((s, p) => s + pkgInfo(p).sizeK, 0)} kB/s)`,
    '(Reading database ... 184221 files and directories currently installed.)'])
  all.forEach((p, i) => chunks.push([`Selecting previously unselected package ${p}.`, `Unpacking ${p} (${pkgInfo(p).ver.replace(/^[0-9]+:/, '')}-1ubuntu1) ...`]))
  all.forEach(p => chunks.push([`Setting up ${p} (${pkgInfo(p).ver.replace(/^[0-9]+:/, '')}-1ubuntu1) ...`]))
  chunks.push(['Processing triggers for man-db (2.10.2-1) ...', 'Processing triggers for libc-bin (2.35-0ubuntu3) ...'])
  return chunks
}

export function createLinuxShell(vm, opts = {}) {
  const vmRef = { current: vm }
  const family = guestOsFamily(vmRef.current)
  const isRhel = family === 'rhel'
  const kernel = isRhel ? '5.14.0-362.8.1.el9_3.x86_64' : '5.15.0-91-generic'
  const hostname = vm?.hostname || vm?.name || (isRhel ? 'rhel-server-01' : 'ubuntu-server-01')
  const ip = vm?.ip || '10.20.30.41'
  const gw = ip.split('.').slice(0, 3).join('.') + '.1'
  const diskGb = vm?.disk_gb || 40
  const memMb = vm?.memory_mb || 4096
  const cpu = vm?.cpu || 2

  const shared = getOrCreateGuestShared(vm)
  const { vfs, services, pkgs } = shared
  const lvm = shared.lvm || (shared.lvm = createLvmState(diskGb))
  let selinuxMode = shared.selinuxMode

  const sessionUser = opts.user || 'root'
  let home = sessionUser === 'root' ? '/root' : `/home/${sessionUser}`
  const cwd = { path: home }
  const env = {
    USER: sessionUser,
    LOGNAME: sessionUser,
    HOME: home,
    SHELL: '/bin/bash',
    PATH: '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    LANG: 'en_US.UTF-8',
    TERM: 'xterm-256color',
    PWD: home,
    HOSTNAME: hostname,
    EDITOR: 'vim',
    VISUAL: 'vim',
    HISTSIZE: '1000',
    HISTFILESIZE: '2000',
  }
  const aliases = {
    ll: 'ls -alF',
    la: 'ls -A',
    l: 'ls -CF',
    grep: 'grep --color=auto',
    fgrep: 'fgrep --color=auto',
    egrep: 'egrep --color=auto',
  }
  const history = []
  let nextPid = 19000

  const prompt = () => {
    const shortHost = hostname.split('.')[0]
    const shortPath = cwd.path === env.HOME ? '~' : cwd.path
    const userPrefix = env.USER === 'root' ? 'root' : env.USER
    return env.USER === 'root'
      ? `[root@${shortHost} ${shortPath === '~' ? '~' : basename(shortPath)}]# `
      : `${userPrefix}@${shortHost}:${cwd.path}$ `
  }
  const abs = (p) => {
    if (!p) return cwd.path
    let expanded = p
    if (expanded.startsWith('~')) expanded = expanded.replace(/^~(?=\/|$)/, env.HOME)
    return normalizePath(cwd.path, expanded)
  }

  // Real stateful git against this guest's VFS (init/clone/commit/branch/merge…).
  const gitSim = createGitSim({ vfs, cwd, abs, username: sessionUser })

  const parsePasswd = () => {
    const node = vfs.resolveNode('/etc/passwd')
    if (!node || node.type !== 'file') return []
    return (node.content || '').split('\n').filter(Boolean).map((line) => {
      const p = line.split(':')
      if (p.length < 7) return null
      return { name: p[0], uid: +p[2], gid: +p[3], home: p[5], shell: p[6] }
    }).filter(Boolean)
  }

  const lookupUser = (name) => parsePasswd().find((u) => u.name === name)

  const switchUser = (user) => {
    const uhome = user === 'root' ? '/root' : `/home/${user}`
    env.USER = user
    env.LOGNAME = user
    env.HOME = uhome
    home = uhome
    cwd.path = uhome
    env.PWD = uhome
  }

  const getStatus = () => {
    const usedGb = Math.max(1, Math.round(diskGb * 0.21))
    const memUsedGb = (memMb * 0.2 / 1024).toFixed(1)
    const memTotalGb = (memMb / 1024).toFixed(1)
    const uptimeMs = Date.now() - shared.bootEpoch
    return {
      hostname: hostname.split('.')[0],
      user: env.USER,
      cwd: cwd.path,
      load: '0.23 0.18 0.12',
      mem: `${memUsedGb}G/${memTotalGb}G`,
      disk: `${usedGb}G/${diskGb}G`,
      uptime: formatUptime(uptimeMs),
      clock: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      os: isRhel ? 'RHEL 9.3' : 'Ubuntu 22.04',
      sessionId: opts.sessionId || 'default',
    }
  }

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

  const applyPipeStage = (stage, inputLines) => {
    const stageParts = stage.trim().split(/\s+/).filter(Boolean)
    const pcmd = (stageParts[0] || '').toLowerCase()
    const pargs = stageParts.slice(1)
    const ppos = pargs.filter(a => !a.startsWith('-'))
    const joined = inputLines.join('\n')
    if (!pcmd) return inputLines
    if (pcmd === 'grep' || pcmd === 'egrep' || pcmd === 'fgrep') {
      const ignore = pargs.includes('-i')
      const invert = pargs.includes('-v')
      const count = pargs.includes('-c')
      const numbered = pargs.includes('-n')
      const pat = ppos[0]?.replace(/^["']|["']$/g, '') || ''
      let re
      try { re = new RegExp(pat, ignore ? 'i' : '') } catch { re = new RegExp(pat.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), ignore ? 'i' : '') }
      const filtered = inputLines.filter(l => re.test(l) !== invert)
      if (count) return [String(filtered.length)]
      return numbered ? filtered.map((l, i) => `${i + 1}:${l}`) : filtered
    }
    if (pcmd === 'awk' || pcmd === 'gawk') {
      const script = pargs.join(' ')
      const fieldSep = (script.match(/-F\s*['"]?([^'"\s]+)['"]?/) || [])[1] || /\s+/
      const printMatch = script.match(/print\s+\\?\$?([0-9]+)/)
      const wantLineNo = /NR/.test(script)
      const idx = printMatch ? Math.max(0, parseInt(printMatch[1], 10) - 1) : null
      return inputLines.map((l, i) => {
        const cols = typeof fieldSep === 'string' ? l.split(fieldSep) : l.trim().split(fieldSep)
        if (wantLineNo && idx !== null) return `${i + 1}: ${cols[idx] || ''}`
        if (idx !== null) return cols[idx] || ''
        return l
      }).filter(Boolean)
    }
    if (pcmd === 'cut') {
      const dIdx = pargs.indexOf('-d')
      const fIdx = pargs.indexOf('-f')
      const cIdx = pargs.indexOf('-c')
      const delim = dIdx >= 0 ? pargs[dIdx + 1]?.replace(/^["']|["']$/g, '') : '\t'
      if (fIdx >= 0) {
        const field = Math.max(1, parseInt(pargs[fIdx + 1], 10) || 1) - 1
        return inputLines.map(l => (l.split(delim)[field] || ''))
      }
      if (cIdx >= 0) {
        const n = Math.max(1, parseInt(pargs[cIdx + 1], 10) || 1)
        return inputLines.map(l => l.slice(n - 1, n))
      }
      return inputLines
    }
    if (pcmd === 'head' || pcmd === 'tail') {
      const nIdx = pargs.indexOf('-n')
      const inline = pargs.find(a => /^-\d+$/.test(a))
      const count = nIdx >= 0 ? parseInt(pargs[nIdx + 1], 10) : inline ? parseInt(inline.slice(1), 10) : 10
      return pcmd === 'head' ? inputLines.slice(0, count) : inputLines.slice(-count)
    }
    if (pcmd === 'wc') {
      if (pargs.includes('-l')) return [String(inputLines.filter(Boolean).length)]
      if (pargs.includes('-w')) return [String(joined.trim() ? joined.trim().split(/\s+/).length : 0)]
      if (pargs.includes('-c')) return [String(joined.length)]
      return [`${String(inputLines.length).padStart(7)} ${String(joined.trim() ? joined.trim().split(/\s+/).length : 0).padStart(7)} ${String(joined.length).padStart(7)}`]
    }
    if (pcmd === 'sort') return [...inputLines].sort()
    if (pcmd === 'uniq') return inputLines.filter((l, i) => l !== inputLines[i - 1])
    if (pcmd === 'tr') {
      if (pargs.includes('[:lower:]') && pargs.includes('[:upper:]')) return [joined.toUpperCase()]
      if (pargs[0] === '-d') return [joined.replace(new RegExp(`[${(pargs[1] || '').replace(/^["']|["']$/g, '')}]`, 'g'), '')]
      return inputLines
    }
    if (pcmd === 'sed') {
      const script = pargs.find(a => /^['"]?s[/:|]/.test(a) || /^['"]?\/.*\/d['"]?$/.test(a))?.replace(/^["']|["']$/g, '') || ''
      if (/^s(.).*\1.*\1/.test(script)) {
        const sep = script[1]
        const [, oldVal = '', newVal = '', flags = ''] = script.split(sep)
        const re = new RegExp(oldVal, flags.includes('g') ? 'g' : '')
        return inputLines.map(l => l.replace(re, newVal))
      }
      if (script === '/^#/d') return inputLines.filter(l => !l.trim().startsWith('#'))
      return inputLines
    }
    if (pcmd === 'tee') {
      const target = ppos[0]
      if (target) vfs.writeFile(abs(target), joined + (joined ? '\n' : ''))
      return inputLines
    }
    if (pcmd === 'xargs') return inputLines
    return inputLines
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

  // Value-aware parser for CLIs like kubectl/aws that use `-n ns`, `-o wide`,
  // `--region r`, `--key=value`. Returns cleaned positionals (flag values
  // removed) plus value/boolean lookups.
  const CLI_VALUE_FLAGS = new Set(['-n', '--namespace', '-o', '--output', '--region', '--name', '-f', '--filename', '--context', '--image', '--cluster'])
  const cliParse = (argv) => {
    const pos = []
    const fval = {}
    for (let i = 0; i < argv.length; i++) {
      const a = argv[i]
      if (a.startsWith('-')) {
        const eq = a.indexOf('=')
        if (eq !== -1) { fval[a.slice(0, eq)] = a.slice(eq + 1); continue }
        if (CLI_VALUE_FLAGS.has(a) && argv[i + 1] !== undefined) { fval[a] = argv[i + 1]; i++; continue }
        fval[a] = true
        continue
      }
      pos.push(a)
    }
    return {
      pos,
      fv: (...names) => { for (const n of names) if (fval[n] !== undefined) return fval[n]; return undefined },
      fhas: (n) => fval[n] !== undefined,
    }
  }

  const run = (raw, opts = {}) => {
    getOrCreateGuestShared(vmRef.current)
    const line = raw.trim()
    if (!line) return { lines: [''], prompt: prompt() }
    if (!opts.noHistory) history.push(line)

    // Handle redirection: cmd > file  /  cmd >> file
    let redirect = null
    let work = line
    const redirMatch = line.match(/\s(>>?)\s*(\S+)\s*$/)
    if (redirMatch) {
      redirect = { append: redirMatch[1] === '>>', path: redirMatch[2] }
      work = line.slice(0, redirMatch.index).trim()
    }

    const hasPipeline = /(^|[^|])\|([^|]|$)/.test(work)
    if ((/(^|\s)(&&|\|\|)(\s|$)/.test(work) || work.includes(';')) && !hasPipeline) {
      const tokens = work.split(/(\s+&&\s+|\s+\|\|\s+|\s*;\s*)/).filter(Boolean)
      let op = ';'
      let collected = []
      let lastHadError = false
      for (const token of tokens) {
        const trimmed = token.trim()
        if (trimmed === '&&' || trimmed === '||' || trimmed === ';') { op = trimmed; continue }
        const shouldRun = op === ';' || (op === '&&' && !lastHadError) || (op === '||' && lastHadError)
        if (!shouldRun) continue
        const res = run(trimmed, { noHistory: true })
        if (res.editor || res.confirm || res.stream || res.reboot || res.poweroff || res.exit || res.clear) return res
        collected = collected.concat(res.lines || [])
        lastHadError = (res.lines || []).some(l => /No such file|not found|failed|error/i.test(l))
      }
      if (redirect) {
        const target = abs(redirect.path)
        const node = vfs.resolveNode(target)
        const existing = node && node.type === 'file' ? node.content : ''
        const payload = collected.join('\n')
        vfs.writeFile(target, redirect.append ? existing + payload + '\n' : payload + (payload ? '\n' : ''))
        collected = ['']
      }
      return { lines: collected.length ? collected : [''], prompt: prompt() }
    }

    if (hasPipeline) {
      const stages = work.split('|').map(s => s.trim()).filter(Boolean)
      const first = run(stages[0], { noHistory: true })
      if (first.editor || first.confirm || first.stream || first.reboot || first.poweroff || first.exit || first.clear) return first
      let pipeOut = first.lines || ['']
      stages.slice(1).forEach(stage => { pipeOut = applyPipeStage(stage, pipeOut) })
      if (redirect) {
        const target = abs(redirect.path)
        const node = vfs.resolveNode(target)
        const existing = node && node.type === 'file' ? node.content : ''
        const payload = pipeOut.join('\n')
        vfs.writeFile(target, redirect.append ? existing + payload + '\n' : payload + (payload ? '\n' : ''))
        pipeOut = ['']
      }
      return { lines: pipeOut.length ? pipeOut : [''], prompt: prompt(), sideEffect: first.sideEffect }
    }

    const parts = work.split(/\s+/)
    const cmd = parts[0]
    const lc = cmd.toLowerCase()
    let args = parts.slice(1)
    if (!['awk', 'gawk', 'sed'].includes(lc)) {
      args = args.map(a => a.replace(/\$\{?(\w+)\}?/g, (m, k) => (env[k] !== undefined ? env[k] : m)))
    }
    const { flags, positional, has } = parseArgs(args)
    const out = []
    let sideEffect = null
    let editor = null

    const notFound = () => out.push(`bash: ${cmd}: command not found`)
    const emit = (s) => { if (Array.isArray(s)) out.push(...s); else String(s).split('\n').forEach(l => out.push(l)) }

    /* =================== file system =================== */
    if (!isRhel && ['dnf', 'yum', 'rpm', 'firewall-cmd'].includes(lc)) emit(`bash: ${cmd}: command not found`)
    else if (isRhel && ['apt', 'apt-get', 'apt-cache', 'dpkg', 'dpkg-query', 'ufw'].includes(lc)) emit(`bash: ${cmd}: command not found`)
    else if (lc === 'pwd') emit(cwd.path)
    else if (lc === 'cd') {
      const dest = abs(positional[0] || env.HOME)
      const node = vfs.resolveNode(dest)
      if (!node) emit(`bash: cd: ${positional[0]}: No such file or directory`)
      else if (node.type !== 'dir') emit(`bash: cd: ${positional[0]}: Not a directory`)
      else { cwd.path = dest; env.PWD = dest }
    }
    else if (lc === 'ls' || lc === 'll' || lc === 'dir' || lc === 'vdir') {
      const long = lc === 'll' || has('-l') || has('-la') || has('-al')
      const allF = has('-a') || has('-la') || has('-al') || has('-A')
      const netTarget = positional.find((t) => abs(t).replace(/\/+$/, '') === '/sys/class/net')
      if (netTarget) {
        const nicNames = ['lo', 'eth0', ...guestExtraNics(vm, shared).map((n) => n.name)]
        if (long) {
          nicNames.forEach((n) => emit(`lrwxrwxrwx 1 root root 0 ${nowStamp()} ${n} -> ../../devices/virtual/net/${n}`))
        } else {
          emit(nicNames.join('  '))
        }
      } else {
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
    else if (lc.endsWith('rescan-scsi-bus.sh') || lc === 'rescan-scsi-bus.sh') {
      const effect = triggerGuestRescan(vm, shared)
      if (effect) sideEffect = effect
      emit([
        'Rescanning SCSI bus...',
        '0 host adapters found',
        'Scanning for new SCSI devices...',
        'Added scsi device(s)...',
      ])
    }
    else if (lc === 'echo') {
      // guest disk rescan side-effect: echo "- - -" > /sys/class/scsi_host/.../scan
      if (line.includes('scsi_host') && line.includes('scan')) {
        const effect = triggerGuestRescan(vm, shared)
        if (effect) sideEffect = effect
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
      const rootSize = Math.max(1, Math.round(lvm.rootFsGb || diskGb))
      const used = Math.max(1, Math.round(rootSize * 0.31))
      const avail = Math.max(0, rootSize - used)
      if (h) emit([
        'Filesystem      Size  Used Avail Use% Mounted on',
        `/dev/mapper/rootvg-root  ${rootSize}G  ${used}G   ${avail}G  31% /`,
        'tmpfs           ' + Math.round(memMb / 2) + 'M     0  ' + Math.round(memMb / 2) + 'M   0% /dev/shm',
        ...(shared.diskMounted && guestExtraDisks(vm, shared).length ? (() => {
          const d = guestExtraDisks(vm, shared)[0]
          const gb = d.capacity_gb || 20
          return [`/dev/sd${d.letter}1         ${gb}G  1.2G   ${gb - 1}G   6% /data`]
        })() : []),
      ])
      else emit([
        'Filesystem     1K-blocks    Used Available Use% Mounted on',
        `/dev/mapper/rootvg-root ${rootSize * 1024 * 1024} ${used * 1024 * 1024} ${avail * 1024 * 1024}  31% /`,
        ...(shared.diskMounted && guestExtraDisks(vm, shared).length ? (() => {
          const d = guestExtraDisks(vm, shared)[0]
          const gb = d.capacity_gb || 20
          return [`/dev/sd${d.letter}1       ${gb * 1024 * 1024} 1258291  ${(gb - 1) * 1024 * 1024}   6% /data`]
        })() : []),
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
    else if (lc === 'whoami') emit(env.USER)
    else if (lc === 'id') {
      const target = positional[0] || env.USER
      const u = lookupUser(target)
      if (!u) emit(`id: '${target}': no such user`)
      else {
        const groups = u.name === 'root' ? '0(root)' : `${u.gid}(${u.name})${isRhel ? ',10(wheel)' : ',27(sudo)'}`
        emit(`uid=${u.uid}(${u.name}) gid=${u.gid}(${u.name}) groups=${groups}`)
      }
    }
    else if (lc === 'groups') {
      const target = positional[0] || env.USER
      const u = lookupUser(target)
      if (!u) emit(`groups: '${target}': no such user`)
      else emit(u.name === 'root' ? 'root : root' : `${u.name} : ${u.name} ${isRhel ? 'wheel' : 'sudo'} adm`)
    }
    else if (lc === 'getent') {
      const db = positional[0]
      const key = positional[1]
      if (db === 'passwd') {
        const users = key ? parsePasswd().filter((u) => u.name === key) : parsePasswd()
        if (key && !users.length) { /* empty output, exit 2 handled below */ }
        else users.forEach((u) => emit(`${u.name}:x:${u.uid}:${u.gid}::${u.home}:${u.shell}`))
      } else if (db === 'group') {
        const gnode = vfs.resolveNode('/etc/group')
        const lines = (gnode?.content || '').split('\n').filter(Boolean)
        const filtered = key ? lines.filter((l) => l.startsWith(`${key}:`)) : lines
        filtered.forEach((l) => emit(l))
      } else emit(`getent: unknown database '${db}'`)
    }
    else if (lc === 'hostname') {
      if (positional[0]) { emit('') } else emit(has('-f') || has('--fqdn') ? `${hostname}.lab.fixitlab.local` : hostname.split('.')[0])
    }
    else if (lc === 'hostnamectl') emit([
      `   Static hostname: ${hostname}`,
      `         Icon name: computer-vm`,
      `           Chassis: vm`,
      `        Machine ID: a1b2c3d4e5f60718293a4b5c6d7e8f90`,
      `  Operating System: ${isRhel ? 'Red Hat Enterprise Linux 9.3 (Plow)' : 'Ubuntu 22.04.4 LTS'}`,
      `            Kernel: Linux ${kernel}`,
      `      Architecture: x86-64`,
    ])
    else if (lc === 'uname') {
      if (has('-a')) emit(`Linux ${hostname.split('.')[0]} ${kernel} #101 SMP PREEMPT_DYNAMIC Tue Nov 14 18:10:51 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux`)
      else if (has('-r')) emit(kernel)
      else if (has('-n')) emit(hostname.split('.')[0])
      else if (has('-m')) emit('x86_64')
      else emit('Linux')
    }
    else if (lc === 'arch') emit('x86_64')
    else if (lc === 'uptime') {
      const ms = Date.now() - (shared.bootEpoch || Date.now())
      const sec = Math.floor(ms / 1000)
      const days = Math.floor(sec / 86400)
      const hrs = Math.floor((sec % 86400) / 3600)
      const mins = Math.floor((sec % 3600) / 60)
      const load = '0.08, 0.12, 0.09'
      const t = new Date().toTimeString().slice(0, 8)
      if (has('-p')) emit(`up ${days} days, ${hrs} hours, ${mins} minutes`)
      else emit(` ${t} up ${days} days, ${hrs}:${String(mins).padStart(2, '0')},  1 user,  load average: ${load}`)
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
      const wide = has('-e') || has('-f') || has('-a') || has('-u') || has('-x') || has('-A') || positional.includes('aux') || positional.includes('ax')
      if (wide && (has('-f') || positional.includes('ef'))) {
        emit([
          'UID          PID    PPID  C STIME TTY          TIME CMD',
          'root           1       0  0 Jun04 ?        00:00:14 /usr/lib/systemd/systemd --system',
          'root         890       1  0 Jun04 ?        00:00:01 /usr/sbin/sshd -D',
          'root        1201     890  0 08:01 ?        00:00:00 sshd: root@pts/0',
          'mysql       1502       1  0 Jun04 ?        00:01:42 /usr/sbin/mysqld',
          ...(services.nginx.active === 'active' ? ['nginx       3300       1  0 Jun04 ?        00:00:02 nginx: master process /usr/sbin/nginx'] : []),
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
          ...(services.nginx.active === 'active' ? ['nginx       3300  0.1  0.2  55240  8800 ?        Ss   Jun04   0:02 nginx: master process /usr/sbin/nginx'] : []),
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
      const extraNics = guestExtraNics(vm, shared)
      if (sub === 'addr' || sub === 'a' || sub === 'address' || !sub) {
        const lines = [
          '1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000',
          '    inet 127.0.0.1/8 scope host lo',
          '2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000',
          '    link/ether 00:50:56:a1:b2:c3 brd ff:ff:ff:ff:ff:ff',
          `    inet ${ip}/24 brd ${ip.split('.').slice(0, 3).join('.')}.255 scope global noprefixroute eth0`,
        ]
        extraNics.forEach((nic, i) => {
          const oct = 20 + i
          lines.push(`${3 + i}: ${nic.name}: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000`)
          lines.push(`    link/ether ${nic.mac || '00:50:56:a1:c3:d4'} brd ff:ff:ff:ff:ff:ff`)
          lines.push(`    inet ${ip.split('.').slice(0, 3).join('.')}.${oct}/24 brd ${ip.split('.').slice(0, 3).join('.')}.255 scope global noprefixroute ${nic.name}`)
        })
        emit(lines)
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
      if (sub === 'reboot') return { lines: ['Rebooting…'], prompt: prompt(), reboot: { single: false } }
      else if (sub === 'poweroff' || sub === 'halt') return { lines: ['Powering off…'], prompt: prompt(), poweroff: true }
      else if (sub === 'rescue' || sub === 'emergency') return { lines: [`Reaching ${sub}.target…`], prompt: prompt(), reboot: { single: true } }
      else if (!sub || sub === 'list-units') {
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
        `[    0.000000] Linux version ${kernel} (build@fixitlab) #101 SMP`,
        `[    0.000000] Command line: BOOT_IMAGE=/boot/vmlinuz-${kernel} root=UUID=8f3b... ro quiet`,
        '[    1.234567] systemd[1]: Reached target Multi-User System.',
        '[    2.100000] sd 2:0:0:0: [sda] Attached SCSI disk',
        ...guestExtraDisks(vm, shared).map((d) =>
          `[ 1284.55] sd 2:0:${d.scsi_unit}:0: [sd${d.letter}] Attached SCSI disk`),
        '[    8.442000] IPv6: ADDRCONF(NETDEV_CHANGE): eth0: link becomes ready',
      ])
    }

    /* =================== packages =================== */
    else if (lc === 'dnf' || lc === 'yum') {
      const sub = positional[0]
      const reqPkgs = positional.slice(1).filter(p => !p.startsWith('-'))
      const pkg = reqPkgs[0] || 'package'
      if (sub === 'install' || sub === 'reinstall' || sub === 'remove' || sub === 'erase' || sub === 'upgrade' || sub === 'update') {
        const action = (sub === 'remove' || sub === 'erase') ? 'remove' : 'install'
        const targets = reqPkgs.length ? reqPkgs : [pkg]
        // remove: only operate on packages that are actually installed
        if (action === 'remove') {
          const present = targets.filter(p => pkgs.has(p))
          if (!present.length) {
            emit(['No match for argument: ' + targets.join(' '), 'No packages marked for removal.'])
          } else {
            const resolve = dnfResolveLines(lc, present, 'remove')
            const chunks = dnfProgressChunks(present, 'remove')
            const commit = () => pkgs.remove(present)
            if (has('-y') || has('--assumeyes')) return { lines: resolve, prompt: prompt(), stream: { chunks, doneLines: [], commit } }
            return { lines: resolve, prompt: prompt(), confirm: { promptText: 'Is this ok [y/N]: ', defaultYes: false, onYesStream: { chunks, commit }, onNoLines: ['Operation aborted.'] } }
          }
        }
        // bare `dnf update` with no package and nothing to do
        else if ((sub === 'update' || sub === 'upgrade') && !reqPkgs.length) {
          emit(['Last metadata expiration check: 0:05:01 ago.', 'Dependencies resolved.', 'Nothing to do.', 'Complete!'])
        }
        // already-installed (plain install, no upgrade) short-circuits like real dnf
        else if (sub === 'install' && targets.every(p => pkgs.has(p))) {
          emit(['Last metadata expiration check: 0:05:01 ago.', ...targets.map(p => `Package ${pkgs.rpmNvra(p)} is already installed.`), 'Dependencies resolved.', 'Nothing to do.', 'Complete!'])
        } else {
          const resolve = dnfResolveLines(lc, targets, 'install')
          const chunks = dnfProgressChunks(targets, 'install')
          const commit = () => pkgs.install(targets)
          if (has('-y') || has('--assumeyes')) {
            // proceed immediately, but still stream the progress
            return { lines: resolve, prompt: prompt(), stream: { chunks, doneLines: [], commit } }
          }
          // ask first; the console renders the prompt and waits for y/N
          return {
            lines: resolve,
            prompt: prompt(),
            confirm: {
              promptText: 'Is this ok [y/N]: ',
              defaultYes: false,
              onYesStream: { chunks, commit },
              onNoLines: ['Operation aborted.'],
            },
          }
        }
      }
      else if (sub === 'list') {
        const which = positional[1]
        if (which === 'installed' || !which) emit(['Installed Packages', ...pkgs.dnfRows()])
        else if (which === 'available') emit(['Available Packages', ...Object.keys(PKG_CATALOG).filter(p => !pkgs.has(p)).sort().map(p => { const r = pkgRecord(p, isRhel); return `${(r.name + '.' + r.arch).padEnd(34)}${(r.ver + '-' + r.rel).padEnd(24)}${r.repo}` })])
        else emit(['Installed Packages', ...pkgs.dnfRows().filter(r => r.startsWith(which))])
      }
      else if (sub === 'search') emit([`========== Name Matched: ${pkg} ==========`, `${pkg}.x86_64 : The ${pkg} package`])
      else if (sub === 'info') {
        const inst = pkgs.has(pkg)
        const r = pkgs.get(pkg) || pkgRecord(pkg, isRhel)
        emit([inst ? 'Installed Packages' : 'Available Packages', `Name         : ${r.name}`, `Version      : ${r.ver}`, `Release      : ${r.rel}`, `Architecture : ${r.arch}`, `Repository   : ${inst ? '@' + (r.repo || 'anaconda') : (r.repo || 'rhel-9-appstream')}`, `Summary      : ${r.name} package`])
      }
      else if (sub === 'provides' || sub === 'whatprovides') emit([`${pkg}-${pkgInfo(pkg).ver}-${pkgInfo(pkg).rel}.x86_64 : The ${pkg} package`, `Repo        : ${pkgs.has(pkg) ? '@System' : 'rhel-9-appstream'}`])
      else if (sub === 'repolist') emit(['repo id            repo name', 'rhel-9-baseos      RHEL 9 BaseOS', 'rhel-9-appstream   RHEL 9 AppStream', 'epel               Extra Packages for Enterprise Linux 9'])
      else if (sub === 'clean') emit('0 files removed')
      else if (sub === 'makecache') emit('Metadata cache created.')
      else if (sub === 'check-update') emit(['Last metadata expiration check: 0:05:01 ago.', ''])
      else if (sub === 'history') emit(['ID     | Command line             | Date and time    | Action(s)      | Altered', '-------------------------------------------------------------------------------', '     1 | install                  | ' + new Date().toISOString().slice(0, 16).replace('T', ' ') + ' | Install        |   ' + pkgs.db.size])
      else emit('Loaded plugins: builddep, changelog, config-manager')
    }
    else if (lc === 'apt' || lc === 'apt-get') {
      const sub = positional[0]
      const reqPkgs = positional.slice(1).filter(p => !p.startsWith('-'))
      const pkg = reqPkgs[0] || 'package'
      if (sub === 'update') emit(['Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease', 'Get:2 http://security.ubuntu.com/ubuntu jammy-security InRelease', 'Reading package lists... Done'])
      else if (sub === 'install' || sub === 'remove' || sub === 'purge' || sub === 'reinstall') {
        const action = (sub === 'remove' || sub === 'purge') ? 'remove' : 'install'
        const targets = reqPkgs.length ? reqPkgs : [pkg]
        if (action === 'remove') {
          const present = targets.filter(p => pkgs.has(p))
          if (!present.length) {
            emit(['Reading package lists... Done', 'Building dependency tree... Done', 'Reading state information... Done', ...targets.map(p => `Package '${p}' is not installed, so not removed`), '0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.'])
          } else {
            const resolve = aptResolveLines(present, sub === 'purge' ? 'purge' : 'remove')
            const chunks = aptProgressChunks(present, sub === 'purge' ? 'purge' : 'remove')
            const commit = () => pkgs.remove(present)
            if (has('-y') || has('--yes') || has('--assume-yes')) return { lines: resolve, prompt: prompt(), stream: { chunks, doneLines: [], commit } }
            return { lines: resolve, prompt: prompt(), confirm: { promptText: 'Do you want to continue? [Y/n] ', defaultYes: true, onYesStream: { chunks, commit }, onNoLines: ['Abort.'] } }
          }
        }
        else if (sub === 'install' && targets.every(p => pkgs.has(p))) {
          emit(['Reading package lists... Done', 'Building dependency tree... Done', 'Reading state information... Done', ...targets.map(p => `${p} is already the newest version (${pkgs.get(p).ver}).`), '0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.'])
        } else {
          const resolve = aptResolveLines(targets, 'install')
          const chunks = aptProgressChunks(targets, 'install')
          const commit = () => pkgs.install(targets)
          if (has('-y') || has('--yes') || has('--assume-yes')) {
            return { lines: resolve, prompt: prompt(), stream: { chunks, doneLines: [], commit } }
          }
          return {
            lines: resolve,
            prompt: prompt(),
            confirm: {
              promptText: 'Do you want to continue? [Y/n] ',
              defaultYes: true,
              onYesStream: { chunks, commit },
              onNoLines: ['Abort.'],
            },
          }
        }
      }
      else if (sub === 'upgrade' || sub === 'dist-upgrade' || sub === 'full-upgrade') emit(['Reading package lists... Done', 'Calculating upgrade... Done', '0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.'])
      else if (sub === 'list') {
        if (has('--installed')) emit(['Listing... Done', ...[...pkgs.db.values()].sort((a, b) => a.name.localeCompare(b.name)).map(r => `${r.name}/jammy,now ${r.ver}${r.rel ? '-' + r.rel : ''} ${r.arch} [installed]`)])
        else emit(['Listing... Done', `${pkg}/jammy ${pkgInfo(pkg).ver.replace(/^[0-9]+:/, '')} amd64${pkgs.has(pkg) ? ' [installed]' : ''}`])
      }
      else if (sub === 'search') emit([`${pkg}/jammy 1.20.1 amd64`, `  ${pkg} package`])
      else if (sub === 'show') { const r = pkgs.get(pkg) || pkgRecord(pkg, false); emit([`Package: ${r.name}`, `Version: ${r.ver}${r.rel ? '-' + r.rel : ''}`, `Priority: optional`, `Architecture: ${r.arch}`]) }
      else emit('E: Invalid operation ' + (sub || ''))
    }
    else if (lc === 'apt-cache') {
      if (positional[0] === 'policy') { const r = pkgs.get(positional[1]); emit([`${positional[1] || 'package'}:`, `  Installed: ${r ? r.ver + (r.rel ? '-' + r.rel : '') : '(none)'}`, `  Candidate: ${pkgInfo(positional[1] || '').ver.replace(/^[0-9]+:/, '')}`]) }
      else emit(`${positional[1] || 'package'} - simulated package description`)
    }
    else if (lc === 'rpm') {
      // -qa / -q -a : list every installed package (reads the live DB)
      if (has('-qa') || (has('-q') && has('-a'))) {
        const pat = positional[0]
        const list = pkgs.rpmList()
        emit(pat ? list.filter(n => n.toLowerCase().includes(pat.toLowerCase())) : list)
      }
      // -q <pkg> [...] : is it installed? (real rpm exit/wording)
      else if (has('-q') || has('--query')) {
        const names = positional.length ? positional : ['package']
        names.forEach(n => { const nvra = pkgs.rpmNvra(n); emit(nvra || `package ${n} is not installed`) })
      }
      else if (has('-V') || has('--verify')) emit('')
      else if (has('-i') || has('-U') || has('--install') || has('--upgrade')) {
        // rpm -i/-U <file.rpm>: derive the package name from the filename and install it
        const file = positional.find(a => a.endsWith('.rpm')) || positional[0] || ''
        const name = basename(file).replace(/\.rpm$/, '').replace(/-[0-9].*$/, '') || 'package'
        pkgs.install([name])
        emit('')
      }
      else if (has('-e') || has('--erase')) {
        const names = positional.length ? positional : []
        const removed = pkgs.remove(names)
        if (!removed && names.length) emit(`error: package ${names[0]} is not installed`)
        else emit('')
      }
      else emit('RPM version 4.16.1.3')
    }
    else if (lc === 'dpkg' || lc === 'dpkg-query') {
      if (has('-l') || has('--list')) {
        const pat = positional[0]
        let rows = pkgs.dpkgRows()
        if (pat) rows = rows.filter(r => r.toLowerCase().includes(pat.toLowerCase()))
        emit(['Desired=Unknown/Install/Remove/Purge/Hold', '| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend', '|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)', '||/ Name                         Version                  Architecture Description', '+++-============================-========================-============-=================================', ...rows])
      }
      else if (has('-s') || has('--status')) {
        const r = pkgs.get(positional[0])
        if (r) emit([`Package: ${r.name}`, 'Status: install ok installed', `Version: ${r.ver}${r.rel ? '-' + r.rel : ''}`, `Architecture: ${r.arch}`])
        else emit(`dpkg-query: package '${positional[0] || ''}' is not installed and no information is available`)
      }
      else if (has('-L')) emit(pkgs.has(positional[0]) ? ['/.', '/usr', '/usr/bin', '/usr/bin/' + (positional[0] || 'pkg')] : [`dpkg-query: package '${positional[0] || ''}' is not installed`])
      else if (has('-i') || has('--install')) { const name = basename(positional.find(a => a.endsWith('.deb')) || positional[0] || '').replace(/_.*$/, '') || 'package'; pkgs.install([name]); emit([`Selecting previously unselected package ${name}.`, `Unpacking ${name} ...`, `Setting up ${name} ...`]) }
      else if (has('-r') || has('-P') || has('--remove') || has('--purge')) { const removed = pkgs.remove(positional); emit(removed ? [`Removing ${positional[0]} ...`] : `dpkg: warning: ignoring request to remove ${positional[0] || 'package'} which isn't installed`) }
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
    else if (lc === 'su') {
      const target = positional[0] || 'root'
      const uhome = target === 'root' ? '/root' : `/home/${target}`
      const node = vfs.resolveNode(uhome)
      if (!node && target !== 'root') emit(`su: user ${target} does not exist`)
      else {
        switchUser(target)
        emit('')
      }
    }
    else if (lc === 'sudo') {
      // strip leading sudo options (-i, -u user, -s, -E) then run the rest verbatim (flags preserved)
      let rest = args.slice()
      while (rest.length && rest[0].startsWith('-')) { if (rest[0] === '-u') rest = rest.slice(2); else rest = rest.slice(1) }
      const cmdline = rest.join(' ')
      if (!cmdline) emit('usage: sudo command')
      else { const r = run(cmdline); return { ...r, prompt: prompt() } }
    }
    else if (lc === 'last' || lc === 'lastlog' || lc === 'who' || lc === 'w') {
      if (lc === 'w') emit(['14:22:01 up 14 days,  3:22,  1 user,  load average: 0.08, 0.12, 0.09', 'USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT', `${env.USER.padEnd(8)} pts/0    ${gw}      08:01    0.00s  0.04s  0.00s w`])
      else if (lc === 'who') emit(`${env.USER.padEnd(8)} pts/0        ${new Date().toISOString().slice(0, 16).replace('T', ' ')} (${gw})`)
      else emit([`${env.USER.padEnd(8)} pts/0        ${gw}    ${nowStamp()}   still logged in`, '', `wtmp begins ${nowStamp()}`])
    }

    /* =================== storage =================== */
    else if (lc === 'lsblk') {
      const extras = guestExtraDisks(vm, shared)
      const extraLines = extras.flatMap((d) => {
        const letter = d.letter || 'b'
        const gb = d.capacity_gb || 20
        const maj = 8 + (letter.charCodeAt(0) - 97) * 16
        return [
          `sd${letter}      ${maj}:0    0   ${gb}G  0 disk`,
          ...(shared.diskFormatted && !lvm.extraPvInVg ? [`└─sd${letter}1   ${maj}:1    0   ${gb}G  0 part${shared.diskMounted ? ' /data' : ''}`] : []),
          ...(lvm.extraPvInVg && lvm.extraPvDevice?.includes(`sd${letter}`) ? [`└─rootvg-root 253:0 0 ${Math.round(lvm.rootLvGb)}G  0 lvm  /`] : []),
        ]
      })
      emit([
        'NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS',
        `sda      8:0    0   ${diskGb}G  0 disk`,
        `├─sda1   8:1    0    1G  0 part /boot`,
        `└─sda2   8:2    0  ${diskGb - 1}G  0 part`,
        `  ├─rootvg-root 253:0 0 ${Math.round(lvm.rootLvGb)}G  0 lvm  /`,
        `  └─rootvg-swap 253:1 0  ${lvm.swapGb}G  0 lvm  [SWAP]`,
        ...extraLines,
        'sr0     11:0    1 1024M  0 rom',
      ])
    }
    else if (lc === 'blkid') {
      const extras = guestExtraDisks(vm, shared)
      emit([
        '/dev/sda1: UUID="1a2b3c4d-5e6f-7081-92a3-b4c5d6e7f809" TYPE="xfs" PARTUUID="000a1b2c-01"',
        '/dev/sda2: UUID="8f3b2c1a-0e4d-4c6b-9a7f-1d2e3f4a5b6c" TYPE="xfs" PARTUUID="000a1b2c-02"',
        ...(lvm.extraPvDevice ? [`${lvm.extraPvDevice}: UUID="lvm-pv-deadc0de" TYPE="LVM2_member"`] : []),
        ...(shared.diskFormatted && extras.length && !lvm.extraPvDevice
          ? [`${extraDiskPartPath(extras[0])}: UUID="deadc0de-1234-5678-9abc-def012345678" TYPE="ext4"`]
          : []),
      ])
    }
    else if (lc === 'fdisk' || lc === 'parted' || lc === 'sfdisk' || lc === 'gdisk') {
      if (has('-l') || lc === 'parted') {
        const extras = guestExtraDisks(vm, shared)
        emit([
          `Disk /dev/sda: ${diskGb} GiB, ${diskGb * 1024 * 1024 * 1024} bytes, ${diskGb * 2 * 1024 * 1024} sectors`,
          'Units: sectors of 1 * 512 = 512 bytes',
          'Device     Boot   Start      End  Sectors Size Type',
          '/dev/sda1  *       2048  2099199  2097152   1G Linux filesystem',
          `/dev/sda2       2099200 ${diskGb * 2 * 1024 * 1024} ... ${diskGb - 1}G Linux filesystem`,
          ...extras.flatMap((d) => {
            const gb = d.capacity_gb || 20
            const dev = extraDiskPath(d)
            return ['', `Disk ${dev}: ${gb} GiB, ${gb * 1024 * 1024 * 1024} bytes`,
              shared.diskFormatted
                ? `${extraDiskPartPath(d)}       2048  41943039  41940992  ${gb}G Linux filesystem`
                : `${dev} doesn't contain a valid partition table`]
          }),
        ])
      } else emit('Welcome to fdisk (util-linux 2.37.4).\nCommand (m for help): (simulated — use \'fdisk -l\' to list disks)')
    }
    else if (lc === 'mkfs' || lc.startsWith('mkfs.') || lc === 'mke2fs' || lc === 'mkswap') {
      const dev = positional.find(a => a.includes('/dev/')) || positional[0] || ''
      if (devMatchesExtraDisk(dev, vm, shared) && shared.diskRescanned && !shared.diskFormatted) {
        shared.diskFormatted = true
        emit([`mke2fs 1.46.5 (30-Dec-2021)`, `Creating filesystem with 5242880 4k blocks and 1310720 inodes`, `Filesystem UUID: deadc0de-1234-5678-9abc-def012345678`, `Writing superblocks and filesystem accounting information: done`])
        sideEffect = { action: 'guest_format_disk', vm_id: vm?.id }
      } else if (devMatchesExtraDisk(dev, vm, shared) && shared.diskFormatted) {
        emit(`mke2fs 1.46.5 (30-Dec-2021)\n${dev} contains a ext4 file system\nProceed anyway? (y,N) (simulated — already formatted)`)
      } else if (dev.includes('sd') && !devMatchesExtraDisk(dev, vm, shared)) emit(`mkfs.ext4: ${dev} not found`)
      else if (dev.includes('sd') && dev.includes('sda')) emit(`mkfs.ext4: will not make a filesystem on '${dev}' — it is mounted`)
      else emit('Usage: mkfs.ext4 /dev/sdX  (attach a disk in vCenter first)')
    }
    else if (lc === 'mount') {
      const dev = positional[0] || ''
      const mnt = positional[1] || '/data'
      const extras = guestExtraDisks(vm, shared)
      if (!positional.length) {
        emit(['/dev/sda2 on / type xfs (rw,relatime,seclabel)', '/dev/sda1 on /boot type xfs (rw,relatime)', 'proc on /proc type proc (rw,nosuid,nodev,noexec)', 'tmpfs on /dev/shm type tmpfs (rw,nosuid,nodev)',
          ...(shared.diskMounted && extras.length ? [`${extraDiskPartPath(extras[0])} on /data type ext4 (rw,relatime)`] : [])])
      } else if (devMatchesExtraDisk(dev, vm, shared) && shared.diskFormatted && !shared.diskMounted) {
        shared.diskMounted = true
        vfs.ensureDir(mnt.startsWith('/') ? mnt : '/data')
        emit('')
        sideEffect = { action: 'guest_mount_disk', vm_id: vm?.id }
      } else if (devMatchesExtraDisk(dev, vm, shared) && !shared.diskFormatted) emit(`mount: ${mnt}: wrong fs type, bad option, bad superblock on ${dev}. (run mkfs.ext4 ${dev} first)`)
      else if (devMatchesExtraDisk(dev, vm, shared) && shared.diskMounted) emit(`mount: ${dev} already mounted on /data.`)
      else if (dev.includes('sd') && !devMatchesExtraDisk(dev, vm, shared)) emit(`mount: ${dev}: special device does not exist`)
      else emit('')
    }
    else if (lc === 'umount') emit('')
    else if (lc === 'swapon' || lc === 'swapoff') emit(lc === 'swapon' ? 'NAME      TYPE      SIZE USED PRIO\n/dev/sda3 partition   2G   0B   -2' : '')
    else if (lc === 'pvs' || lc === 'pvdisplay') {
      emit([
        '  PV         VG     Fmt  Attr PSize   PFree',
        `  /dev/sda2  rootvg lvm2 a--  ${fmtGb(lvm.rootPvGb, { lt: true })}  0`,
        ...(lvm.extraPvDevice ? [`  ${lvm.extraPvDevice.padEnd(10)} ${lvm.extraPvInVg ? 'rootvg' : ''} lvm2 a--  ${fmtGb(lvm.extraPvGb)}  ${lvm.extraPvInVg ? fmtGb(lvm.vgFreeGb) : fmtGb(lvm.extraPvGb)}`] : []),
      ])
    }
    else if (lc === 'vgs' || lc === 'vgdisplay') {
      emit(['  VG     #PV #LV #SN Attr   VSize   VFree', `  rootvg   ${lvm.extraPvInVg ? 2 : 1}   2   0 wz--n- ${fmtGb(lvm.rootPvGb + (lvm.extraPvInVg ? lvm.extraPvGb : 0), { lt: true })} ${fmtGb(lvm.vgFreeGb)}`])
    }
    else if (lc === 'lvs' || lc === 'lvdisplay') emit(['  LV     VG     Attr       LSize   Pool Origin', `  root   rootvg -wi-ao---- ${fmtGb(lvm.rootLvGb, { lt: true })}`, `  swap   rootvg -wi-ao----   ${fmtGb(lvm.swapGb)}`])
    else if (lc === 'pvcreate') {
      const dev = normalizeDevName(positional.find(a => a.includes('/dev/')) || positional[0] || '')
      const extras = guestExtraDisks(vm, shared)
      if (!dev) emit('pvcreate: Please enter a physical volume path')
      else if (!extras.length || !devMatchesExtraDisk(dev, vm, shared)) emit(`  Device ${dev} not found.`)
      else if (lvm.extraPvDevice) emit(`  Physical volume "${lvm.extraPvDevice}" is already initialized.`)
      else {
        lvm.extraPvDevice = dev
        lvm.extraPvGb = extras[0]?.capacity_gb || 20
        shared.diskFormatted = false
        shared.diskMounted = false
        emit(`  Physical volume "${dev}" successfully created.`)
      }
    }
    else if (lc === 'vgextend') {
      const vg = positional[0] || 'rootvg'
      const dev = normalizeDevName(positional.find(a => a.includes('/dev/')) || positional[1] || '')
      if (!vg || !dev) emit('vgextend: missing argument')
      else if (vg !== 'rootvg') emit(`  Volume group "${vg}" not found`)
      else if (!lvm.extraPvDevice || dev !== lvm.extraPvDevice) emit(`  Physical volume "${dev}" not found`)
      else if (lvm.extraPvInVg) emit(`  Physical volume "${dev}" is already in volume group "rootvg"`)
      else {
        lvm.extraPvInVg = true
        lvm.vgFreeGb += lvm.extraPvGb
        emit(`  Volume group "rootvg" successfully extended`)
      }
    }
    else if (lc === 'lvextend') {
      const lv = normalizeDevName(positional.find(a => a.includes('/dev/')) || positional[positional.length - 1] || '')
      const growFs = args.includes('-r') || args.includes('--resizefs')
      const requested = parseSizeGb(args, lvm.vgFreeGb)
      const growBy = Math.min(lvm.vgFreeGb, requested || lvm.vgFreeGb)
      if (!lv || !lv.includes('root')) emit('  Logical volume rootvg/root not found')
      else if (growBy <= 0) emit('  Insufficient free space: 0 extents available')
      else {
        lvm.rootLvGb += growBy
        lvm.vgFreeGb = Math.max(0, lvm.vgFreeGb - growBy)
        if (growFs) lvm.rootFsGb = lvm.rootLvGb
        emit([
          `  Size of logical volume rootvg/root changed from ${fmtGb(lvm.rootLvGb - growBy, { lt: true })} to ${fmtGb(lvm.rootLvGb, { lt: true })}.`,
          '  Logical volume rootvg/root successfully resized.',
          ...(growFs ? [`meta-data=/dev/mapper/rootvg-root isize=512 agcount=4, agsize=... blks`, `data blocks changed to ${Math.round(lvm.rootFsGb * 262144)}`] : []),
        ])
      }
    }
    else if (lc === 'resize2fs' || lc === 'xfs_growfs') {
      if (lvm.rootFsGb >= lvm.rootLvGb) emit(lc === 'xfs_growfs' ? 'data size unchanged, skipping' : 'The filesystem is already the requested size.')
      else {
        const before = lvm.rootFsGb
        lvm.rootFsGb = lvm.rootLvGb
        emit(lc === 'xfs_growfs'
          ? [`meta-data=/dev/mapper/rootvg-root isize=512 agcount=4, agsize=... blks`, `data blocks changed from ${Math.round(before * 262144)} to ${Math.round(lvm.rootFsGb * 262144)}`]
          : [`resize2fs 1.46.5 (30-Dec-2021)`, `The filesystem on /dev/mapper/rootvg-root is now ${Math.round(lvm.rootFsGb * 262144)} (4k) blocks long.`])
      }
    }
    else if (lc === 'vgcreate' || lc === 'lvcreate') emit(`${lc}: simulated — operation completed`)

    /* =================== kernel modules =================== */
    else if (lc === 'lsmod') {
      emit([
        'Module                  Size  Used by',
        'xfs                   987136  2',
        'overlay               151552  1',
        ...(shared.moduleLoaded ? ['nf_conntrack          172032  2 nf_nat,xt_state', 'br_netfilter           32768  0'] : []),
        'vmw_balloon            24576  0',
        'vmxnet3                65536  0',
      ])
    }
    else if (lc === 'modprobe' || lc === 'insmod' || lc === 'modinfo') {
      const mod = positional[0] || ''
      if (lc === 'modinfo') emit(`filename:       /lib/modules/5.15.0-91/kernel/net/${mod}.ko\nlicense:        GPL\ndescription:    ${mod} kernel module`)
      else if (vm?.kernel_module_missing && !shared.moduleLoaded && (mod.includes('nf_conntrack') || mod.includes('br_netfilter') || mod.includes('bridge') || mod.includes('overlay'))) {
        shared.moduleLoaded = true
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
      // `command -v X` is the portable form; the binary's name is the last arg.
      const t = lc === 'command' ? positional[positional.length - 1] : positional[0]
      // Core utilities that always exist even on a minimal box, plus anything in
      // the installed-package DB. Unknown binaries report "not found" like a real
      // shell — so `which nginx` only succeeds after `dnf install nginx`.
      const ALWAYS = new Set(['ls', 'cd', 'cat', 'echo', 'bash', 'sh', 'cp', 'mv', 'rm', 'mkdir',
        'grep', 'sed', 'awk', 'find', 'ps', 'top', 'kill', 'systemctl', 'ip', 'ping', 'ssh',
        'vi', 'vim', 'nano', 'tar', 'gzip', 'df', 'du', 'free', 'uname', 'sudo', 'su', 'chmod',
        'chown', 'ln', 'touch', 'head', 'tail', 'wc', 'sort', 'uniq', 'cut', 'curl', 'python3',
        isRhel ? 'dnf' : 'apt', isRhel ? 'yum' : 'apt-get', isRhel ? 'rpm' : 'dpkg'])
      const known = !!t && (ALWAYS.has(t) || pkgs.has(t) || !!vfs.resolveNode(`/usr/bin/${t}`) || !!vfs.resolveNode(`/usr/sbin/${t}`))
      if (!t) emit('')
      else if (!known) {
        if (lc === 'which') emit(`/usr/bin/which: no ${t} in (${env.PATH})`)
        else if (lc === 'type') emit(`bash: type: ${t}: not found`)
        else if (lc === 'command') emit('')  // `command -v` prints nothing + nonzero exit
        else emit(`${t}:`)
      }
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
      // Local re-parse: `parseArgs` only tracks boolean flags and dumps flag
      // VALUES into positional, so capture `-n ns` / `-o wide` here.
      const { pos, fv, fhas } = cliParse(args)
      const sub = pos[0]
      const ns = fv('-n', '--namespace') || 'default'
      const oFmt = fv('-o', '--output')
      if (sub === 'get') {
        const res = (pos[1] || '').replace(/s$/, '')
        const wide = oFmt === 'wide'
        if (res === 'node' || res === 'no') {
          if (wide) emit(['NAME       STATUS   ROLES           AGE   VERSION   INTERNAL-IP   OS-IMAGE', 'node01     Ready    control-plane   14d   v1.29.2   10.0.0.1      Red Hat Enterprise Linux 9.3', 'node02     Ready    <none>          14d   v1.29.2   10.0.0.2      Red Hat Enterprise Linux 9.3'])
          else emit(['NAME       STATUS   ROLES           AGE   VERSION', 'node01     Ready    control-plane   14d   v1.29.2', 'node02     Ready    <none>          14d   v1.29.2'])
        }
        else if (res === 'pod' || res === 'po') {
          if (wide) emit(['NAME                   READY   STATUS    RESTARTS   AGE   IP            NODE', 'web-7d9f8c6b5-x2k9p    1/1     Running   0          2h    10.244.1.7    node02', 'db-0                   1/1     Running   0          2h    10.244.0.5    node01'])
          else emit(['NAME                   READY   STATUS    RESTARTS   AGE', 'web-7d9f8c6b5-x2k9p    1/1     Running   0          2h', 'db-0                   1/1     Running   0          2h'])
        }
        else if (res === 'deployment' || res === 'deploy') emit(['NAME   READY   UP-TO-DATE   AVAILABLE   AGE', 'web    3/3     3            3           5d', 'api    2/2     2            2           5d'])
        else if (res === 'svc' || res === 'service') emit(['NAME         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE', 'kubernetes   ClusterIP   10.96.0.1       <none>        443/TCP   14d', 'web          ClusterIP   10.96.12.40     <none>        80/TCP    5d'])
        else if (res === 'ns' || res === 'namespace') emit(['NAME          STATUS   AGE', 'default       Active   14d', 'kube-system   Active   14d', 'kube-public   Active   14d'])
        else if (res === 'event') emit(['LAST SEEN   TYPE     REASON      OBJECT           MESSAGE', '2m          Normal   Scheduled   pod/web-7d9f8c   Successfully assigned default/web to node02'])
        else if (res === 'cm' || res === 'configmap') emit(['NAME               DATA   AGE', 'kube-root-ca.crt   1      14d', 'app-config         3      5d'])
        else if (res === 'secret') emit(['NAME       TYPE     DATA   AGE', 'db-creds   Opaque   2      5d'])
        else if (res === 'pvc') emit(['NAME      STATUS   VOLUME      CAPACITY   ACCESS MODES   STORAGECLASS   AGE', 'db-data   Bound    pvc-8a1f2   10Gi       RWO            standard       5d'])
        else if (oFmt === 'json') emit('{\n    "apiVersion": "v1",\n    "kind": "List",\n    "items": []\n}')
        else if (oFmt === 'yaml') emit('apiVersion: v1\nkind: List\nitems: []')
        else emit(`No resources found in ${ns} namespace.`)
      }
      else if (sub === 'version') emit(fhas('--short') ? 'Client Version: v1.29.2\nServer Version: v1.29.2' : 'Client Version: version.Info{Major:"1", Minor:"29", GitVersion:"v1.29.2"}\nServer Version: version.Info{Major:"1", Minor:"29", GitVersion:"v1.29.2"}')
      else if (sub === 'cluster-info') emit('Kubernetes control plane is running at https://10.0.0.1:6443\nCoreDNS is running at https://10.0.0.1:6443/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy')
      else if (sub === 'config') {
        if (pos[1] === 'current-context') emit('kubernetes-admin@kubernetes')
        else if (pos[1] === 'get-contexts') emit(['CURRENT   NAME                          CLUSTER      AUTHINFO', '*         kubernetes-admin@kubernetes   kubernetes   kubernetes-admin'])
        else if (pos[1] === 'view') emit('apiVersion: v1\nkind: Config\nclusters:\n- cluster:\n    server: https://10.0.0.1:6443\n  name: kubernetes')
        else emit('Modify kubeconfig files using the subcommands like "kubectl config set-context".')
      }
      else if (sub === 'describe') {
        const res = pos[1] || 'pod'
        const name = pos[2] || 'web-7d9f8c6b5-x2k9p'
        emit([`Name:             ${name}`, `Namespace:        ${ns}`, 'Status:           Running', 'IP:               10.244.1.7', 'Containers:', `  ${res}:`, '    State:          Running', '    Ready:          True', '    Restart Count:  0', 'Events:           <none>'])
      }
      else if (sub === 'logs') emit([`[info] starting ${pos[1] || 'web'} on :8080`, '[info] connected to database', '[info] ready to accept connections'])
      else if (sub === 'exec') emit(pos.includes('--') ? '' : 'error: you must specify at least one command for the container')
      else if (sub === 'apply') emit(`${(fv('-f', '--filename') || 'resource')} configured`)
      else if (sub === 'create') emit(`${pos[1] || 'resource'}/${pos[2] || 'new'} created`)
      else if (sub === 'delete') emit(`${pos[1] || 'resource'} "${pos[2] || 'name'}" deleted`)
      else if (sub === 'scale') emit(`deployment.apps/${(pos[1] || 'web').replace('deployment/', '')} scaled`)
      else if (sub === 'rollout') {
        if (pos[1] === 'status') emit(`deployment "${(pos[2] || 'web').replace('deployment/', '')}" successfully rolled out`)
        else if (pos[1] === 'restart') emit(`deployment.apps/${(pos[2] || 'web').replace('deployment/', '')} restarted`)
        else if (pos[1] === 'undo') emit(`deployment.apps/${(pos[2] || 'web').replace('deployment/', '')} rolled back`)
        else if (pos[1] === 'history') emit(['REVISION  CHANGE-CAUSE', '1         <none>', '2         kubectl set image'])
        else emit('Manage the rollout of one or more resources.')
      }
      else if (sub === 'top') {
        if (pos[1] === 'nodes' || pos[1] === 'node') emit(['NAME       CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%', 'node01     220m         11%    1421Mi          37%', 'node02     180m         9%     1198Mi          31%'])
        else emit(['NAME                   CPU(cores)   MEMORY(bytes)', 'web-7d9f8c6b5-x2k9p    12m          84Mi', 'db-0                   45m          312Mi'])
      }
      else if (sub === 'api-resources') emit(['NAME          SHORTNAMES   APIVERSION   NAMESPACED   KIND', 'pods          po           v1           true         Pod', 'services      svc          v1           true         Service', 'deployments   deploy       apps/v1      true         Deployment'])
      else if (sub === 'explain') emit(`KIND:     ${pos[1] || 'Pod'}\nVERSION:  v1\n\nDESCRIPTION:\n     ${pos[1] || 'Pod'} is a collection of containers that can run on a host.`)
      else if (sub === 'set' && pos[1] === 'image') emit(`deployment.apps/${(pos[2] || 'web').replace('deployment/', '')} image updated`)
      else emit('kubectl controls the Kubernetes cluster manager.\n\nFind more information at: https://kubernetes.io/docs/reference/kubectl/')
    }
    else if (lc === 'aws') {
      const { pos, fv, fhas } = cliParse(args)
      const svc = pos[0]
      const op = pos[1]
      const region = fv('--region') || 'us-east-1'
      const outFmt = fv('--output') || 'json'
      const jblock = (obj) => emit(outFmt === 'text' ? obj.text : obj.json)
      if (!svc || fhas('help')) {
        emit('usage: aws [options] <command> <subcommand> [<subcommand> ...] [parameters]\nTo see help text, you can run:\n  aws help\n  aws <command> help')
      }
      else if (svc === '--version' || svc === 'version') emit('aws-cli/2.15.30 Python/3.11.8 Linux/5.14.0 exe/x86_64.rhel.9')
      else if (svc === 'configure') {
        if (op === 'list') emit(['      Name                    Value             Type    Location', '      ----                    -----             ----    --------', '   access_key     ****************WXYZ shared-credentials-file', '       region                us-east-1      config-file    ~/.aws/config'])
        else emit('')
      }
      else if (svc === 'sts' && op === 'get-caller-identity') {
        jblock({
          json: '{\n    "UserId": "AIDAEXAMPLE1234567890",\n    "Account": "123456789012",\n    "Arn": "arn:aws:iam::123456789012:user/devops"\n}',
          text: 'AIDAEXAMPLE1234567890\t123456789012\tarn:aws:iam::123456789012:user/devops',
        })
      }
      else if (svc === 'ec2') {
        if (op === 'describe-instances') jblock({
          json: '{\n    "Reservations": [\n        {\n            "Instances": [\n                {\n                    "InstanceId": "i-0abcd1234efgh5678",\n                    "InstanceType": "t3.medium",\n                    "State": { "Name": "running" },\n                    "PrivateIpAddress": "10.0.1.25"\n                }\n            ]\n        }\n    ]\n}',
          text: 'i-0abcd1234efgh5678\tt3.medium\trunning\t10.0.1.25',
        })
        else if (op === 'describe-instance-status') emit('{\n    "InstanceStatuses": [\n        { "InstanceId": "i-0abcd1234efgh5678", "InstanceState": { "Name": "running" } }\n    ]\n}')
        else if (op === 'start-instances') emit('{\n    "StartingInstances": [\n        { "InstanceId": "i-0abcd1234efgh5678", "CurrentState": { "Name": "pending" } }\n    ]\n}')
        else if (op === 'stop-instances') emit('{\n    "StoppingInstances": [\n        { "InstanceId": "i-0abcd1234efgh5678", "CurrentState": { "Name": "stopping" } }\n    ]\n}')
        else if (op === 'describe-regions') emit('{\n    "Regions": [\n        { "RegionName": "us-east-1" },\n        { "RegionName": "us-west-2" },\n        { "RegionName": "eu-west-1" }\n    ]\n}')
        else emit(`aws: ec2: simulated (${op || 'no subcommand'}) in ${region}`)
      }
      else if (svc === 's3') {
        if (op === 'ls') {
          if (pos[2]) emit(['2024-05-01 10:22:14       1024 index.html', '2024-05-01 10:22:15       4096 app.tar.gz'])
          else emit(['2024-04-12 09:00:00 my-app-bucket', '2024-04-20 14:30:00 backups-prod'])
        }
        else if (op === 'cp') emit(`upload: ${pos[2] || './file'} to ${pos[3] || 's3://bucket/file'}`)
        else if (op === 'sync') emit(`Completed sync to ${pos[3] || pos[2] || 's3://bucket'}`)
        else if (op === 'mb') emit(`make_bucket: ${(pos[2] || 's3://bucket').replace('s3://', '')}`)
        else if (op === 'rb') emit(`remove_bucket: ${(pos[2] || 's3://bucket').replace('s3://', '')}`)
        else if (op === 'rm') emit(`delete: ${pos[2] || 's3://bucket/file'}`)
        else emit('usage: aws s3 <ls|cp|mv|rm|sync|mb|rb> ...')
      }
      else if (svc === 's3api' && op === 'list-buckets') emit('{\n    "Buckets": [\n        { "Name": "my-app-bucket", "CreationDate": "2024-04-12T09:00:00Z" }\n    ]\n}')
      else if (svc === 'iam') {
        if (op === 'list-users') emit('{\n    "Users": [\n        { "UserName": "devops", "Arn": "arn:aws:iam::123456789012:user/devops" }\n    ]\n}')
        else if (op === 'get-user') emit('{\n    "User": { "UserName": "devops", "UserId": "AIDAEXAMPLE1234567890" }\n}')
        else if (op === 'list-roles') emit('{\n    "Roles": [\n        { "RoleName": "eks-node-role", "Arn": "arn:aws:iam::123456789012:role/eks-node-role" }\n    ]\n}')
        else emit(`aws: iam: simulated (${op || 'no subcommand'})`)
      }
      else if (svc === 'eks') {
        if (op === 'list-clusters') emit('{\n    "clusters": [\n        "prod-cluster"\n    ]\n}')
        else if (op === 'update-kubeconfig') emit(`Updated context arn:aws:eks:${region}:123456789012:cluster/${fv('--name') || 'prod-cluster'} in ~/.kube/config`)
        else if (op === 'describe-cluster') emit('{\n    "cluster": { "name": "prod-cluster", "status": "ACTIVE", "version": "1.29" }\n}')
        else emit(`aws: eks: simulated (${op || 'no subcommand'})`)
      }
      else if (svc === 'logs' && op === 'describe-log-groups') emit('{\n    "logGroups": [\n        { "logGroupName": "/aws/eks/prod-cluster/cluster" }\n    ]\n}')
      else emit(`aws: ${svc}: simulated (${[op, ...pos.slice(2)].filter(Boolean).join(' ') || 'no subcommand'}) in ${region}`)
    }
    else if (lc === 'helm') {
      const sub = positional[0] || ''
      if (sub === 'list') emit('NAME\tNAMESPACE\tREVISION\tSTATUS\tCHART\nwebapp\tdefault\t3\tdeployed\twebapp-1.2.0')
      else if (sub === 'upgrade' || sub === 'install') emit('Release webapp has been upgraded. Happy Helming!')
      else if (sub === 'history') emit('REVISION\tUPDATED\tSTATUS\tCHART\n3\t2024-05-01 12:00:00\tdeployed\twebapp-1.2.0')
      else emit('NAME\tNAMESPACE\tREVISION\tSTATUS\tCHART')
    }
    else if (lc === 'git') emit(gitSim.run(work))
    else if (['argocd', 'flux', 'mvn', 'sonar-scanner'].includes(lc) || cmd === './mvnw' || (lc === 'java' && work.includes('jenkins-cli'))) {
      const joined = positional.join(' ')
      if (lc === 'argocd' && joined.includes('app sync')) emit('Sync Status: Synced\nHealth Status: Healthy')
      else if (lc === 'argocd') emit(`argocd: ${joined || 'OK'}`)
      else if (lc === 'flux') emit('NAME\tREADY\tSTATUS\nwebapp\tTrue\tApplied')
      else if (lc.startsWith('mvn') || lc === './mvnw') emit(joined.includes('package') || joined.includes('install') ? 'BUILD SUCCESS\nTotal time: 12.4 s' : 'Apache Maven 3.9.6')
      else if (lc === 'sonar-scanner' || joined.includes('sonar:')) emit('ANALYSIS SUCCESSFUL\nQuality gate status: PASSED')
      else emit(`${lc}: OK`)
    }
    else if (['ansible', 'ansible-playbook', 'terraform', 'packer', 'vagrant'].includes(lc)) {
      if (lc === 'terraform' && positional[0] === 'version') emit('Terraform v1.7.4\non linux_amd64')
      else emit(`${lc}: simulated (${positional.join(' ') || 'no args'})`)
    }

    /* =================== power =================== */
    else if (['reboot', 'shutdown', 'poweroff', 'halt'].includes(lc)) {
      // `shutdown -h now` / poweroff / halt power the guest OFF; reboot replays boot.
      const halts = lc === 'poweroff' || lc === 'halt' || (lc === 'shutdown' && (has('-h') || has('-P') || has('-H')))
      const reboots = lc === 'reboot' || (lc === 'shutdown' && (has('-r') || !halts))
      return { lines: [reboots ? 'Rebooting…' : 'Powering off…'], prompt: prompt(), reboot: reboots ? { single: false } : undefined, poweroff: halts ? true : undefined }
    }
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
    syncVm: (nextVm) => { if (nextVm) vmRef.current = nextVm; getOrCreateGuestShared(vmRef.current) },
    pkgManager: () => pkgManager(vmRef.current),
    // Stateful package DB queries (used by tests + any future programmatic checks).
    isInstalled: (name) => pkgs.has(name),
    installedPackages: () => pkgs.rpmList(),
    getStatus,
    getCwd: () => cwd.path,
    getUser: () => env.USER,
    switchUser,
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

/* ------------------------------------------------------------------ *
 * Realistic, time-paced boot / reboot sequence
 * ------------------------------------------------------------------ *
 * The VmwareConsole component schedules each stage with setTimeout using the
 * per-stage `delay` (ms). A full run lands around 45-70s. Everything is data
 * so the pacing logic in React stays trivial and interruptible.
 */

// SeaBIOS / POST — printed first, before the GRUB menu.
export const POST_LINES = [
  'SeaBIOS (version fixitlab-1.16.0)',
  'Machine UUID 564d8a1f-2b3c-4d5e-6f70-8192a3b4c5d6',
  '',
  'iPXE (https://ipxe.org) 00:03.0 — PCI booting disabled',
  'Booting from Hard Disk...',
  'GRUB loading.',
  'Welcome to GRUB!',
  '',
]

const KERNEL_PRIMARY = '5.15.0-91-generic'
const KERNEL_OLDER = '5.15.0-88-generic'

// GRUB menu entries are distro-flavoured; index 1 is always the rescue/recovery entry.
export function buildGrubEntries(vm) {
  const isRhel = guestOsFamily(vm) === 'rhel'
  if (isRhel) {
    return [
      'Red Hat Enterprise Linux (5.14.0-362.el9.x86_64) 9.3 (Plow)',
      'Red Hat Enterprise Linux (5.14.0-362.el9.x86_64) 9.3 (Plow) — rescue mode',
      'Red Hat Enterprise Linux (5.14.0-284.el9.x86_64) 9.3 (Plow)',
      'UEFI Firmware Settings',
    ]
  }
  return [
    `Ubuntu, with Linux ${KERNEL_PRIMARY}`,
    `Advanced options for Ubuntu — recovery mode (${KERNEL_PRIMARY})`,
    `Ubuntu, with Linux ${KERNEL_OLDER}`,
    'UEFI Firmware Settings',
  ]
}

// Back-compat aliases (legacy importers).
export const GRUB_ENTRIES = buildGrubEntries({})
export const BOOT_SEQUENCE = [] // superseded by buildBootStages(); kept so old imports don't crash.

// Build the full kernel→initramfs→mount→systemd→login stage list.
// Each item: { text: string|string[], delay: ms-before-printing-this-line }.
// `single` => single-user / rescue mode (drops to a maintenance shell, no graphical login).
export function buildBootStages(vm, { single = false } = {}) {
  const isRhel = guestOsFamily(vm) === 'rhel'
  const hostname = (vm?.hostname || vm?.name || (isRhel ? 'rhel-app01' : 'ubuntu-app01')).split('.')[0]
  const memMb = vm?.memory_mb || 4096
  const cpu = vm?.cpu || 2
  const kver = isRhel ? '5.14.0-362.el9.x86_64' : KERNEL_PRIMARY
  const s = []
  // PACE scales the relative per-stage delays so a full boot lands ~50-60s (the
  // user wants the reboot to take "atleast 1 min"), with a floor so no two lines
  // appear in the same frame.
  const PACE = 3.2
  const push = (text, delay) => s.push({ text, delay: Math.max(160, Math.round(delay * PACE)) })

  // ---- early kernel ----
  push(`Loading Linux ${kver} ...`, 250)
  push('Loading initial ramdisk ...', 700)
  push('', 300)
  push(`[    0.000000] Linux version ${kver} (mockbuild@fixitlab) (gcc 11.4.0) #1 SMP`, 600)
  push('[    0.000000] Command line: BOOT_IMAGE=/boot/vmlinuz-' + kver + ' root=UUID=8f3b2c1a ro' + (single ? ' single' : ' quiet'), 200)
  push(`[    0.004000] x86/fpu: Supporting XSAVE feature 0x002: 'SSE registers'`, 220)
  push(`[    0.118000] Memory: ${memMb * 1024}K/${memMb * 1024}K available (${cpu} CPUs)`, 260)
  push('[    0.342891] ACPI: Core revision 20210730', 200)
  push('[    0.512300] smpboot: Allowing ' + cpu + ' CPUs, 0 hotplug CPUs', 240)
  push('[    0.884512] pci 0000:00:0f.0: [15ad:0405] VMware SVGA II Adapter', 200)
  push('[    1.024000] sd 0:0:0:0: [sda] Attached SCSI disk', 280)
  push('[    1.210400] vmxnet3 0000:0b:00.0 eth0: NIC Link is Up 10000 Mbps', 220)

  // ---- initramfs / dracut ----
  if (isRhel) {
    push('[    1.640000] dracut: dracut-057-21.git20230214.el9', 350)
    push('[    1.920000] dracut: Mounted root filesystem /dev/mapper/rootvg-root', 380)
    push('[    2.140000] systemd[1]: Switching root.', 300)
  } else {
    push('Begin: Loading essential drivers ... done.', 360)
    push('Begin: Running /scripts/init-premount ... done.', 320)
    push('Begin: Mounting root file system ... Begin: Running /scripts/local-top ... done.', 360)
    push('Begin: Running /scripts/local-premount ... done.', 300)
  }
  push('[    2.418000] EXT4-fs (sda2): mounted filesystem with ordered data mode.', 420)

  // ---- systemd takes over ----
  push(`[    2.612000] systemd[1]: systemd 252 running in system mode`, 380)
  push(`[    2.640000] systemd[1]: Detected virtualization vmware.`, 200)
  push(`[    2.680000] systemd[1]: Detected architecture x86-64.`, 180)
  push('', 150)
  push(isRhel ? 'Welcome to Red Hat Enterprise Linux 9.3 (Plow)!' : 'Welcome to Ubuntu 22.04.4 LTS!', 250)
  push('', 150)

  // ---- filesystem mounts (explicit, as the user asked) ----
  push(okLine('Created slice Slice /system.'), 220)
  push(okLine('Reached target Local Encrypted Volumes.'), 200)
  push(okLine('Started Journal Service.'), 260)
  push(okLine('Mounting /boot (xfs) ...'), 320)
  push(okLine('Mounted /boot.'), 280)
  push(okLine('Activating swap /dev/mapper/rootvg-swap ...'), 300)
  push(okLine('Activated swap /dev/mapper/rootvg-swap.'), 240)
  push(okLine('Reached target Swaps.'), 180)
  push(okLine('Mounting /dev/shm (tmpfs) ...'), 260)
  push(okLine('Mounted /dev/shm.'), 220)
  push(okLine('Reached target Local File Systems.'), 200)

  if (single) {
    // single-user / rescue: stop here and hand the user a maintenance shell
    push('', 200)
    push('You are in rescue mode. After logging in, type "journalctl -xb" to view', 250)
    push('system logs, "systemctl reboot" to reboot, or "exit" to continue booting.', 200)
    push('', 150)
    push('Give root password for maintenance', 300)
    push('(or press Control-D to continue): ', 200)
    return s
  }

  // ---- normal multi-user unit start-up, one [ OK ] at a time ----
  const units = [
    'Started udev Kernel Device Manager.',
    'Started Network Manager.',
    'Reached target Network.',
    'Started Network Name Resolution.',
    'Started Hostname Service.',
    'Started Login Service.',
    'Started irqbalance daemon.',
    'Started System Logging Service.',
    'Started Self Monitoring and Reporting Technology (SMART) Daemon.',
    'Started NTP client/server (chronyd).',
    isRhel ? 'Started firewalld - dynamic firewall daemon.' : 'Started Uncomplicated firewall.',
    'Started D-Bus System Message Bus.',
    'Started OpenSSH server daemon.',
    'Started Docker Application Container Engine.',
    'Started MySQL Server.',
    'Started Command Scheduler (crond).',
    'Started Permit User Sessions.',
    'Started Getty on tty1.',
    'Reached target Login Prompts.',
    'Reached target Multi-User System.',
    'Reached target Graphical Interface.',
  ]
  units.forEach((u, i) => push(okLine(u), 180 + (i % 4) * 70))

  push('', 250)
  return s
}

function okLine(text) {
  return `[  OK  ] ${text}`
}
