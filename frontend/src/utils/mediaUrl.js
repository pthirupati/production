/**
 * Resolve media URLs for same-origin display (fixes broken backend-internal absolute URLs).
 */
export function resolveMediaUrl(url) {
  if (!url) return ''
  const trimmed = String(url).trim()
  if (trimmed.startsWith('data:')) return trimmed
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    try {
      const path = new URL(trimmed).pathname
      if (path.startsWith('/media/')) return path
    } catch {
      /* keep original */
    }
    return trimmed
  }
  if (trimmed.startsWith('/media/') || trimmed.startsWith('/')) return trimmed
  return `/media/${trimmed.replace(/^\/+/, '')}`
}

export const IMAGE_UPLOAD_HINTS = {
  promo_banner: '1200×280 px — PNG, JPEG, or WebP',
  maintenance_banner: '1200×200 px — PNG, JPEG, or WebP',
  community_screenshot: '200×120 to 1920×1080 px — screenshot only',
}
