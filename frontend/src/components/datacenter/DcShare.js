/**
 * Shareable PNG helpers for the data-hall twin — kept free of R3F so the 2D
 * floor view can import them without pulling Three.js into the main chunk.
 */

/** Download a canvas as PNG. Returns the data URL (or null). */
export function captureCanvasPng(canvas, { filename = 'fixitlab-dc-photo.png', download = true } = {}) {
  if (!canvas || typeof canvas.toDataURL !== 'function') return null
  let url
  try { url = canvas.toDataURL('image/png') } catch { return null }
  if (download && typeof document !== 'undefined') {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
  }
  return url
}

/** Flat orthographic rack map — shareable 2D floor plan without WebGL. */
export function renderFloorPlanPng(
  { racks = [], serversByRack = {}, width = 900, height = 560 } = {},
  { filename = 'fixitlab-dc-floor.png', download = true, createCanvas } = {},
) {
  const make = createCanvas
    || (typeof document !== 'undefined' ? (w, h) => {
      const c = document.createElement('canvas')
      c.width = w
      c.height = h
      return c
    } : null)
  if (!make) return null
  const canvas = make(width, height)
  const ctx = canvas.getContext?.('2d')
  if (!ctx) return null
  ctx.fillStyle = '#0b1220'
  ctx.fillRect(0, 0, width, height)
  ctx.fillStyle = '#94a3b8'
  ctx.font = '14px sans-serif'
  ctx.fillText('FixitLab · Data hall floor plan', 16, 28)
  const cols = 4
  const cellW = (width - 48) / cols
  const cellH = 110
  ;(racks || []).forEach((rack, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    const x = 24 + col * cellW
    const y = 48 + row * (cellH + 16)
    const list = serversByRack?.[rack.id] || []
    const alert = list.some((s) => Object.values(s.components || {}).some((c) => c !== 'healthy'))
    ctx.fillStyle = alert ? '#7f1d1d' : '#1e293b'
    ctx.fillRect(x, y, cellW - 12, cellH)
    ctx.strokeStyle = alert ? '#ef4444' : '#38bdf8'
    ctx.strokeRect(x, y, cellW - 12, cellH)
    ctx.fillStyle = '#e2e8f0'
    ctx.fillText(String(rack.id || `R${i}`), x + 8, y + 22)
    ctx.fillStyle = '#94a3b8'
    ctx.fillText(`${list.length} servers`, x + 8, y + 44)
  })
  return captureCanvasPng(canvas, { filename, download })
}
