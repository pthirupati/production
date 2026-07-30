/**
 * Technology subscription helpers for lab console gating.
 * Prefer `has_access` (includes grace) over `is_active` alone.
 */

/** @typedef {{ complimentary_access?: boolean, subscriptions?: Array<{ has_access?: boolean, is_active?: boolean, technology?: { slug?: string } | null }> }} SubsPayload */

/**
 * @param {SubsPayload | null | undefined} payload
 * @param {string} slug
 * @returns {boolean}
 */
export function userHasTechAccess(payload, slug) {
  if (!payload || !slug) return false
  if (payload.complimentary_access) return true
  const want = String(slug).toLowerCase()
  return (payload.subscriptions || []).some((s) => {
    const techSlug = (s?.technology?.slug || '').toLowerCase()
    if (techSlug !== want) return false
    if (typeof s.has_access === 'boolean') return s.has_access
    return !!s.is_active
  })
}

/**
 * Whether the learner may open a companion console for a given slug.
 * Scenario must opt in via the link flag AND the user must be entitled.
 *
 * @param {SubsPayload | null | undefined} payload
 * @param {boolean} scenarioLinkFlag
 * @param {string} techSlug
 * @returns {boolean}
 */
export function canOpenCompanionConsole(payload, scenarioLinkFlag, techSlug) {
  return !!scenarioLinkFlag && userHasTechAccess(payload, techSlug)
}
