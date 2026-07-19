// AWS CloudShell terminal — Amazon Linux 2023 with pre-installed AWS CLI v2 and Terraform.
import { createLinuxShell } from '../../vmware/linuxShell'
import { awsCli } from './awscli'
import { createTerraform } from './terraformSim'
import { createEc2SimShell } from './ec2SimBridge'
import { defaultUser } from './vfs'
import { findInstanceByHost, instanceAllowsInbound } from './sgReachability'

function writeLines(onWrite, lines) {
  ;(lines || []).forEach((line) => onWrite(`${line}\r\n`))
}

function cloudShellVm(region) {
  return {
    id: 'cloudshell',
    name: 'cloudshell',
    hostname: 'ip-10-0-0-12',
    ip: '10.0.0.12',
    guest_os: 'Amazon Linux 2023',
    guest_os_version: 'Amazon Linux 2023',
    disk_gb: 8,
    disks: [{ scsi_unit: 0, capacity_gb: 8, label: 'Root volume', scsi_id: '0:0' }],
    nics: [{ label: 'Eth0', mac_address: '02:00:00:00:00:01', connected: true }],
    memory_mb: 1024,
    cpu: 2,
    workload: 'linux',
    region,
  }
}

/** Seed starter IaC files in the CloudShell home directory (once per session). */
function seedCloudShellFiles(linux) {
  const home = linux.getCwd?.() || '/home/cloudshell-user'
  const mainTf = `terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = "${linux.region || 'us-east-1'}"
}

# Example — terraform plan / apply creates resources in this console
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  tags = { Name = "cloudshell-web" }
}
`
  if (!linux.readFile?.(`${home}/main.tf`)) {
    linux.saveFile?.(`${home}/main.tf`, mainTf)
  }
}

function parseSshTarget(line) {
  // ssh [-i key] user@host  OR  ssh host
  const parts = line.trim().split(/\s+/).slice(1).filter((p) => p && !p.startsWith('-'))
  const target = parts[0] || ''
  if (!target) return null
  if (target.includes('@')) {
    const [user, host] = target.split('@')
    return { user: user || '', host: host || '' }
  }
  return { user: '', host: target }
}

/**
 * @param {{ store: object, region?: string }} opts
 */
export function createCloudShellShell(opts = {}) {
  const store = opts.store
  const region = opts.region || store?.region || 'us-east-1'
  const vm = cloudShellVm(region)
  const linux = createLinuxShell(vm, { user: 'cloudshell-user' })
  linux.region = region
  seedCloudShellFiles(linux)

  const terraform = createTerraform({
    store,
    readFile: linux.readFile?.bind(linux),
    getCwd: linux.getCwd?.bind(linux),
    region,
  })

  let nested = null // active SSH session into an EC2 instance

  const shell = {
    workload: 'linux',
    workloadLabel: 'AWS CloudShell',
    prompt: () => (nested ? nested.prompt() : linux.prompt()),
    history: linux.history,
    saveFile: linux.saveFile?.bind(linux),
    readFile: linux.readFile?.bind(linux),
    run(rawLine, onWrite) {
      const line = rawLine.trim()
      if (!line) return

      // Inside an SSH session — `exit` returns to CloudShell.
      if (nested) {
        if (line === 'exit' || line === 'logout') {
          writeLines(onWrite, ['Connection to instance closed.'])
          nested = null
          return
        }
        nested.run(line, onWrite)
        return
      }

      if (line === 'aws' || line.startsWith('aws ')) {
        const args = line.split(/\s+/).slice(1)
        const result = awsCli(args, store, { region })
        result.split('\n').forEach((row) => onWrite(`${row}\r\n`))
        linux.history.push(line)
        return
      }

      if (line === 'terraform' || line.startsWith('terraform ')) {
        const args = line.split(/\s+/).slice(1)
        writeLines(onWrite, terraform.run(args))
        linux.history.push(line)
        return
      }

      if (line === 'ssh' || line.startsWith('ssh ')) {
        const parsed = parseSshTarget(line)
        if (!parsed?.host) {
          writeLines(onWrite, ['usage: ssh [-i key] [user@]hostname'])
          linux.history.push(line)
          return
        }
        const liveStore = store || opts.store
        const instance = findInstanceByHost(liveStore, parsed.host)
        if (!instance) {
          writeLines(onWrite, [
            `ssh: Could not resolve hostname ${parsed.host}: Name or service not known`,
          ])
          linux.history.push(line)
          return
        }
        if (instance.state !== 'running') {
          writeLines(onWrite, [
            `ssh: connect to host ${parsed.host} port 22: Connection refused`,
            `(instance ${instance.id} is ${instance.state})`,
          ])
          linux.history.push(line)
          return
        }
        if (!instanceAllowsInbound(liveStore, instance, 22, 'TCP')) {
          writeLines(onWrite, [
            `ssh: connect to host ${parsed.host} port 22: Connection timed out`,
            `(security group does not allow inbound TCP/22 from 0.0.0.0/0 — open SSH in the instance SG)`,
          ])
          linux.history.push(line)
          return
        }
        const user = parsed.user || defaultUser(instance.os)
        nested = createEc2SimShell(instance, {
          store: liveStore,
          user,
          labSessionId: `cloudshell-ssh-${instance.id}`,
          onExit: () => { nested = null },
        })
        writeLines(onWrite, [
          `Connecting to ${instance.id} (${parsed.host}) as ${user}…`,
          `Last login: ${new Date().toUTCString()} from cloudshell`,
        ])
        linux.history.push(line)
        return
      }

      const result = linux.run(line)
      if (result.clear) onWrite('\x1b[2J\x1b[H')
      if (result.editor) {
        onWrite('\r\n\x1b[33m[Editor: use cat > file or your EC2 SSH session for vi/nano overlays.]\x1b[0m\r\n')
        writeLines(onWrite, result.lines)
        return
      }
      writeLines(onWrite, result.lines)
    },
  }
  return shell
}
