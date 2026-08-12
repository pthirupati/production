// Validation rules matching real AWS constraints.

// S3 bucket naming rules (general purpose buckets).
export function isValidBucketName(name) {
  if (!name || name.length < 3 || name.length > 63) return false
  if (!/^[a-z0-9.-]+$/.test(name)) return false
  if (!/^[a-z0-9]/.test(name) || !/[a-z0-9]$/.test(name)) return false
  if (name.includes('..')) return false
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(name)) return false // not IP-formatted
  if (name.startsWith('xn--') || name.startsWith('sthree-')) return false
  if (name.endsWith('-s3alias') || name.endsWith('--ol-s3')) return false
  return true
}

// IPv4 CIDR block (e.g. 10.0.0.0/16).
export function isValidCidr(cidr) {
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\/(\d{1,2})$/.exec(cidr || '')
  if (!m) return false
  const octets = [m[1], m[2], m[3], m[4]].map(Number)
  if (octets.some((o) => o > 255)) return false
  const prefix = Number(m[5])
  return prefix >= 0 && prefix <= 32
}

// Parse a CIDR into { net: [o0,o1,o2,o3], prefix } or null if invalid.
function parseCidr(cidr) {
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\/(\d{1,2})$/.exec(cidr || '')
  if (!m) return null
  const net = [m[1], m[2], m[3], m[4]].map(Number)
  if (net.some((o) => o > 255)) return null
  const prefix = Number(m[5])
  if (prefix < 0 || prefix > 32) return null
  return { net, prefix }
}

function cidrToInt(net) {
  return ((net[0] << 24) >>> 0) + (net[1] << 16) + (net[2] << 8) + net[3]
}

function maskBounds(cidr) {
  const p = parseCidr(cidr)
  if (!p) return null
  const base = cidrToInt(p.net) >>> 0
  const hostBits = 32 - p.prefix
  const mask = p.prefix === 0 ? 0 : (0xffffffff << hostBits) >>> 0
  const start = (base & mask) >>> 0
  const size = hostBits === 32 ? 0x100000000 : 2 ** hostBits
  const end = start + size - 1
  return { start, end }
}

// Is `child` fully contained within `parent` (VPC CIDR)?
export function cidrWithinVpc(child, parent) {
  const c = maskBounds(child)
  const p = maskBounds(parent)
  const cp = parseCidr(child)
  const pp = parseCidr(parent)
  if (!c || !p || !cp || !pp) return false
  if (cp.prefix < pp.prefix) return false // child block bigger than parent
  return c.start >= p.start && c.end <= p.end
}

// Do two CIDR ranges overlap at all?
export function cidrsOverlap(a, b) {
  const ba = maskBounds(a)
  const bb = maskBounds(b)
  if (!ba || !bb) return false
  return ba.start <= bb.end && bb.start <= ba.end
}

// AMI architecture must match the instance-type architecture (x86_64 vs arm64).
export function amiArchMatchesInstanceType(amiArch, instanceArch) {
  if (!amiArch || !instanceArch) return true // unknown -> permissive
  return String(amiArch) === String(instanceArch)
}

// Classic/Xen families boot without ENA; Nitro (t3/t4g/c5/…) requires it.
const XEN_CLASSIC_FAMILIES = new Set([
  't1', 't2', 'm1', 'm2', 'm3', 'c1', 'c3', 'r3', 'i2', 'hs1',
])

export function instanceRequiresEna(instanceType) {
  const family = String(instanceType || '').split('.')[0]
  return Boolean(family) && !XEN_CLASSIC_FAMILIES.has(family)
}

export function amiHasEna(ami) {
  if (!ami) return true
  if ('ena' in ami) return Boolean(ami.ena)
  if ('ena_support' in ami) return Boolean(ami.ena_support)
  const manifest = ami.manifest && typeof ami.manifest === 'object' ? ami.manifest : {}
  if ('ena' in manifest) return Boolean(manifest.ena)
  if ('ena_driver' in manifest) return Boolean(manifest.ena_driver)
  if ('ena_support' in manifest) return Boolean(manifest.ena_support)
  if (Array.isArray(manifest.drivers) && manifest.drivers.length) {
    return manifest.drivers.map((d) => String(d).toLowerCase()).includes('ena')
  }
  return true
}

export function amiEnaMatchesInstanceType(ami, instanceType) {
  if (!instanceRequiresEna(instanceType)) return true
  return amiHasEna(ami)
}

// Security-group names must be unique within a VPC.
export function duplicateSgNameInVpc(name, vpcId, groups) {
  return (groups || []).some((g) => g.name === name && g.vpcId === vpcId)
}

// Minimal IAM policy JSON sanity check.
export function isValidPolicyJson(text) {
  try {
    const p = JSON.parse(text)
    if (!p.Statement) return { ok: false, error: 'Policy must contain a Statement element.' }
    const stmts = Array.isArray(p.Statement) ? p.Statement : [p.Statement]
    for (const s of stmts) {
      if (!s.Effect || !['Allow', 'Deny'].includes(s.Effect)) return { ok: false, error: 'Each statement needs Effect: Allow|Deny.' }
      if (!s.Action && !s.NotAction) return { ok: false, error: 'Each statement needs Action or NotAction.' }
    }
    return { ok: true }
  } catch (e) {
    return { ok: false, error: `Invalid JSON: ${e.message}` }
  }
}
