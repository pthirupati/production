import { useEffect } from 'react'

const BASE = 'FixitLab'

/** Set document.title for SPA pages (SEO + browser tab). */
export function usePageTitle(title, description) {
  useEffect(() => {
    const prev = document.title
    document.title = title ? `${title} | ${BASE}` : BASE
    if (description) {
      let meta = document.querySelector('meta[name="description"]')
      if (!meta) {
        meta = document.createElement('meta')
        meta.name = 'description'
        document.head.appendChild(meta)
      }
      meta.content = description
    }
    return () => { document.title = prev }
  }, [title, description])
}
