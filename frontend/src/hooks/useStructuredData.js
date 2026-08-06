import { useEffect } from 'react'

// JSON-LD structured data (audit Z6-7). There was none anywhere on the site, so
// Google had no machine-readable description of 7,280 hands-on labs — the single
// highest-value structured-data opportunity here, since `Course` is exactly what
// they are.
//
// This is a client-side injection and that limits what it buys: Googlebot renders
// JavaScript and will see it, but Bing, LinkedIn and Slack largely do not. Those
// need real prerendering, which stays open in Z6-7. Worth doing anyway — Google is
// the traffic that matters for a search-discovered training catalog, and the cost
// is one script tag.
//
// Each block is keyed by `id` and removed on unmount, so navigating between
// scenarios cannot leave a previous lab's Course block behind describing the page
// you are now on. That is the failure mode of naive JSON-LD in an SPA: stale
// structured data is worse than none, because it is confidently wrong.

function upsertJsonLd(id, data) {
  const elId = `ld-${id}`
  let el = document.getElementById(elId)
  if (!data) {
    el?.remove()
    return
  }
  if (!el) {
    el = document.createElement('script')
    el.id = elId
    el.type = 'application/ld+json'
    document.head.appendChild(el)
  }
  el.textContent = JSON.stringify(data)
}

/** Inject one JSON-LD block, replacing any previous block with the same id. */
export function useStructuredData(id, data) {
  const serialized = data ? JSON.stringify(data) : null
  useEffect(() => {
    upsertJsonLd(id, serialized ? JSON.parse(serialized) : null)
    return () => upsertJsonLd(id, null)
    // `serialized` rather than `data`: an object literal built inline in a
    // component is a new reference every render, which would re-inject the tag
    // on every render forever.
  }, [id, serialized])
}

const ORIGIN = typeof window !== 'undefined' ? window.location.origin : ''

export const organizationSchema = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'FixitLab',
  url: ORIGIN,
  logo: `${ORIGIN}/logo.png`,
  description:
    'Hands-on DevOps, cloud, GPU and AI infrastructure labs with real broken systems to diagnose and fix.',
}

/**
 * `Course` for one scenario.
 *
 * `hasCourseInstance` is required for Google to treat a Course as eligible: a
 * Course without one is valid schema that earns no rich result, which is the
 * usual reason this markup silently does nothing. These labs are self-paced and
 * online, so that is what it says.
 */
export function scenarioCourseSchema(scenario) {
  if (!scenario?.title) return null
  const name = scenario.technology_name || scenario.technology?.name || ''
  return {
    '@context': 'https://schema.org',
    '@type': 'Course',
    name: scenario.title,
    description:
      scenario.subtitle
      || scenario.description
      || `Hands-on ${name} troubleshooting lab: diagnose and fix a real broken system.`,
    provider: {
      '@type': 'Organization',
      name: 'FixitLab',
      sameAs: ORIGIN,
    },
    url: `${ORIGIN}/scenarios/${scenario.slug || scenario.id}`,
    ...(name ? { about: name } : {}),
    ...(scenario.difficulty ? { educationalLevel: scenario.difficulty } : {}),
    hasCourseInstance: {
      '@type': 'CourseInstance',
      courseMode: 'online',
      courseWorkload: scenario.time_limit
        // ISO 8601 duration. `time_limit` is seconds; Google rejects a bare number.
        ? `PT${Math.max(1, Math.round(scenario.time_limit / 60))}M`
        : undefined,
    },
  }
}

/** BreadcrumbList — the trail Google prints under a result instead of a raw URL. */
export function breadcrumbSchema(trail) {
  const items = (trail || []).filter((t) => t && t.name)
  if (items.length < 2) return null
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: item.name,
      ...(item.path ? { item: `${ORIGIN}${item.path}` } : {}),
    })),
  }
}
