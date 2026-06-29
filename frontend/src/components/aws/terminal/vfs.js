// In-memory virtual filesystem for a simulated EC2 instance.
// Nodes: { type:'dir'|'file', content?:string, mode, owner, group, mtime }

function osRelease(os) {
  switch (os) {
    case 'amazon-linux-2023':
      return 'NAME="Amazon Linux"\nVERSION="2023"\nID="amzn"\nID_LIKE="fedora"\nVERSION_ID="2023"\nPRETTY_NAME="Amazon Linux 2023"\nHOME_URL="https://aws.amazon.com/linux/amazon-linux-2023/"\n'
    case 'amazon-linux-2':
      return 'NAME="Amazon Linux"\nVERSION="2"\nID="amzn"\nID_LIKE="centos rhel fedora"\nVERSION_ID="2"\nPRETTY_NAME="Amazon Linux 2"\n'
    case 'ubuntu-22.04':
      return 'PRETTY_NAME="Ubuntu 22.04.4 LTS"\nNAME="Ubuntu"\nVERSION_ID="22.04"\nVERSION="22.04.4 LTS (Jammy Jellyfish)"\nVERSION_CODENAME=jammy\nID=ubuntu\nID_LIKE=debian\n'
    case 'ubuntu-24.04':
      return 'PRETTY_NAME="Ubuntu 24.04 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\nVERSION="24.04 LTS (Noble Numbat)"\nVERSION_CODENAME=noble\nID=ubuntu\nID_LIKE=debian\n'
    case 'rhel-9':
      return 'NAME="Red Hat Enterprise Linux"\nVERSION="9.3 (Plow)"\nID="rhel"\nID_LIKE="fedora"\nVERSION_ID="9.3"\nPRETTY_NAME="Red Hat Enterprise Linux 9.3 (Plow)"\n'
    case 'debian-12':
      return 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nNAME="Debian GNU/Linux"\nVERSION_ID="12"\nVERSION="12 (bookworm)"\nVERSION_CODENAME=bookworm\nID=debian\n'
    default:
      return 'PRETTY_NAME="Linux"\n'
  }
}

export function kernelVersion(os) {
  switch (os) {
    case 'amazon-linux-2023': return '6.1.79-99.167.amzn2023.x86_64'
    case 'amazon-linux-2': return '5.10.209-198.812.amzn2.x86_64'
    case 'ubuntu-22.04': return '6.5.0-1018-aws'
    case 'ubuntu-24.04': return '6.8.0-1010-aws'
    case 'rhel-9': return '5.14.0-362.18.1.el9_3.x86_64'
    case 'debian-12': return '6.1.0-18-cloud-amd64'
    default: return '6.1.0-aws'
  }
}

export function defaultUser(os) {
  if (os.startsWith('ubuntu')) return 'ubuntu'
  if (os === 'debian-12') return 'admin'
  return 'ec2-user'
}

export function createVfs(os, hostname, privateIp, preferredUser) {
  const user = preferredUser || defaultUser(os)
  const home = `/home/${user}`
  const fs = {}
  const dir = (p) => { fs[p] = { type: 'dir', mode: 'drwxr-xr-x', owner: 'root', group: 'root' } }
  const file = (p, content, owner = 'root', mode = '-rw-r--r--') => { fs[p] = { type: 'file', content, mode, owner, group: owner } }

  ;['/', '/bin', '/boot', '/dev', '/etc', '/etc/ssh', '/home', home, `${home}/.ssh`, '/lib', '/lib64', '/media', '/mnt', '/opt', '/proc', '/root', '/run', '/sbin', '/srv', '/sys', '/tmp', '/usr', '/usr/bin', '/usr/local', '/usr/local/bin', '/usr/sbin', '/var', '/var/log', '/var/run', '/var/tmp'].forEach(dir)

  file('/etc/os-release', osRelease(os))
  file('/etc/hostname', `${hostname}\n`)
  file('/etc/hosts', `127.0.0.1 localhost localhost.localdomain\n${privateIp} ${hostname}\n::1 localhost6\n`)
  file('/etc/resolv.conf', 'nameserver 172.31.0.2\nsearch ec2.internal\n')
  file('/etc/fstab', `UUID=$(blkid)  /  xfs  defaults,noatime  0 0\n`)
  file('/etc/passwd', `root:x:0:0:root:/root:/bin/bash\n${user}:x:1000:1000:Cloud User:${home}:/bin/bash\nsshd:x:74:74:Privilege-separated SSH:/var/empty/sshd:/sbin/nologin\nssm-user:x:1001:1001::/home/ssm-user:/bin/bash\nchrony:x:998:996::/var/lib/chrony:/sbin/nologin\n`)
  file('/etc/group', `root:x:0:\nwheel:x:10:${user}\nadm:x:4:${user}\n${user}:x:1000:\nssm-user:x:1001:\n`)
  file('/etc/sudoers', `root ALL=(ALL) ALL\n${user} ALL=(ALL) NOPASSWD:ALL\n`)
  file('/etc/ssh/sshd_config', 'Port 22\nPermitRootLogin no\nPasswordAuthentication no\nPubkeyAuthentication yes\nChallengeResponseAuthentication no\nUsePAM yes\nX11Forwarding yes\n')
  file('/etc/motd', os.startsWith('amazon') ? '   ,     #_\n   ~\\_  ####_        Amazon Linux 2023\n  ~~  \\_#####\\\n  ~~     \\###|\n  ~~       \\#/ ___   https://aws.amazon.com/linux/amazon-linux-2023\n   ~~       V~\' \'->\n    ~~~         /\n      ~~._.   _/\n         _/ _/\n       _/m/\'\n' : `Welcome to ${os}\n`)
  file('/var/log/messages', `Jan 15 09:00:01 ${hostname} systemd[1]: Started Session 1 of user ${user}.\nJan 15 09:00:02 ${hostname} sshd[789]: Accepted publickey for ${user} from 203.0.113.10 port 51234 ssh2\nJan 15 09:00:02 ${hostname} chronyd[512]: Selected source 169.254.169.123\n`)
  file('/var/log/secure', `Jan 15 09:00:02 ${hostname} sshd[789]: Accepted publickey for ${user} from 203.0.113.10 port 51234 ssh2: RSA SHA256:abcd\nJan 15 09:00:02 ${hostname} sudo: ${user} : TTY=pts/0 ; PWD=${home} ; USER=root ; COMMAND=/bin/bash\n`)
  file('/var/log/cloud-init-output.log', 'Cloud-init v. 23.4 running \'modules:final\'\nCloud-init v. 23.4 finished\n')
  file('/proc/version', `Linux version ${kernelVersion(os)} (mockbuild@aws) #1 SMP\n`)
  file('/proc/uptime', '9241.32 18204.11\n')
  file('/proc/loadavg', '0.00 0.01 0.05 1/142 7912\n')
  file(`${home}/.bashrc`, `# .bashrc\nalias ll='ls -la'\nalias la='ls -A'\nalias l='ls -CF'\nalias grep='grep --color=auto'\nexport PS1='[\\u@\\h \\W]\\$ '\n`)
  file(`${home}/.bash_profile`, '# .bash_profile\nif [ -f ~/.bashrc ]; then . ~/.bashrc; fi\nexport PATH=$PATH:$HOME/.local/bin:$HOME/bin\n')
  file(`${home}/.bash_history`, '')
  file(`${home}/.ssh/authorized_keys`, 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQAB...demo-key-pair\n', user, '-rw-------')
  fs[`${home}/.ssh`].mode = 'drwx------'
  fs[`${home}/.ssh`].owner = user
  fs[home].owner = user
  fs[home].group = user

  return { fs, home, user }
}

// Path helpers operating on a flat path map.
export function normalizePath(cwd, p) {
  if (!p) return cwd
  let base = p.startsWith('/') ? p : `${cwd}/${p}`
  const parts = base.split('/').filter(Boolean)
  const out = []
  for (const part of parts) {
    if (part === '.') continue
    if (part === '..') out.pop()
    else out.push(part)
  }
  return `/${out.join('/')}`
}

export function listDir(fs, path) {
  const prefix = path === '/' ? '/' : `${path}/`
  const entries = new Set()
  Object.keys(fs).forEach((k) => {
    if (k === path) return
    if (k.startsWith(prefix)) {
      const rest = k.slice(prefix.length)
      const name = rest.split('/')[0]
      if (name) entries.add(name)
    }
  })
  return Array.from(entries).sort()
}
