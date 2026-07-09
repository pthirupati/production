/**
 * Sync Terraform apply results into the AWS console simulator store so learners
 * can verify resources visually after `terraform apply` in the lab terminal.
 */
import { useAwsStore } from '../components/aws/store/awsStore'

function parseMainTf(mainTf = '') {
  const nameMatch = /tags\s*=\s*\{[^}]*Name\s*=\s*"([^"]+)"/.exec(mainTf)
  const amiMatch = /ami\s*=\s*"([^"]+)"/.exec(mainTf)
  const typeMatch = /instance_type\s*=\s*"([^"]+)"/.exec(mainTf)
  const bucketMatch = /resource\s+"aws_s3_bucket"\s+"([^"]+)"/.exec(mainTf)
  return {
    instanceName: nameMatch?.[1] || 'terraform-web',
    amiId: amiMatch?.[1] || 'ami-0c55b159cbfafe1f0',
    instanceType: typeMatch?.[1] || 't3.micro',
    bucketLogical: bucketMatch?.[1] || null,
  }
}

/** After terraform apply (backend or terminal), mirror resources into AWS GUI. */
export function syncTerraformApplyToAwsConsole(state) {
  const tf = state?.state?.terraform || state?.terraform || {}
  if (!tf?.last_apply) return

  const files = state?.state?.files || state?.files || {}
  const mainTf = files.main_tf || files['main.tf'] || ''
  const parsed = parseMainTf(mainTf)
  const store = useAwsStore.getState()
  const created = []

  const resources = tf.resources || []
  const wantsInstance = resources.some((r) => r.type === 'aws_instance') || /aws_instance/.test(mainTf)
  const wantsBucket = resources.some((r) => r.type === 'aws_s3_bucket') || /aws_s3_bucket/.test(mainTf)
  const wantsSg = resources.some((r) => r.type === 'aws_security_group') || /aws_security_group/.test(mainTf)

  if (wantsInstance) {
    const launched = store.launchInstances({
      name: parsed.instanceName,
      amiId: parsed.amiId,
      type: parsed.instanceType,
      count: 1,
      keyName: 'demo-key-pair',
      securityGroups: ['sg-0a1b2c3web00001'],
      volumeSize: 8,
      tags: { ManagedBy: 'Terraform', Lab: 'fixitlab' },
    })
    created.push(...(launched || []).map((i) => i.id))
  }

  if (wantsBucket) {
    const bucketName = `${parsed.bucketLogical || 'tf-lab'}-${Date.now().toString(36).slice(-6)}`
    store.createBucket?.({ name: bucketName, region: store.region })
    created.push(`bucket:${bucketName}`)
  }

  if (wantsSg && !store.securityGroups?.some((sg) => sg.name === 'web-sg-tf')) {
    const sg = store.createSecurityGroup?.({
      name: 'web-sg-tf',
      description: 'Terraform-managed web security group',
      vpcId: store.vpcs?.[0]?.id,
      inbound: [{ id: 'sgr-tf', type: 'HTTP', protocol: 'TCP', from: 80, to: 80, source: '0.0.0.0/0', description: 'HTTP' }],
    })
    if (sg?.id) created.push(`sg:web-sg-tf`)
  }

  if (created.length) {
    store.markLabManaged?.(created)
    store.pushFlash('success', `${created.length} resource(s) from Terraform apply — open AWS Console to verify.`)
  }
}

/** Tear down lab-created AWS sim resources when the lab session ends. */
export function resetTerraformAwsLabState() {
  const store = useAwsStore.getState()
  if (store.resetLabManaged) {
    store.resetLabManaged()
  } else {
    store.resetSimulation()
  }
}

export function awsConsoleUrlForResource(type, id) {
  const region = useAwsStore.getState().region || 'us-east-1'
  if (type === 'instance' && id) {
    return `/aws-sim/ec2/instances/${id}`
  }
  if (type === 'bucket') {
    return `/aws-sim/s3/buckets/${encodeURIComponent(id)}`
  }
  return '/aws-sim/console/home'
}
