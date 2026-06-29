// Bridges AWS EC2 Instance Connect to the existing FixitLab VMware/Linux and
// Windows simulation shells so SSH sessions behave like real lab terminals.
import { createLinuxShell } from '../../vmware/linuxShell'
import { createWindowsShell } from '../../vmware/windowsShell'
import { getInstanceType } from '../lib/instanceTypes'
import { defaultUser } from './vfs'
import { awsCli } from './awscli'
import { resolveEc2Workload, WORKLOAD_LABELS } from './ec2Workload'

function guestOsLabel(os) {
  const map = {
    'amazon-linux-2023': 'Amazon Linux 2023',
    'amazon-linux-2': 'Amazon Linux 2',
    'ubuntu-22.04': 'Ubuntu 22.04 LTS',
    'ubuntu-24.04': 'Ubuntu 24.04 LTS',
    'rhel-9': 'Red Hat Enterprise Linux 9',
    'debian-12': 'Debian GNU/Linux 12',
    'windows-server-2022': 'Windows Server 2022',
    'windows-server-2019': 'Windows Server 2019',
  }
  return map[os] || os || 'Linux'
}

function instanceToVm(instance) {
  const it = getInstanceType(instance.type)
  const hostname = `ip-${(instance.privateIp || '172.31.14.52').replace(/\./g, '-')}`
  return {
    id: instance.id,
    name: instance.name || instance.id,
    hostname,
    ip: instance.privateIp || '172.31.14.52',
    guest_os: guestOsLabel(instance.os),
    guest_os_version: guestOsLabel(instance.os),
    disk_gb: 30,
    memory_mb: Math.max(512, Math.round((it.memGiB || 1) * 1024)),
    cpu: it.vcpu || 1,
    workload: resolveEc2Workload(instance),
  }
}

function writeLines(onWrite, lines) {
  ;(lines || []).forEach((line) => onWrite(`${line}\r\n`))
}

/**
 * @param {object} instance EC2 instance from the AWS store
 * @param {{ store?: object, user?: string, onExit?: () => void }} opts
 */
export function createEc2SimShell(instance, opts = {}) {
  const workload = resolveEc2Workload(instance)
  const vm = instanceToVm(instance)
  const store = opts.store
  const onExit = opts.onExit

  if (workload === 'windows') {
    const win = createWindowsShell(vm)
    return {
      workload,
      workloadLabel: WORKLOAD_LABELS.windows,
      prompt: () => win.prompt(),
      history: win.history,
      run(rawLine, onWrite) {
        const line = rawLine.trim()
        if (!line) return
        const result = win.run(line)
        if (result.clear) onWrite('\x1b[2J\x1b[H')
        writeLines(onWrite, result.lines)
        if (result.exit && onExit) onExit()
      },
    }
  }

  const sshUser = opts.user || defaultUser(instance.os)
  const linux = createLinuxShell(vm, { user: sshUser })

  return {
    workload,
    workloadLabel: WORKLOAD_LABELS[workload] || WORKLOAD_LABELS.linux,
    prompt: () => linux.prompt(),
    history: linux.history,
    saveFile: linux.saveFile?.bind(linux),
    readFile: linux.readFile?.bind(linux),
    run(rawLine, onWrite) {
      const line = rawLine.trim()
      if (!line) return

      // Keep AWS CLI in the EC2 context (linuxShell does not implement `aws`).
      if (line === 'aws' || line.startsWith('aws ')) {
        const tokens = line.split(/\s+/)
        const args = tokens.slice(1)
        const result = awsCli(args, store, { region: instance.region })
        result.split('\n').forEach((row) => onWrite(`${row}\r\n`))
        linux.history.push(line)
        return
      }

      const result = linux.run(line)
      if (result.clear) onWrite('\x1b[2J\x1b[H')
      if (result.editor) {
        onWrite('\r\n\x1b[33m[Editor mode: use the in-lab terminal for vi/nano overlays — editing is supported via echo/cat > file here.]\x1b[0m\r\n')
        writeLines(onWrite, result.lines)
        return
      }
      writeLines(onWrite, result.lines)
      if (result.exit && onExit) onExit()
    },
  }
}

export { resolveEc2Workload, WORKLOAD_LABELS }
