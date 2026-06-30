// AWS CloudShell terminal — Amazon Linux 2023 with pre-installed AWS CLI v2 and Terraform.
import { createLinuxShell } from '../../vmware/linuxShell'
import { awsCli } from './awscli'
import { createTerraform } from './terraformSim'

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

# Example — terraform plan / apply creates resources in this simulation console
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

  return {
    workload: 'linux',
    workloadLabel: 'AWS CloudShell',
    prompt: () => linux.prompt(),
    history: linux.history,
    saveFile: linux.saveFile?.bind(linux),
    readFile: linux.readFile?.bind(linux),
    run(rawLine, onWrite) {
      const line = rawLine.trim()
      if (!line) return

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
}
