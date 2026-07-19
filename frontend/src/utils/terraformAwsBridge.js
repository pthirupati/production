/**
 * Sync Terraform apply results into the AWS console store so learners
 * can verify resources visually after `terraform apply` in the lab IDE.
 *
 * This delegates to the same HCL tokenizer the terminal engine uses
 * (components/aws/terminal/hclParser.js), so the IDE-driven apply path creates
 * the same accurate resources as the terminal `terraform apply` path — honoring
 * multiple resources, count, real key names / security groups, and full ingress
 * rules — instead of the old single-regex parser that hardcoded most values.
 *
 * Azure (azurerm_*) and GCP (google_*) resources are mirrored into the
 * server-authoritative Azure/GCP portal engines for the same lab sessionId.
 */
import { useAwsStore } from '../components/aws/store/awsStore'
import { parseHcl, parseBody } from '../components/aws/terminal/hclParser'
import { awsCli } from '../components/aws/terminal/awscli'
import { azureApi } from '../api/azure'
import { gcpApi } from '../api/gcp'

// Resource addresses already mirrored into the console this page session, so a
// re-apply of an unchanged config does not duplicate instances/buckets/SGs.
// Mirrors the per-session apply ledger the terminal engine keeps in
// terraformSim.js. Cleared on lab teardown (resetTerraformAwsLabState).
const syncedAddresses = new Set()

/** Concatenate every *.tf file in the workspace so multi-file configs parse. */
export function collectHcl(files = {}) {
  let src = ''
  for (const [key, content] of Object.entries(files)) {
    if (typeof content !== 'string') continue
    // Backend stores dotted keys (main.tf); tolerate underscore keys (main_tf) too.
    if (/(\.|_)tf$/.test(key)) src += `\n${content}\n`
  }
  return src
}

/**
 * Mirror a single parsed HCL resource into the shared AWS store. Returns the
 * created store handles (ids / names) so callers can build both a `markLabManaged`
 * ledger and progressive `terraform apply` output. Idempotent per address via the
 * shared `syncedAddresses` ledger, so re-applying an unchanged config is a no-op.
 */
function createResourceInStore(store, r, region) {
  const address = `${r.type}.${r.name}`
  if (syncedAddresses.has(address)) return []
  const attrs = r.attrs || {}
  const created = []

  if (r.type === 'aws_instance') {
    const count = Number(attrs.count) || 1
    const name = (attrs.tags && attrs.tags.Name) || r.name
    const launched = store.launchInstances({
      name,
      amiId: attrs.ami || undefined,
      type: attrs.instance_type || 't3.micro',
      count,
      keyName: attrs.key_name || '',
      subnetId: attrs.subnet_id || '',
      securityGroups: Array.isArray(attrs.vpc_security_group_ids) ? attrs.vpc_security_group_ids : [],
      volumeSize: attrs.root_block_device?.volume_size || 8,
      volumeType: attrs.root_block_device?.volume_type || 'gp3',
      monitoring: !!attrs.monitoring,
      tags: attrs.tags || {},
    }) || []
    created.push(...launched.map((i) => i.id))
  } else if (r.type === 'aws_s3_bucket') {
    const bucketName = attrs.bucket || r.name
    if (!store.s3Buckets?.some((b) => b.name === bucketName)) {
      store.createBucket?.({ name: bucketName, region, blockPublic: true })
      created.push(`bucket:${bucketName}`)
    }
  } else if (r.type === 'aws_security_group') {
    const sgName = attrs.name || r.name
    if (!store.securityGroups?.some((sg) => sg.name === sgName)) {
      const inbound = (r.blocks || []).filter((b) => b.key === 'ingress').map((b) => {
        const ia = parseBody(b.body).attrs
        return {
          id: `sgr-${Math.random().toString(16).slice(2, 8)}`,
          type: 'Custom',
          protocol: ia.protocol || 'tcp',
          from: Number(ia.from_port) || 0,
          to: Number(ia.to_port) || 0,
          source: (Array.isArray(ia.cidr_blocks) ? ia.cidr_blocks[0] : ia.cidr_blocks) || '0.0.0.0/0',
          description: ia.description || '',
        }
      })
      const sg = store.createSecurityGroup?.({
        name: sgName,
        description: attrs.description || 'Managed by Terraform',
        vpcId: attrs.vpc_id || store.vpcs?.[0]?.id || '',
        inbound,
      })
      if (sg?.id) created.push(`sg:${sgName}`)
    }
  }
  // aws_instance / bucket / SG mirrored above; any other type is recorded so a
  // re-apply stays consistent but creates no store object.
  syncedAddresses.add(address)
  return created
}

/**
 * Render a single applied resource as a `terraform state show`-style block,
 * resolving live attributes out of the shared AWS store. `r` is the parsed HCL
 * resource; matching against the store is by name/tag so it reflects what apply
 * actually created.
 */
function renderResourceState(store, r) {
  const attrs = []
  const address = `${r.type}.${r.name}`
  const a = r.attrs || {}
  if (r.type === 'aws_instance') {
    const wanted = (a.tags && a.tags.Name) || r.name
    const inst = (store.instances || []).find((i) => i.name === wanted || i.tags?.Name === wanted)
    if (inst) {
      attrs.push(['id', inst.id], ['ami', inst.amiId || a.ami || ''], ['instance_type', inst.type],
        ['availability_zone', inst.az], ['private_ip', inst.privateIp || ''],
        ['public_ip', inst.publicIp || ''], ['key_name', inst.keyName || ''],
        ['subnet_id', inst.subnetId || ''], ['instance_state', inst.state])
    }
  } else if (r.type === 'aws_s3_bucket') {
    const name = a.bucket || r.name
    const b = (store.s3Buckets || []).find((x) => x.name === name)
    if (b) attrs.push(['id', b.name], ['bucket', b.name], ['region', b.region])
  } else if (r.type === 'aws_security_group') {
    const name = a.name || r.name
    const sg = (store.securityGroups || []).find((x) => x.name === name)
    if (sg) attrs.push(['id', sg.id], ['name', sg.name], ['vpc_id', sg.vpcId || ''],
      ['description', sg.description || ''])
  }
  const lines = [`# ${address}:`, `resource "${r.type}" "${r.name}" {`]
  for (const [k, v] of attrs) lines.push(`    ${k} = "${v}"`)
  lines.push('}')
  return lines
}

/** After terraform apply (backend or terminal), mirror resources into AWS GUI. */
export function syncTerraformApplyToAwsConsole(state, { sessionId } = {}) {
  const tf = state?.state?.terraform || state?.terraform || {}
  if (!tf?.last_apply) return

  const files = state?.state?.files || state?.files || {}
  const src = collectHcl(files)
  if (!src.trim()) return

  const { resources, provider } = parseHcl(src)
  if (!resources.length) return

  const store = useAwsStore.getState()
  const region = provider?.region || store.region
  const created = []

  for (const r of resources) {
    created.push(...createResourceInStore(store, r, region))
  }

  if (created.length) {
    store.markLabManaged?.(created)
    store.pushFlash('success', `${created.length} resource(s) from Terraform apply — open AWS Console to verify.`)
  }

  // Fire-and-forget Azure/GCP portal mirrors (same lab session).
  if (sessionId) {
    syncTerraformApplyToAzureGcp(resources, sessionId).catch(() => {})
  }
}

/**
 * Mirror azurerm_* / google_* resources into the Azure Portal / GCP Console
 * engines for this lab session so learners can open those consoles and see VMs.
 */
export async function syncTerraformApplyToAzureGcp(resources, sessionId) {
  if (!sessionId || !resources?.length) return
  for (const r of resources) {
    const address = `${r.type}.${r.name}`
    if (syncedAddresses.has(`cloud:${address}`)) continue
    const attrs = r.attrs || {}
    try {
      if (r.type === 'azurerm_linux_virtual_machine' || r.type === 'azurerm_windows_virtual_machine'
          || r.type === 'azurerm_virtual_machine') {
        const name = attrs.name || r.name
        await azureApi.createVm(sessionId, {
          name,
          size: attrs.size || attrs.vm_size || 'Standard_B2s',
          location: attrs.location || 'eastus',
        })
        syncedAddresses.add(`cloud:${address}`)
      } else if (r.type === 'google_compute_instance') {
        const name = attrs.name || r.name
        await gcpApi.createInstance(sessionId, {
          name,
          machine_type: attrs.machine_type || 'e2-medium',
          zone: attrs.zone || 'us-central1-a',
        })
        syncedAddresses.add(`cloud:${address}`)
      }
    } catch {
      // Portal session may be unavailable for pure-AWS terraform labs — non-fatal.
    }
  }
}

/** Addresses currently mirrored into the console — backs `terraform state list`. */
export function terraformStateList() {
  return Array.from(syncedAddresses)
}

/**
 * Run a `terraform` subcommand against the live workspace files and the SHARED
 * AWS store, so the terraform lab terminal drives the exact same infrastructure
 * the IDE buttons and the AWS Console read from. Returns an array of output lines
 * (ANSI allowed) mirroring the real CLI. `apply` performs the store mutations and
 * marks them lab-managed for teardown.
 */
export function runTerraformCommand(argv = [], files = {}) {
  const sub = (argv[0] || '').replace(/^-+/, '')
  const rest = argv.slice(1)
  const src = collectHcl(files)
  const store = useAwsStore.getState()

  if (!sub || sub === 'help') {
    return [
      'Usage: terraform [global options] <subcommand> [args]',
      '',
      'Common commands:',
      '  init        Prepare your working directory for other commands',
      '  validate    Check whether the configuration is valid',
      '  plan        Show changes required by the current configuration',
      '  apply       Create or update infrastructure (mirrors into the AWS Console)',
      '  destroy     Destroy previously-created infrastructure',
      '  state       Advanced state management (list, show)',
      '  show        Show the current state',
      '  output      Show output values from your root module',
      '  providers   Show the providers required for this configuration',
      '  workspace   Workspace management',
    ]
  }
  if (sub === 'version') return ['Terraform v1.7.5', 'on linux_amd64', '+ provider registry.terraform.io/hashicorp/aws v5.40.0']
  if (sub === 'fmt') return rest.includes('-check') ? [] : ['main.tf']
  if (sub === 'init') {
    return [
      '\x1b[1mInitializing the backend...\x1b[0m',
      '\x1b[1mInitializing provider plugins...\x1b[0m',
      '- Installing hashicorp/aws v5.40.0...',
      '- Installed hashicorp/aws v5.40.0 (signed by HashiCorp)',
      '',
      '\x1b[32mTerraform has been successfully initialized!\x1b[0m',
    ]
  }

  const { resources, provider, outputs } = src.trim() ? parseHcl(src) : { resources: [], provider: null, outputs: [] }

  if (sub === 'validate') {
    if (!src.trim()) return ['\x1b[31mError: No configuration files found.\x1b[0m']
    return ['\x1b[32mSuccess!\x1b[0m The configuration is valid.']
  }
  if (sub === 'plan') {
    if (!resources.length) return ['\x1b[31mError: No resources to create — write HCL in the editor first.\x1b[0m']
    const toAdd = resources.filter((r) => !syncedAddresses.has(`${r.type}.${r.name}`))
    const lines = ['Terraform will perform the following actions:', '']
    toAdd.forEach((r) => lines.push(`  \x1b[32m+\x1b[0m resource "${r.type}" "${r.name}"`))
    lines.push('', `\x1b[1mPlan:\x1b[0m ${toAdd.length} to add, 0 to change, 0 to destroy.`)
    return lines
  }
  if (sub === 'apply') {
    if (!resources.length) return ['\x1b[31mError: No resources to create — write HCL in the editor first.\x1b[0m']
    const region = provider?.region || store.region
    const toAdd = resources.filter((r) => !syncedAddresses.has(`${r.type}.${r.name}`))
    if (!toAdd.length) {
      return ['\x1b[1mNo changes.\x1b[0m Your infrastructure matches the configuration.', '', '\x1b[32mApply complete!\x1b[0m Resources: 0 added, 0 changed, 0 destroyed.']
    }
    const lines = []
    const created = []
    toAdd.forEach((r) => {
      lines.push(`aws_${r.type.replace(/^aws_/, '')}.${r.name}: Creating...`)
      const handles = createResourceInStore(store, r, region)
      created.push(...handles)
      const idLabel = handles[0] || r.name
      lines.push(`aws_${r.type.replace(/^aws_/, '')}.${r.name}: Creation complete after 3s [id=${idLabel}]`)
    })
    if (created.length) {
      store.markLabManaged?.(created)
      store.pushFlash?.('success', `${created.length} resource(s) from Terraform apply — open AWS Console to verify.`)
    }
    lines.push('', `\x1b[32mApply complete!\x1b[0m Resources: ${toAdd.length} added, 0 changed, 0 destroyed.`)
    lines.push('Run `aws ec2 describe-instances` or open the AWS Console to see them.')
    return lines
  }
  if (sub === 'destroy') {
    const addrs = terraformStateList()
    if (!addrs.length) return ['\x1b[1mNo changes.\x1b[0m No objects need to be destroyed.', '', '\x1b[32mDestroy complete!\x1b[0m Resources: 0 destroyed.']
    resetTerraformAwsLabState()
    const lines = addrs.map((a) => `${a}: Destruction complete after 1s`)
    return [...lines, '', `\x1b[32mDestroy complete!\x1b[0m Resources: ${addrs.length} destroyed.`]
  }
  if (sub === 'state') {
    if (rest[0] === 'list') return terraformStateList()
    if (rest[0] === 'show') {
      const addr = rest[1]
      if (!addr) return ['\x1b[31mError:\x1b[0m Exactly one argument expected.', 'Usage: terraform state show ADDRESS']
      if (!syncedAddresses.has(addr)) {
        return [`\x1b[31mError:\x1b[0m No instance found for ${addr}`, 'Run `terraform state list` to see tracked resources.']
      }
      const r = resources.find((x) => `${x.type}.${x.name}` === addr)
      return r ? renderResourceState(store, r) : [`# ${addr}`, '(no attributes available)']
    }
    return ['Usage: terraform state <subcommand> [args]', '', 'Subcommands:', '  list   List resources in the state', '  show   Show a resource in the state']
  }
  if (sub === 'show') {
    const addrs = terraformStateList()
    if (!addrs.length) return ['The state file is empty. No resources are represented.']
    const lines = ['# terraform.tfstate', '']
    for (const addr of addrs) {
      const r = resources.find((x) => `${x.type}.${x.name}` === addr)
      if (r) lines.push(...renderResourceState(store, r), '')
    }
    return lines
  }
  if (sub === 'providers') {
    return ['Providers required by configuration:', '.', '└── provider[registry.terraform.io/hashicorp/aws] >= 5.0']
  }
  if (sub === 'refresh') {
    const n = terraformStateList().length
    return ['\x1b[32mApply complete!\x1b[0m Resources: 0 added, 0 changed, 0 destroyed.',
      n ? `Refreshed ${n} resource(s) in state.` : 'Empty or non-existent state, no refresh needed.']
  }
  if (sub === 'workspace') {
    if (rest[0] === 'show') return ['default']
    if (rest[0] === 'list') return ['* default']
    if (rest[0] === 'new' || rest[0] === 'select') return [`Switched to workspace "${rest[1] || 'default'}".`]
    return ['Usage: terraform workspace <list|show|new|select> [name]']
  }
  if (sub === 'output') {
    const asJson = rest.includes('-json')
    if (!outputs.length) return asJson ? ['{}'] : ['\x1b[33mWarning:\x1b[0m No outputs found']
    if (asJson) {
      const obj = {}
      outputs.forEach((o) => { obj[o.name] = { sensitive: false, type: 'string', value: o.attrs.value ?? '' } })
      return JSON.stringify(obj, null, 2).split('\n')
    }
    const named = rest.find((x) => !x.startsWith('-'))
    if (named) {
      const o = outputs.find((x) => x.name === named)
      return o ? [`"${o.attrs.value ?? ''}"`] : [`\x1b[31mError:\x1b[0m Output "${named}" not found`]
    }
    return outputs.map((o) => `${o.name} = "${o.attrs.value ?? ''}"`)
  }
  return [`Terraform has no command named "${sub}".`, 'Run "terraform help" to see available commands.']
}

/**
 * Run an `aws ...` CLI command against the SHARED AWS store, so the terraform lab
 * terminal can verify resources terraform apply created (e.g.
 * `aws ec2 describe-instances`). Delegates to the console's read-only awscli
 * engine; returns output split into lines.
 */
export function runAwsCommand(argv = []) {
  const store = useAwsStore.getState()
  const out = awsCli(argv, store, { region: store.region })
  return String(out ?? '').split('\n')
}

/** Tear down lab-created AWS sim resources when the lab session ends. */
export function resetTerraformAwsLabState() {
  syncedAddresses.clear()
  const store = useAwsStore.getState()
  if (store.resetLabManaged) {
    store.resetLabManaged()
  } else {
    store.resetSimulation()
  }
}

export function awsConsoleUrlForResource(type, id) {
  if (type === 'instance' && id) {
    return `/aws-sim/ec2/instances/${id}`
  }
  if (type === 'bucket') {
    return `/aws-sim/s3/buckets/${encodeURIComponent(id)}`
  }
  return '/aws-sim/console/home'
}
