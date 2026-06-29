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
