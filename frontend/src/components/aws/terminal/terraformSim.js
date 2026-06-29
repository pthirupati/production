// Terraform simulation for the AWS EC2 SSH / CloudShell terminal.
//
// Parses a practical subset of HCL from the working directory's *.tf files and
// applies it against the same AWS store the console renders from, so a
// `terraform apply` actually creates EC2 instances / S3 buckets / security
// groups that show up in the EC2 and S3 pages. This wires Terraform into the
// "complete stack": write HCL → apply → see it in the AWS Console → SSH in.
//
// Supported: terraform version|init|validate|fmt|plan|apply|destroy|
//            state list|show|output. Resources: aws_instance, aws_s3_bucket,
//            aws_security_group, aws_key_pair (others are planned but no-op).

const TF_VERSION = 'Terraform v1.7.5\non linux_amd64\n+ provider registry.terraform.io/hashicorp/aws v5.40.0'

const TF_FILES = ['main.tf', 'variables.tf', 'outputs.tf', 'providers.tf', 'terraform.tf', 'ec2.tf', 's3.tf', 'network.tf']

// Strip // and # line comments and /* */ blocks without touching strings.
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .map((line) => {
      // remove trailing # or // comments (naive: ok for lab HCL)
      const hashOutside = line.replace(/("(?:[^"\\]|\\.)*")|(#.*$)|(\/\/.*$)/g, (m, str) => (str ? str : ''))
      return hashOutside
    })
    .join('\n')
}

// Extract `key = value` and `key { ... }` pairs from a block body.
function parseBody(body) {
  const attrs = {}
  const blocks = []
  let i = 0
  const n = body.length
  while (i < n) {
    // skip whitespace/commas
    while (i < n && /\s|,/.test(body[i])) i += 1
    if (i >= n) break
    // read identifier
    const idMatch = /^[A-Za-z0-9_-]+/.exec(body.slice(i))
    if (!idMatch) { i += 1; continue }
    const key = idMatch[0]
    i += key.length
    while (i < n && /\s/.test(body[i])) i += 1
    if (body[i] === '{') {
      // nested block (ingress, tags as block-style, etc.)
      const { inner, end } = readBraces(body, i)
      blocks.push({ key, body: inner })
      i = end
    } else if (body[i] === '=') {
      i += 1
      while (i < n && /\s/.test(body[i])) i += 1
      if (body[i] === '{') {
        const { inner, end } = readBraces(body, i)
        attrs[key] = parseBody(inner).attrs // map value e.g. tags = { Name = "x" }
        i = end
      } else if (body[i] === '[') {
        const { inner, end } = readBrackets(body, i)
        attrs[key] = inner.split(',').map((s) => unquote(s.trim())).filter(Boolean)
        i = end
      } else {
        // scalar until newline
        let j = i
        while (j < n && body[j] !== '\n') j += 1
        attrs[key] = unquote(body.slice(i, j).trim())
        i = j
      }
    } else {
      i += 1
    }
  }
  return { attrs, blocks }
}

function readBraces(src, open) {
  let depth = 0
  for (let i = open; i < src.length; i += 1) {
    if (src[i] === '{') depth += 1
    else if (src[i] === '}') { depth -= 1; if (depth === 0) return { inner: src.slice(open + 1, i), end: i + 1 } }
  }
  return { inner: src.slice(open + 1), end: src.length }
}
function readBrackets(src, open) {
  let depth = 0
  for (let i = open; i < src.length; i += 1) {
    if (src[i] === '[') depth += 1
    else if (src[i] === ']') { depth -= 1; if (depth === 0) return { inner: src.slice(open + 1, i), end: i + 1 } }
  }
  return { inner: src.slice(open + 1), end: src.length }
}
function unquote(s) {
  if (!s) return s
  const m = /^"((?:[^"\\]|\\.)*)"$/.exec(s)
  if (m) return m[1]
  if (s === 'true') return true
  if (s === 'false') return false
  if (/^-?\d+$/.test(s)) return parseInt(s, 10)
  return s
}

// Parse all resource/provider/variable/output blocks from concatenated HCL.
function parseHcl(src) {
  const clean = stripComments(src)
  const resources = []
  let provider = null
  const outputs = []
  const re = /\b(resource|provider|variable|output|data)\b/g
  let m
  while ((m = re.exec(clean))) {
    const kind = m[1]
    let i = m.index + kind.length
    // read quoted labels until {
    const labels = []
    while (i < clean.length && clean[i] !== '{') {
      const lm = /"((?:[^"\\]|\\.)*)"/.exec(clean.slice(i))
      const idm = /[A-Za-z0-9_-]+/.exec(clean.slice(i))
      if (lm && clean.slice(i).indexOf(lm[0]) <= 2) { labels.push(lm[1]); i += clean.slice(i).indexOf(lm[0]) + lm[0].length }
      else if (clean[i] === '{') break
      else if (idm && /\S/.test(clean[i])) { labels.push(idm[0]); i += clean.slice(i).indexOf(idm[0]) + idm[0].length }
      else i += 1
    }
    if (clean[i] !== '{') continue
    const { inner, end } = readBraces(clean, i)
    re.lastIndex = end
    const parsed = parseBody(inner)
    if (kind === 'resource') resources.push({ type: labels[0], name: labels[1], ...parsed })
    else if (kind === 'provider' && labels[0] === 'aws') provider = parsed.attrs
    else if (kind === 'output') outputs.push({ name: labels[0], ...parsed })
  }
  return { resources, provider, outputs }
}

function addr(r) {
  return `${r.type}.${r.name}`
}

export function createTerraform({ store, readFile, getCwd, region }) {
  // Per-session apply ledger so `destroy` can roll back what we created.
  const applied = new Map() // address -> { kind, ids: [] }

  const readConfig = () => {
    const cwd = (getCwd ? getCwd() : '/root') || '/root'
    let src = ''
    for (const f of TF_FILES) {
      const c = readFile ? readFile(`${cwd}/${f}`) : null
      if (c) src += `\n${c}\n`
    }
    return src
  }

  const planFromConfig = () => {
    const src = readConfig()
    if (!src.trim()) return { resources: [], provider: null, outputs: [], empty: true }
    return { ...parseHcl(src), empty: false }
  }

  const fmtAddr = (r) => `aws_${r.type.replace(/^aws_/, '')}.${r.name}`

  const applyResource = (r) => {
    const a = addr(r)
    if (applied.has(a)) return [] // already created this session
    const region2 = (planFromConfig().provider?.region) || region || store.region
    if (r.type === 'aws_instance') {
      const count = Number(r.attrs.count) || 1
      const name = (r.attrs.tags && r.attrs.tags.Name) || r.name
      const created = store.launchInstances({
        name,
        amiId: r.attrs.ami || undefined,
        type: r.attrs.instance_type || 't3.micro',
        count,
        keyName: r.attrs.key_name || '',
        subnetId: r.attrs.subnet_id || '',
        securityGroups: Array.isArray(r.attrs.vpc_security_group_ids) ? r.attrs.vpc_security_group_ids : [],
        volumeSize: r.attrs.root_block_device?.volume_size || 8,
        volumeType: r.attrs.root_block_device?.volume_type || 'gp3',
        monitoring: !!r.attrs.monitoring,
        tags: r.attrs.tags || {},
      }) || []
      applied.set(a, { kind: 'instance', ids: created.map((c) => c.id) })
      return created.map((c) => `${fmtAddr(r)}: Creation complete after 4s [id=${c.id}]`)
    }
    if (r.type === 'aws_s3_bucket') {
      const bname = r.attrs.bucket || r.name
      store.createBucket({ name: bname, region: region2, blockPublic: true })
      applied.set(a, { kind: 'bucket', ids: [bname] })
      return [`${fmtAddr(r)}: Creation complete after 1s [id=${bname}]`]
    }
    if (r.type === 'aws_security_group') {
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
      const sg = store.createSecurityGroup({ name: r.attrs.name || r.name, description: r.attrs.description || 'Managed by Terraform', vpcId: r.attrs.vpc_id || '', inbound })
      applied.set(a, { kind: 'sg', ids: [sg.id] })
      return [`${fmtAddr(r)}: Creation complete after 1s [id=${sg.id}]`]
    }
    if (r.type === 'aws_key_pair') {
      const kp = store.createKeyPair({ name: r.attrs.key_name || r.name, type: 'rsa' })
      applied.set(a, { kind: 'keypair', ids: [kp.name] })
      return [`${fmtAddr(r)}: Creation complete after 0s [id=${kp.name}]`]
    }
    // Unmodeled resource — record so plan/state stay consistent.
    applied.set(a, { kind: 'noop', ids: [] })
    return [`${fmtAddr(r)}: Creation complete after 0s [id=${r.name}]`]
  }

  const destroyAll = () => {
    const lines = []
    for (const [a, rec] of applied.entries()) {
      if (rec.kind === 'instance' && rec.ids.length) {
        store.instanceAction(rec.ids, 'terminate')
        lines.push(`${a}: Destruction complete after 2s`)
      } else if (rec.kind === 'bucket') {
        rec.ids.forEach((b) => store.deleteBucket && store.deleteBucket(b))
        lines.push(`${a}: Destruction complete after 1s`)
      } else {
        lines.push(`${a}: Destruction complete after 0s`)
      }
    }
    const n = applied.size
    applied.clear()
    return { lines, n }
  }

  return {
    isTerraform: true,
    run(args) {
      const sub = args[0]
      const rest = args.slice(1)
      if (!sub || sub === '-help' || sub === '--help' || sub === 'help') {
        return [
          'Usage: terraform [global options] <subcommand> [args]',
          '',
          'Common commands:',
          '  init        Prepare your working directory for other commands',
          '  validate    Check whether the configuration is valid',
          '  plan        Show changes required by the current configuration',
          '  apply       Create or update infrastructure',
          '  destroy     Destroy previously-created infrastructure',
          '  fmt         Reformat your configuration in the standard style',
          '  output      Show output values from your root module',
          "  state       Advanced state management (e.g. 'state list')",
        ]
      }
      if (sub === 'version' || sub === '-version' || sub === '--version') return TF_VERSION.split('\n')
      if (sub === 'fmt') return rest.includes('-check') ? [] : ['main.tf']
      if (sub === 'init') {
        return [
          '\x1b[1mInitializing the backend...\x1b[0m',
          '\x1b[1mInitializing provider plugins...\x1b[0m',
          '- Finding hashicorp/aws versions matching ">= 5.0"...',
          '- Installing hashicorp/aws v5.40.0...',
          '- Installed hashicorp/aws v5.40.0 (signed by HashiCorp)',
          '',
          '\x1b[32mTerraform has been successfully initialized!\x1b[0m',
        ]
      }
      if (sub === 'validate') {
        const { empty } = planFromConfig()
        if (empty) return ['\x1b[31m╷', '│ Error: No configuration files', '│', "│ No .tf files found in the current directory.", '╵\x1b[0m']
        return ['\x1b[32mSuccess!\x1b[0m The configuration is valid.']
      }
      if (sub === 'plan') {
        const { resources, empty } = planFromConfig()
        if (empty) return ['\x1b[31mError: No configuration files found.\x1b[0m']
        const toAdd = resources.filter((r) => !applied.has(addr(r)))
        const lines = ['Terraform used the selected providers to generate the following execution plan.', 'Resource actions are indicated with the following symbols:', '  \x1b[32m+\x1b[0m create', '']
        toAdd.forEach((r) => {
          lines.push(`  \x1b[32m+\x1b[0m resource "${r.type}" "${r.name}" {`)
          Object.entries(r.attrs).slice(0, 6).forEach(([k, v]) => {
            if (typeof v === 'object') return
            lines.push(`      \x1b[32m+\x1b[0m ${k} = "${v}"`)
          })
          lines.push('    }')
        })
        lines.push('')
        lines.push(`\x1b[1mPlan:\x1b[0m ${toAdd.length} to add, 0 to change, 0 to destroy.`)
        return lines
      }
      if (sub === 'apply') {
        const { resources, empty } = planFromConfig()
        if (empty) return ['\x1b[31mError: No configuration files found.\x1b[0m']
        const toAdd = resources.filter((r) => !applied.has(addr(r)))
        if (!toAdd.length) return ['\x1b[1mNo changes.\x1b[0m Your infrastructure matches the configuration.', '', '\x1b[32mApply complete! Resources: 0 added, 0 changed, 0 destroyed.\x1b[0m']
        const lines = []
        toAdd.forEach((r) => {
          lines.push(`${fmtAddr(r)}: Creating...`)
          lines.push(...applyResource(r))
        })
        lines.push('')
        lines.push(`\x1b[32mApply complete!\x1b[0m Resources: ${toAdd.length} added, 0 changed, 0 destroyed.`)
        lines.push('Run `aws ec2 describe-instances` or open the EC2 / S3 console to see them.')
        return lines
      }
      if (sub === 'destroy') {
        const { lines, n } = destroyAll()
        if (!n) return ['\x1b[1mNo changes.\x1b[0m No objects need to be destroyed.', '', '\x1b[32mDestroy complete! Resources: 0 destroyed.\x1b[0m']
        return [...lines, '', `\x1b[32mDestroy complete!\x1b[0m Resources: ${n} destroyed.`]
      }
      if (sub === 'state') {
        if (rest[0] === 'list') return Array.from(applied.keys())
        if (rest[0] === 'show') return ['# Use the AWS console (EC2/S3) to inspect managed resources.']
        return ['Usage: terraform state <list|show>']
      }
      if (sub === 'output') {
        const { outputs } = planFromConfig()
        if (!outputs.length) return ['\x1b[33mWarning:\x1b[0m No outputs found']
        return outputs.map((o) => `${o.name} = "${o.attrs.value ?? ''}"`)
      }
      return [`Terraform has no command named "${sub}".`, 'Run "terraform -help" to see available commands.']
    },
  }
}
