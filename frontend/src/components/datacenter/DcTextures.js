/**
 * Procedural canvas textures for the datacenter twin (no CDN assets).
 * Floor tile albedo + brushed-metal rack map — audit D12 texture half.
 */
import * as THREE from 'three'

function makeCanvas(size) {
  const canvas = typeof document !== 'undefined'
    ? document.createElement('canvas')
    : null
  if (!canvas) return null
  canvas.width = size
  canvas.height = size
  return canvas
}

/** Raised-floor tile: dark panel with optional perforation grid. */
export function makeFloorTileTexture({ perforated = false, size = 128 } = {}) {
  const canvas = makeCanvas(size)
  if (!canvas) return null
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = perforated ? '#243044' : '#1a2030'
  ctx.fillRect(0, 0, size, size)
  // Bevel / panel seam
  ctx.strokeStyle = '#0b1220'
  ctx.lineWidth = 3
  ctx.strokeRect(2, 2, size - 4, size - 4)
  ctx.strokeStyle = '#334155'
  ctx.lineWidth = 1
  ctx.strokeRect(6, 6, size - 12, size - 12)
  if (perforated) {
    ctx.fillStyle = '#0ea5e9'
    const step = Math.max(8, Math.floor(size / 10))
    for (let y = step; y < size - step; y += step) {
      for (let x = step; x < size - step; x += step) {
        ctx.beginPath()
        ctx.arc(x, y, 2.2, 0, Math.PI * 2)
        ctx.fill()
      }
    }
  } else {
    // Speckle for concrete/raised-floor noise
    ctx.fillStyle = 'rgba(148,163,184,0.12)'
    for (let i = 0; i < 80; i++) {
      ctx.fillRect(Math.random() * size, Math.random() * size, 1.5, 1.5)
    }
  }
  const tex = new THREE.CanvasTexture(canvas)
  if ('SRGBColorSpace' in THREE) tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 4
  tex.needsUpdate = true
  return tex
}

/** Brushed metal for rack chassis — horizontal grain. */
export function makeBrushedMetalTexture({ size = 128, base = '#334155' } = {}) {
  const canvas = makeCanvas(size)
  if (!canvas) return null
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = base
  ctx.fillRect(0, 0, size, size)
  for (let y = 0; y < size; y++) {
    const a = 0.04 + (Math.sin(y * 0.35) + 1) * 0.03
    ctx.fillStyle = `rgba(226,232,240,${a})`
    ctx.fillRect(0, y, size, 1)
  }
  const tex = new THREE.CanvasTexture(canvas)
  if ('SRGBColorSpace' in THREE) tex.colorSpace = THREE.SRGBColorSpace
  tex.wrapS = THREE.RepeatWrapping
  tex.wrapT = THREE.RepeatWrapping
  tex.repeat.set(1, 2)
  tex.needsUpdate = true
  return tex
}
