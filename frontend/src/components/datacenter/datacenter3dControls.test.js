/**
 * Audit D2/D3/D4/D6/D8/D9/D12 — first-person control-loop and scene contracts.
 *
 * The suite is split in two deliberately:
 *  - Behavioural tests against the pure helpers exported from DatacenterTwin3D.
 *    These are the ones that can actually fail on a regression.
 *  - Source-level contract tests for the wiring that only exists inside R3F
 *    components. vitest runs in `environment: 'node'` (see vite.config.js) with no
 *    DOM and no WebGL, so a <Canvas> cannot be mounted here; asserting on the
 *    source is the honest alternative to not testing it at all. The same technique
 *    is already used by datacenter3dParity.test.js for the Twin3DSafe contract.
 */
import { describe, expect, it } from 'vitest'
import { promises as fs } from 'fs'
import * as THREE from 'three'
import { decay, computeTipWorld, updateCurvePoints, estimateBendRadiusMm, minBendRadiusMm, suppressPointerUnlockPause, isPointerUnlockPauseSuppressed } from './DcCableSystem'
import {
  MAX_FRAME_DT,
  clampDt,
  DEFAULT_LOOK,
  DEFAULT_BINDS,
  PITCH_LIMIT,
  applyLook,
  readLookSettings,
  writeLookSettings,
  readBinds,
  writeBinds,
  movementIntent,
  mergeIntent,
  gamepadSample,
  setTouchHold,
  clearTouchHold,
  touchHoldRef,
  touchLookDelta,
  deviceOrientationLookDelta,
  requestGyroPermission,
  prefersCoarsePointer,
  pduLoadFraction,
  pduMeterLabel,
  pdusForRack,
  buildPduPsuCables,
  walkKeySet,
  isTypingTarget,
  isSprinting,
  WALK_KEYS,
  chassisMetrics,
  freeUSlots,
  findInteractable,
  MAX_INTERACT_DISTANCE,
  FACE_DETAIL_MAX_DIST,
  FACE_HTML_MAX_DIST,
  DistanceCullingHtml,
  HTML_LABEL_MAX_DIST,
  EYE_Y,
  CONTROL_BINDINGS,
  buildHallColliders,
  resolveWalk,
  stepVertical,
  PLAYER_RADIUS,
  HALL_BOUNDS,
  CROUCH_EYE_Y,
  CEILING_Y,
  sanitizeSpawn,
  readPlayerPos,
  writePlayerPos,
  playerPosKey,
  SAFE_SPAWN,
  captureCanvasPng,
  renderFloorPlanPng,
  nextFpsLodState,
  applyFpsLodCfg,
  FPS_LOD_THRESHOLD,
} from './DatacenterTwin3D'

const readSource = (name) => fs.readFile(new URL(`./${name}`, import.meta.url), 'utf8')

const makeStore = (seed) => {
  const data = { ...seed }
  return {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v) },
    removeItem: (k) => { delete data[k] },
  }
}

describe('D4 — frame delta clamping', () => {
  it('clamps an alt-tab / GC pause to the max step', () => {
    // 3.4s at sprint speed (6.1 m/s) is a 20m jump — straight through the racks.
    expect(clampDt(3.4)).toBe(MAX_FRAME_DT)
    expect(clampDt(3.4) * 6.1).toBeLessThan(0.65)
  })

  it('leaves a normal 60fps frame untouched', () => {
    expect(clampDt(1 / 60)).toBeCloseTo(1 / 60, 6)
  })

  it('survives NaN / undefined / negative dt without producing NaN movement', () => {
    expect(clampDt(NaN)).toBe(0)
    expect(clampDt(undefined)).toBe(0)
    expect(clampDt(-1)).toBe(0)
  })

  it('the walk loop, rack intro and particles all route dt through the clamp', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    // Regression guard for the specific bug: wall-clock deltas in the intro
    // animations completed them while the tab was hidden.
    const rackIntro = src.slice(src.indexOf('function RackMesh'), src.indexOf('function RackMesh') + 1200)
    expect(rackIntro).toContain('clampDt')
    const rackCode = rackIntro.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '')
    expect(rackCode).not.toMatch(/performance\.now\(\)/)

    const stack = src.slice(src.indexOf('function ServerStack'), src.indexOf('function ServerFaceDetail'))
    expect(stack).toContain('clampDt')
    // Strip comments first — the fix is documented with a prose reference to the
    // wall clock, and that must not count as a use of it.
    const stackCode = stack.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '')
    expect(stackCode).not.toMatch(/performance\.now\(\)/)
  })
})

describe('D3 — camera Y is written before it is read', () => {
  it('assigns pos.current.y above the camera.position.set() that consumes it', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    // Y is now the output of stepVertical() rather than the EYE_Y constant
    // (crouch/jump, audit L578) — the write-before-read ordering is the invariant,
    // not the particular right-hand side.
    const assign = src.indexOf('pos.current.y = vert.y')
    const consume = src.indexOf('camera.position.set(pos.current.x + sway')
    expect(assign).toBeGreaterThan(-1)
    expect(consume).toBeGreaterThan(-1)
    // The whole bug was that these two were the other way round.
    expect(assign).toBeLessThan(consume)
  })

  it('exposes eye height as a shared constant rather than a magic literal', () => {
    expect(EYE_Y).toBeGreaterThan(1.4)
    expect(EYE_Y).toBeLessThan(1.9)
  })
})

describe('D6 — mouse look', () => {
  it('applies the historical 0.0026 rad/px by default on both axes', () => {
    const r = applyLook({ yaw: 0, pitch: 0 }, 100, 100, DEFAULT_LOOK)
    expect(r.yaw).toBeCloseTo(-0.26, 6)
    expect(r.pitch).toBeCloseTo(-0.26, 6)
  })

  it('honours a sensitivity change', () => {
    const slow = applyLook({ yaw: 0, pitch: 0 }, 100, 0, { ...DEFAULT_LOOK, sensitivity: 0.0013 })
    expect(slow.yaw).toBeCloseTo(-0.13, 6)
  })

  it('inverts Y only, never X', () => {
    const normal = applyLook({ yaw: 0, pitch: 0 }, 50, 50, DEFAULT_LOOK)
    const inverted = applyLook({ yaw: 0, pitch: 0 }, 50, 50, { ...DEFAULT_LOOK, invertY: true })
    expect(inverted.yaw).toBeCloseTo(normal.yaw, 9)
    expect(inverted.pitch).toBeCloseTo(-normal.pitch, 9)
  })

  it('scales the Y axis independently', () => {
    const r = applyLook({ yaw: 0, pitch: 0 }, 100, 100, { ...DEFAULT_LOOK, yScale: 0.5 })
    expect(r.pitch).toBeCloseTo(-0.13, 6)
    expect(r.yaw).toBeCloseTo(-0.26, 6)
  })

  it('clamps pitch so the camera cannot roll over the top', () => {
    expect(applyLook({ yaw: 0, pitch: 0 }, 0, -100000).pitch).toBe(PITCH_LIMIT)
    expect(applyLook({ yaw: 0, pitch: 0 }, 0, 100000).pitch).toBe(-PITCH_LIMIT)
  })

  it('never yields NaN from a movementless event', () => {
    const r = applyLook({ yaw: 0.5, pitch: 0.1 }, 0, 0)
    expect(Number.isFinite(r.yaw)).toBe(true)
    expect(Number.isFinite(r.pitch)).toBe(true)
  })
})

describe('D6 — look settings persistence', () => {
  const makeStore = (seed) => {
    const store = { ...seed }
    return {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v) },
      raw: store,
    }
  }

  it('falls back to defaults with no stored value', () => {
    expect(readLookSettings(makeStore({}))).toEqual(DEFAULT_LOOK)
  })

  it('round-trips a saved setting', () => {
    const s = makeStore({})
    writeLookSettings(s, { sensitivity: 0.004, yScale: 1.5, invertY: true })
    expect(readLookSettings(s)).toEqual({ sensitivity: 0.004, yScale: 1.5, invertY: true })
  })

  it('clamps a hostile stored value instead of soft-locking the camera', () => {
    // 0 sensitivity is unrecoverable in-world: you cannot look at the menu button
    // that would fix it. Huge values are equally unusable.
    const zero = readLookSettings(makeStore({ 'fixitlab.dc.look': '{"sensitivity":0}' }))
    expect(zero.sensitivity).toBeGreaterThan(0)
    const huge = readLookSettings(makeStore({ 'fixitlab.dc.look': '{"sensitivity":999}' }))
    expect(huge.sensitivity).toBeLessThanOrEqual(0.012)
  })

  it('survives corrupt JSON and a throwing storage (private mode)', () => {
    expect(readLookSettings(makeStore({ 'fixitlab.dc.look': 'not json' }))).toEqual(DEFAULT_LOOK)
    const throwing = { getItem() { throw new Error('denied') }, setItem() { throw new Error('denied') } }
    expect(readLookSettings(throwing)).toEqual(DEFAULT_LOOK)
    expect(() => writeLookSettings(throwing, DEFAULT_LOOK)).not.toThrow()
    expect(readLookSettings(null)).toEqual(DEFAULT_LOOK)
  })
})

describe('D6 — key rebinding', () => {
  it('round-trips remapped walk binds', () => {
    const s = makeStore({})
    writeBinds(s, { ...DEFAULT_BINDS, forward: 'KeyI', interact: 'KeyF' })
    const loaded = readBinds(s)
    expect(loaded.forward).toBe('KeyI')
    expect(loaded.interact).toBe('KeyF')
    expect(loaded.back).toBe('KeyS')
  })

  it('drives movementIntent from the bind map (arrows stay aliases)', () => {
    const binds = { ...DEFAULT_BINDS, forward: 'KeyI' }
    expect(movementIntent({ KeyI: true }, binds).forward).toBe(true)
    expect(movementIntent({ KeyW: true }, binds).forward).toBe(false)
    expect(movementIntent({ ArrowUp: true }, binds).forward).toBe(true)
    expect(walkKeySet(binds).has('KeyI')).toBe(true)
  })

  it('exposes rebind actions on the controls table', () => {
    const rebindable = CONTROL_BINDINGS.filter((b) => b.rebind?.length)
    expect(rebindable.length).toBeGreaterThanOrEqual(4)
  })
})

describe('D6 — gamepad half', () => {
  it('gamepadSample maps stick + buttons; mergeIntent ORs keyboard', () => {
    const pad = {
      connected: true,
      axes: [0.8, -0.9, 0.3, 0],
      buttons: [
        { pressed: true, value: 1 },
        { pressed: false, value: 0 },
        { pressed: false, value: 0 },
        { pressed: false, value: 0 },
        { pressed: true, value: 1 },
      ],
    }
    const g = gamepadSample(pad)
    expect(g.intent.forward).toBe(true)
    expect(g.intent.right).toBe(true)
    expect(g.jump).toBe(true)
    expect(g.sprint).toBe(true)
    expect(g.lookDx).toBeGreaterThan(0)
    expect(mergeIntent({ forward: true }, { left: true })).toEqual({
      forward: true, back: false, left: true, right: false,
    })
  })

  it('WalkController polls getGamepads', async () => {
    const src = await fs.readFile(new URL('./DatacenterTwin3D.jsx', import.meta.url), 'utf8')
    expect(src).toContain('getGamepads')
    expect(src).toContain('gamepadSample')
    expect(src).toContain('mergeIntent')
  })
})

describe('D6 — touch pad half', () => {
  it('touchHoldRef merges with setTouchHold', () => {
    clearTouchHold()
    setTouchHold({ forward: true, sprint: true })
    expect(touchHoldRef.current.forward).toBe(true)
    expect(touchHoldRef.current.sprint).toBe(true)
    expect(mergeIntent(movementIntent({}), touchHoldRef.current).forward).toBe(true)
    clearTouchHold()
    expect(touchHoldRef.current.forward).toBe(false)
  })

  it('mounts TouchWalkPad and SSAO/Vignette quality gates', async () => {
    const src = await fs.readFile(new URL('./DatacenterTwin3D.jsx', import.meta.url), 'utf8')
    expect(src).toContain('TouchWalkPad')
    expect(src).toContain('data-testid="dc-touch-pad"')
    expect(src).toContain('SSAO')
    expect(src).toContain('Vignette')
    expect(src).toContain('ssao: true')
    expect(prefersCoarsePointer(() => ({ matches: true }))).toBe(true)
  })

  it('touch look-stick yields deltas without pointer lock', () => {
    clearTouchHold()
    setTouchHold({ lookLeft: true, lookUp: true })
    const d = touchLookDelta(touchHoldRef.current, 2)
    expect(d.dx).toBe(-2)
    expect(d.dy).toBe(-2)
    clearTouchHold()
  })

  it('deviceOrientationLookDelta is relative and requestGyroPermission is safe', async () => {
    const prev = { current: null }
    expect(deviceOrientationLookDelta({ beta: 10, gamma: 5 }, prev)).toEqual({ dx: 0, dy: 0 })
    const d = deviceOrientationLookDelta({ beta: 12, gamma: 9 }, prev, 1)
    expect(d.dx).toBe(4)
    expect(d.dy).toBe(2)
    expect(await requestGyroPermission({ requestPermission: async () => 'granted' })).toBe(true)
    expect(await requestGyroPermission({ requestPermission: async () => 'denied' })).toBe(false)
  })
})

describe('D12 — ToR-in-rack + Noise', () => {
  it('mounts per-rack TorSwitch and high-quality Noise', async () => {
    const src = await fs.readFile(new URL('./DatacenterTwin3D.jsx', import.meta.url), 'utf8')
    expect(src).toContain('tor-${rack.id}')
    expect(src).toContain('RACK_H + 0.18')
    expect(src).toContain('Noise')
    expect(src).toContain('noise: true')
  })
})

describe('D12 — PDU whips + patch panel', () => {
  it('buildPduPsuCables emits A/B whips; PatchPanel mounts', async () => {
    const cables = buildPduPsuCables(
      [{ id: 'r1', name: 'R1' }],
      [
        { id: 'PDU-r1', rack: 'r1', feed: 'A' },
        { id: 'PDU-r1-B', rack: 'r1', feed: 'B' },
      ],
    )
    expect(cables.length).toBe(2)
    expect(cables[0].from).toHaveLength(3)
    const src = await fs.readFile(new URL('./DatacenterTwin3D.jsx', import.meta.url), 'utf8')
    expect(src).toContain('PduPsuCables')
    expect(src).toContain('PatchPanel')
  })
})

describe('D12 — dual PDU + amp meter', () => {
  it('pduLoadFraction prefers kW rating; pdusForRack pairs A/B', () => {
    expect(pduLoadFraction({ load_kw: 4, rating_kw: 8 })).toBe(0.5)
    expect(pduMeterLabel({ load_kw: 4, rating_kw: 8 })).toContain('4.0/8kW')
    expect(pduMeterLabel({ status: 'tripped' })).toBe('PDU TRIP')
    const { feedA, feedB } = pdusForRack([
      { id: 'PDU-r1', rack: 'r1', feed: 'A', load_kw: 2, rating_kw: 8 },
      { id: 'PDU-r1-B', rack: 'r1', feed: 'B', load_kw: 1, rating_kw: 8 },
    ], 'r1')
    expect(feedA.feed).toBe('A')
    expect(feedB.feed).toBe('B')
  })
})

describe('Photo mode / floor share', () => {
  it('captureCanvasPng returns a data URL without requiring download DOM', () => {
    const canvas = {
      toDataURL: () => 'data:image/png;base64,AAA',
    }
    expect(captureCanvasPng(canvas, { download: false })).toBe('data:image/png;base64,AAA')
    expect(captureCanvasPng(null, { download: false })).toBeNull()
  })

  it('renderFloorPlanPng draws racks onto a stub canvas', () => {
    const ops = []
    const stub = {
      width: 0,
      height: 0,
      getContext: () => ({
        fillRect: (...a) => ops.push(['fillRect', ...a]),
        strokeRect: (...a) => ops.push(['strokeRect', ...a]),
        fillText: (...a) => ops.push(['fillText', a[0]]),
        fillStyle: '',
        strokeStyle: '',
        font: '',
      }),
      toDataURL: () => 'data:image/png;base64,FLOOR',
    }
    const url = renderFloorPlanPng(
      { racks: [{ id: 'R01' }], serversByRack: { R01: [{ components: { psu: 'healthy' } }] } },
      { download: false, createCanvas: () => stub },
    )
    expect(url).toBe('data:image/png;base64,FLOOR')
    expect(ops.some((o) => o[0] === 'fillText' && String(o[1]).includes('R01'))).toBe(true)
  })
})

describe('D6 — keyboard hygiene', () => {
  it('treats text-entry surfaces as not-the-game', () => {
    // This is the fix for "WASD types into every input in the app".
    expect(isTypingTarget({ tagName: 'INPUT' })).toBe(true)
    expect(isTypingTarget({ tagName: 'textarea' })).toBe(true)
    expect(isTypingTarget({ tagName: 'SELECT' })).toBe(true)
    expect(isTypingTarget({ tagName: 'DIV', isContentEditable: true })).toBe(true)
    expect(isTypingTarget({ tagName: 'CANVAS' })).toBe(false)
    expect(isTypingTarget(null)).toBe(false)
    expect(isTypingTarget(undefined)).toBe(false)
  })

  it('claims the keys that would otherwise scroll the page', () => {
    // Space and the arrows scroll the document underneath the canvas.
    expect(WALK_KEYS.has('Space')).toBe(true)
    expect(WALK_KEYS.has('ArrowUp')).toBe(true)
    expect(WALK_KEYS.has('ArrowDown')).toBe(true)
    // ...but must not swallow the room hotkeys or Esc, which other handlers own.
    expect(WALK_KEYS.has('Escape')).toBe(false)
    expect(WALK_KEYS.has('Digit1')).toBe(false)
    expect(WALK_KEYS.has('KeyV')).toBe(false)
  })

  it('sprints on either shift key', () => {
    expect(isSprinting({ ShiftLeft: true })).toBe(true)
    // The bug: only ShiftLeft was read, so right-handed arrow-key players
    // had no sprint at all.
    expect(isSprinting({ ShiftRight: true })).toBe(true)
    expect(isSprinting({})).toBe(false)
    expect(isSprinting(null)).toBe(false)
  })

  it('binds keydown with a target guard and preventDefault, and clears held keys on blur', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const walk = src.slice(src.indexOf('function WalkController'), src.indexOf('/** Floating dust motes'))
    expect(walk).toContain('isTypingTarget(e.target)')
    expect(walk).toContain('e.preventDefault()')
    // Alt-tab while holding W used to leave the player drifting forever.
    expect(walk).toContain("window.addEventListener('blur', clearKeys)")
    expect(walk).toContain("document.addEventListener('visibilitychange'")
  })

  it('binds mousemove to the canvas, not window', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const walk = src.slice(src.indexOf('function WalkController'), src.indexOf('/** Floating dust motes'))
    expect(walk).toContain("canvas.addEventListener('mousemove', move)")
    expect(walk).not.toContain("window.addEventListener('mousemove'")
  })

  it('keeps paused out of the listener effect deps so a menu toggle does not rebuild them', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const walk = src.slice(src.indexOf('function WalkController'), src.indexOf('/** Floating dust motes'))
    expect(walk).toContain('pausedRef')
    // The dep array of the listener effect must not contain `paused`.
    const deps = walk.match(/\}, \[enabled, camera, gl[^\]]*\]\)/)
    expect(deps).toBeTruthy()
    expect(deps[0]).not.toContain('paused')
  })
})

describe('D2 — pointer lock is observed, not assumed', () => {
  it('registers pointerlockchange and pointerlockerror listeners', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    // Zero of either existed before; loss of lock was undetectable.
    expect(src).toContain("document.addEventListener('pointerlockchange'")
    expect(src).toContain("document.addEventListener('pointerlockerror'")
    expect(src).toContain("document.removeEventListener('pointerlockchange'")
    expect(src).toContain("document.removeEventListener('pointerlockerror'")
  })

  it('no longer auto-locks on a timer without a user gesture', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const walk = src.slice(src.indexOf('function WalkController'), src.indexOf('/** Floating dust motes'))
    // The old setTimeout(() => requestPointerLock(), 120) threw SecurityError in
    // Chrome and was swallowed by an empty catch.
    expect(walk).not.toMatch(/setTimeout\([^)]*requestPointerLock/s)
    expect(src).toContain('ClickToPlay')
  })

  it('Esc opens the menu but never toggles it closed', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    // Prefer the immersive room-hotkey handler — ControlsPanel also listens for Escape
    // while capturing a rebind, which must not confuse this contract.
    const marker = 'Open-only. The browser has already released'
    const at = src.indexOf(marker)
    expect(at).toBeGreaterThan(0)
    const esc = src.slice(at - 120, at + 420)
    // A plain toggle fights the unlock-triggered open and makes the menu reopen
    // itself on every unlock (the risk called out in the audit).
    expect(esc).not.toContain('setMenuOpen((m) => !m)')
    expect(esc).toContain('setMenuOpen(true)')
  })

  it('resuming re-locks the pointer instead of stranding the player', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const resume = src.slice(src.indexOf('const resumeWalking'), src.indexOf('const resumeWalking') + 260)
    expect(resume).toContain('engagePointerLock()')
    // and the menu's Resume button must be wired to it, not to a bare setMenuOpen(false)
    expect(src).toContain('onResume={resumeWalking}')
  })
})

describe('D6/D11 — crosshair interaction', () => {
  it('finds the interact descriptor on an ancestor of the hit mesh', () => {
    const root = { userData: { interact: { label: 'Open rack RACK-01', action: () => 'opened' } }, parent: null }
    const mid = { userData: {}, parent: root }
    const leafMesh = { userData: {}, parent: mid }
    const found = findInteractable(leafMesh)
    expect(found.label).toBe('Open rack RACK-01')
    expect(found.action()).toBe('opened')
  })

  it('returns null for scenery and does not walk forever on a cyclic parent', () => {
    expect(findInteractable({ userData: {}, parent: null })).toBeNull()
    expect(findInteractable(null)).toBeNull()
    const a = { userData: {} }
    a.parent = a
    expect(findInteractable(a)).toBeNull()
  })

  it('stops at the configured depth rather than scanning the whole scene graph', () => {
    let node = { userData: { interact: { label: 'far', action: () => {} } }, parent: null }
    for (let i = 0; i < 20; i += 1) node = { userData: {}, parent: node }
    expect(findInteractable(node)).toBeNull()
  })

  it('limits reach to arm-ish distance', () => {
    expect(MAX_INTERACT_DISTANCE).toBeGreaterThan(1)
    expect(MAX_INTERACT_DISTANCE).toBeLessThan(6)
    expect(FACE_DETAIL_MAX_DIST).toBeGreaterThan(MAX_INTERACT_DISTANCE)
    expect(FACE_HTML_MAX_DIST).toBeLessThanOrEqual(FACE_DETAIL_MAX_DIST)
    expect(FACE_HTML_MAX_DIST).toBe(HTML_LABEL_MAX_DIST)
  })

  it('distance-culls rack/PDU/ticket/portal/cable Html labels (D10 half)', async () => {
    expect(typeof DistanceCullingHtml).toBe('function')
    const twin = await readSource('DatacenterTwin3D.jsx')
    expect(twin).toContain('DistanceCullingHtml')
    expect(twin).toMatch(/DistanceCullingHtml[\s\S]*RACK_H \+ 0\.06/)
    expect(twin).toContain('TicketWaypoint')
    const cable = await readSource('DcCableSystem.jsx')
    expect(cable).toContain('DistanceCullingHtml')
    const lod = await readSource('DcLod.jsx')
    expect(lod).toContain('group.current.visible')
    expect(lod).toContain('distanceTo')
  })

  it('uses a real raycaster instead of a synthetic MouseEvent at canvas center', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const ci = src.slice(src.indexOf('function CrosshairInteract'), src.indexOf('function InteractPrompt'))
    expect(ci).toContain('raycaster.setFromCamera')
    // The old implementation faked the raycast and picked drei <Html> overlays.
    expect(ci).not.toContain('new MouseEvent')
    expect(ci).not.toContain('dispatchEvent')
  })

  it('reports unlocked state instead of silently no-opping', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const ci = src.slice(src.indexOf('function CrosshairInteract'), src.indexOf('function InteractPrompt'))
    expect(ci).toContain("kind: 'locked'")
    expect(src).toContain('InteractPrompt')
  })

  it('tags the racks, portals, badge desk and ticket beacons as interactables', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const tags = src.match(/userData=\{\{[\s\S]{0,200}?interact:/g) || []
    expect(tags.length).toBeGreaterThanOrEqual(4)
    expect(src).toContain('Open rack ${rack.name || rack.id}')
    expect(src).toContain('Badge in at the mantrap')
  })
})

describe('D12 — multi-U chassis and rack occupancy', () => {
  it('renders a 1U chassis as 1U', () => {
    const m = chassisMetrics({ u_slot: 1, u_height: 1 }, 1)
    expect(m.uHeight).toBe(1)
    expect(m.height).toBeCloseTo(0.9, 6)
  })

  it('renders a 4U GPU chassis four times as tall', () => {
    // The 3D layer ignored u_height entirely, so every chassis drew as 1U.
    const one = chassisMetrics({ u_slot: 10, u_height: 1 }, 1)
    const four = chassisMetrics({ u_slot: 10, u_height: 4 }, 1)
    expect(four.height / one.height).toBeCloseTo(4, 6)
  })

  it('centres a multi-U chassis over the U span it occupies, not over its bottom U', () => {
    // u_slot is the BOTTOM U (DCIM convention): a 2U at U10 fills U10-U11.
    const two = chassisMetrics({ u_slot: 10, u_height: 2 }, 1)
    expect(two.y).toBeCloseTo(9 + 1 + 0.05, 6)
    const one = chassisMetrics({ u_slot: 10, u_height: 1 }, 1)
    expect(two.y - one.y).toBeCloseTo(0.5, 6)
  })

  it('defaults missing / junk u_height to 1U and clamps absurd values', () => {
    expect(chassisMetrics({}).uHeight).toBe(1)
    expect(chassisMetrics({ u_height: null }).uHeight).toBe(1)
    expect(chassisMetrics({ u_height: 'abc' }).uHeight).toBe(1)
    expect(chassisMetrics({ u_height: 0 }).uHeight).toBe(1)
    expect(chassisMetrics({ u_height: 900 }).uHeight).toBe(12)
  })

  it('reports free U, accounting for the full span of multi-U chassis', () => {
    const free = freeUSlots([{ u_slot: 1, u_height: 4 }], 42)
    // U1-U4 taken by the 4U box.
    expect(free).not.toContain(1)
    expect(free).not.toContain(4)
    expect(free).toContain(5)
    expect(free).toHaveLength(38)
  })

  it('reports a full rack as zero free U and an empty rack as all 42', () => {
    const packed = Array.from({ length: 42 }, (_, i) => ({ u_slot: i + 1, u_height: 1 }))
    expect(freeUSlots(packed, 42)).toHaveLength(0)
    expect(freeUSlots([], 42)).toHaveLength(42)
  })

  it('renders blanking panels over the empty U', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    expect(src).toContain('freeUSlots(servers)')
    expect(src).toContain('blank-')
  })
})

describe('D9 — FPS readout does not reconcile the scene', () => {
  it('writes the counter into a DOM node instead of root state', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    // setFps on the root re-rendered <Canvas> children once per second.
    expect(src).not.toContain('const [fps, setFps] = useState(0)')
    expect(src).toContain('fpsElRef')
    expect(src).toContain('fpsElRef.current.textContent')
  })
})

describe('D12 — lighting and particle budget', () => {
  it('does not create one pointLight per ceiling fixture', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const fn = src.slice(src.indexOf('function CeilingLights'), src.indexOf('function HotAisleGlow'))
    const inFixtureLoop = fn.slice(fn.indexOf('fixtures.map'), fn.indexOf('</group>\n      ))}'))
    expect(inFixtureLoop).not.toContain('pointLight')
  })

  it('keeps the particle budget fixed instead of scaling it with thermal stress', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    // Framerate used to be worst exactly during a crisis.
    expect(src).not.toContain('220 * animBoost * (1 + thermalStress * 1.4)')
    expect(src).toContain('220 * animBoost')
  })

  it('drives a red strobe from an alarm level', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    expect(src).toContain('function AlarmLighting')
    expect(src).toContain('alarm={alarmLevel}')
  })
})

describe('D7 — cables do not reallocate geometry per frame', () => {
  it('decays toward zero and clamps, without going negative', () => {
    expect(decay(1, 1 / 60, 2.2)).toBeCloseTo(1 - 2.2 / 60, 6)
    // A long frame must not push recoil below zero and re-trigger the >0 branch.
    expect(decay(0.1, 5, 2.2)).toBe(0)
    expect(decay(0, 1 / 60, 2.2)).toBe(0)
    // Guard against NaN dt poisoning the tip position for the rest of the session.
    expect(decay(1, NaN, 2.2)).toBe(1)
  })

  it('writes the tip position into the caller-owned vector instead of allocating', () => {
    const out = new THREE.Vector3()
    const to = new THREE.Vector3(1, 2, 3)
    const same = computeTipWorld(out, { to, loose: false, dragging: false, recoil: 0 })
    // Same object every call is the whole point: the Html overlay and the tip
    // group hold this reference across frames.
    expect(same).toBe(out)
    expect(out.toArray()).toEqual([1, 2, 3])

    computeTipWorld(out, { to, loose: true, dragging: false, tipOffset: new THREE.Vector3(), recoil: 0 })
    expect(out.y).toBeCloseTo(2 - 0.55, 6)
    expect(out.x).toBeCloseTo(1 + 0.22, 6)

    // Recoil sags the tip further, and unplugged cables must not snap back to `to`.
    computeTipWorld(out, { to, loose: false, dragging: false, tipOffset: new THREE.Vector3(), recoil: 1 })
    expect(out.y).toBeCloseTo(2 - 0.08 - 0.25, 6)
  })

  it('mutates the curve in place so packet animation follows the live path', () => {
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(),
      new THREE.Vector3(),
      new THREE.Vector3(),
      new THREE.Vector3(),
    ])
    const points = curve.points
    updateCurvePoints(curve, {
      from: new THREE.Vector3(0, 1, 0),
      tip: new THREE.Vector3(2, 1, 0),
      loose: false,
      dragging: false,
    })
    const firstEnd = curve.getPointAt(1).clone()
    expect(firstEnd.x).toBeCloseTo(2, 6)

    updateCurvePoints(curve, {
      from: new THREE.Vector3(0, 1, 0),
      tip: new THREE.Vector3(5, -1, 0),
      loose: true,
      dragging: false,
    })
    // Same Vector3 instances reused — no per-frame allocation.
    expect(curve.points).toBe(points)
    curve.points.forEach((p, i) => expect(p).toBe(points[i]))
    // getPointAt caches arc lengths; without updateArcLengths() the packets keep
    // riding the previous frame's curve even though the control points moved.
    const secondEnd = curve.getPointAt(1)
    expect(secondEnd.x).toBeCloseTo(5, 6)
    expect(secondEnd.y).toBeCloseTo(-1, 6)
    expect(secondEnd.distanceTo(firstEnd)).toBeGreaterThan(1)
  })

  it('copying a same-topology tube keeps one buffer and rewrites its vertices', () => {
    // This is the mechanism syncTube relies on: rebuilding on identical segment
    // counts yields identical buffer lengths, so the live geometry can absorb it.
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(1, 1, 0),
      new THREE.Vector3(2, -1, 0),
      new THREE.Vector3(3, 0, 1),
    ])
    const tube = new THREE.TubeGeometry(curve, 36, 0.013, 8, false)
    const buffer = tube.attributes.position
    const before = buffer.array.slice()

    curve.points[3].set(6, -2, 2)
    curve.updateArcLengths()
    const next = new THREE.TubeGeometry(curve, 36, 0.011, 8, false)
    expect(next.attributes.position.count).toBe(buffer.count)
    tube.attributes.position.copy(next.attributes.position)

    expect(tube.attributes.position).toBe(buffer)
    expect(Array.from(buffer.array)).not.toEqual(Array.from(before))
    next.dispose()
    tube.dispose()
  })

  it('never decays recoil/snapFlash through React state', async () => {
    const src = await readSource('DcCableSystem.jsx')
    const body = src.slice(src.indexOf('export function InteractiveCable'))
    // The original bug: setRecoil/setSnapFlash called inside useFrame re-rendered
    // the cable ~60x/sec, and the useMemo'd TubeGeometry(36x8) was rebuilt and
    // leaked on every one of those renders.
    expect(body).not.toMatch(/setRecoil|setSnapFlash/)
    expect(body).toMatch(/const recoil = useRef\(0\)/)
    expect(body).toMatch(/const snapFlash = useRef\(0\)/)
    // TubeGeometry must not be memo'd on anything that changes per frame.
    expect(body).toMatch(/useMemo\(\(\) => new THREE\.TubeGeometry\(curve, 36, 0\.013, 8, false\), \[curve\]\)/)
  })
})

describe('D8 — GPU resources are disposed', () => {
  it('disposes the ServerStack geometry and material on unmount', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const stack = src.slice(src.indexOf('function ServerStack'), src.indexOf('useFrame(({ clock }, rawDt)'))
    expect(stack).toContain('geo.dispose()')
    expect(stack).toContain('mat.dispose()')
  })

  it('disposes every cable TubeGeometry', async () => {
    const src = await readSource('DcCableSystem.jsx')
    expect(src).toContain('tube.dispose()')
  })
})

describe('D13 — onboarding and audio', () => {
  it('ships a re-readable controls screen covering every binding', () => {
    // Onboarding was a 5.2s toast shown once per mount with no way to re-read it.
    const actions = CONTROL_BINDINGS.map((b) => b.action.toLowerCase()).join(' ')
    expect(CONTROL_BINDINGS.length).toBeGreaterThanOrEqual(6)
    expect(actions).toMatch(/move/)
    expect(actions).toMatch(/sprint/)
    expect(actions).toMatch(/interact/)
    expect(actions).toMatch(/pause menu/)
    const keys = CONTROL_BINDINGS.flatMap((b) => b.keys)
    expect(keys).toContain('E')
    expect(keys).toContain('Esc')
  })

  it('reaches the controls screen from the pause menu', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    expect(src).toContain('function ControlsPanel')
    expect(src).toContain("setTab('controls')")
    // and the panel actually edits the look settings.
    expect(src).toContain('onLookChange')
  })

  it('adds footsteps, relay, door and klaxon SFX on the shared ambience bus', async () => {
    const src = await readSource('DcAmbientAudio.jsx')
    expect(src).toContain('footstep(')
    expect(src).toContain('relayClack(')
    expect(src).toContain('doorCycle(')
    expect(src).toContain('setKlaxon(')
    // Broadband noise, not a third oscillator — this is what makes HVAC read as air.
    expect(src).toContain('makeNoiseBuffer')
  })

  it('routes walk footsteps through that bus rather than a private AudioContext', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    expect(src).toContain('dcSfx()?.footstep')
    // A second AudioContext ignored the mute toggle.
    expect(src).not.toContain('WalkController._ac')
  })

  it('exposes a volume slider and keeps mute flags mutable after arm', async () => {
    const src = await readSource('DcAmbientAudio.jsx')
    expect(src).toContain('aria-label="Ambience volume"')
    expect(src).toContain('setVolume')
    // Stale create-time `muted` broke unmute for footsteps — flags object is required.
    expect(src).toContain('flags.muted')
    expect(src).toContain('AMBIENT_BASE_GAIN')
  })
})

describe('FPS LOD — cut particles / Rapier under 40fps', () => {
  it('enters LOD after consecutive low samples and exits after sustained recovery', () => {
    let s = { low: 0, high: 0, active: false }
    s = nextFpsLodState(s, 55)
    expect(s.active).toBe(false)
    s = nextFpsLodState(s, 30)
    expect(s.active).toBe(false) // first sample only
    s = nextFpsLodState(s, 28)
    expect(s.active).toBe(true)
    expect(s.low).toBeGreaterThanOrEqual(2)
    // One good frame is not enough to leave LOD.
    s = nextFpsLodState(s, 60)
    expect(s.active).toBe(true)
    for (let i = 0; i < 5; i += 1) s = nextFpsLodState(s, 60)
    expect(s.active).toBe(false)
  })

  it(`thresholds at ${FPS_LOD_THRESHOLD}fps and strips expensive post when active`, () => {
    const high = {
      dpr: [1, 2], dust: 160, shadows: true, anim: 1, shadowMap: 2048,
      bloom: true, ssao: true, vignette: true, noise: true,
    }
    const lod = applyFpsLodCfg(high, true)
    expect(lod.dust).toBeLessThanOrEqual(28)
    expect(lod.anim).toBeLessThanOrEqual(0.45)
    expect(lod.bloom).toBe(false)
    expect(lod.ssao).toBe(false)
    expect(lod.noise).toBe(false)
    expect(applyFpsLodCfg(high, false)).toEqual(high)
  })

  it('wires setFps into nextFpsLodState and gates Rapier on effectivePhysics', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    expect(src).toContain('nextFpsLodState')
    expect(src).toContain('effectivePhysics')
    expect(src).toContain('applyFpsLodCfg')
  })
})

describe('tablet z-index / pointer unlock', () => {
  it('lets twin chrome receive clicks while the field tablet is open', async () => {
    const css = await readSource('DatacenterSimulator.css')
    expect(css).toMatch(/\.dc-tablet-backdrop\s*\{[^}]*pointer-events:\s*none/s)
    expect(css).toContain('.dc-tablet-backdrop > .dc-tablet')
    expect(css).toMatch(/pointer-events:\s*auto/)
  })

  it('suppresses pause-menu open for cable drag and tablet unlock', async () => {
    suppressPointerUnlockPause(50)
    expect(isPointerUnlockPauseSuppressed()).toBe(true)
    const src = await readSource('DatacenterTwin3D.jsx')
    expect(src).toContain('isPointerUnlockPauseSuppressed()')
    expect(src).toContain('suppressPointerUnlockPause')
    const cable = await readSource('DcCableSystem.jsx')
    expect(cable).toContain('document.exitPointerLock')
    expect(cable).toContain('suppressPointerUnlockPause')
  })
})

describe('cable bend-radius warn', () => {
  it('estimates tighter bends for short chords with deep sag', () => {
    const loose = estimateBendRadiusMm(0.15, 0.5)
    const gentle = estimateBendRadiusMm(2.0, 0.12)
    expect(loose).toBeLessThan(gentle)
    expect(loose).toBeLessThan(minBendRadiusMm('Cat6A'))
    expect(gentle).toBeGreaterThan(minBendRadiusMm('Fiber-LC'))
  })

  it('surfaces bend feedback on InteractiveCable drag', async () => {
    const src = await readSource('DcCableSystem.jsx')
    expect(src).toContain('estimateBendRadiusMm')
    expect(src).toContain('Bend <')
    expect(src).toContain('dc-3d-chip-warn')
  })
})

describe('D12 — minimap', () => {
  it('draws walls, racks and a heading indicator', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const mm = src.slice(src.indexOf('function Minimap'), src.indexOf('function ArModeChip'))
    // yaw was already populated in posRef and simply never drawn.
    expect(mm).toContain('posRef.current.yaw')
    expect(mm).toContain('rotate(')
    expect(mm).toContain('dc-3d-minimap-walls')
    expect(mm).toContain('dc-3d-minimap-rack')
  })

  it('has styling for the new minimap elements', async () => {
    const css = await readSource('DatacenterSimulator.css')
    expect(css).toContain('.dc-3d-minimap-walls')
    expect(css).toContain('.dc-3d-minimap-rack')
  })
})

describe('chunk loading UX', () => {
  it('shows sized, timed progress rather than a bare spinner', async () => {
    const src = await readSource('DatacenterSimulator.jsx')
    expect(src).toContain('function Twin3DLoading')
    expect(src).toContain('dc-3d-loading-bar')
    // Must never claim 100% — import() reports no byte progress.
    expect(src).toContain('Math.min(92')
    expect(src).toContain('onSkipTo2D')
  })
})

/**
 * Audit L536/L542/L544/L578 — world collision, wall-slide, badge-gated mantrap,
 * and vertical movement. Pure helpers so the whole contract is exercisable in
 * `environment: 'node'` with no WebGL.
 */
describe('L536 — hall collider list', () => {
  it('derives rack colliders from the same rackPosition() the meshes use', () => {
    const cols = buildHallColliders({ rackCount: 8 })
    const racks = cols.filter((c) => c.id.startsWith('rack-'))
    expect(racks).toHaveLength(8)
    // rack 0 sits at x -2.1, z -0.5 with a 0.6 x 1.05 footprint.
    expect(racks[0].minX).toBeCloseTo(-2.4, 6)
    expect(racks[0].maxX).toBeCloseTo(-1.8, 6)
    expect(racks[0].minZ).toBeCloseTo(-1.025, 6)
    expect(racks[0].maxZ).toBeCloseTo(0.025, 6)
  })

  it('scales with the real rack and CRAC counts rather than a hardcoded list', () => {
    expect(buildHallColliders({ rackCount: 0, cracCount: 0 })
      .some((c) => c.id.startsWith('rack-'))).toBe(false)
    expect(buildHallColliders({ rackCount: 3, cracCount: 2 })
      .filter((c) => c.id.startsWith('crac-'))).toHaveLength(2)
  })

  it('includes the corridor walls, MDF cage and reception desk', () => {
    const ids = buildHallColliders({}).map((c) => c.id)
    expect(ids).toEqual(expect.arrayContaining([
      'reception-wall', 'corridor-wall-x', 'corridor-wall-z', 'reception-desk', 'mdf-cage',
    ]))
  })
})

describe('L542 — capsule-vs-AABB resolution', () => {
  const cols = buildHallColliders({ rackCount: 8, cracCount: 2, doorOpen: true })

  it('blocks a walk straight into a rack', () => {
    // Start in the aisle just south of rack 0 (collider maxZ 0.025, so the
    // capsule stops at 0.305) and push north into it.
    const start = { x: -2.1, z: 0.4 }
    const out = resolveWalk(start, { x: 0, z: -0.2 }, cols)
    expect(out.z).toBeGreaterThan(0.025 + PLAYER_RADIUS - 1e-6)
    expect(out.z).toBe(start.z) // fully rejected, not partially tunnelled
  })

  it('slides along a wall instead of sticking (independent X/Z passes)', () => {
    // Diagonal into rack 0's face: the Z component is refused, the X component
    // must survive — that tangential motion IS the slide.
    const start = { x: -2.1, z: 0.4 }
    const out = resolveWalk(start, { x: 0.35, z: -0.2 }, cols)
    expect(out.z).toBe(start.z)
    expect(out.x).toBeCloseTo(-1.75, 6)
  })

  it('never lets a diagonal squeeze through a corner between two boxes', () => {
    // The Z pass is re-tested against the resolved X, so a corner cannot be
    // crossed by combining two individually-legal axis moves.
    const box = [{ id: 'b', minX: 0, maxX: 1, minZ: 0, maxZ: 1 }]
    const out = resolveWalk({ x: -0.5, z: -0.5 }, { x: 1.0, z: 1.0 }, box, 0.2)
    const inside = out.x > box[0].minX - 0.2 && out.x < box[0].maxX + 0.2
      && out.z > box[0].minZ - 0.2 && out.z < box[0].maxZ + 0.2
    expect(inside).toBe(false)
  })

  it('keeps the outer bounds authoritative even with no colliders', () => {
    const out = resolveWalk({ x: 7.4, z: 6.4 }, { x: 99, z: 99 }, [])
    expect(out.x).toBe(HALL_BOUNDS.maxX)
    expect(out.z).toBe(HALL_BOUNDS.maxZ)
  })

  it('does not trap a player who somehow starts inside a collider', () => {
    // Overlapping spawn must still be able to move OUT along a free axis rather
    // than being frozen forever.
    const box = [{ id: 'b', minX: -1, maxX: 1, minZ: -1, maxZ: 1 }]
    const out = resolveWalk({ x: 0, z: 0 }, { x: 3, z: 0 }, box, 0.2)
    expect(out.x).toBeGreaterThan(0)
  })
})

describe('L544 — badge-gated mantrap door', () => {
  it('is solid before badge-in and gone after', () => {
    const closed = buildHallColliders({ doorOpen: false }).map((c) => c.id)
    const open = buildHallColliders({ doorOpen: true }).map((c) => c.id)
    expect(closed).toContain('mantrap-door')
    expect(open).not.toContain('mantrap-door')
  })

  /**
   * The regression this guards is a soft-lock: the box clamp used to be the ONLY
   * thing keeping the player in bounds, so a bad door collider can seal them in a
   * room with no way out. Flood-fill the walkable plane from the spawn point and
   * assert both the hall and the reception end stay reachable in BOTH door states.
   */
  const floodFrom = (cols, sx, sz) => {
    const step = 0.1
    const hit = (x, z) => cols.some((c) => (
      x > c.minX - PLAYER_RADIUS && x < c.maxX + PLAYER_RADIUS
      && z > c.minZ - PLAYER_RADIUS && z < c.maxZ + PLAYER_RADIUS
    ))
    const key = (x, z) => `${Math.round(x / step)},${Math.round(z / step)}`
    const seen = new Set([key(sx, sz)])
    const stack = [[sx, sz]]
    const pts = [[sx, sz]]
    while (stack.length) {
      const [x, z] = stack.pop()
      for (const [dx, dz] of [[step, 0], [-step, 0], [0, step], [0, -step]]) {
        const nx = x + dx
        const nz = z + dz
        if (nx < HALL_BOUNDS.minX || nx > HALL_BOUNDS.maxX) continue
        if (nz < HALL_BOUNDS.minZ || nz > HALL_BOUNDS.maxZ) continue
        const k = key(nx, nz)
        if (seen.has(k) || hit(nx, nz)) continue
        seen.add(k)
        stack.push([nx, nz])
        pts.push([nx, nz])
      }
    }
    return pts
  }

  it.each([false, true])('leaves no soft-lock with doorOpen=%s', (doorOpen) => {
    const cols = buildHallColliders({ rackCount: 8, cracCount: 2, doorOpen })
    // Spawn matches WalkController's initial pos (5.2, _, 4.5).
    const reachable = floodFrom(cols, 5.2, 4.5)
    expect(reachable.length).toBeGreaterThan(5000)
    // The cold aisle deep in the hall.
    expect(reachable.some(([x, z]) => Math.abs(x) < 0.2 && z < -2)).toBe(true)
    // The reception / corridor end.
    expect(reachable.some(([x, z]) => x < -4.5 && z > 4.6)).toBe(true)
  })

  it('does not spawn the player inside a collider', () => {
    const cols = buildHallColliders({ rackCount: 8, cracCount: 2, doorOpen: false })
    const overlapping = cols.filter((c) => (
      5.2 > c.minX - PLAYER_RADIUS && 5.2 < c.maxX + PLAYER_RADIUS
      && 4.5 > c.minZ - PLAYER_RADIUS && 4.5 < c.maxZ + PLAYER_RADIUS
    ))
    expect(overlapping).toEqual([])
  })
})

describe('L578 — crouch and jump', () => {
  const dt = 1 / 60

  it('eases the eye down to crouch height while Ctrl is held', () => {
    let s = { y: EYE_Y, vy: 0, grounded: true }
    for (let i = 0; i < 120; i += 1) s = stepVertical(s, { ControlLeft: true }, dt)
    expect(s.crouching).toBe(true)
    expect(s.y).toBeCloseTo(CROUCH_EYE_Y, 2)
    expect(s.y).toBeLessThan(EYE_Y)
  })

  it('stands back up when the key is released', () => {
    let s = { y: CROUCH_EYE_Y, vy: 0, grounded: true }
    for (let i = 0; i < 120; i += 1) s = stepVertical(s, {}, dt)
    expect(s.y).toBeCloseTo(EYE_Y, 2)
  })

  it('jumps and lands back exactly at eye height', () => {
    let s = stepVertical({ y: EYE_Y, vy: 0, grounded: true }, { Space: true }, dt)
    expect(s.grounded).toBe(false)
    expect(s.vy).toBeGreaterThan(0)
    let peak = s.y
    for (let i = 0; i < 600 && !s.grounded; i += 1) {
      s = stepVertical(s, {}, dt)
      peak = Math.max(peak, s.y)
    }
    expect(peak).toBeGreaterThan(EYE_Y + 0.2)
    expect(s.grounded).toBe(true)
    expect(s.y).toBe(EYE_Y)
    expect(s.vy).toBe(0)
  })

  it('cannot double-jump in mid-air', () => {
    let s = stepVertical({ y: EYE_Y, vy: 0, grounded: true }, { Space: true }, dt)
    const vyAfterFirst = s.vy
    s = stepVertical(s, { Space: true }, dt)
    expect(s.vy).toBeLessThan(vyAfterFirst)
  })

  it('never leaves the room through the ceiling', () => {
    // Even with an absurd upward velocity the head is clamped under the soffit.
    const s = stepVertical({ y: EYE_Y, vy: 50, grounded: false }, {}, 1)
    expect(s.y).toBeLessThanOrEqual(CEILING_Y)
  })

  it('does not jump out of a crouch', () => {
    const s = stepVertical({ y: CROUCH_EYE_Y, vy: 0, grounded: true }, { Space: true, KeyC: true }, dt)
    expect(s.grounded).toBe(true)
  })
})

describe('L536/L542/L578 — wiring into the walk loop', () => {
  it('the movement loop resolves against colliders instead of a bare box clamp', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const walk = src.slice(src.indexOf('function WalkController'), src.indexOf('function HallDust'))
    expect(walk).toContain('resolveWalk(')
    expect(walk).toContain('stepVertical(')
    // The old unconditional clamp pair must be gone from the walk loop.
    expect(walk).not.toContain('Math.max(-8.5, Math.min(7.5')
    // Y is no longer a hard-pinned constant.
    expect(walk).not.toContain('pos.current.y = EYE_Y')
  })

  it('the collider list is memoized from the rendered rack and CRAC counts', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    expect(src).toContain('buildHallColliders({')
    expect(src).toContain('rackCount: (racks || []).length')
    expect(src).toContain('colliders={walkColliders}')
  })

  it('crouch and jump keys are swallowed so they do not scroll the page', () => {
    expect(WALK_KEYS.has('Space')).toBe(true)
    expect(WALK_KEYS.has('ControlLeft')).toBe(true)
    expect(WALK_KEYS.has('KeyC')).toBe(true)
  })
})

/** Audit L2234 — per-room player position persistence with a safe-spawn fallback. */
describe('L2234 — player position persistence', () => {
  const mkStorage = () => ({
    store: {},
    getItem(k) { return this.store[k] ?? null },
    setItem(k, v) { this.store[k] = String(v) },
  })

  it('round-trips a position through storage', () => {
    const ls = mkStorage()
    writePlayerPos(ls, 'sess-1', 'Data Hall A', { x: 1.5, z: -3.2, yaw: 0.4 })
    expect(readPlayerPos(ls, 'sess-1', 'Data Hall A')).toEqual({ x: 1.5, z: -3.2, yaw: 0.4 })
  })

  it('namespaces per session AND per room so coordinates never leak across', () => {
    expect(playerPosKey('a', 'Data Hall A')).not.toBe(playerPosKey('a', 'MDF'))
    expect(playerPosKey('a', 'MDF')).not.toBe(playerPosKey('b', 'MDF'))
    const ls = mkStorage()
    writePlayerPos(ls, 'sess-1', 'Data Hall A', { x: 1, z: 1, yaw: 0 })
    expect(readPlayerPos(ls, 'sess-1', 'MDF')).toBeNull()
    expect(readPlayerPos(ls, 'sess-2', 'Data Hall A')).toBeNull()
  })

  it('survives private mode / corrupt JSON without throwing', () => {
    expect(readPlayerPos(null, 's', 'r')).toBeNull()
    const bad = { getItem: () => '{not json', setItem() {} }
    expect(readPlayerPos(bad, 's', 'r')).toBeNull()
    expect(() => writePlayerPos({ setItem() { throw new Error('quota') } }, 's', 'r', {})).not.toThrow()
  })

  it('falls back to the safe spawn when nothing is saved', () => {
    expect(sanitizeSpawn(null, [])).toEqual(SAFE_SPAWN)
    expect(sanitizeSpawn({ x: 'nope', z: NaN }, [])).toEqual(SAFE_SPAWN)
  })

  it('rejects a saved position that is now inside a rack', () => {
    // The layout-changed case: rack 0 sits where the player used to stand.
    const cols = buildHallColliders({ rackCount: 8 })
    expect(sanitizeSpawn({ x: -2.1, z: -0.5, yaw: 0 }, cols)).toEqual(SAFE_SPAWN)
  })

  it('rejects a saved position outside the room bounds', () => {
    expect(sanitizeSpawn({ x: 99, z: 0 }, [])).toEqual(SAFE_SPAWN)
    expect(sanitizeSpawn({ x: 0, z: -99 }, [])).toEqual(SAFE_SPAWN)
  })

  it('keeps a valid saved position, yaw included', () => {
    const cols = buildHallColliders({ rackCount: 8 })
    expect(sanitizeSpawn({ x: 5.2, z: 4.5, yaw: 1.2 }, cols)).toEqual({ x: 5.2, z: 4.5, yaw: 1.2 })
  })

  it('the walk controller restores on enter and commits on teardown', async () => {
    const src = await readSource('DatacenterTwin3D.jsx')
    const walk = src.slice(src.indexOf('function WalkController'), src.indexOf('function HallDust'))
    expect(walk).toContain('spawnRef.current')
    expect(walk).toContain('onPosCommitRef.current?.(')
    // The restore must be validated by the caller, not trusted raw from storage.
    expect(src).toContain('sanitizeSpawn(')
    expect(src).toContain('readPlayerPos(')
  })
})
