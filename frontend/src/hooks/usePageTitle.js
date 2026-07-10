import { useEffect } from 'react'

const BASE = 'FixitLab'
const DEFAULT_OG_IMAGE = '/og-image.png'

function upsertMeta(attr, key, content) {
  if (!content) return
  let el = document.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.content = content
}

function upsertLink(rel, href) {
  if (!href) return
  let el = document.querySelector(`link[rel="${rel}"]`)
  if (!el) {
    el = document.createElement('link')
    el.rel = rel
    document.head.appendChild(el)
  }
  el.href = href
}

/** Set document.title and SEO/OG/Twitter meta for SPA pages. */
export function usePageTitle(title, description, options = {}) {
  const { image, canonical, noIndex } = options

  useEffect(() => {
    const prev = {
      title: document.title,
      description: document.querySelector('meta[name="description"]')?.content,
    }
    const fullTitle = title ? `${title} | ${BASE}` : BASE
    document.title = fullTitle

    if (description) {
      upsertMeta('name', 'description', description)
      upsertMeta('property', 'og:description', description)
      upsertMeta('name', 'twitter:description', description)
    }
    upsertMeta('property', 'og:title', fullTitle)
    upsertMeta('name', 'twitter:title', fullTitle)
    upsertMeta('property', 'og:site_name', BASE)
    upsertMeta('name', 'twitter:card', 'summary_large_image')
    upsertMeta('property', 'og:type', 'website')

    const ogImage = image || `${window.location.origin}${DEFAULT_OG_IMAGE}`
    upsertMeta('property', 'og:image', ogImage)
    upsertMeta('name', 'twitter:image', ogImage)

    const url = canonical || window.location.href
    upsertMeta('property', 'og:url', url)
    upsertLink('canonical', canonical || window.location.href)

    if (noIndex) {
      upsertMeta('name', 'robots', 'noindex, nofollow')
    }

    return () => {
      document.title = prev.title
      if (prev.description) upsertMeta('name', 'description', prev.description)
    }
  }, [title, description, image, canonical, noIndex])
}
