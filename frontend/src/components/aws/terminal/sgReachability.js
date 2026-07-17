/** Security-group helpers for AWS simulation connectivity. */

function ruleAllowsPort(rule, port, protocol = 'TCP') {
  if (!rule) return false
  const proto = String(rule.protocol || '').toUpperCase()
  if (proto && proto !== 'ALL' && proto !== '-1' && proto !== protocol.toUpperCase()) return false
  const from = Number(rule.from ?? 0)
  const to = Number(rule.to ?? 65535)
  if (Number.isNaN(from) || Number.isNaN(to)) return proto === 'ALL' || proto === '-1'
  return port >= from && port <= to
}

/**
 * True when any attached security group allows inbound `port` from a public
 * client (0.0.0.0/0, ::/0, or "Anywhere"). Matches real AWS SG semantics for labs.
 */
export function instanceAllowsInbound(store, instance, port, protocol = 'TCP') {
  if (!instance || instance.state !== 'running') return false
  const sgs = (store?.securityGroups || []).filter((sg) => (instance.securityGroups || []).includes(sg.id))
  if (!sgs.length) return false
  for (const sg of sgs) {
    for (const rule of sg.inbound || []) {
      if (!ruleAllowsPort(rule, port, protocol)) continue
      const src = String(rule.source || '').toLowerCase()
      if (
        src === '0.0.0.0/0'
        || src === '::/0'
        || src === 'anywhere'
        || src.includes('0.0.0.0/0')
      ) {
        return true
      }
    }
  }
  return false
}

/** Find a non-terminated instance by public IP, private IP, public DNS, or id. */
export function findInstanceByHost(store, host) {
  const h = String(host || '').trim().toLowerCase()
  if (!h) return null
  const list = (store?.instances || []).filter((i) => i.state !== 'terminated')
  return (
    list.find((i) => (i.publicIp || '').toLowerCase() === h)
    || list.find((i) => (i.privateIp || '').toLowerCase() === h)
    || list.find((i) => (i.id || '').toLowerCase() === h)
    || list.find((i) => (`ec2-${i.id}.compute.amazonaws.com`).toLowerCase() === h)
    || list.find((i) => (i.publicDns || '').toLowerCase() === h)
    || null
  )
}
