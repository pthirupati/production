// Resource ID + ARN generators matching real AWS formats exactly.
const HEX = '0123456789abcdef'
const ALNUM = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

function hex(n) {
  let s = ''
  for (let i = 0; i < n; i += 1) s += HEX[Math.floor(Math.random() * 16)]
  return s
}
function alnum(n) {
  let s = ''
  for (let i = 0; i < n; i += 1) s += ALNUM[Math.floor(Math.random() * ALNUM.length)]
  return s
}

// EC2 family: prefix-[17 hex]
export const newInstanceId = () => `i-0${hex(16)}`
export const newVolumeId = () => `vol-0${hex(16)}`
export const newSnapshotId = () => `snap-0${hex(16)}`
export const newAmiId = () => `ami-0${hex(16)}`
export const newSgId = () => `sg-0${hex(16)}`
export const newSubnetId = () => `subnet-0${hex(16)}`
export const newVpcId = () => `vpc-0${hex(16)}`
export const newIgwId = () => `igw-0${hex(16)}`
export const newRtbId = () => `rtb-0${hex(16)}`
export const newEniId = () => `eni-0${hex(16)}`
export const newNatId = () => `nat-0${hex(16)}`
export const newEipAllocId = () => `eipalloc-0${hex(16)}`
export const newEipAssocId = () => `eipassoc-0${hex(16)}`
export const newKeyPairId = () => `key-0${hex(16)}`
export const newAclId = () => `acl-0${hex(16)}`
export const newSgRuleId = () => `sgr-0${hex(16)}`
export const newLtId = () => `lt-0${hex(16)}`

// IAM
export const newIamUserId = () => `AIDA${alnum(16)}`
export const newIamRoleId = () => `AROA${alnum(16)}`
export const newIamGroupId = () => `AGPA${alnum(16)}`
export const newAccessKeyId = () => `AKIA${alnum(16)}`
export const newSecretAccessKey = () => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  let s = ''
  for (let i = 0; i < 40; i += 1) s += chars[Math.floor(Math.random() * chars.length)]
  return s
}

// Random private IPv4 in a /20 subnet base (e.g. 172.31.16.0)
export function newPrivateIp(subnetBase) {
  const parts = subnetBase.split('.')
  const host = 4 + Math.floor(Math.random() * 4090)
  const third = parseInt(parts[2], 10) + Math.floor(host / 256)
  return `${parts[0]}.${parts[1]}.${third}.${host % 256}`
}

export function newPublicIp() {
  const r = () => 1 + Math.floor(Math.random() * 254)
  return `${[3, 18, 34, 44, 52, 54][Math.floor(Math.random() * 6)]}.${r()}.${r()}.${r()}`
}

// EC2 public DNS name: ec2-X-X-X-X.compute-1.amazonaws.com (us-east-1) / .REGION.compute.amazonaws.com
export function publicDns(ip, region) {
  if (!ip) return ''
  const dashed = ip.replace(/\./g, '-')
  return region === 'us-east-1'
    ? `ec2-${dashed}.compute-1.amazonaws.com`
    : `ec2-${dashed}.${region}.compute.amazonaws.com`
}
export function privateDns(ip, region) {
  if (!ip) return ''
  const dashed = ip.replace(/\./g, '-')
  return region === 'us-east-1'
    ? `ip-${dashed}.ec2.internal`
    : `ip-${dashed}.${region}.compute.internal`
}
export function hostnameFromIp(ip) {
  return `ip-${ip.replace(/\./g, '-')}`
}

// ARN builder: arn:aws:SERVICE:REGION:ACCOUNT:RESOURCE
export function arn(service, region, account, resource) {
  // S3 and IAM have empty region/account segments in real AWS.
  if (service === 's3') return `arn:aws:s3:::${resource}`
  if (service === 'iam') return `arn:aws:iam::${account}:${resource}`
  return `arn:aws:${service}:${region}:${account}:${resource}`
}
