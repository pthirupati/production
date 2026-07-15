// Minimal IAM policy evaluation engine.
//
// Scope is intentionally small (portfolio simulation):
//   - deny-overrides-allow, explicit-deny-wins
//   - Action / NotAction with `*` and `?` wildcard globbing
//   - Resource / NotResource with `*` and `?` wildcard globbing
//   - NO conditions, NO principals, NO SCP/permission-boundary layering
//
// A principal carries an array of attached policy documents (each a standard
// IAM policy JSON: { Version, Statement: [{ Effect, Action|NotAction,
// Resource|NotResource }] }). evaluate() returns { effect, allowed, reason }.

/** Convert an IAM wildcard pattern (`*`, `?`) into an anchored RegExp. */
export function globToRegExp(pattern) {
  const escaped = String(pattern)
    .replace(/[.+^${}()|[\]\\]/g, '\\$&') // escape regex specials (not * or ?)
    .replace(/\*/g, '.*')
    .replace(/\?/g, '.')
  return new RegExp(`^${escaped}$`, 'i')
}

/** Does `value` match any pattern in `patterns` (array or scalar)? */
function matchesAny(patterns, value) {
  const list = Array.isArray(patterns) ? patterns : [patterns]
  return list.some((p) => globToRegExp(p).test(value))
}

/** Does a single statement match this (action, resource)? */
function statementMatches(stmt, action, resource) {
  // Action / NotAction
  let actionMatch
  if (stmt.Action != null) actionMatch = matchesAny(stmt.Action, action)
  else if (stmt.NotAction != null) actionMatch = !matchesAny(stmt.NotAction, action)
  else actionMatch = false
  if (!actionMatch) return false

  // Resource / NotResource — absence means all resources ("*")
  let resourceMatch
  if (stmt.Resource != null) resourceMatch = matchesAny(stmt.Resource, resource)
  else if (stmt.NotResource != null) resourceMatch = !matchesAny(stmt.NotResource, resource)
  else resourceMatch = true
  return resourceMatch
}

function statementsOf(policy) {
  const doc = policy && policy.document ? policy.document : policy
  if (!doc || !doc.Statement) return []
  return Array.isArray(doc.Statement) ? doc.Statement : [doc.Statement]
}

/**
 * Evaluate whether `principal` may perform `action` on `resource`.
 * principal: { name, policies: [{ document } | document], ... }
 * Returns { effect: 'Allow'|'Deny', allowed: boolean, reason: string }.
 */
export function evaluate(principal, action, resource = '*') {
  const policies = (principal && principal.policies) || []
  let sawAllow = false
  for (const policy of policies) {
    for (const stmt of statementsOf(policy)) {
      if (!statementMatches(stmt, action, resource)) continue
      if (stmt.Effect === 'Deny') {
        return { effect: 'Deny', allowed: false, reason: `Explicit deny on ${action}` }
      }
      if (stmt.Effect === 'Allow') sawAllow = true
    }
  }
  if (sawAllow) return { effect: 'Allow', allowed: true, reason: `Allowed by policy` }
  return { effect: 'Deny', allowed: false, reason: `Implicit deny — no matching Allow for ${action}` }
}

// Well-known managed policy documents used to seed principals.
export const MANAGED_POLICY_DOCS = {
  AdministratorAccess: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Action: '*', Resource: '*' }] },
  ReadOnlyAccess: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Action: ['*:Describe*', '*:Get*', '*:List*', 's3:Head*'], Resource: '*' }] },
  PowerUserAccess: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', NotAction: ['iam:*', 'organizations:*', 'account:*'], Resource: '*' }] },
}

/** Build a principal's policies array from managed policy names + inline docs. */
export function policiesFromNames(names = [], inline = []) {
  const out = []
  for (const n of names) {
    if (MANAGED_POLICY_DOCS[n]) out.push({ name: n, document: MANAGED_POLICY_DOCS[n] })
  }
  for (const doc of inline) out.push({ name: doc.name || 'inline', document: doc.document || doc })
  return out
}
