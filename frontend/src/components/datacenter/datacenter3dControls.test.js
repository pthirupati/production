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
import { decay, computeTipWorld, updateCurvePoints } from './DcCableSystem'
import {
  MAX_FRAME_DT,
  clampDt,
  DEFAULT_LOOK,
  PITCH_LIMIT,
  applyLook,
  readLookSettings,
  writeLookSettings,
  isTypingTarget,
  isSprinting,
  WALK_KEYS,
  chassisMetrics,
  freeUSlots,
  findInteractable,
  MAX_INTERACT_DISTANCE,
  EYE_Y,
  CONTROL_BINDINGS,
} from './DatacenterTwin3D'

const readSource = (name) => fs.readFile(new URL(`./${name}`, import.meta.url), 'utf8')

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
    const assign = src.indexOf('pos.current.y = EYE_Y')
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
    const esc = src.slice(src.indexOf("if (e.code === 'Escape')"), src.indexOf("if (e.code === 'Escape')") + 400)
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
