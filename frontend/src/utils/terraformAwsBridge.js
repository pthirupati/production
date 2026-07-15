/**
 * Sync Terraform apply results into the AWS console simulator store so learners
 * can verify resources visually after `terraform apply` in the lab IDE.
 *
 * This delegates to the same HCL tokenizer the terminal engine uses
 * (components/aws/terminal/hclParser.js), so the IDE-driven apply path creates
 * the same accurate resources as the terminal `terraform apply` path — honoring
 * multiple resources, count, real key names / security groups, and full ingress
 * rules — instead of the old single-regex parser that hardcoded most values.
 */
import { useAwsStore } from '../components/aws/store/awsStore'
import { parseHcl, parseBody } from '../components/aws/terminal/hclParser'

// Resource addresses already mirrored into the console this page session, so a
// re-apply of an unchanged config does not duplicate instances/buckets/SGs.
// Mirrors the per-session apply ledger the terminal engine keeps in
// terraformSim.js. Cleared on lab teardown (resetTerraformAwsLabState).
const syncedAddresses = new Set()

/** Concatenate every *.tf file in the workspace so multi-file configs parse. */
function collectHcl(files = {}) {
  let src = ''
  for (const [key, content] of Object.entries(files)) {
    if (typeof content !== 'string') continue
    // Backend stores dotted keys (main.tf); tolerate underscore keys (main_tf) too.
    if (/(\.|_)tf$/.test(key)) src += `\n${content}\n`
  }
  return src
}

/** After terraform apply (backend or terminal), mirror resources into AWS GUI. */
export function syncTerraformApplyToAwsConsole(state) {
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
    const address = `${r.type}.${r.name}`
    if (syncedAddresses.has(address)) continue
    const attrs = r.attrs || {}

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
      syncedAddresses.add(address)
    } else if (r.type === 'aws_s3_bucket') {
      const bucketName = attrs.bucket || r.name
      if (!store.s3Buckets?.some((b) => b.name === bucketName)) {
        store.createBucket?.({ name: bucketName, region, blockPublic: true })
        created.push(`bucket:${bucketName}`)
      }
      syncedAddresses.add(address)
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
      syncedAddresses.add(address)
    } else {
      // Unmodeled resource type — record so a re-apply stays consistent.
      syncedAddresses.add(address)
    }
  }

  if (created.length) {
    store.markLabManaged?.(created)
    store.pushFlash('success', `${created.length} resource(s) from Terraform apply — open AWS Console to verify.`)
  }
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
