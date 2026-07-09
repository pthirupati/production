/** Flatten scenario tags for search/heuristics without assuming API shape. */
export function scenarioTagHaystack(scenario = {}) {
  const tags = scenario.tags
  let tagText = ''
  if (Array.isArray(tags)) {
    tagText = tags
      .map((t) => (typeof t === 'string' ? t : (t?.name || t?.slug || '')))
      .filter(Boolean)
      .join(' ')
  } else if (typeof tags === 'string') {
    tagText = tags
  }
  return `${scenario.slug || ''} ${scenario.title || ''} ${tagText}`.trim().toLowerCase()
}
