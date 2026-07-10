// Bridges AWS EC2 Instance Connect to the existing FixitLab VMware/Linux and
// Windows simulation shells so SSH sessions behave like real lab terminals.
import { createLinuxShell } from '../../vmware/linuxShell'
import { createWindowsShell } from '../../vmware/windowsShell'
import { getInstanceType } from '../lib/instanceTypes'
import { defaultUser } from './vfs'
import { awsCli } from './awscli'
import { createTerraform } from './terraformSim'
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

function instanceToVm(instance, store) {
  const it = getInstanceType(instance.type)
  const hostname = `ip-${(instance.privateIp || '172.31.14.52').replace(/\./g, '-')}`
  const attached = (store?.volumes || []).filter((v) => v.attachedTo === instance.id)
  const rootVol = attached.find((v) => (v.device || '').includes('xvda') || (v.device || '').includes('sda')) || attached[0]
  const diskGb = rootVol?.size || 30
  const disks = attached.map((v, i) => ({
    scsi_unit: i,
    capacity_gb: v.size || 8,
    label: i === 0 ? 'Root volume' : `EBS volume ${i + 1}`,
    scsi_id: `0:${i}`,
  }))
  return {
    id: instance.id,
    name: instance.name || instance.id,
    hostname,
    ip: instance.privateIp || '172.31.14.52',
    guest_os: guestOsLabel(instance.os),
    guest_os_version: guestOsLabel(instance.os),
    disk_gb: diskGb,
    disks,
    nics: [{ label: 'Eth0', mac_address: '02:00:00:00:00:01', connected: true }],
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
  const vm = instanceToVm(instance, store)
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
  const linux = createLinuxShell(vm, {
    user: sshUser,
    labSessionId: opts.labSessionId || `ec2-${instance.id}`,
  })
  // Terraform engine shares the AWS store, so `terraform apply` here creates
  // EC2/S3/SG resources that appear in the console — the full IaC → AWS stack.
  const terraform = createTerraform({
    store,
    readFile: linux.readFile?.bind(linux),
    getCwd: linux.getCwd?.bind(linux),
    region: instance.region,
  })

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

      // Terraform — operates on the same AWS store (linuxShell has no `terraform`).
      if (line === 'terraform' || line.startsWith('terraform ')) {
        const args = line.split(/\s+/).slice(1)
        writeLines(onWrite, terraform.run(args))
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
