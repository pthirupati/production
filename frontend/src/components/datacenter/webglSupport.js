/** Feature-detect WebGL before mounting R3F Canvas (avoids silent Twin3DSafe trips). */

export function detectWebGL() {
  if (typeof document === 'undefined') {
    return { ok: false, reason: 'no document (SSR)' }
  }
  try {
    const canvas = document.createElement('canvas')
    const gl2 = canvas.getContext('webgl2', { failIfMajorPerformanceCaveat: false })
    if (gl2) return { ok: true, version: 2, reason: null }
    const gl1 = canvas.getContext('webgl', { failIfMajorPerformanceCaveat: false })
      || canvas.getContext('experimental-webgl', { failIfMajorPerformanceCaveat: false })
    if (gl1) return { ok: true, version: 1, reason: null }
    return { ok: false, reason: 'WebGL not available in this browser/GPU' }
  } catch (err) {
    return { ok: false, reason: err?.message || String(err) }
  }
}
