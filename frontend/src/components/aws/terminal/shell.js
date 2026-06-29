// Bash-like command interpreter for a simulated EC2 instance. Each Shell binds
// to one instance's OS + virtual filesystem. run(line, onWrite) executes a
// command, streaming output through onWrite (supports incremental output for
// ping/top). Backed by the AWS store for `aws` CLI + system facts.
import { createVfs, normalizePath, listDir, kernelVersion } from './vfs'
import { getInstanceType } from '../lib/instanceTypes'
import { awsCli } from './awscli'

const RESET = '\x1b[0m'
const RED = '\x1b[31m'
const GREEN = '\x1b[32m'
const BLUE = '\x1b[1;34m'
const CYAN = '\x1b[36m'

export class Shell {
  constructor({ instance, store }) {
    this.store = store
    this.instance = instance
    this.os = instance.os
    this.hostname = `ip-${(instance.privateIp || '172.31.14.52').replace(/\./g, '-')}`
    this.privateIp = instance.privateIp || '172.31.14.52'
    this.publicIp = instance.publicIp || ''
    const { fs, home, user } = createVfs(this.os, this.hostname, this.privateIp, instance.sshUser)
    this.storageKey = `aws-sim-vfs:${instance.id}:${user}`
    this.fs = fs
    try {
      const saved = JSON.parse(localStorage.getItem(this.storageKey) || 'null')
      if (saved && typeof saved === 'object') this.fs = saved
    } catch {
      this.fs = fs
    }
    this.user = user
    this.home = home
    this.cwd = home
    this.history = []
    this.env = {
      HOME: home, USER: user, LOGNAME: user, SHELL: '/bin/bash', PWD: home,
      PATH: '/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin', LANG: 'C.UTF-8',
      HOSTNAME: this.hostname, TERM: 'xterm-256color', AWS_DEFAULT_REGION: instance.region,
    }
  }

  prompt() {
    const cwdLabel = this.cwd === this.home ? '~' : this.cwd.split('/').pop() || '/'
    if (this.os.startsWith('ubuntu') || this.os === 'debian-12') {
      return `${GREEN}${this.user}@${this.hostname}${RESET}:${BLUE}${cwdLabel === '~' ? '~' : this.cwd}${RESET}$ `
    }
    return `[${this.user}@${this.hostname} ${cwdLabel}]$ `
  }

  resolve(p) { return normalizePath(this.cwd, p) }

  async run(rawLine, onWrite) {
    const line = rawLine.trim()
    if (line) this.history.push(line)
    if (!line) return
    // Output redirection (very small subset): cmd > file / cmd >> file
    let redirect = null
    let work = line
    const rm = work.match(/(.*?)\s+(>>?)\s+(\S+)\s*$/)
    if (rm) { work = rm[1]; redirect = { mode: rm[2], path: this.resolve(rm[3]) } }

    const tokens = work.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || []
    const cleaned = tokens.map((t) => t.replace(/^['"]|['"]$/g, '').replace(/\$(\w+)/g, (_, v) => this.env[v] || ''))
    const cmd = cleaned[0]
    const args = cleaned.slice(1)

    const collected = []
    const out = (text) => {
      if (redirect) collected.push(text)
      else onWrite(text)
    }

    const handler = this.commands[cmd]
    if (handler) {
      await handler.call(this, args, out, onWrite)
    } else if (cmd === undefined) {
      // empty
    } else {
      onWrite(`${RED}bash: ${cmd}: command not found${RESET}\r\n`)
    }

    if (redirect) {
      const content = collected.join('').replace(/\r\n/g, '\n').replace(/\x1b\[[0-9;]*m/g, '')
      const existing = this.fs[redirect.path]
      const prev = redirect.mode === '>>' && existing?.type === 'file' ? existing.content : ''
      this.fs[redirect.path] = { type: 'file', content: prev + content, mode: '-rw-r--r--', owner: this.user, group: this.user }
    }
    this.persist()
  }

  nl(out, s = '') { out(`${s}\r\n`) }

  persist() {
    try { localStorage.setItem(this.storageKey, JSON.stringify(this.fs)) } catch { /* ignore quota/private mode */ }
  }

  get commands() {
    if (this._commands) return this._commands
    const c = {}

    c.pwd = function (a, out) { this.nl(out, this.cwd) }
    c.clear = function (a, out) { out('\x1b[2J\x1b[H') }
    c.echo = function (a, out) {
      let arr = a
      if (arr[0] === '-n') { out(arr.slice(1).join(' ')); return }
      if (arr[0] === '-e') arr = arr.slice(1)
      this.nl(out, arr.join(' '))
    }
    c.whoami = function (a, out) { this.nl(out, this.user) }
    c.hostname = function (a, out) { this.nl(out, a[0] === '-f' ? `${this.hostname}.ec2.internal` : a[0] === '-I' || a[0] === '-i' ? this.privateIp : this.hostname) }
    c.id = function (a, out) { this.nl(out, `uid=1000(${this.user}) gid=1000(${this.user}) groups=1000(${this.user}),4(adm),10(wheel)`) }
    c.uptime = function (a, out) { this.nl(out, ` ${new Date().toTimeString().slice(0, 8)} up 2:34,  1 user,  load average: 0.00, 0.01, 0.05`) }
    c.date = function (a, out) { this.nl(out, new Date().toString()) }
    c.env = c.printenv = function (a, out) { Object.entries(this.env).forEach(([k, v]) => this.nl(out, `${k}=${v}`)) }
    c.export = function (a, out) { a.forEach((kv) => { const [k, ...v] = kv.split('='); if (v.length) this.env[k] = v.join('=') }) }
    c.history = function (a, out) { this.history.forEach((h, i) => this.nl(out, `${String(i + 1).padStart(5)}  ${h}`)) }
    c.exit = c.logout = function (a, out) { this.nl(out, 'logout'); if (this.onExit) this.onExit() }

    c.uname = function (a, out) {
      if (a.includes('-a')) { this.nl(out, `Linux ${this.hostname} ${kernelVersion(this.os)} #1 SMP x86_64 x86_64 x86_64 GNU/Linux`); return }
      if (a.includes('-r')) { this.nl(out, kernelVersion(this.os)); return }
      if (a.includes('-m')) { this.nl(out, 'x86_64'); return }
      if (a.includes('-n')) { this.nl(out, this.hostname); return }
      this.nl(out, 'Linux')
    }
    c.hostnamectl = function (a, out) {
      this.nl(out, `   Static hostname: ${this.hostname}`)
      this.nl(out, `         Icon name: computer-vm`)
      this.nl(out, `           Chassis: vm`)
      this.nl(out, `    Virtualization: amazon`)
      this.nl(out, `  Operating System: ${this.os}`)
      this.nl(out, `            Kernel: Linux ${kernelVersion(this.os)}`)
      this.nl(out, `      Architecture: x86-64`)
    }

    c.lscpu = function (a, out) {
      const it = getInstanceType(this.instance.type)
      this.nl(out, 'Architecture:            x86_64')
      this.nl(out, '  CPU op-mode(s):        32-bit, 64-bit')
      this.nl(out, '  Byte Order:            Little Endian')
      this.nl(out, `CPU(s):                  ${it.vcpu}`)
      this.nl(out, `  Vendor ID:             GenuineIntel`)
      this.nl(out, `  Model name:            Intel(R) Xeon(R) CPU E5-2686 v4 @ 2.30GHz`)
      this.nl(out, `  Thread(s) per core:    ${it.vcpu > 1 ? 2 : 1}`)
      this.nl(out, `  Hypervisor vendor:     ${this.os.startsWith('amazon') ? 'KVM' : 'Xen'}`)
    }
    c.free = function (a, out) {
      const it = getInstanceType(this.instance.type)
      const total = Math.round(it.memGiB * 1024 * 1024)
      const used = Math.round(total * 0.28)
      const buff = Math.round(total * 0.22)
      const free = total - used - buff
      const fmt = a.includes('-h')
        ? (kb) => (kb > 1048576 ? `${(kb / 1048576).toFixed(1)}Gi` : `${Math.round(kb / 1024)}Mi`)
        : (kb) => String(kb)
      this.nl(out, '               total        used        free      shared  buff/cache   available')
      this.nl(out, `Mem:    ${String(fmt(total)).padStart(12)}${String(fmt(used)).padStart(12)}${String(fmt(free)).padStart(12)}${String(fmt(0)).padStart(12)}${String(fmt(buff)).padStart(12)}${String(fmt(free + buff)).padStart(12)}`)
      this.nl(out, `Swap:   ${String(fmt(0)).padStart(12)}${String(fmt(0)).padStart(12)}${String(fmt(0)).padStart(12)}`)
    }
    c.df = function (a, out) {
      const vol = this.store.volumes.find((v) => v.id === this.instance.rootVolume)
      const size = vol ? vol.size : 8
      const used = Math.round(size * 0.19 * 10) / 10
      this.nl(out, 'Filesystem      Size  Used Avail Use% Mounted on')
      this.nl(out, `/dev/xvda1      ${size}.0G  ${used}G  ${(size - used).toFixed(1)}G  19% /`)
      this.nl(out, 'tmpfs           ' + `${(getInstanceType(this.instance.type).memGiB / 2).toFixed(1)}G     0  ${(getInstanceType(this.instance.type).memGiB / 2).toFixed(1)}G   0% /dev/shm`)
    }
    c.lsblk = function (a, out) {
      const vol = this.store.volumes.find((v) => v.id === this.instance.rootVolume)
      const size = vol ? vol.size : 8
      this.nl(out, 'NAME    MAJ:MIN RM SIZE RO TYPE MOUNTPOINTS')
      this.nl(out, `xvda    202:0    0  ${size}G  0 disk`)
      this.nl(out, `└─xvda1 202:1    0  ${size}G  0 part /`)
    }

    c.ps = function (a, out) {
      this.nl(out, 'USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND')
      this.nl(out, 'root           1  0.0  0.3 169436 12648 ?        Ss   09:00   0:01 /usr/lib/systemd/systemd')
      this.nl(out, 'root         456  0.0  0.2  92456  6320 ?        Ss   09:00   0:00 sshd: /usr/sbin/sshd -D')
      this.nl(out, 'root         512  0.0  0.1  84320  3120 ?        S    09:00   0:00 /usr/sbin/chronyd')
      this.nl(out, `${this.user}      791  0.0  0.1 124500  5200 pts/0    Ss   09:01   0:00 -bash`)
      this.nl(out, `${this.user}      842  0.0  0.0 156360  3680 pts/0    R+   09:05   0:00 ps ${a.join(' ')}`)
    }
    c.top = c.htop = async function (a, out, onWrite) {
      const it = getInstanceType(this.instance.type)
      const render = () => {
        const cpu = (Math.random() * 8).toFixed(1)
        onWrite('\x1b[2J\x1b[H')
        this.nl(onWrite, `top - ${new Date().toTimeString().slice(0, 8)} up 2:34,  1 user,  load average: 0.00, 0.01, 0.05`)
        this.nl(onWrite, 'Tasks: 142 total,   1 running, 141 sleeping,   0 stopped,   0 zombie')
        this.nl(onWrite, `%Cpu(s):  ${cpu} us,  0.7 sy,  0.0 ni, ${(99 - cpu).toFixed(1)} id,  0.0 wa`)
        this.nl(onWrite, `MiB Mem : ${(it.memGiB * 1024).toFixed(1)} total,   ${(it.memGiB * 1024 * 0.5).toFixed(1)} free`)
        this.nl(onWrite, '')
        this.nl(onWrite, '    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND')
        this.nl(onWrite, `      1 root      20   0  169436  12648   8200 S   0.0   0.3   0:01.20 systemd`)
        this.nl(onWrite, `    791 ${this.user.padEnd(8)}  20   0  124500   5200   3400 S   0.0   0.1   0:00.30 bash`)
        this.nl(onWrite, '')
        this.nl(onWrite, `${CYAN}(press q to quit)${RESET}`)
      }
      render()
      await new Promise((resolve) => {
        const iv = setInterval(render, 2500)
        this._interrupt = () => { clearInterval(iv); this._interrupt = null; onWrite('\r\n'); resolve() }
      })
    }

    c.ip = function (a, out) {
      if (a[0] === 'addr' || a[0] === 'a' || (a[0] === 'address')) {
        this.nl(out, '1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default')
        this.nl(out, '    inet 127.0.0.1/8 scope host lo')
        this.nl(out, '2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 9001 qdisc mq state UP group default qlen 1000')
        this.nl(out, `    link/ether 0a:1b:2c:3d:4e:5f brd ff:ff:ff:ff:ff:ff`)
        this.nl(out, `    inet ${this.privateIp}/20 brd 172.31.31.255 scope global dynamic eth0`)
      } else if (a[0] === 'route' || a[0] === 'r') {
        this.nl(out, `default via 172.31.0.1 dev eth0 proto dhcp src ${this.privateIp} metric 100`)
        this.nl(out, `172.31.0.0/20 dev eth0 proto kernel scope link src ${this.privateIp}`)
      } else this.nl(out, 'Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }')
    }
    c.ifconfig = function (a, out) {
      this.nl(out, `eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 9001`)
      this.nl(out, `        inet ${this.privateIp}  netmask 255.255.240.0  broadcast 172.31.31.255`)
      this.nl(out, `        ether 0a:1b:2c:3d:4e:5f  txqueuelen 1000  (Ethernet)`)
      this.nl(out, 'lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536')
      this.nl(out, '        inet 127.0.0.1  netmask 255.0.0.0')
    }

    c.ping = async function (a, out, onWrite) {
      const host = a.filter((x) => !x.startsWith('-')).pop() || '8.8.8.8'
      const cIdx = a.indexOf('-c')
      const count = cIdx >= 0 ? parseInt(a[cIdx + 1], 10) : 4
      this.nl(onWrite, `PING ${host} (${/^\d/.test(host) ? host : '8.8.8.8'}) 56(84) bytes of data.`)
      let recv = 0
      for (let seq = 1; seq <= count; seq += 1) {
        // eslint-disable-next-line no-await-in-loop
        await new Promise((r) => setTimeout(r, 600))
        if (this._aborted) break
        const t = (10 + Math.random() * 8).toFixed(1)
        recv += 1
        this.nl(onWrite, `64 bytes from ${/^\d/.test(host) ? host : '8.8.8.8'}: icmp_seq=${seq} ttl=52 time=${t} ms`)
      }
      this.nl(onWrite, '')
      this.nl(onWrite, `--- ${host} ping statistics ---`)
      const loss = Math.round(((count - recv) / count) * 100)
      this.nl(onWrite, `${count} packets transmitted, ${recv} received, ${loss}% packet loss, time ${count * 1000}ms`)
      this.nl(onWrite, 'rtt min/avg/max/mdev = 10.112/13.402/17.881/2.110 ms')
    }

    c.curl = async function (a, out, onWrite) {
      const url = a.filter((x) => !x.startsWith('-')).pop() || ''
      const meta = '169.254.169.254/latest/meta-data'
      if (url.includes(`${meta}/instance-id`)) { out(this.instance.id); return }
      if (url.includes(`${meta}/local-ipv4`)) { out(this.privateIp); return }
      if (url.includes(`${meta}/public-ipv4`)) { out(this.publicIp || '169.254.169.254'); return }
      if (url.includes(`${meta}/placement/availability-zone`)) { out(this.instance.az); return }
      if (url.includes(`${meta}/instance-type`)) { out(this.instance.type); return }
      if (url.includes(`${meta}/iam/security-credentials/`) && url.trim().endsWith('security-credentials/')) { out(this.instance.iamRole || ''); return }
      if (url.includes(`${meta}/`)) { this.nl(out, 'ami-id\nhostname\ninstance-id\ninstance-type\nlocal-ipv4\nmac\nplacement/\npublic-ipv4\nsecurity-groups'); return }
      if (url.includes('checkip.amazonaws.com') || url.includes('ifconfig.me')) { this.nl(out, this.publicIp || '54.210.123.45'); return }
      if (a.includes('-I')) { this.nl(out, 'HTTP/1.1 200 OK'); this.nl(out, 'Server: nginx/1.24.0'); this.nl(out, 'Content-Type: text/html'); return }
      await new Promise((r) => setTimeout(r, 400))
      this.nl(out, `<!DOCTYPE html><html><head><title>Welcome</title></head><body><h1>It works! (${url || 'localhost'})</h1></body></html>`)
    }
    c.wget = async function (a, out) {
      const url = a.filter((x) => !x.startsWith('-')).pop() || ''
      this.nl(out, `--${new Date().toISOString().slice(0, 19)}--  ${url}`)
      this.nl(out, 'Resolving host... 93.184.216.34')
      this.nl(out, 'HTTP request sent, awaiting response... 200 OK')
      this.nl(out, "Length: 1256 (1.2K) [text/html]")
      this.nl(out, "100%[===================>] 1,256       --.-K/s   in 0s")
      this.nl(out, 'saved')
    }

    c.ls = function (a, out) {
      const flags = a.filter((x) => x.startsWith('-')).join('')
      const long = flags.includes('l')
      const all = flags.includes('a')
      const target = a.find((x) => !x.startsWith('-'))
      const path = this.resolve(target || '.')
      if (!this.fs[path]) { this.nl(out, `${RED}ls: cannot access '${target}': No such file or directory${RESET}`); return }
      if (this.fs[path].type === 'file') { this.nl(out, target); return }
      let entries = listDir(this.fs, path)
      if (all) entries = ['.', '..', ...entries]
      if (long) {
        this.nl(out, `total ${entries.length * 4}`)
        entries.forEach((name) => {
          const full = name === '.' ? path : name === '..' ? normalizePath(path, '..') : normalizePath(path, name)
          const node = this.fs[full] || { type: 'dir', mode: 'drwxr-xr-x', owner: 'root', group: 'root' }
          const isDir = node.type === 'dir'
          const size = node.type === 'file' ? (node.content || '').length : 4096
          const display = isDir ? `${BLUE}${name}${RESET}` : name
          this.nl(out, `${node.mode || (isDir ? 'drwxr-xr-x' : '-rw-r--r--')} 1 ${(node.owner || 'root').padEnd(8)} ${(node.group || 'root').padEnd(8)} ${String(size).padStart(6)} Mar  1 10:00 ${display}`)
        })
      } else {
        const colored = entries.map((name) => {
          const full = normalizePath(path, name)
          return this.fs[full]?.type === 'dir' || ['.', '..'].includes(name) ? `${BLUE}${name}${RESET}` : name
        })
        if (colored.length) this.nl(out, colored.join('  '))
      }
    }
    c.cd = function (a, out) {
      const target = a[0] || this.home
      const path = target === '-' ? this.home : target === '~' ? this.home : this.resolve(target.replace(/^~/, this.home))
      if (!this.fs[path]) { this.nl(out, `${RED}-bash: cd: ${target}: No such file or directory${RESET}`); return }
      if (this.fs[path].type !== 'dir') { this.nl(out, `${RED}-bash: cd: ${target}: Not a directory${RESET}`); return }
      this.cwd = path
      this.env.PWD = path
    }
    c.cat = function (a, out) {
      const files = a.filter((x) => !x.startsWith('-'))
      if (!files.length) { this.nl(out, '(reading from stdin not supported in this terminal)'); return }
      files.forEach((f) => {
        const path = this.resolve(f)
        const node = this.fs[path]
        if (!node) { this.nl(out, `${RED}cat: ${f}: No such file or directory${RESET}`); return }
        if (node.type === 'dir') { this.nl(out, `${RED}cat: ${f}: Is a directory${RESET}`); return }
        (node.content || '').split('\n').forEach((l, i, arr) => { if (i < arr.length - 1 || l) this.nl(out, l) })
      })
    }
    c.head = function (a, out) {
      const nIdx = a.indexOf('-n')
      const n = nIdx >= 0 ? parseInt(a[nIdx + 1], 10) : 10
      const f = a.filter((x) => !x.startsWith('-') && x !== String(n))[0]
      const node = f && this.fs[this.resolve(f)]
      if (!node || node.type !== 'file') { this.nl(out, `${RED}head: cannot open '${f}'${RESET}`); return }
      node.content.split('\n').slice(0, n).forEach((l) => this.nl(out, l))
    }
    c.tail = function (a, out) {
      const nIdx = a.indexOf('-n')
      const n = nIdx >= 0 ? parseInt(a[nIdx + 1], 10) : 10
      const f = a.filter((x) => !x.startsWith('-') && x !== String(n))[0]
      const node = f && this.fs[this.resolve(f)]
      if (!node || node.type !== 'file') { this.nl(out, `${RED}tail: cannot open '${f}'${RESET}`); return }
      const lines = node.content.split('\n').filter((l) => l !== '')
      lines.slice(-n).forEach((l) => this.nl(out, l))
    }
    c.grep = function (a, out) {
      const flags = a.filter((x) => x.startsWith('-'))
      const rest = a.filter((x) => !x.startsWith('-'))
      const pattern = rest[0]
      const files = rest.slice(1)
      const ignoreCase = flags.some((f) => f.includes('i'))
      const re = new RegExp(pattern, ignoreCase ? 'i' : '')
      files.forEach((f) => {
        const node = this.fs[this.resolve(f)]
        if (!node || node.type !== 'file') return
        node.content.split('\n').forEach((l) => {
          if (re.test(l)) this.nl(out, files.length > 1 ? `${f}:${l.replace(re, (m) => `${RED}${m}${RESET}`)}` : l.replace(re, (m) => `${RED}${m}${RESET}`))
        })
      })
    }
    c.wc = function (a, out) {
      const f = a.filter((x) => !x.startsWith('-'))[0]
      const node = f && this.fs[this.resolve(f)]
      if (!node || node.type !== 'file') { this.nl(out, `${RED}wc: ${f}: No such file${RESET}`); return }
      const text = node.content
      const lines = text.split('\n').length - 1
      const words = text.split(/\s+/).filter(Boolean).length
      this.nl(out, ` ${lines} ${words} ${text.length} ${f}`)
    }
    c.mkdir = function (a, out) {
      a.filter((x) => !x.startsWith('-')).forEach((d) => { this.fs[this.resolve(d)] = { type: 'dir', mode: 'drwxr-xr-x', owner: this.user, group: this.user } })
    }
    c.touch = function (a, out) {
      a.filter((x) => !x.startsWith('-')).forEach((f) => { const p = this.resolve(f); if (!this.fs[p]) this.fs[p] = { type: 'file', content: '', mode: '-rw-r--r--', owner: this.user, group: this.user } })
    }
    c.rm = function (a, out) {
      const recursive = a.some((x) => x.startsWith('-') && (x.includes('r') || x.includes('R')))
      a.filter((x) => !x.startsWith('-')).forEach((f) => {
        const p = this.resolve(f)
        if (!this.fs[p]) { this.nl(out, `${RED}rm: cannot remove '${f}': No such file or directory${RESET}`); return }
        if (this.fs[p].type === 'dir' && !recursive) { this.nl(out, `${RED}rm: cannot remove '${f}': Is a directory${RESET}`); return }
        Object.keys(this.fs).forEach((k) => { if (k === p || k.startsWith(`${p}/`)) delete this.fs[k] })
      })
    }
    c.cp = function (a, out) {
      const files = a.filter((x) => !x.startsWith('-'))
      const [src, dest] = files
      const sp = this.resolve(src); const dp = this.resolve(dest)
      if (!this.fs[sp]) { this.nl(out, `${RED}cp: cannot stat '${src}': No such file or directory${RESET}`); return }
      this.fs[dp] = { ...this.fs[sp], owner: this.user }
    }
    c.mv = function (a, out) {
      const files = a.filter((x) => !x.startsWith('-'))
      const [src, dest] = files
      const sp = this.resolve(src); const dp = this.resolve(dest)
      if (!this.fs[sp]) { this.nl(out, `${RED}mv: cannot stat '${src}': No such file or directory${RESET}`); return }
      this.fs[dp] = this.fs[sp]; delete this.fs[sp]
    }
    c.which = function (a, out) {
      const known = ['ls', 'cat', 'aws', 'curl', 'wget', 'python3', 'bash', 'sudo', 'systemctl', 'grep', 'vi', 'docker', 'git']
      a.forEach((cmd) => { if (known.includes(cmd)) this.nl(out, `/usr/bin/${cmd}`); else this.nl(out, `${RED}/usr/bin/which: no ${cmd} in (${this.env.PATH})${RESET}`) })
    }
    c.sudo = async function (a, out, onWrite) {
      if (!a.length) { this.nl(out, 'usage: sudo command'); return }
      if (a[0] === '-i' || (a[0] === 'su')) { this.nl(out, '(switched to root — passwordless sudo configured for this user)'); return }
      // Re-run remaining as the same shell (passwordless).
      await this.run(a.join(' '), onWrite)
    }
    c.su = function (a, out) { this.nl(out, 'Password: (passwordless sudo is configured; use `sudo -i` for root)') }

    c.systemctl = function (a, out) {
      const sub = a[0]; const unit = a[1] || ''
      const services = { 'sshd.service': 'active (running)', 'chronyd.service': 'active (running)', 'amazon-ssm-agent.service': 'active (running)', 'crond.service': 'active (running)', 'nginx.service': 'inactive (dead)' }
      if (sub === 'status') {
        const st = services[unit] || services[`${unit}.service`] || 'could not be found'
        const active = st.includes('running')
        this.nl(out, `${active ? GREEN + '●' + RESET : '○'} ${unit} - ${unit.replace('.service', '')} daemon`)
        this.nl(out, `     Loaded: loaded (/usr/lib/systemd/system/${unit}; enabled; preset: enabled)`)
        this.nl(out, `     Active: ${active ? GREEN : RED}${st}${RESET} since ${new Date().toUTCString()}`)
        if (active) this.nl(out, `   Main PID: ${456 + Math.floor(Math.random() * 400)} (${unit.replace('.service', '')})`)
        return
      }
      if (['start', 'stop', 'restart', 'enable', 'disable', 'reload'].includes(sub)) { return }
      if (sub === 'list-units') { this.nl(out, 'UNIT                  LOAD   ACTIVE SUB     DESCRIPTION'); Object.entries(services).forEach(([u, st]) => this.nl(out, `${u.padEnd(22)}loaded ${st.includes('running') ? 'active running' : 'inactive dead'} ${u}`)); return }
      this.nl(out, '')
    }
    c.service = function (a, out) { this.commands.systemctl.call(this, [a[1], a[0]], out) }
    c.journalctl = function (a, out) {
      this.nl(out, `-- Logs begin at ${new Date().toUTCString()} --`)
      this.nl(out, `Mar 01 10:00:01 ${this.hostname} systemd[1]: Started Daily Cleanup of Temporary Directories.`)
      this.nl(out, `Mar 01 10:00:02 ${this.hostname} sshd[789]: Accepted publickey for ${this.user}`)
    }

    const pkgInstall = async function (a, out, onWrite, mgr) {
      const pkgs = a.filter((x) => !x.startsWith('-') && !['install', 'update', 'upgrade', 'remove'].includes(x))
      if (a.includes('update')) { this.nl(onWrite, `${mgr} metadata refreshed.`); return }
      if (!pkgs.length) { this.nl(onWrite, `Usage: ${mgr} install <package>`); return }
      this.nl(onWrite, `Resolving dependencies...`)
      await new Promise((r) => setTimeout(r, 500))
      pkgs.forEach((p) => this.nl(onWrite, `Installing : ${p}-1.0.0`))
      await new Promise((r) => setTimeout(r, 400))
      this.nl(onWrite, `Complete! Installed ${pkgs.length} package(s).`)
    }
    c.yum = function (a, out, onWrite) { return pkgInstall.call(this, a, out, onWrite, 'yum') }
    c.dnf = function (a, out, onWrite) { return pkgInstall.call(this, a, out, onWrite, 'dnf') }
    c.apt = c['apt-get'] = function (a, out, onWrite) { return pkgInstall.call(this, a, out, onWrite, 'apt') }
    c.pip3 = c.pip = function (a, out, onWrite) { return pkgInstall.call(this, a, out, onWrite, 'pip') }

    c.man = function (a, out) {
      this.nl(out, `${(a[0] || 'man').toUpperCase()}(1)                  User Commands`)
      this.nl(out, '')
      this.nl(out, `NAME\n       ${a[0]} - simulated manual page`)
      this.nl(out, '\nDESCRIPTION\n       This is a simulated AWS environment. Common flags and behavior are supported.')
    }
    c.help = function (a, out) {
      this.nl(out, 'Simulated bash. Supported: ls cd pwd cat echo grep head tail wc mkdir touch rm cp mv')
      this.nl(out, 'whoami id uname hostname free df lsblk ps top ip ifconfig ping curl wget')
      this.nl(out, 'systemctl journalctl yum dnf apt pip3 sudo which env export history aws clear exit')
    }

    c.aws = function (a, out) {
      const result = awsCli(a, this.store, { region: this.instance.region })
      result.split('\n').forEach((l) => this.nl(out, l))
    }

    c.python3 = c.python = function (a, out) {
      if (a.includes('-c')) { this.nl(out, '(simulated python execution)'); return }
      this.nl(out, 'Python 3.12.0 (main, simulated) on linux')
      this.nl(out, 'Type "help", "copyright", "credits" or "license" for more information.')
      this.nl(out, '(interactive REPL not supported in this terminal — use python3 -c)')
    }

    this._commands = c
    return c
  }
}
