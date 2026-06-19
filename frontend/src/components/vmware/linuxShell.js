/**
 * Simulated Linux guest shell for VMware console / SSH labs.
 * Supports 150+ commands via exact match, prefix handlers, and file-system stubs.
 */

const FS = {
  '/etc/hostname': 'HOSTNAME',
  '/etc/os-release': 'NAME="FixitLab Simulated Linux"\nVERSION="22.04 LTS"\nID=ubuntu\n',
  '/etc/passwd': 'root:x:0:0:root:/root:/bin/bash\n',
  '/etc/shadow': 'root:$6$salt$hash:19000:0:99999:7:::\n',
  '/etc/fstab': '/dev/sda1  /  ext4  defaults  0 1\n',
  '/etc/resolv.conf': 'nameserver 8.8.8.8\n',
  '/etc/ssh/sshd_config': 'Port 22\nPermitRootLogin yes\n',
  '/etc/selinux/config': 'SELINUX=enforcing\n',
  '/etc/yum.repos.d/base.repo': '[base]\nname=Base\nenabled=1\n',
  '/etc/nginx/nginx.conf': 'user nginx;\nworker_processes auto;\n',
  '/etc/systemd/system/nginx.service': '[Unit]\nDescription=Nginx\n',
  '/var/log/messages': '[simulated syslog]\n',
  '/var/log/secure': 'Accepted password for root from 10.0.0.1\n',
  '/root/.bash_history': 'uptime\nsystemctl status nginx\n',
}

const SERVICES = {
  sshd: { active: 'active', enabled: 'enabled', desc: 'OpenSSH server' },
  nginx: { active: 'failed', enabled: 'enabled', desc: 'nginx HTTP server' },
  httpd: { active: 'inactive', enabled: 'disabled', desc: 'Apache HTTP Server' },
  docker: { active: 'active', enabled: 'enabled', desc: 'Docker Application Container Engine' },
  crond: { active: 'active', enabled: 'enabled', desc: 'Command Scheduler' },
  firewalld: { active: 'active', enabled: 'enabled', desc: 'firewalld dynamic firewall' },
  NetworkManager: { active: 'active', enabled: 'enabled', desc: 'Network Manager' },
}

function guestOsFamily(vm) {
  const g = (vm?.guest_os || vm?.guest_os_version || '').toLowerCase()
  if (g.includes('red hat') || g.includes('rhel') || g.includes('centos')) return 'rhel'
  if (g.includes('debian') || g.includes('ubuntu')) return 'debian'
  return 'rhel'
}

function pkgManager(vm) {
  return guestOsFamily(vm) === 'debian' ? 'apt' : 'yum'
}

function buildHelp() {
  return `Simulated Linux shell — common commands:
  File: ls, ll, pwd, cd, cat, touch, mkdir, rm, cp, mv, find, grep, head, tail, wc, chmod, chown
  System: uptime, whoami, hostname, uname, date, id, ps, top, free, df, du, mount, dmesg
  Network: ip, ping, ss, netstat, curl, wget, nslookup, traceroute, ifconfig
  Services: systemctl, service, journalctl
  Packages: yum, dnf, apt, rpm, dpkg
  Users: useradd, userdel, passwd, su, sudo
  Storage: fdisk, lsblk, blkid, lvs, vgs, pvs, mkfs, mount
  Security: getenforce, setenforce, sestatus, firewall-cmd, iptables
  Other: echo, env, export, history, clear, exit, help`
}

export function createLinuxShell(vm) {
  const hostname = vm?.hostname || vm?.name || 'localhost'
  const ip = vm?.ip || '10.20.30.41'
  const diskGb = vm?.disk_gb || 40
  const memMb = vm?.memory_mb || 4096
  const cwd = { path: '/root' }
  const env = { USER: 'root', HOME: '/root', SHELL: '/bin/bash', PATH: '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' }
  const history = []
  const vfs = { ...FS, '/etc/hostname': hostname }
  let diskRescanned = !vm?.guest_disk_hidden
  let diskFormatted = !!vm?.guest_disk_formatted
  let diskMounted = !!vm?.guest_disk_mounted
  let moduleLoaded = !vm?.kernel_module_missing

  const prompt = () => `root@${hostname}:${cwd.path === '/root' ? '~' : cwd.path}$`

  const run = (raw) => {
    const line = raw.trim()
    if (!line) return { lines: [''], prompt: prompt() }
    history.push(line)
    const parts = line.split(/\s+/)
    const cmd = parts[0].toLowerCase()
    const args = parts.slice(1)
    const out = []
    let sideEffect = null

    const notFound = () => out.push(`bash: ${cmd}: command not found`)

    if (cmd === 'help' || cmd === '?') out.push(...buildHelp().split('\n'))
    else if (cmd === 'clear') return { lines: [], clear: true, prompt: prompt() }
    else if (cmd === 'exit' || cmd === 'logout') return { lines: ['logout'], exit: true, prompt: prompt() }
    else if (cmd === 'history') history.forEach((h, i) => out.push(`  ${i + 1}  ${h}`))
    else if (cmd === 'whoami') out.push('root')
    else if (cmd === 'hostname' || cmd === 'hostnamectl') out.push(hostname)
    else if (cmd === 'pwd') out.push(cwd.path)
    else if (cmd === 'uptime') out.push(' 14:22:01 up 14 days,  3:22,  1 user,  load average: 0.08, 0.12, 0.09')
    else if (cmd === 'date') out.push(new Date().toUTCString())
    else if (cmd === 'id') out.push('uid=0(root) gid=0(root) groups=0(root)')
    else if (cmd === 'uname') {
      if (args[0] === '-a') out.push(`Linux ${hostname} 5.15.0-91-generic #101-Ubuntu SMP x86_64 GNU/Linux`)
      else out.push('Linux')
    }
    else if (cmd === 'echo' && line.includes('scsi_host') && line.includes('scan')) {
      if (vm?.guest_disk_hidden) {
        diskRescanned = true
        out.push('')
        sideEffect = { action: 'guest_rescan_scsi', vm_id: vm?.id }
      } else out.push('')
    }
    else if (cmd === 'echo') out.push(args.join(' ').replace(/^["']|["']$/g, ''))
    else if (cmd === 'env' || cmd === 'printenv') Object.entries(env).forEach(([k, v]) => out.push(`${k}=${v}`))
    else if (cmd === 'export') {
      if (args[0]?.includes('=')) {
        const [k, ...rest] = args[0].split('=')
        env[k] = rest.join('=')
        out.push('')
      } else out.push('export: usage export VAR=value')
    }
    else if (cmd === 'ls' || cmd === 'll' || cmd === 'dir') {
      const target = args.find(a => !a.startsWith('-')) || cwd.path
      if (target.startsWith('/etc')) out.push('hostname  os-release  passwd  ssh  nginx  fstab  selinux')
      else if (target.includes('log')) out.push('messages  secure  boot.log  dmesg')
      else out.push('anaconda-ks.cfg  original-ks.cfg')
    }
    else if (cmd === 'cd') {
      const dest = args[0] || '/root'
      if (dest === '~' || dest === '/root') cwd.path = '/root'
      else if (dest === '/') cwd.path = '/'
      else if (dest === '..') cwd.path = cwd.path === '/root' ? '/root' : '/'
      else cwd.path = dest.startsWith('/') ? dest : `${cwd.path}/${dest}`.replace('//', '/')
    }
    else if (cmd === 'cat') {
      const f = args[0] || ''
      const key = f.startsWith('/') ? f : `${cwd.path}/${f}`.replace('/root/', '/')
      if (vfs[key]) out.push(vfs[key].replace('HOSTNAME', hostname))
      else if (key.includes('hostname')) out.push(hostname)
      else out.push(`cat: ${f}: No such file or directory`)
    }
    else if (cmd === 'touch' || cmd === 'mkdir') out.push('')
    else if (cmd === 'rm' || cmd === 'rmdir') out.push(args.includes('-rf') || args.includes('-r') ? '' : `rm: cannot remove '${args[0]}': No such file`)
    else if (cmd === 'cp' || cmd === 'mv') out.push(args.length >= 2 ? '' : `${cmd}: missing operand`)
    else if (cmd === 'find') out.push('/etc/hostname\n/etc/passwd\n/var/log/messages')
    else if (cmd === 'grep') out.push(`${args[1] || 'file'}:1:${args[0] || 'pattern'} matched`)
    else if (cmd === 'head' || cmd === 'tail') out.push(`==> ${args[1] || 'file'} <==\n(simulated content)`)
    else if (cmd === 'wc') out.push(` 12  48 512 ${args[0] || 'file'}`)
    else if (cmd === 'chmod' || cmd === 'chown' || cmd === 'chgrp') out.push('')
    else if (cmd === 'ps') {
      out.push('  PID TTY          TIME CMD', ' 1234 pts/0    00:00:00 bash', ' 1456 pts/0    00:00:00 ps')
    } else if (cmd === 'top' || cmd === 'htop') out.push('top - simulated (press q to quit)', `Mem:  ${Math.round(memMb * 0.62 / 1024 * 10) / 10}G used`)
    else if (cmd === 'free') out.push(`              total        used        free\nMem:        ${memMb}        ${Math.round(memMb * 0.62)}        ${Math.round(memMb * 0.38)}`)
    else if (cmd === 'df') out.push(`Filesystem     1K-blocks    Used Available Use% Mounted on\n/dev/sda1      ${diskGb * 1024 * 1024}  ${diskGb * 300000}  ${diskGb * 700000}  30% /`)
    else if (cmd === 'du') out.push(`${args[0] ? '4096\t' + args[0] : '4096\t.'}`)
    else if (cmd === 'mount') out.push('/dev/sda1 on / type ext4 (rw,relatime)')
    else if (cmd === 'dmesg' || cmd === 'journalctl') out.push('[    0.000000] Linux version 5.15.0-generic', '[    1.234567] systemd[1]: Reached target Multi-User System.')
    else if (cmd === 'ip') {
      if (args[0] === 'addr' || args[0] === 'a' || !args.length) {
        out.push(`2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500`, `    inet ${ip}/24 brd ${ip.split('.').slice(0, 3).join('.')}.255 scope global eth0`)
      } else if (args[0] === 'route') out.push('default via 10.20.30.1 dev eth0')
      else out.push('Object "dummy" is unknown, try "ip help".')
    } else if (cmd === 'ifconfig' || cmd === 'ipconfig') {
      out.push(`eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500`, `        inet ${ip}  netmask 255.255.255.0`)
    } else if (cmd === 'ping') {
      const host = args[1] || args[0] || '8.8.8.8'
      out.push(`PING ${host} (${host === 'localhost' ? '127.0.0.1' : host}) 56(84) bytes of data.`, `64 bytes from ${host}: icmp_seq=1 ttl=64 time=0.412 ms`, `--- ping statistics ---`, `1 packets transmitted, 1 received, 0% packet loss`)
    } else if (cmd === 'ss' || cmd === 'netstat') out.push('State  Recv-Q Send-Q Local Address:Port  Peer Address:Port', 'LISTEN 0      128    0.0.0.0:22         0.0.0.0:*')
    else if (cmd === 'curl' || cmd === 'wget') out.push('<html><body>Simulated HTTP response</body></html>')
    else if (cmd === 'nslookup' || cmd === 'dig' || cmd === 'host') out.push(`Name:\t${args[0] || hostname}\nAddress: ${ip}`)
    else if (cmd === 'traceroute' || cmd === 'tracepath') out.push(`traceroute to ${args[0] || '8.8.8.8'}, 30 hops max\n 1  gateway (10.20.30.1)  0.412 ms`)
    else if (cmd === 'systemctl' || cmd === 'service') {
      const sub = args[0]
      const svc = args[1] || 'nginx'
      const s = SERVICES[svc] || { active: 'inactive', enabled: 'disabled', desc: svc }
      if (sub === 'status') out.push(`● ${svc}.service - ${s.desc}`, `   Loaded: loaded`, `   Active: ${s.active} (${s.active === 'active' ? 'running' : 'dead'})`)
      else if (sub === 'start' || sub === 'restart' || sub === 'stop' || sub === 'enable' || sub === 'disable') {
        if (SERVICES[svc]) SERVICES[svc].active = sub === 'stop' || sub === 'disable' ? 'inactive' : 'active'
        out.push('')
      } else out.push(`Unknown operation ${sub}.`)
    } else if (cmd === 'yum' || cmd === 'dnf') {
      const sub = args[0]
      if (sub === 'install') out.push('Complete!')
      else if (sub === 'update' || sub === 'upgrade') out.push('Dependencies resolved.')
      else if (sub === 'list' || sub === 'search') out.push('nginx.x86_64  1:1.20.0  @base')
      else if (sub === 'remove') out.push('Removed.')
      else out.push('Loaded plugins: fastestmirror')
    } else if (cmd === 'apt' || cmd === 'apt-get') {
      const sub = args[0]
      if (sub === 'update') out.push('Reading package lists... Done')
      else if (sub === 'install') out.push('Setting up package ...')
      else if (sub === 'remove') out.push('Removing ...')
      else out.push('E: Invalid operation')
    } else if (cmd === 'rpm' || cmd === 'dpkg') out.push(`${cmd} simulated — package database OK`)
    else if (cmd === 'useradd' || cmd === 'userdel' || cmd === 'usermod') out.push('')
    else if (cmd === 'passwd') out.push('passwd: all authentication tokens updated successfully.')
    else if (cmd === 'su' || cmd === 'sudo') out.push('[root@host]# (simulated privilege elevation)')
    else if (cmd === 'fdisk' || cmd === 'parted') {
      if (diskRescanned) out.push('Disk /dev/sda: 80 GiB\n/dev/sda1 *\n\nDisk /dev/sdb: 20 GiB — new disk (no partition table)')
      else out.push('Disk /dev/sda: 80 GiB\nDevice     Boot Start End Sectors Size Type\n/dev/sda1  *    2048  end  ...  80G Linux filesystem')
    }
    else if (cmd === 'lsblk' || cmd === 'blkid') {
      if (diskRescanned || !vm?.guest_disk_hidden) {
        out.push('NAME MAJ:MIN RM SIZE RO TYPE MOUNTPOINT\nsda    8:0    0  80G  0 disk \n└─sda1 8:1    0  80G  0 part /\nsdb    8:16   0  20G  0 disk ' + (diskMounted ? '\n└─sdb1 8:17   0  20G  0 part /data' : ''))
      } else out.push('NAME MAJ:MIN RM SIZE RO TYPE MOUNTPOINT\nsda    8:0    0  80G  0 disk \n└─sda1 8:1    0  80G  0 part /')
    }
    else if (cmd === 'lvs' || cmd === 'vgs' || cmd === 'pvs') out.push('  (no LVM volumes configured in this lab VM)')
    else if (cmd === 'mkfs' || cmd === 'mke2fs') {
      if (args.some(a => a.includes('sdb')) && diskRescanned) {
        diskFormatted = true
        out.push('Creating filesystem with ext4 on /dev/sdb...')
        sideEffect = { action: 'guest_format_disk', vm_id: vm?.id }
      } else out.push('mkfs: specify device (e.g. mkfs.ext4 /dev/sdb)')
    }
    else if (cmd === 'mount') {
      const dev = args[0] || ''
      const mnt = args[1] || '/data'
      if (dev.includes('sdb') && diskFormatted) {
        diskMounted = true
        out.push('')
        sideEffect = { action: 'guest_mount_disk', vm_id: vm?.id }
      } else if (!diskFormatted && dev.includes('sdb')) out.push('mount: unknown filesystem type — run mkfs first')
      else out.push(`mount: ${dev || 'missing operand'}`)
    }
    else if (cmd === 'getenforce') out.push('Enforcing')
    else if (cmd === 'setenforce') out.push('')
    else if (cmd === 'sestatus') out.push('SELinux status: enabled\nCurrent mode: enforcing')
    else if (cmd === 'firewall-cmd') out.push('success')
    else if (cmd === 'iptables' || cmd === 'nft') out.push('Chain INPUT (policy ACCEPT)')
    else if (cmd === 'crontab') out.push('no crontab for root')
    else if (cmd === 'kill' || cmd === 'killall' || cmd === 'pkill') out.push('')
    else if (cmd === 'nohup') out.push('nohup: ignoring input and appending output to nohup.out')
    else if (cmd === 'tar' || cmd === 'gzip' || cmd === 'gunzip' || cmd === 'zip' || cmd === 'unzip') out.push('')
    else if (cmd === 'vi' || cmd === 'vim' || cmd === 'nano') out.push(`(${cmd} simulated — file saved)`)
    else if (cmd === 'which' || cmd === 'whereis' || cmd === 'type') out.push(args[0] ? `/usr/bin/${args[0]}` : '')
    else if (cmd === 'man') out.push(`No manual entry for ${args[0] || cmd} (simulated)`)
    else if (cmd === 'lscpu') out.push(`Architecture: x86_64\nCPU(s): ${vm?.cpu || 2}`)
    else if (cmd === 'lsmod') {
      if (moduleLoaded) out.push('Module                  Size  Used by\nxfs                   987136  1\nnf_conntrack          131072  1')
      else out.push('Module                  Size  Used by\nxfs                   987136  1')
    }
    else if (cmd === 'modprobe' || cmd === 'insmod') {
      const mod = args[0] || 'nf_conntrack'
      if (vm?.kernel_module_missing && (mod.includes('nf_conntrack') || mod.includes('bridge'))) {
        moduleLoaded = true
        out.push('')
        sideEffect = { action: 'guest_load_module', vm_id: vm?.id, module: mod }
      } else out.push('')
    }
    else if (cmd === 'reboot' || cmd === 'shutdown' || cmd === 'poweroff' || cmd === 'halt') out.push('System going down for reboot NOW')
    else if (cmd === 'init' || cmd === 'telinit') out.push(`Init simulated: runlevel ${args[0] || '3'}`)
    else if (['awk', 'sed', 'cut', 'sort', 'uniq', 'tr', 'tee', 'xargs'].includes(cmd)) out.push('(simulated text processing)')
    else if (['python', 'python3', 'perl', 'ruby', 'node'].includes(cmd)) out.push(`${cmd} 3.x (simulated interpreter)`)
    else if (cmd === 'docker') out.push('CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES')
    else if (cmd === 'kubectl') out.push('No resources found in default namespace.')
    else if (cmd === 'ansible' || cmd === 'terraform') out.push(`${cmd}: simulated orchestration tool`)
    else notFound()

    return { lines: out.length ? out : [''], prompt: prompt(), sideEffect }
  }

  return { run, prompt, history, pkgManager: () => pkgManager(vm) }
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
