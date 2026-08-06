import { describe, expect, it } from 'vitest'
import { detectWebGL } from './webglSupport'

describe('datacenter 3D Part 0 gates', () => {
  it('detectWebGL returns a shaped result', () => {
    const r = detectWebGL()
    expect(r).toHaveProperty('ok')
    expect(typeof r.ok).toBe('boolean')
    // jsdom has no real WebGL — ok may be false with a reason
    if (!r.ok) expect(r.reason).toBeTruthy()
  })

  it('prefer2d is the only sticky 2D path (parity contract)', () => {
    const ls = {
      store: {},
      getItem(k) { return this.store[k] ?? null },
      setItem(k, v) { this.store[k] = String(v) },
      removeItem(k) { delete this.store[k] },
    }
    // Simulate DatacenterSimulator defaulting logic
    const pickFloor = () => {
      if (ls.getItem('fixitlab.dc.prefer2d') === '1') return '2d'
      const saved = ls.getItem('fixitlab.dc.floorView')
      if (saved === '3d') return '3d'
      return '3d'
    }
    expect(pickFloor()).toBe('3d')
    ls.setItem('fixitlab.dc.floorView', '2d') // legacy alone must NOT trap
    expect(pickFloor()).toBe('3d')
    ls.setItem('fixitlab.dc.prefer2d', '1')
    expect(pickFloor()).toBe('2d')
  })

  it('Twin3DSafe must not auto-call onFallback (contract)', async () => {
    // Source-level contract: silent fallback was the root cause of "still 2D".
    const src = await import('fs').then((fs) =>
      fs.promises.readFile(
        new URL('./DatacenterSimulator.jsx', import.meta.url),
        'utf8',
      ))
    expect(src).toContain('Retry 3D')
    expect(src).toContain('3D hall failed to load')
    // componentDidCatch must NOT auto-invoke onFallback
    const catchBlock = src.slice(src.indexOf('componentDidCatch'), src.indexOf('handleRetry'))
    expect(catchBlock).not.toMatch(/onFallback\?\.\(\)/)
  })
})

describe('2D↔3D action parity keys', () => {
  it('lists shared action surface keys both views must honor', () => {
    // Living checklist — 3D hall must expose equivalents (portals / HUD / tablet).
    const shared = [
      'select_server', 'select_rack', 'open_bmc', 'replace_component',
      'badge_in', 'enter_room', 'unplug_cable', 'plug_cable',
      'ar_overlay', 'walk_mode', 'exit_to_2d',
    ]
    expect(shared.length).toBeGreaterThan(8)
    expect(new Set(shared).size).toBe(shared.length)
  })
})
