import { lazy } from 'react'

/** True when a dynamic import failed because a stale deploy dropped the chunk file. */
export function isChunkLoadError(err) {
  const msg = `${err?.message || ''} ${String(err)}`
  return /Failed to fetch dynamically imported module|Loading chunk|ChunkLoadError|Importing a module script failed|error loading dynamically imported module/i.test(
    msg,
  )
}

/**
 * Wrap React.lazy() with retries + one hard reload on chunk mismatch.
 * Returning users with a cached index.html often reference deleted hashed chunks
 * after deploy; a reload fetches the current entry and fixes admin/pages.
 */
export function lazyWithRetry(importFn, { retries = 2, reloadKey = 'fixitlab-chunk-reload' } = {}) {
  return lazy(() => {
    const attempt = (left) =>
      importFn().catch((err) => {
        if (!isChunkLoadError(err)) throw err
        if (left > 0) {
          return new Promise((r) => setTimeout(r, 800)).then(() => attempt(left - 1))
        }
        const reloaded = sessionStorage.getItem(reloadKey)
        if (!reloaded) {
          sessionStorage.setItem(reloadKey, '1')
          window.location.reload()
          return new Promise(() => {})
        }
        sessionStorage.removeItem(reloadKey)
        throw err
      })
    return attempt(retries)
  })
}
