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

describe('LOD face-detail cull contract', () => {
  it('ServerFaceDetail distance-culls face detail', async () => {
    const fs = await import('fs')
    const src = await fs.promises.readFile(
      new URL('./DatacenterTwin3D.jsx', import.meta.url),
      'utf8',
    )
    const face = src.slice(src.indexOf('function ServerFaceDetail'), src.indexOf('function RackInner'))
    expect(face).toContain('FACE_DETAIL_MAX_DIST')
    expect(face).toContain('FACE_HTML_MAX_DIST')
    expect(face).toContain('distanceTo')
    expect(face).toContain('group.current.visible')
  })
})

describe('shadow map quality contract', () => {
  it('high quality uses 2048² shadow map; medium keeps 1024', async () => {
    const fs = await import('fs')
    const src = await fs.promises.readFile(
      new URL('./DatacenterTwin3D.jsx', import.meta.url),
      'utf8',
    )
    expect(src).toContain('shadowMap: 2048')
    expect(src).toContain('shadowMap: 1024')
    expect(src).toContain('shadow-camera-left={-12}')
    expect(src).toContain('shadowMapSize={qualityCfg.shadowMap}')
  })
})

describe('bloom postprocessing contract', () => {
  it('gates Bloom on qualityCfg.bloom and imports postprocessing', async () => {
    const fs = await import('fs')
    const pkg = JSON.parse(await fs.promises.readFile(
      new URL('../../../package.json', import.meta.url),
      'utf8',
    ))
    expect(pkg.dependencies['@react-three/postprocessing']).toBeTruthy()
    const src = await fs.promises.readFile(
      new URL('./DatacenterTwin3D.jsx', import.meta.url),
      'utf8',
    )
    expect(src).toContain("@react-three/postprocessing")
    expect(src).toContain('bloom: false')
    expect(src).toContain('bloom: true')
    expect(src).toContain('qualityCfg.bloom')
    expect(src).toContain('<Bloom')
  })
})

describe('procedural textures contract', () => {
  it('Floor and racks use DcTextures canvas maps', async () => {
    const fs = await import('fs')
    const src = await fs.promises.readFile(
      new URL('./DatacenterTwin3D.jsx', import.meta.url),
      'utf8',
    )
    expect(src).toContain("from './DcTextures'")
    expect(src).toContain('makeFloorTileTexture')
    expect(src).toContain('makeBrushedMetalTexture')
    const tex = await fs.promises.readFile(
      new URL('./DcTextures.js', import.meta.url),
      'utf8',
    )
    expect(tex).toContain('CanvasTexture')
  })
})

describe('walkable 3D room types', () => {
  it('gates 3D twin on network/mechanical/electrical/security/campus/office/ops', async () => {
    const fs = await import('fs')
    const src = await fs.promises.readFile(
      new URL('./DatacenterSimulator.jsx', import.meta.url),
      'utf8',
    )
    expect(src).toContain("WALKABLE_3D_ROOM_TYPES")
    expect(src).toContain("'network'")
    expect(src).toContain("'mechanical'")
    expect(src).toContain("'electrical'")
    expect(src).toContain("'security'")
    expect(src).toContain("'campus'")
    expect(src).toContain("'office'")
    expect(src).toContain("'ops'")
    expect(src).toContain('isWalkable3dRoom(currentRoom.type)')
  })
})
