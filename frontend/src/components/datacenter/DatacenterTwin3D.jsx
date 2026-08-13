/**
 * Phase 7+ — Animated Lab Environment 3D digital twin (R3F + Rapier).
 * Camera intro, rack doors, LED/power pulse, fans, cable packets, airflow.
 */
import {
  Suspense, cloneElement, isValidElement, useCallback, useEffect, useMemo, useRef, useState,
} from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import {
  OrbitControls, Html, Environment, Lightformer, ContactShadows, RoundedBox, Float, Bvh,
} from '@react-three/drei'
import { Physics, RigidBody } from '@react-three/rapier'
import { EffectComposer, Bloom, SSAO, Vignette, Noise } from '@react-three/postprocessing'
import * as THREE from 'three'
import { StatusLed, InteractiveCable, CablePhysicsBits, isPointerUnlockPauseSuppressed, suppressPointerUnlockPause } from './DcCableSystem'
import { dcSfx } from './DcAmbientAudio'
import PhysicsSafe from './PhysicsSafe'
import { captureCanvasPng } from './DcShare'
import { DistanceCullingHtml, HTML_LABEL_MAX_DIST } from './DcLod'
import { makeBrushedMetalTexture, makeFloorTileTexture } from './DcTextures'

export { captureCanvasPng, renderFloorPlanPng } from './DcShare'
export { DistanceCullingHtml, HTML_LABEL_MAX_DIST } from './DcLod'

const RACK_W = 0.6
const RACK_D = 1.05
const RACK_H = 2.0
const U_H = RACK_H / 42

/** Eye height in metres. Kept as a constant so the head-bob write order in
 *  WalkController is obviously "set Y first, then read it" (audit D3). */
export const EYE_Y = 1.55

/** Max simulated step. An alt-tab, GC pause or a breakpoint yields a multi-second
 *  `dt`; at sprint speed that is a 30m+ jump which tunnels the player through every
 *  wall and rack in one frame. 0.1s ≈ 10fps — slow motion below that beats teleport. */
export const MAX_FRAME_DT = 0.1
export const clampDt = (dt) => (Number.isFinite(dt) ? Math.max(0, Math.min(MAX_FRAME_DT, dt)) : 0)

/** Auto LOD when sustained FPS falls below this (TODO 449 — cut particles / Rapier). */
export const FPS_LOD_THRESHOLD = 40
export const FPS_LOD_ENTER_SAMPLES = 2
export const FPS_LOD_EXIT_SAMPLES = 5

/**
 * Hysteresis helper for FPS-driven LOD. Pure so tests can drive consecutive samples
 * without mounting Canvas. `state` shape: `{ low, high, active }`.
 */
export function nextFpsLodState(state, fps, threshold = FPS_LOD_THRESHOLD) {
  const prev = state || { low: 0, high: 0, active: false }
  const n = Number(fps)
  if (!Number.isFinite(n)) return { ...prev }
  if (n < threshold) {
    const low = prev.low + 1
    return {
      low,
      high: 0,
      active: prev.active || low >= FPS_LOD_ENTER_SAMPLES,
    }
  }
  const high = prev.high + 1
  return {
    low: 0,
    high,
    active: prev.active && high < FPS_LOD_EXIT_SAMPLES ? true : false,
  }
}

/** Cut draw cost while fps LOD is active — particles + post + Rapier. */
export function applyFpsLodCfg(qualityCfg, active) {
  if (!active || !qualityCfg) return qualityCfg
  return {
    ...qualityCfg,
    dust: Math.min(qualityCfg.dust ?? 40, 28),
    anim: Math.min(qualityCfg.anim ?? 1, 0.45),
    bloom: false,
    ssao: false,
    noise: false,
    dpr: [1, 1],
  }
}

/** Mouse-look tuning. Radians per pixel of `movementX/Y`; the historical hardcoded
 *  value was 0.0026 on both axes, which stays the default so existing muscle memory
 *  survives. Y is separately scalable + invertible — an accessibility requirement,
 *  not a nicety (vestibular sensitivity, and inverted-Y is a hard preference). */
export const DEFAULT_LOOK = { sensitivity: 0.0026, yScale: 1, invertY: false }
const LOOK_STORAGE_KEY = 'fixitlab.dc.look'

export function readLookSettings(storage) {
  const fallback = { ...DEFAULT_LOOK }
  try {
    const raw = storage?.getItem?.(LOOK_STORAGE_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    const sens = Number(parsed?.sensitivity)
    const yScale = Number(parsed?.yScale)
    return {
      // Clamp to a sane band: 0 sensitivity is an unrecoverable soft-lock and
      // huge values make the camera unusable with no in-world way back.
      sensitivity: Number.isFinite(sens) ? Math.max(0.0004, Math.min(0.012, sens)) : DEFAULT_LOOK.sensitivity,
      yScale: Number.isFinite(yScale) ? Math.max(0.25, Math.min(2.5, yScale)) : DEFAULT_LOOK.yScale,
      invertY: !!parsed?.invertY,
    }
  } catch {
    return fallback
  }
}

export function writeLookSettings(storage, look) {
  try { storage?.setItem?.(LOOK_STORAGE_KEY, JSON.stringify(look)) } catch { /* private mode */ }
}

/** Remappable walk actions. Arrow keys stay as always-on aliases so muscle memory
 *  for the controls table still works after a rebind. */
export const DEFAULT_BINDS = {
  forward: 'KeyW',
  back: 'KeyS',
  left: 'KeyA',
  right: 'KeyD',
  jump: 'Space',
  crouch: 'KeyC',
  sprint: 'ShiftLeft',
  interact: 'KeyE',
}
const BINDS_STORAGE_KEY = 'fixitlab.dc.binds'
const BIND_ACTIONS = Object.keys(DEFAULT_BINDS)

export function readBinds(storage) {
  const fallback = { ...DEFAULT_BINDS }
  try {
    const raw = storage?.getItem?.(BINDS_STORAGE_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    const next = { ...DEFAULT_BINDS }
    for (const action of BIND_ACTIONS) {
      const code = parsed?.[action]
      if (typeof code === 'string' && /^[A-Za-z0-9]+$/.test(code) && code.length <= 24) {
        next[action] = code
      }
    }
    return next
  } catch {
    return fallback
  }
}

export function writeBinds(storage, binds) {
  try { storage?.setItem?.(BINDS_STORAGE_KEY, JSON.stringify({ ...DEFAULT_BINDS, ...binds })) } catch { /* private mode */ }
}

/** Codes the walk controller must swallow (preventDefault) while unlocked keys scroll. */
export function walkKeySet(binds = DEFAULT_BINDS) {
  return new Set([
    binds.forward, binds.back, binds.left, binds.right,
    binds.jump, binds.crouch, binds.sprint, binds.interact,
    'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
    'ShiftLeft', 'ShiftRight', 'ControlLeft', 'ControlRight', 'Space',
  ])
}

/** Keys the walk controller owns. Anything held here must be swallowed
 *  (preventDefault) while in-game or Space/arrows scroll the page underneath. */
export const WALK_KEYS = walkKeySet(DEFAULT_BINDS)

export function movementIntent(keys, binds = DEFAULT_BINDS) {
  return {
    forward: !!(keys?.[binds.forward] || keys?.ArrowUp),
    back: !!(keys?.[binds.back] || keys?.ArrowDown),
    left: !!(keys?.[binds.left] || keys?.ArrowLeft),
    right: !!(keys?.[binds.right] || keys?.ArrowRight),
  }
}

/** Merge keyboard + gamepad binary intents (OR). */
export function mergeIntent(a = {}, b = {}) {
  return {
    forward: !!(a.forward || b.forward),
    back: !!(a.back || b.back),
    left: !!(a.left || b.left),
    right: !!(a.right || b.right),
  }
}

/** Shared hold state for on-screen touch D-pad (WalkController merges each frame). */
export const touchHoldRef = {
  current: {
    forward: false, back: false, left: false, right: false,
    jump: false, sprint: false,
    lookLeft: false, lookRight: false, lookUp: false, lookDown: false,
  },
}

export function setTouchHold(partial) {
  touchHoldRef.current = { ...touchHoldRef.current, ...partial }
}

export function clearTouchHold() {
  touchHoldRef.current = {
    forward: false, back: false, left: false, right: false,
    jump: false, sprint: false,
    lookLeft: false, lookRight: false, lookUp: false, lookDown: false,
  }
}

/** Look deltas from on-screen look-stick holds (pixels-equivalent per frame). */
export function touchLookDelta(hold = touchHoldRef.current, scale = 2.4) {
  const h = hold || {}
  return {
    dx: ((h.lookRight ? 1 : 0) - (h.lookLeft ? 1 : 0)) * scale,
    dy: ((h.lookDown ? 1 : 0) - (h.lookUp ? 1 : 0)) * scale,
  }
}

/** Shared gyro look sample written by deviceorientation listener, read in useFrame. */
export const gyroLookRef = { current: { dx: 0, dy: 0 } }

/**
 * Convert DeviceOrientationEvent into a look delta using relative beta/gamma change.
 * `prevRef` stores the last sample so absolute orientation doesn't slam yaw on enable.
 */
export function deviceOrientationLookDelta(event, prevRef, scale = 0.35) {
  if (!event || prevRef == null) return { dx: 0, dy: 0 }
  const beta = Number(event.beta)
  const gamma = Number(event.gamma)
  if (!Number.isFinite(beta) || !Number.isFinite(gamma)) return { dx: 0, dy: 0 }
  if (!prevRef.current) {
    prevRef.current = { beta, gamma }
    return { dx: 0, dy: 0 }
  }
  const dx = (gamma - prevRef.current.gamma) * scale
  const dy = (beta - prevRef.current.beta) * scale
  prevRef.current = { beta, gamma }
  // Clamp so a single noisy sample cannot spin the camera.
  return {
    dx: Math.max(-8, Math.min(8, dx)),
    dy: Math.max(-8, Math.min(8, dy)),
  }
}

/** iOS requires a user-gesture permission grant for deviceorientation. */
export async function requestGyroPermission(
  DOE = typeof window !== 'undefined' ? window.DeviceOrientationEvent : undefined,
) {
  try {
    if (DOE && typeof DOE.requestPermission === 'function') {
      const state = await DOE.requestPermission()
      return state === 'granted'
    }
    return typeof window !== 'undefined' && 'DeviceOrientationEvent' in window
  } catch {
    return false
  }
}

export function prefersCoarsePointer(mq = typeof window !== 'undefined' ? window.matchMedia : null) {
  try {
    return !!mq?.('(pointer: coarse)')?.matches
  } catch {
    return false
  }
}

/**
 * Standard gamepad → walk intent + look deltas.
 * Left stick: move. Right stick: look. A/Cross (0): jump. LT/L2 (6) or B (1): crouch.
 * RT/R2 (7) or LB (4): sprint.
 */
export function gamepadSample(pad, deadzone = 0.22) {
  const empty = {
    intent: { forward: false, back: false, left: false, right: false },
    lookDx: 0,
    lookDy: 0,
    jump: false,
    crouch: false,
    sprint: false,
  }
  if (!pad || !pad.connected) return empty
  const ax = Array.isArray(pad.axes) ? pad.axes : []
  const btns = Array.isArray(pad.buttons) ? pad.buttons : []
  const pressed = (i) => !!(btns[i] && (btns[i].pressed || (btns[i].value || 0) > 0.5))
  const stick = (v) => (Math.abs(v) < deadzone ? 0 : v)
  const lx = stick(Number(ax[0]) || 0)
  const ly = stick(Number(ax[1]) || 0)
  const rx = stick(Number(ax[2]) || 0)
  const ry = stick(Number(ax[3]) || 0)
  return {
    intent: {
      forward: ly < -deadzone,
      back: ly > deadzone,
      left: lx < -deadzone,
      right: lx > deadzone,
    },
    lookDx: rx * 14,
    lookDy: ry * 14,
    jump: pressed(0),
    crouch: pressed(1) || pressed(6),
    sprint: pressed(7) || pressed(4),
  }
}

/** Sprint reads the bound sprint key plus either Shift so arrow-key players still sprint. */
export const isSprinting = (keys, binds = DEFAULT_BINDS) => !!(
  keys?.[binds.sprint] || keys?.ShiftLeft || keys?.ShiftRight
)

export const PITCH_LIMIT = 1.25

/** Pure mouse-look integration so the sensitivity/invert-Y contract is testable
 *  without a WebGL context. Returns clamped {yaw, pitch}. */
export function applyLook({ yaw, pitch }, movementX, movementY, look = DEFAULT_LOOK) {
  const s = look.sensitivity ?? DEFAULT_LOOK.sensitivity
  const yDir = look.invertY ? -1 : 1
  const nextYaw = yaw - movementX * s
  const nextPitch = pitch - movementY * s * (look.yScale ?? 1) * yDir
  return {
    yaw: nextYaw,
    pitch: Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, nextPitch)),
  }
}

/** True when a keystroke belongs to a text-entry surface rather than the game.
 *  Without this, WASD types into every input in the surrounding app because the
 *  listener is on `window`. */
export function isTypingTarget(target) {
  if (!target || typeof target !== 'object') return false
  const tag = (target.tagName || '').toUpperCase()
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (target.isContentEditable) return true
  return false
}

/** Grid position of rack `index` on the hall floor. Declared here rather than beside
 *  RackMesh because buildHallColliders() must use the *same* function the racks are
 *  rendered from — a second copy of this formula is how colliders drift off the
 *  visuals. */
function rackPosition(index) {
  return {
    x: (index % 4) * 1.4 - 2.1,
    z: Math.floor(index / 4) * -2.2 - 0.5,
  }
}

/** Player capsule radius in metres — shoulder half-width, not a point. Aisles are
 *  1.4m rack-pitch minus 0.6m rack width ≈ 0.8m clear, so 0.28 leaves ~0.24m either
 *  side: tight enough to feel like a real aisle, wide enough not to snag. */
export const PLAYER_RADIUS = 0.28

/** Soft bounds of the walkable volume. Was the *only* movement constraint before
 *  colliders existed; it stays as the outer backstop so a resolution bug can never
 *  eject the player into the void. */
export const HALL_BOUNDS = { minX: -8.5, maxX: 7.5, minZ: -5.5, maxZ: 6.5 }

/** Head/floor clamp. `maxY` is the soffit underside (2.35 - 0.04) minus a little,
 *  so a jump cannot punch through the ceiling now that Y is no longer pinned. */
export const CROUCH_EYE_Y = 0.95
export const CEILING_Y = 2.25
export const JUMP_SPEED = 3.5
export const GRAVITY = 9.81

/**
 * Axis-aligned collider boxes for the static hall, derived from the *same*
 * constants the meshes are rendered from. Every entry is {minX,maxX,minZ,maxZ}
 * in world space, already inflated by the player radius is NOT applied here —
 * resolveWalk() inflates at test time so one collider list serves any radius.
 *
 * `doorOpen` removes the mantrap leaf: badge-in physically opens the door. This is
 * the only collider that is ever conditional, and it is deliberately the one thing
 * standing between the corridor and the hall (audit L544).
 */
export function buildHallColliders({ rackCount = 0, cracCount = 0, doorOpen = false } = {}) {
  const boxes = []
  const box = (id, cx, cz, w, d) => boxes.push({
    id,
    minX: cx - w / 2,
    maxX: cx + w / 2,
    minZ: cz - d / 2,
    maxZ: cz + d / 2,
  })

  // Racks — RackMesh at rackPosition(i), RACK_W x RACK_D footprint.
  for (let i = 0; i < rackCount; i += 1) {
    const { x, z } = rackPosition(i)
    box(`rack-${i}`, x, z, RACK_W, RACK_D)
  }

  // CRAC units — CracUnits group at [-6.2, 0, -2], each child at z = -i * 1.4,
  // RoundedBox args [0.9, 1.4, 0.7] → 0.9 wide x 0.7 deep.
  for (let i = 0; i < cracCount; i += 1) {
    box(`crac-${i}`, -6.2, -2 - i * 1.4, 0.9, 0.7)
  }

  // CorridorShell static geometry, mirroring the meshes one-for-one.
  box('reception-wall', -7.2, 5.2, 3.2, 0.12)
  box('corridor-wall-x', -3.8, 2.4, 0.12, 5.5)
  box('corridor-wall-z', 0.2, 3.6, 7.5, 0.12)
  box('reception-desk', -5.5, 4.0, 1.4, 0.55)
  box('mdf-cage', 6.4, -1.2, 1.8, 2.2)

  // Mantrap leaf. The door group sits at [-3.9, ?, 4.35] with the leaf offset
  // +0.55 in x and 1.1 wide, so closed it spans x -3.8..-2.8 at z 4.35.
  if (!doorOpen) box('mantrap-door', -2.8 + -0.55, 4.35, 1.1, 0.14)

  return boxes
}

/**
 * Capsule-vs-AABB resolution with independent X then Z passes.
 *
 * Resolving both axes together makes the player stick on every wall they brush;
 * resolving them independently is what produces the "slide along the wall" feel.
 * Each axis is applied, then tested and pushed back out on that axis alone, so a
 * diagonal into a wall keeps the tangential component.
 *
 * Pure and dependency-free so the whole contract is testable without WebGL.
 */
export function resolveWalk(from, delta, colliders = [], radius = PLAYER_RADIUS, bounds = HALL_BOUNDS) {
  const hits = (x, z) => colliders.some((c) => (
    x > c.minX - radius && x < c.maxX + radius
    && z > c.minZ - radius && z < c.maxZ + radius
  ))

  let { x, z } = from

  // X pass — reject only the X component, leaving Z free to slide.
  const tryX = x + (delta.x || 0)
  if (!hits(tryX, z)) x = tryX

  // Z pass — re-tested against the *already resolved* X, otherwise a corner lets
  // the player squeeze diagonally through the gap between two boxes.
  const tryZ = z + (delta.z || 0)
  if (!hits(x, tryZ)) z = tryZ

  // Outer backstop. Kept after resolution so it is authoritative: a collider
  // overlap bug can slow the player down but can never push them out of the world.
  x = Math.max(bounds.minX, Math.min(bounds.maxX, x))
  z = Math.max(bounds.minZ, Math.min(bounds.maxZ, z))
  return { x, z }
}

/**
 * Vertical player state: crouch (hold Ctrl/C) and jump (Space).
 *
 * Returns the new {y, vy, crouching}. Eye height eases toward the crouch/stand
 * target so the transition reads as a body movement rather than a teleport, while
 * an airborne player is fully ballistic. Ceiling is clamped so jump cannot leave
 * the room — the old X/Z-only bounds gave no vertical containment at all.
 */
export function stepVertical({ y, vy = 0, grounded = true }, keys = {}, dt = 0, binds = DEFAULT_BINDS) {
  const crouchCode = binds.crouch || DEFAULT_BINDS.crouch
  const jumpCode = binds.jump || DEFAULT_BINDS.jump
  const crouching = !!(keys.ControlLeft || keys.ControlRight || keys[crouchCode])
  const standY = crouching ? CROUCH_EYE_Y : EYE_Y

  let nextVy = vy
  let nextY = y
  let nextGrounded = grounded

  if (grounded && keys[jumpCode] && !crouching) {
    // No jump out of a crouch: it reads as a bug when the head is already low and
    // it is the usual way players clip into rack tops.
    nextVy = JUMP_SPEED
    nextGrounded = false
  }

  if (!nextGrounded) {
    nextVy -= GRAVITY * dt
    nextY += nextVy * dt
    if (nextY <= standY) { nextY = standY; nextVy = 0; nextGrounded = true }
  } else {
    // Grounded: ease the eye toward the stand/crouch height.
    nextY += (standY - nextY) * Math.min(1, dt * 11)
    nextVy = 0
  }

  if (nextY > CEILING_Y) { nextY = CEILING_Y; nextVy = Math.min(0, nextVy) }
  return { y: nextY, vy: nextVy, grounded: nextGrounded, crouching }
}

/** Where the player stands when there is nothing valid to restore. Matches the
 *  cinematic camera's landing point so the intro and a cold start agree. */
export const SAFE_SPAWN = { x: 5.2, z: 4.5, yaw: 0 }
const POS_STORAGE_KEY = 'fixitlab.dc.pos'

/**
 * Validate a restored player position against the CURRENT geometry.
 *
 * A saved position is only as good as the layout it was saved in: racks move when
 * the scenario changes, so a naive restore can drop the player inside a rack or
 * outside the room. Anything out of bounds or overlapping a collider falls back to
 * SAFE_SPAWN rather than being nudged — a nudge can land in another collider.
 */
export function sanitizeSpawn(saved, colliders = [], bounds = HALL_BOUNDS, radius = PLAYER_RADIUS) {
  const x = Number(saved?.x)
  const z = Number(saved?.z)
  const yaw = Number(saved?.yaw)
  if (!Number.isFinite(x) || !Number.isFinite(z)) return { ...SAFE_SPAWN }
  if (x < bounds.minX || x > bounds.maxX || z < bounds.minZ || z > bounds.maxZ) return { ...SAFE_SPAWN }
  const blocked = colliders.some((c) => (
    x > c.minX - radius && x < c.maxX + radius && z > c.minZ - radius && z < c.maxZ + radius
  ))
  if (blocked) return { ...SAFE_SPAWN }
  return { x, z, yaw: Number.isFinite(yaw) ? yaw : 0 }
}

/** Namespaced per room AND per session: one room's coordinates applied to another
 *  spawns the player in a wall, and two concurrent labs must not share a spot. */
export const playerPosKey = (sessionId, roomId) => (
  `${POS_STORAGE_KEY}.${sessionId || 'anon'}.${roomId || 'data-hall-a'}`
)

export function readPlayerPos(storage, sessionId, roomId) {
  try {
    const raw = storage?.getItem?.(playerPosKey(sessionId, roomId))
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function writePlayerPos(storage, sessionId, roomId, pos) {
  try {
    storage?.setItem?.(playerPosKey(sessionId, roomId), JSON.stringify({
      x: pos?.x, z: pos?.z, yaw: pos?.yaw,
    }))
  } catch { /* private mode */ }
}

/** AR HUD overlay cycle — Off / Thermal / Power / Network (key `V`). */
const AR_MODES = ['off', 'thermal', 'power', 'network']
const AR_MODE_LABELS = { off: 'Off', thermal: 'Thermal', power: 'Power', network: 'Network' }

/** Lerp between two `#rrggbb` colors without allocating a THREE.Color per call. */
function lerpHex(a, b, t) {
  const clamped = Math.max(0, Math.min(1, t))
  const ah = parseInt(a.slice(1), 16)
  const bh = parseInt(b.slice(1), 16)
  const ar = (ah >> 16) & 255; const ag = (ah >> 8) & 255; const ab = ah & 255
  const br = (bh >> 16) & 255; const bg = (bh >> 8) & 255; const bb = bh & 255
  const rr = Math.round(ar + (br - ar) * clamped)
  const rg = Math.round(ag + (bg - ag) * clamped)
  const rb = Math.round(ab + (bb - ab) * clamped)
  return `rgb(${rr}, ${rg}, ${rb})`
}

function vendorColor(vendor) {
  const v = (vendor || '').toLowerCase()
  if (v.includes('hpe') || v === 'hp') return '#01a982'
  if (v.includes('lenovo')) return '#e2231a'
  if (v.includes('super')) return '#f5a623'
  if (v.includes('cisco')) return '#049fd9'
  if (v.includes('gigabyte')) return '#00a651'
  return '#2494e8'
}

function FpsMeter({ onFps }) {
  const frames = useRef({ n: 0, t: performance.now() })
  useFrame(() => {
    frames.current.n += 1
    const now = performance.now()
    if (now - frames.current.t >= 1000) {
      onFps?.(frames.current.n)
      frames.current = { n: 0, t: now }
    }
  })
  return null
}

/** Dolly + orbit settle when the 3D twin mounts. */
function CameraIntro({ enabled, cinematic = false }) {
  const { camera } = useThree()
  const controls = useThree((s) => s.controls)
  const t0 = useRef(null)
  const done = useRef(false)
  // Cinematic: security desk → corridor → cold aisle settle (Steam-style enter)
  const from = useMemo(
    () => (cinematic ? new THREE.Vector3(-8.5, 1.6, 6.5) : new THREE.Vector3(12, 9, 14)),
    [cinematic],
  )
  const mid = useMemo(() => new THREE.Vector3(-2.5, 1.55, 2.2), [])
  const to = useMemo(
    () => (cinematic ? new THREE.Vector3(5.2, 1.55, 4.5) : new THREE.Vector3(6, 5, 7)),
    [cinematic],
  )
  const look = useMemo(() => new THREE.Vector3(1, 0.8, -1.5), [])
  const lookMid = useMemo(() => new THREE.Vector3(-1, 1.1, -0.5), [])

  useEffect(() => {
    if (!enabled) return
    t0.current = performance.now()
    done.current = false
    camera.position.copy(from)
    camera.lookAt(cinematic ? lookMid : look)
  }, [enabled, camera, from, look, lookMid, cinematic])

  useFrame(() => {
    if (!enabled || done.current || t0.current == null) return
    const dur = cinematic ? 2600 : 1600
    const u = Math.min(1, (performance.now() - t0.current) / dur)
    const e = 1 - (1 - u) ** 3
    if (cinematic) {
      if (u < 0.45) {
        const t = e / 0.45
        camera.position.lerpVectors(from, mid, Math.min(1, t))
        camera.lookAt(lookMid)
      } else {
        const t = (e - 0.45) / 0.55
        camera.position.lerpVectors(mid, to, Math.min(1, t))
        camera.lookAt(look)
      }
    } else {
      camera.position.lerpVectors(from, to, e)
      camera.lookAt(look)
    }
    if (controls?.target) controls.target.lerp(look, 0.08)
    if (u >= 1) done.current = true
  })
  return null
}

/** Corridor walls: reception → staging → data hall → MDF (low-poly Steam layout). */
function CorridorShell({ dockBusy = false, doorOpen = false }) {
  const wall = '#1e293b'
  const trim = '#334155'
  const door = useRef()
  const forklift = useRef()
  useFrame(({ clock }) => {
    if (door.current) {
      // Closed until badge-in; then swings open (Steam mantrap).
      const target = doorOpen ? -1.15 : -0.05
      const cur = door.current.rotation.y
      door.current.rotation.y = cur + (target - cur) * Math.min(1, 0.08 + Math.sin(clock.elapsedTime) * 0.01)
    }
    if (forklift.current) {
      const bob = dockBusy ? Math.sin(clock.elapsedTime * 2.2) * 0.04 : 0
      const slide = dockBusy ? Math.sin(clock.elapsedTime * 0.6) * 0.35 : 0
      forklift.current.position.x = -6.4 + slide
      forklift.current.position.y = 0.35 + bob
    }
  })
  return (
    <group>
      {/* Reception / badge desk zone */}
      <mesh position={[-7.2, 1.1, 5.2]} castShadow receiveShadow>
        <boxGeometry args={[3.2, 2.2, 0.12]} />
        <meshStandardMaterial color={wall} roughness={0.85} />
      </mesh>
      <mesh position={[-5.5, 0.55, 4.0]} castShadow>
        <boxGeometry args={[1.4, 1.1, 0.55]} />
        <meshStandardMaterial color="#0f172a" metalness={0.35} roughness={0.5} />
      </mesh>
      <Html position={[-5.5, 1.35, 4.0]} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label">Reception · badge</div>
      </Html>

      {/* Mantrap / badge door into the hall */}
      <group ref={door} position={[-3.9, 1.05, 4.35]}>
        <mesh castShadow position={[0.55, 0, 0]}>
          <boxGeometry args={[1.1, 2.05, 0.06]} />
          <meshStandardMaterial color="#1e3a5f" metalness={0.45} roughness={0.4} />
        </mesh>
        <mesh position={[0.95, 0.1, 0.04]}>
          <boxGeometry args={[0.08, 0.12, 0.04]} />
          <meshStandardMaterial color="#fbbf24" emissive="#f59e0b" emissiveIntensity={0.6} />
        </mesh>
      </group>
      <Html position={[-3.6, 2.2, 4.35]} center distanceFactor={11} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label">Mantrap · badge-in</div>
      </Html>

      {/* Corridor side walls */}
      <mesh position={[-3.8, 1.15, 2.4]} receiveShadow>
        <boxGeometry args={[0.12, 2.3, 5.5]} />
        <meshStandardMaterial color={wall} roughness={0.9} />
      </mesh>
      <mesh position={[0.2, 1.15, 3.6]} receiveShadow>
        <boxGeometry args={[7.5, 2.3, 0.12]} />
        <meshStandardMaterial color={trim} roughness={0.88} />
      </mesh>

      {/* Staging / dock stub + forklift / pallet */}
      <mesh position={[-6.0, 0.08, 1.5]} receiveShadow>
        <boxGeometry args={[2.4, 0.06, 2.0]} />
        <meshStandardMaterial color="#3f3f46" metalness={0.2} roughness={0.7} />
      </mesh>
      <group ref={forklift} position={[-6.4, 0.35, 1.2]}>
        <mesh castShadow>
          <boxGeometry args={[0.9, 0.45, 0.55]} />
          <meshStandardMaterial color="#f59e0b" metalness={0.3} roughness={0.55} />
        </mesh>
        <mesh position={[0.55, 0.35, 0]} castShadow>
          <boxGeometry args={[0.08, 0.9, 0.08]} />
          <meshStandardMaterial color="#78716c" metalness={0.6} />
        </mesh>
        <mesh position={[0.55, -0.05, 0.2]} castShadow>
          <boxGeometry args={[0.55, 0.06, 0.08]} />
          <meshStandardMaterial color="#a8a29e" metalness={0.5} />
        </mesh>
        <mesh position={[0.55, -0.05, -0.2]} castShadow>
          <boxGeometry args={[0.55, 0.06, 0.08]} />
          <meshStandardMaterial color="#a8a29e" metalness={0.5} />
        </mesh>
        {/* Pallet + FRU crate */}
        <mesh position={[-0.85, -0.12, 0]} castShadow>
          <boxGeometry args={[0.55, 0.12, 0.45]} />
          <meshStandardMaterial color="#92400e" roughness={0.9} />
        </mesh>
        <mesh position={[-0.85, 0.12, 0]} castShadow>
          <boxGeometry args={[0.4, 0.28, 0.32]} />
          <meshStandardMaterial color="#334155" roughness={0.7} />
        </mesh>
      </group>
      <Html position={[-6.0, 1.4, 1.5]} center distanceFactor={12} style={{ pointerEvents: 'none' }}>
        <div className={`dc-3d-label ${dockBusy ? 'dc-3d-label-hot' : ''}`}>
          Staging / dock{dockBusy ? ' · FRU inbound' : ''}
        </div>
      </Html>

      {/* MDF cage glass */}
      <mesh position={[6.4, 1.2, -1.2]} castShadow>
        <boxGeometry args={[1.8, 2.4, 2.2]} />
        <meshStandardMaterial color="#0ea5e9" transparent opacity={0.12} metalness={0.6} roughness={0.2} />
      </mesh>
      <Html position={[6.4, 2.55, -1.2]} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label dc-3d-label-hot">MDF cage</div>
      </Html>

      {/* Ceiling soffit over corridor */}
      <mesh position={[-2.5, 2.35, 2.5]}>
        <boxGeometry args={[8, 0.08, 3.2]} />
        <meshStandardMaterial color="#0f172a" />
      </mesh>
    </group>
  )
}

/** Thermal aisle haze — CRAC stress + open ticket severity (Steam heat overlay). */
function ThermalHaze({ stress = 0, ticketHeat = 0 }) {
  const ref = useRef()
  const combined = Math.min(1, stress + ticketHeat * 0.55)
  useFrame(({ clock }) => {
    if (!ref.current) return
    const pulse = 0.04 + combined * 0.14 + Math.sin(clock.elapsedTime * 1.4) * 0.015
    ref.current.material.opacity = Math.max(0.02, pulse)
    const hot = ticketHeat > 0.5
    ref.current.material.color.set(hot ? '#ef4444' : '#f97316')
  })
  if (combined < 0.05) return null
  return (
    <group>
      <mesh ref={ref} position={[1.2, 1.1, -2.6]} rotation={[-0.08, 0, 0]}>
        <planeGeometry args={[10, 2.4]} />
        <meshBasicMaterial color="#f97316" transparent opacity={0.08} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      {/* Per-aisle heat ribbons — stronger when critical tickets are open */}
      {[-1.6, -3.8].map((z, i) => (
        <mesh key={z} position={[0.2, 0.9 + i * 0.05, z]} rotation={[-Math.PI / 2.4, 0, 0]}>
          <planeGeometry args={[7.5, 1.1]} />
          <meshBasicMaterial
            color={ticketHeat > 0.5 ? '#dc2626' : '#fb923c'}
            transparent
            opacity={0.03 + combined * 0.1}
            depthWrite={false}
            side={THREE.DoubleSide}
          />
        </mesh>
      ))}
    </group>
  )
}

/** First-person hall walk (WASD + mouse look) with cinematic head-bob. Orbit disabled while active. */
function WalkController({
  enabled, paused = false, posRef, look = DEFAULT_LOOK, binds = DEFAULT_BINDS,
  onPointerLockChange, colliders = [],
  spawn = null, onPosCommit,
}) {
  const { camera, gl } = useThree()
  const keys = useRef({})
  const yaw = useRef(0)
  const pitch = useRef(-0.12)
  const pos = useRef(new THREE.Vector3(5.2, EYE_Y, 4.5))
  const bobPhase = useRef(0)
  const bobAmount = useRef(0)
  const vy = useRef(0)
  const grounded = useRef(true)
  const spawnRef = useRef(spawn)
  spawnRef.current = spawn
  const onPosCommitRef = useRef(onPosCommit)
  onPosCommitRef.current = onPosCommit
  // Same ref trick as `paused`/`look`: colliders is a new array whenever the rack
  // list re-renders, and it must not tear down the listener effect.
  const collidersRef = useRef(colliders)
  collidersRef.current = colliders
  // `paused` and `look` live in refs so the listener effect does NOT depend on them.
  // Previously `paused` was in the dep array, so every pause-menu toggle tore down
  // and rebuilt all four listeners AND re-copied the camera from pos.current,
  // discarding in-flight look state.
  const pausedRef = useRef(paused)
  pausedRef.current = paused
  const lookRef = useRef(look)
  lookRef.current = look
  const bindsRef = useRef(binds)
  bindsRef.current = binds

  useEffect(() => {
    if (!enabled) return undefined
    const canvas = gl.domElement
    const down = (e) => {
      // window-level listener: never steal keys from a text field in the
      // surrounding app, and never let Space/arrows scroll the page under us.
      if (isTypingTarget(e.target)) return
      keys.current[e.code] = true
      if (walkKeySet(bindsRef.current).has(e.code) && !pausedRef.current) e.preventDefault()
    }
    const up = (e) => { keys.current[e.code] = false }
    const move = (e) => {
      if (pausedRef.current) return
      if (document.pointerLockElement !== canvas) return
      const next = applyLook(
        { yaw: yaw.current, pitch: pitch.current },
        e.movementX || 0,
        e.movementY || 0,
        lookRef.current,
      )
      yaw.current = next.yaw
      pitch.current = next.pitch
    }
    // Held keys survive an alt-tab otherwise: the keyup fires on the OTHER window
    // and you come back drifting forward forever.
    const clearKeys = () => { keys.current = {} }
    const onVisibility = () => { if (document.hidden) clearKeys() }
    const click = () => { if (!pausedRef.current) canvas.requestPointerLock?.() }
    // Single source of truth for "do we have the mouse". The browser eats Esc to
    // release the lock, and tab/window switches release it silently; without this
    // the player is left with live WASD and a dead mouse and no indication why.
    const onLockChange = () => {
      const locked = document.pointerLockElement === canvas
      if (!locked) clearKeys()
      onPointerLockChange?.(locked)
    }
    const onLockError = () => {
      // Chrome throws SecurityError for a lock request with no user gesture and
      // reports it here, not as a rejected promise.
      onPointerLockChange?.(false)
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    // Bound to the canvas, not window: pointer-lock movement events target the
    // locked element, and an unlocked stray mousemove elsewhere must not steer.
    canvas.addEventListener('mousemove', move)
    canvas.addEventListener('click', click)
    window.addEventListener('blur', clearKeys)
    document.addEventListener('visibilitychange', onVisibility)
    document.addEventListener('pointerlockchange', onLockChange)
    document.addEventListener('pointerlockerror', onLockError)
    // Restore the saved spot for this room. Already sanitized against the current
    // collider set by the caller, so it can be trusted here.
    if (spawnRef.current) {
      pos.current.set(spawnRef.current.x, EYE_Y, spawnRef.current.z)
      yaw.current = spawnRef.current.yaw || 0
    }
    camera.position.copy(pos.current)
    // No programmatic auto-lock: a requestPointerLock() with no user gesture
    // throws SecurityError in Chrome and used to be swallowed, so the first entry
    // into walk mode silently had no mouse look. The click-to-play overlay
    // (ImmersiveMenu / canvas click) is the only lock entry point now.
    onPointerLockChange?.(document.pointerLockElement === canvas)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      canvas.removeEventListener('mousemove', move)
      canvas.removeEventListener('click', click)
      window.removeEventListener('blur', clearKeys)
      document.removeEventListener('visibilitychange', onVisibility)
      document.removeEventListener('pointerlockchange', onLockChange)
      document.removeEventListener('pointerlockerror', onLockError)
      try { document.exitPointerLock?.() } catch { /* */ }
      // Save on the way out — leaving walk mode, unmounting and navigating away
      // all funnel through this teardown, so there is no separate exit path to miss.
      // The lint rule guards against reading a STALE DOM node here; `pos` is a
      // plain Vector3 and the value at teardown is precisely what must be saved.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      onPosCommitRef.current?.({ x: pos.current.x, z: pos.current.z, yaw: yaw.current })
    }
  }, [enabled, camera, gl, onPointerLockChange])

  useFrame((_, rawDt) => {
    if (!enabled) return
    if (paused) { keys.current = {}; return }
    const dt = clampDt(rawDt)
    // Gamepad (first connected pad) OR'd with keyboard — mobile/touch still residual.
    let padSample = null
    try {
      const pads = typeof navigator !== 'undefined' ? navigator.getGamepads?.() : null
      const pad = pads && (pads[0] || pads[1] || pads[2] || pads[3])
      if (pad) padSample = gamepadSample(pad)
    } catch { /* Secure context / permissions */ }
    if (padSample && (padSample.lookDx || padSample.lookDy) && document.pointerLockElement === gl.domElement) {
      const next = applyLook(
        { yaw: yaw.current, pitch: pitch.current },
        padSample.lookDx,
        padSample.lookDy,
        lookRef.current,
      )
      yaw.current = next.yaw
      pitch.current = next.pitch
    }
    // Touch look-stick works without pointer lock (phones can't capture mouse look).
    const tLook = touchLookDelta(touchHoldRef.current)
    if (tLook.dx || tLook.dy) {
      const next = applyLook(
        { yaw: yaw.current, pitch: pitch.current },
        tLook.dx,
        tLook.dy,
        lookRef.current,
      )
      yaw.current = next.yaw
      pitch.current = next.pitch
    }
    const gLook = gyroLookRef.current
    if (gLook && (gLook.dx || gLook.dy)) {
      const next = applyLook(
        { yaw: yaw.current, pitch: pitch.current },
        gLook.dx,
        gLook.dy,
        lookRef.current,
      )
      yaw.current = next.yaw
      pitch.current = next.pitch
      // Consume so a stalled sensor does not keep drifting.
      gyroLookRef.current = { dx: 0, dy: 0 }
    }
    const padKeys = padSample ? {
      ...(padSample.jump ? { [bindsRef.current.jump]: true } : {}),
      ...(padSample.crouch ? { [bindsRef.current.crouch]: true } : {}),
      ...(padSample.sprint ? { [bindsRef.current.sprint]: true } : {}),
    } : {}
    const touchKeys = {
      ...(touchHoldRef.current.jump ? { [bindsRef.current.jump]: true } : {}),
      ...(touchHoldRef.current.sprint ? { [bindsRef.current.sprint]: true } : {}),
    }
    const mergedKeys = { ...keys.current, ...padKeys, ...touchKeys }
    const sprinting = isSprinting(mergedKeys, bindsRef.current)
      || !!(padSample?.sprint)
      || !!touchHoldRef.current.sprint
    const speed = (sprinting ? 6.1 : 3.15) * dt
    const forward = new THREE.Vector3(-Math.sin(yaw.current), 0, -Math.cos(yaw.current))
    const right = new THREE.Vector3(Math.cos(yaw.current), 0, -Math.sin(yaw.current))
    let moving = false
    // Accumulate the whole frame's intent into one delta, then resolve it ONCE.
    // Resolving per-key would test W and D against the geometry separately and
    // let a diagonal slip through a corner that neither axis alone can pass.
    const delta = new THREE.Vector3()
    const intent = mergeIntent(
      mergeIntent(
        movementIntent(keys.current, bindsRef.current),
        padSample?.intent,
      ),
      touchHoldRef.current,
    )
    if (intent.forward) { delta.addScaledVector(forward, speed); moving = true }
    if (intent.back) { delta.addScaledVector(forward, -speed); moving = true }
    if (intent.left) { delta.addScaledVector(right, -speed); moving = true }
    if (intent.right) { delta.addScaledVector(right, speed); moving = true }

    const solved = resolveWalk(
      { x: pos.current.x, z: pos.current.z },
      delta,
      collidersRef.current,
      PLAYER_RADIUS,
    )
    pos.current.x = solved.x
    pos.current.z = solved.z

    // Game-style boot-fall head-bob — stronger while sprinting.
    const bobFreq = sprinting ? 15.5 : 9.5
    const bobTarget = moving ? (sprinting ? 0.09 : 0.055) : 0
    bobAmount.current += (bobTarget - bobAmount.current) * Math.min(1, dt * 12)
    const prevPhase = bobPhase.current
    if (moving) bobPhase.current += dt * bobFreq
    const bob = Math.sin(bobPhase.current) * bobAmount.current
    const sway = Math.cos(bobPhase.current * 0.5) * bobAmount.current * 0.7
    // Soft procedural footfall when bob crosses zero (raised-floor thump feel).
    if (moving && Math.sin(prevPhase) <= 0 && Math.sin(bobPhase.current) > 0) {
      // Routed through the shared ambience bus rather than a private AudioContext:
      // a second context ignored the mute toggle and burned one of the browser's
      // small per-tab context budget. Null when audio is disarmed or muted.
      try { dcSfx()?.footstep(sprinting) } catch { /* no audio */ }
    }

    // Y must be written BEFORE it is read, or the camera renders last frame's
    // eye height. Now that crouch/jump exist this is real jitter, not theory.
    const vert = stepVertical(
      { y: pos.current.y, vy: vy.current, grounded: grounded.current },
      mergedKeys,
      dt,
      bindsRef.current,
    )
    pos.current.y = vert.y
    vy.current = vert.vy
    grounded.current = vert.grounded
    camera.position.set(pos.current.x + sway, pos.current.y + bob, pos.current.z)
    camera.rotation.order = 'YXZ'
    camera.rotation.y = yaw.current
    camera.rotation.x = pitch.current + bob * 0.28
    // Sprint FOV punch
    const targetFov = sprinting && moving ? 82 : 70
    if (camera.isPerspectiveCamera) {
      camera.fov += (targetFov - camera.fov) * Math.min(1, dt * 7)
      camera.updateProjectionMatrix()
    }

    if (posRef) {
      posRef.current.x = pos.current.x
      posRef.current.z = pos.current.z
      posRef.current.yaw = yaw.current
    }
  })
  return null
}

/** Floating dust motes in the cold aisle — cheap game-atmosphere particles. */
function HallDust({ count = 80 }) {
  const ref = useRef()
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3)
    for (let i = 0; i < count; i += 1) {
      arr[i * 3] = (Math.random() - 0.5) * 14
      arr[i * 3 + 1] = 0.4 + Math.random() * 2.4
      arr[i * 3 + 2] = (Math.random() - 0.5) * 10
    }
    return arr
  }, [count])
  useFrame(({ clock }) => {
    if (!ref.current) return
    const t = clock.elapsedTime
    const pos = ref.current.geometry.attributes.position.array
    for (let i = 0; i < count; i += 1) {
      pos[i * 3 + 1] += Math.sin(t * 0.4 + i) * 0.0008
      if (pos[i * 3 + 1] > 2.9) pos[i * 3 + 1] = 0.35
    }
    ref.current.geometry.attributes.position.needsUpdate = true
  })
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={count} array={positions} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial size={0.025} color="#94a3b8" transparent opacity={0.45} depthWrite={false} sizeAttenuation />
    </points>
  )
}

/** Walk up an object's ancestors looking for the nearest `userData.interact`
 *  descriptor. Interactables tag a *group*, but the raycaster hits a child mesh. */
export function findInteractable(object, maxDepth = 8) {
  let node = object
  let depth = 0
  while (node && depth < maxDepth) {
    if (node.userData?.interact) return { node, ...node.userData.interact }
    node = node.parent
    depth += 1
  }
  return null
}

export const MAX_INTERACT_DISTANCE = 3.2

/** Beyond this distance (metres) ServerFaceDetail hides LED/fan/Html detail —
 *  cheap LOD so far racks don't pay Html + ~13 meshes per server every frame. */
export const FACE_DETAIL_MAX_DIST = 10
export const FACE_HTML_MAX_DIST = HTML_LABEL_MAX_DIST

/** Crosshair interaction. Casts a REAL ray from screen center every few frames to
 *  find what you are aiming at, publishes the label for the `[E]` prompt, and runs
 *  that object's action on E.
 *
 *  This replaces a synthetic `MouseEvent` dispatched at canvas center, which
 *  bypassed R3F's raycaster ordering and picked drei `<Html>` overlays instead of
 *  the world geometry behind them. It also no longer silently no-ops when the
 *  pointer is unlocked — `onPrompt` reports why nothing happened. */
function CrosshairInteract({
  enabled, paused = false, locked = true, onPrompt, binds = DEFAULT_BINDS,
}) {
  const { camera, scene } = useThree()
  const raycaster = useMemo(() => new THREE.Raycaster(), [])
  const center = useMemo(() => new THREE.Vector2(0, 0), [])
  const target = useRef(null)
  const accum = useRef(0)
  const lastLabel = useRef(undefined)
  const bindsRef = useRef(binds)
  bindsRef.current = binds

  const publish = (next) => {
    if (lastLabel.current === next) return
    lastLabel.current = next
    onPrompt?.(next)
  }

  useFrame((_, rawDt) => {
    if (!enabled) return
    if (paused) { target.current = null; publish(null); return }
    if (!locked) {
      // Not a silent no-op any more: tell the player the mouse is unlocked so
      // "E does nothing" is explainable rather than a bug report.
      target.current = null
      publish({ kind: 'locked', label: 'Click to resume mouse look' })
      return
    }
    // Raycast at ~15Hz, not 60 — the crosshair target only has to be fresh enough
    // for a prompt, and BVH raycasts against the whole hall are not free.
    accum.current += clampDt(rawDt)
    if (accum.current < 0.066) return
    accum.current = 0
    raycaster.setFromCamera(center, camera)
    raycaster.far = MAX_INTERACT_DISTANCE
    const hits = raycaster.intersectObjects(scene.children, true)
    for (let i = 0; i < hits.length; i += 1) {
      const found = findInteractable(hits[i].object)
      if (found && hits[i].distance <= MAX_INTERACT_DISTANCE) {
        target.current = found
        publish({ kind: 'target', label: found.label })
        return
      }
    }
    target.current = null
    publish(null)
  })

  useEffect(() => {
    if (!enabled) return undefined
    const handler = (e) => {
      if (e.code !== bindsRef.current.interact) return
      if (paused || isTypingTarget(e.target)) return
      const hit = target.current
      if (hit?.action) hit.action()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [enabled, paused])

  useEffect(() => () => onPrompt?.(null), [onPrompt])
  return null
}

/** Interact prompt under the crosshair — key comes from the active bind map. */
function InteractPrompt({ prompt, interactKey = 'E' }) {
  if (!prompt) return null
  const unlocked = prompt.kind === 'locked'
  return (
    <div className={`dc-3d-interact-prompt${unlocked ? ' dc-3d-interact-prompt-warn' : ''}`}>
      {!unlocked && <kbd>{interactKey}</kbd>} {prompt.label}
    </div>
  )
}

/** Raised floor: 600mm tiles + perforated cold-aisle openings (procedural maps). */
function Floor() {
  const mat = useRef()
  const { solidMap, perfMap } = useMemo(() => ({
    solidMap: makeFloorTileTexture({ perforated: false }),
    perfMap: makeFloorTileTexture({ perforated: true }),
  }), [])
  const tiles = useMemo(() => {
    const list = []
    for (let gx = -10; gx <= 10; gx++) {
      for (let gz = -6; gz <= 4; gz++) {
        const coldAisle = Math.abs(gz + 1) < 0.6 || Math.abs(gz + 3.2) < 0.6
        list.push({
          key: `${gx}-${gz}`,
          x: gx * 0.6,
          z: gz * 0.6,
          perforated: coldAisle && (gx + gz) % 2 === 0,
        })
      }
    }
    return list
  }, [])
  useFrame(({ clock }) => {
    if (mat.current) mat.current.emissiveIntensity = 0.03 + Math.sin(clock.elapsedTime * 0.6) * 0.015
  })
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} receiveShadow>
        <planeGeometry args={[24, 16]} />
        <meshStandardMaterial
          ref={mat}
          color="#12151c"
          roughness={0.95}
          metalness={0.05}
          emissive="#1e293b"
          emissiveIntensity={0.04}
        />
      </mesh>
      {tiles.map((t) => (
        <mesh key={t.key} position={[t.x, 0.01, t.z]} receiveShadow>
          <boxGeometry args={[0.58, 0.04, 0.58]} />
          <meshStandardMaterial
            map={t.perforated ? perfMap : solidMap}
            color={t.perforated ? '#243044' : '#1a2030'}
            roughness={t.perforated ? 0.55 : 0.88}
            metalness={t.perforated ? 0.35 : 0.12}
            emissive={t.perforated ? '#0ea5e9' : '#000000'}
            emissiveIntensity={t.perforated ? 0.06 : 0}
          />
        </mesh>
      ))}
    </group>
  )
}

/** Strobing red beacon + hall wash for a thermal / power emergency. Real halls
 *  run a visual alarm precisely because the aisles are too loud for an audible one. */
function AlarmLighting({ level = 0 }) {
  const strobeA = useRef()
  const strobeB = useRef()
  const wash = useRef()
  useFrame(({ clock }) => {
    if (level <= 0) return
    // ~1.4Hz rotating-beacon sweep rather than a hard flash: staying under 3
    // flashes/sec keeps this outside the photosensitive band WCAG 2.3.1 flags.
    const s = (Math.sin(clock.elapsedTime * 8.8) + 1) / 2
    const pulse = level * (0.25 + s * 0.75)
    if (strobeA.current) strobeA.current.intensity = pulse * 3.2
    if (strobeB.current) strobeB.current.intensity = pulse * 3.2
    if (wash.current) wash.current.intensity = level * 0.55
  })
  if (level <= 0) return null
  return (
    <group>
      <pointLight ref={strobeA} position={[-3.2, 3.1, -1.6]} color="#ef4444" distance={11} decay={2} intensity={0} />
      <pointLight ref={strobeB} position={[3.2, 3.1, -3.8]} color="#ef4444" distance={11} decay={2} intensity={0} />
      {/* Constant red fill so the hall still reads "in alarm" between strobe peaks. */}
      <ambientLight ref={wash} color="#7f1d1d" intensity={0} />
    </group>
  )
}

/** Overhead LED fixtures along cold aisles.
 *  Emissive strips + two real lights, NOT one pointLight per fixture: ten forward-
 *  rendered point lights multiply every material's shader permutation and push at
 *  WebGL's uniform limit. The strips carry the look; the two lights supply falloff. */
function CeilingLights({ alarm = 0 }) {
  const fixtures = useMemo(() => {
    const list = []
    for (let x = -5; x <= 5; x += 2.5) {
      list.push([x, 3.35, -1.6], [x, 3.35, -3.8])
    }
    return list
  }, [])
  // House lights dim and shift red under alarm.
  const tubeColor = alarm > 0.15 ? '#fecaca' : '#f8fafc'
  const tubeEmissive = alarm > 0.15 ? '#fca5a5' : '#e2e8f0'
  return (
    <group>
      {fixtures.map(([x, y, z], i) => (
        <group key={i} position={[x, y, z]}>
          <mesh>
            <boxGeometry args={[1.4, 0.06, 0.28]} />
            <meshStandardMaterial color="#334155" metalness={0.5} roughness={0.4} />
          </mesh>
          <mesh position={[0, -0.04, 0]}>
            <boxGeometry args={[1.25, 0.02, 0.18]} />
            <meshStandardMaterial
              color={tubeColor}
              emissive={tubeEmissive}
              emissiveIntensity={0.85 * (1 - alarm * 0.45)}
              toneMapped={false}
            />
          </mesh>
        </group>
      ))}
      {/* Two aisle lights replace ten per-fixture lights. */}
      <pointLight color="#e8f0ff" intensity={1.5 * (1 - alarm * 0.5)} distance={16} decay={2} position={[0, 3.1, -1.6]} />
      <pointLight color="#e8f0ff" intensity={1.5 * (1 - alarm * 0.5)} distance={16} decay={2} position={[0, 3.1, -3.8]} />
      <AlarmLighting level={alarm} />
    </group>
  )
}

function HotAisleGlow({ z }) {
  const mesh = useRef()
  useFrame(({ clock }) => {
    if (mesh.current?.material) {
      mesh.current.material.opacity = 0.08 + Math.sin(clock.elapsedTime * 1.4 + z) * 0.05
    }
  })
  return (
    <mesh ref={mesh} position={[0, 0.02, z]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[18, 0.4]} />
      <meshBasicMaterial color="#f97316" transparent opacity={0.12} depthWrite={false} />
    </mesh>
  )
}

/** Rising heat/airflow particles in cold→hot aisle. */
function AirflowParticles({ count = 180, stress = 0 }) {
  const ref = useRef()
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 10
      arr[i * 3 + 1] = Math.random() * 2.2
      arr[i * 3 + 2] = -1.2 - Math.random() * 3.5
    }
    return arr
  }, [count])
  const speeds = useMemo(
    () => Float32Array.from({ length: count }, () => 0.25 + Math.random() * 0.55),
    [count],
  )

  const driftT = useRef(0)
  useFrame((_, rawDt) => {
    const mesh = ref.current
    if (!mesh) return
    // Clamped + accumulated: an unclamped dt after an alt-tab flung every particle
    // past the respawn ceiling in one step, and performance.now() kept advancing the
    // lateral drift phase while useFrame was paused.
    const dt = clampDt(rawDt)
    driftT.current += dt
    const pos = mesh.geometry.attributes.position.array
    const boost = 1 + stress * 1.8
    for (let i = 0; i < count; i++) {
      pos[i * 3 + 1] += speeds[i] * dt * boost
      pos[i * 3] += Math.sin(driftT.current + i) * 0.002 * boost
      if (pos[i * 3 + 1] > 2.4) {
        pos[i * 3 + 1] = 0.05
        pos[i * 3] = (Math.random() - 0.5) * 10
      }
    }
    mesh.geometry.attributes.position.needsUpdate = true
    if (mesh.material) {
      mesh.material.color.set(stress > 0.4 ? '#f97316' : '#38bdf8')
      mesh.material.opacity = 0.45 + stress * 0.35
    }
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.035}
        color="#38bdf8"
        transparent
        opacity={0.55}
        depthWrite={false}
        sizeAttenuation
      />
    </points>
  )
}

function CracUnits({ cooling = [] }) {
  return (
    <group position={[-6.2, 0, -2]}>
      {cooling.slice(0, 4).map((c, i) => {
        const failed = c.status !== 'running'
        return (
          <group key={c.id || i} position={[0, 0.7, -i * 1.4]}>
            <RoundedBox args={[0.9, 1.4, 0.7]} radius={0.03} castShadow>
              <meshStandardMaterial
                color={failed ? '#7f1d1d' : '#1e293b'}
                metalness={0.4}
                roughness={0.45}
                emissive={failed ? '#ef4444' : '#0ea5e9'}
                emissiveIntensity={failed ? 0.45 : 0.08}
              />
            </RoundedBox>
            <FanSpinner position={[0.2, 0.35, 0.38]} powered={!failed} />
            <DistanceCullingHtml position={[0, 0.85, 0]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
              <div className={`dc-3d-label ${failed ? 'dc-3d-label-hot' : ''}`}>
                {c.id} · {c.temp_c ?? '—'}°C
              </div>
            </DistanceCullingHtml>
          </group>
        )
      })}
    </group>
  )
}

function FanSpinner({ position, powered, rpmScale = 1, fault = false }) {
  const blades = useRef()
  const led = useRef()
  useFrame(({ clock }, dt) => {
    if (blades.current && powered && !fault) {
      // ~RPM-proportional spin (rpmScale 1 ≈ 9000 RPM visual)
      blades.current.rotation.z += dt * (18 + rpmScale * 22)
    } else if (blades.current && fault) {
      blades.current.rotation.z += dt * 1.2
    }
    if (led.current?.material) {
      if (fault) {
        led.current.material.emissiveIntensity = 0.4 + (Math.sin(clock.elapsedTime * 9) > 0 ? 0.6 : 0)
        led.current.material.emissive.set('#ef4444')
      } else if (powered) {
        led.current.material.emissiveIntensity = 0.5
        led.current.material.emissive.set('#34d399')
      } else {
        led.current.material.emissiveIntensity = 0
      }
    }
  })
  return (
    <group position={position}>
      <mesh>
        <cylinderGeometry args={[0.018, 0.018, 0.008, 10]} />
        <meshStandardMaterial color="#0f172a" metalness={0.7} />
      </mesh>
      <group ref={blades}>
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <mesh key={i} rotation={[0, 0, (i / 7) * Math.PI * 2]} position={[0, 0, 0.001]}>
            <boxGeometry args={[0.058, 0.011, 0.003]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.55} roughness={0.35} />
          </mesh>
        ))}
      </group>
      <mesh position={[0, 0, 0.006]}>
        <ringGeometry args={[0.05, 0.056, 16]} />
        <meshStandardMaterial color="#334155" metalness={0.6} />
      </mesh>
      <mesh ref={led} position={[0.04, 0.04, 0.01]}>
        <sphereGeometry args={[0.006, 8, 8]} />
        <meshStandardMaterial color="#34d399" emissive="#34d399" toneMapped={false} />
      </mesh>
    </group>
  )
}

/** PDU load as 0..1+ fraction of breaker rating (prefers kW / load_pct over fabricated amps). */
export function pduLoadFraction(pdu = {}) {
  const rating = Number(pdu.rating_kw)
  const loadKw = Number(pdu.load_kw)
  if (Number.isFinite(rating) && rating > 0 && Number.isFinite(loadKw)) {
    return Math.max(0, loadKw / rating)
  }
  const pct = Number(pdu.load_pct)
  if (Number.isFinite(pct)) return Math.max(0, pct / 100)
  return Math.min(1, (Number(pdu.load_amps) || Number(pdu.amps) || 12) / 32)
}

/** Amp/kW meter label for PDU Html chip. */
export function pduMeterLabel(pdu = {}) {
  if (pdu.status === 'tripped' || pdu.breaker === 'open') return 'PDU TRIP'
  const loadKw = Number(pdu.load_kw)
  const rating = Number(pdu.rating_kw)
  const derate = Number(pdu.continuous_derate_kw)
  if (Number.isFinite(loadKw) && Number.isFinite(rating) && rating > 0) {
    const pct = Math.round((loadKw / rating) * 100)
    const derateHint = Number.isFinite(derate) && derate > 0 && loadKw > derate * 0.95
      ? ' · 80%'
      : ''
    return `${loadKw.toFixed(1)}/${rating}kW ${pct}%${derateHint}`
  }
  return `${Math.round(pduLoadFraction(pdu) * 100)}%`
}

/** Pair A/B feed PDUs per rack for dual-strip rendering. */
export function pdusForRack(pdus = [], rackId) {
  const matches = (pdus || []).filter((p) => p.rack === rackId)
  const feedA = matches.find((p) => (p.feed || 'A').toUpperCase() === 'A'
    || (!p.feed && !String(p.id || '').endsWith('-B')))
    || matches[0]
    || {}
  const feedB = matches.find((p) => (p.feed || '').toUpperCase() === 'B'
    || String(p.id || '').endsWith('-B'))
    || (feedA.id ? { ...feedA, id: `${feedA.id}-B`, feed: 'B', load_kw: 0, load_pct: 0 } : null)
  return { feedA, feedB }
}

/** Short outlet→PSU whip segments from each PDU strip into the rack chassis. */
export function buildPduPsuCables(racks = [], pdus = []) {
  const out = []
  ;(racks || []).forEach((rack, i) => {
    const { x, z } = rackPosition(i)
    const { feedA, feedB } = pdusForRack(pdus, rack.id)
    ;[
      { pdu: feedA, side: 1, key: 'A' },
      ...(feedB ? [{ pdu: feedB, side: -1, key: 'B' }] : []),
    ].forEach(({ pdu, side, key }) => {
      if (!pdu || !pdu.id) return
      const tripped = pdu.status === 'tripped' || pdu.breaker === 'open'
      out.push({
        id: `whip-${rack.id}-${key}`,
        from: [x + side * (RACK_W / 2 + 0.08), RACK_H * 0.55, z],
        to: [x + side * (RACK_W / 2 - 0.02), RACK_H * 0.35, z + RACK_D * 0.15],
        feed: key,
        tripped,
      })
    })
  })
  return out
}

function PduPsuCables({ racks = [], pdus = [] }) {
  const cables = useMemo(() => buildPduPsuCables(racks, pdus), [racks, pdus])
  return (
    <group>
      {cables.map((c) => {
        const mid = [
          (c.from[0] + c.to[0]) / 2,
          (c.from[1] + c.to[1]) / 2 - 0.04,
          (c.from[2] + c.to[2]) / 2,
        ]
        const pts = [new THREE.Vector3(...c.from), new THREE.Vector3(...mid), new THREE.Vector3(...c.to)]
        const curve = new THREE.CatmullRomCurve3(pts)
        const geo = new THREE.TubeGeometry(curve, 8, 0.012, 5, false)
        return (
          <mesh key={c.id} geometry={geo}>
            <meshStandardMaterial
              color={c.tripped ? '#7f1d1d' : '#334155'}
              emissive={c.tripped ? '#ef4444' : c.feed === 'B' ? '#38bdf8' : '#22c55e'}
              emissiveIntensity={c.tripped ? 0.4 : 0.15}
              metalness={0.4}
              roughness={0.55}
            />
          </mesh>
        )
      })}
    </group>
  )
}

/** Horizontal patch panel near the MDF spine — residual after ToR-in-rack. */
function PatchPanel({ position = [4.15, 1.05, -1.2], ports = 24 }) {
  return (
    <group position={position}>
      <RoundedBox args={[0.85, 0.28, 0.12]} radius={0.01} castShadow>
        <meshStandardMaterial color="#111827" metalness={0.55} roughness={0.4} />
      </RoundedBox>
      {Array.from({ length: ports }).map((_, i) => {
        const col = i % 12
        const row = Math.floor(i / 12)
        const x = -0.36 + col * 0.06
        const y = 0.05 - row * 0.08
        return (
          <mesh key={i} position={[x, y, 0.07]}>
            <boxGeometry args={[0.04, 0.035, 0.02]} />
            <meshStandardMaterial
              color="#0f172a"
              emissive={i % 3 === 0 ? '#38bdf8' : '#22c55e'}
              emissiveIntensity={0.45}
            />
          </mesh>
        )
      })}
      <Html position={[0, 0.22, 0]} center distanceFactor={8} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label">Patch · {ports}p</div>
      </Html>
    </group>
  )
}

function PduStrips({ racks = [], pdus = [], onSelectPdu, arMode = 'off' }) {
  const powerBoost = arMode === 'power'
  return (
    <group>
      {racks.map((rack, i) => {
        const { x, z } = rackPosition(i)
        const { feedA, feedB } = pdusForRack(pdus, rack.id)
        const strips = [
          { pdu: feedA, side: 1, key: 'A' },
          ...(feedB ? [{ pdu: feedB, side: -1, key: 'B' }] : []),
        ]
        return strips.map(({ pdu, side, key }) => {
          const tripped = pdu.status === 'tripped' || pdu.breaker === 'open'
          const load = Math.min(1.2, pduLoadFraction(pdu))
          const overDerate = Number.isFinite(Number(pdu.continuous_derate_kw))
            && Number(pdu.load_kw) > Number(pdu.continuous_derate_kw)
          return (
            <group
              key={`pdu-${rack.id}-${key}`}
              position={[x + side * (RACK_W / 2 + 0.08), RACK_H / 2, z]}
            >
              <mesh
                castShadow
                onClick={(e) => { e.stopPropagation(); onSelectPdu?.(pdu.id || rack.id) }}
              >
                <boxGeometry args={[0.09, RACK_H * 0.92, 0.14]} />
                <meshStandardMaterial
                  color={tripped ? '#7f1d1d' : overDerate ? '#7c2d12' : '#1e293b'}
                  emissive={tripped ? '#ef4444' : overDerate ? '#f97316' : '#22c55e'}
                  emissiveIntensity={tripped ? 0.55 : (powerBoost ? 0.4 : 0.12)}
                  metalness={0.65}
                />
              </mesh>
              {Array.from({ length: 12 }).map((_, oi) => {
                const oy = -RACK_H * 0.4 + oi * (RACK_H * 0.78 / 11)
                const lit = !tripped && oi / 12 < load + 0.15
                return (
                  <mesh key={oi} position={[side * 0.05, oy, 0.04]}>
                    <boxGeometry args={[0.02, 0.035, 0.03]} />
                    <meshStandardMaterial
                      color={lit ? '#0f172a' : '#334155'}
                      emissive={tripped ? '#ef4444' : lit ? (overDerate ? '#f97316' : '#22c55e') : '#000'}
                      emissiveIntensity={tripped ? 0.7 : lit ? (powerBoost ? 0.85 : 0.45) : (powerBoost ? 0.12 : 0)}
                    />
                  </mesh>
                )
              })}
              <DistanceCullingHtml
                distanceFactor={8}
                position={[side * 0.12, RACK_H * 0.42, 0]}
                style={{ pointerEvents: 'none' }}
              >
                <div className="dc-3d-chip">{key} · {pduMeterLabel(pdu)}</div>
              </DistanceCullingHtml>
            </group>
          )
        })
      })}
    </group>
  )
}

function SelectionAura({ active }) {
  const ref = useRef()
  useFrame(({ clock }) => {
    if (!ref.current) return
    const t = (Math.sin(clock.elapsedTime * 3) + 1) / 2
    ref.current.material.opacity = active ? 0.12 + t * 0.18 : 0
    ref.current.scale.setScalar(active ? 1 + t * 0.03 : 1)
  })
  return (
    <mesh ref={ref} position={[0, 0, RACK_D / 2 + 0.025]}>
      <planeGeometry args={[RACK_W * 1.08, RACK_H * 1.04]} />
      <meshBasicMaterial color="#f97316" transparent opacity={0} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  )
}

function RackDoor({ open, side = 'left' }) {
  const ref = useRef()
  const target = open ? (side === 'left' ? -1.35 : 1.35) : 0
  useFrame((_, dt) => {
    if (!ref.current) return
    ref.current.rotation.y = THREE.MathUtils.damp(ref.current.rotation.y, target, 4, dt)
  })
  const x = side === 'left' ? -RACK_W / 2 : RACK_W / 2
  return (
    <group position={[x, 0, RACK_D / 2]} ref={ref}>
      <mesh position={[side === 'left' ? -0.14 : 0.14, 0, 0.01]} castShadow>
        <boxGeometry args={[0.28, RACK_H * 0.96, 0.02]} />
        <meshStandardMaterial color="#1e293b" metalness={0.45} roughness={0.4} transparent opacity={0.92} />
      </mesh>
    </group>
  )
}

/** Per-U chassis with drive-bay LEDs, dual PSU glow, NIC activity, fans.
 *  Steam-style tray slide-in on mount: chassis rails in from the aisle, then
 *  seat with staggered LED cascade (power → drives → NIC). */
/** Front face centre-Y and box height for a chassis, honouring multi-U models.
 *  `u_slot` is the BOTTOM U (DCIM convention), so a 2U server at U10 occupies
 *  U10-U11 and its centre sits half a U higher than a 1U in the same slot.
 *  The 3D layer used to ignore `u_height` entirely, drawing every 4U GPU box as 1U. */
export function chassisMetrics(server, uh = U_H) {
  const uHeight = Math.max(1, Math.min(12, Math.round(Number(server?.u_height) || 1)))
  const slot = Math.max(1, Number(server?.u_slot) || 1)
  const height = uh * uHeight * 0.9
  const y = (slot - 1) * uh + (uh * uHeight) / 2 + 0.05
  return { uHeight, slot, height, y }
}

/** Which of a rack's 42 U are unoccupied, given the chassis in it. Drives the
 *  blanking panels (an unbroken cold/hot aisle seal is real DC practice) and the
 *  free-U readout. */
export function freeUSlots(servers = [], totalU = 42) {
  const taken = new Set()
  servers.forEach((s) => {
    const { slot, uHeight } = chassisMetrics(s)
    for (let u = slot; u < slot + uHeight; u += 1) taken.add(u)
  })
  const free = []
  for (let u = 1; u <= totalU; u += 1) if (!taken.has(u)) free.push(u)
  return free
}

function ServerStack({ servers, onSelect, animBoost = 1, onOpenBmc }) {
  const meshRef = useRef()
  // Simulated install clock, advanced by clamped `dt` rather than wall-clock
  // performance.now(). useFrame does not tick while the tab is hidden, so a
  // wall-clock delta made the whole slide-in complete invisibly during an alt-tab
  // and you returned to already-seated trays.
  const installT = useRef(0)
  const geo = useMemo(() => new THREE.BoxGeometry(RACK_W * 0.88, U_H * 0.9, RACK_D * 0.72), [])
  const mat = useMemo(() => new THREE.MeshStandardMaterial({ metalness: 0.45, roughness: 0.35, vertexColors: true }), [])
  // R3F disposes what it created via JSX, but useMemo'd GPU resources are ours.
  // The twin unmounts on every 2D/3D toggle and room switch, so this leaked per toggle.
  useEffect(() => () => geo.dispose(), [geo])
  useEffect(() => () => mat.dispose(), [mat])
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const color = useMemo(() => new THREE.Color(), [])
  const count = servers.length
  const seatZ = useRef(new Float32Array(Math.max(count, 1)))
  const [hoverIdx, setHoverIdx] = useState(null)

  useFrame(({ clock }, rawDt) => {
    const mesh = meshRef.current
    if (!mesh || !count) return
    installT.current += clampDt(rawDt) * 1000
    const pulse = 0.08 + Math.sin(clock.elapsedTime * 2.5) * 0.04
    const now = installT.current
    servers.forEach((s, i) => {
      const failed = Object.values(s.components || {}).some((x) => x !== 'healthy')
      const powered = s.power_state === 'on'
      const { y, uHeight } = chassisMetrics(s)
      const delay = i * 160
      const u = Math.min(1, Math.max(0, (now - delay) / 850))
      const e = 1 - (1 - u) ** 3
      const slide = (1 - e) * 0.62
      seatZ.current[i] = -0.04 + slide
      const bob = powered && animBoost && e > 0.98 ? Math.sin(clock.elapsedTime * 1.4 + i) * 0.008 : 0
      const hoverBoost = hoverIdx === i ? 1.04 : 1
      dummy.position.set(0, y + bob, seatZ.current[i])
      // Slight nose-up while sliding, then level on the rails.
      dummy.rotation.x = (1 - e) * -0.12
      // Base geometry is exactly 1U tall, so Y-scale IS the chassis U height —
      // this is what makes a 2U/4U box actually look 2U/4U.
      dummy.scale.set(hoverBoost, uHeight * hoverBoost, (0.92 + e * 0.08) * hoverBoost)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
      if (failed) color.set('#ef4444')
      else if (!powered) color.set('#475569')
      else if (hoverIdx === i) color.set('#fdba74')
      else if (e < 1) color.set('#94a3b8')
      else color.set(vendorColor(s.vendor))
      mesh.setColorAt(i, color)
    })
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
    mesh.material.emissiveIntensity = pulse * animBoost
  })

  if (!count) return null
  const hovered = hoverIdx != null ? servers[hoverIdx] : null
  const hoverY = hovered ? chassisMetrics(hovered).y + chassisMetrics(hovered).height / 2 : 0
  const free = freeUSlots(servers)
  return (
    <group>
      <instancedMesh
        ref={meshRef}
        args={[geo, mat, count]}
        castShadow
        onClick={(e) => {
          e.stopPropagation()
          const id = e.instanceId
          if (id != null && servers[id]) onSelect?.(servers[id].id)
        }}
        onDoubleClick={(e) => {
          e.stopPropagation()
          const id = e.instanceId
          if (id != null && servers[id]) onOpenBmc?.(servers[id].id)
        }}
        onPointerMove={(e) => {
          e.stopPropagation()
          const id = e.instanceId
          if (id != null) setHoverIdx(id)
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          setHoverIdx(null)
          document.body.style.cursor = 'default'
        }}
      />
      {hovered && (
        <Html position={[0, hoverY + 0.22, RACK_D * 0.55]} center distanceFactor={7} style={{ pointerEvents: 'none' }}>
          <div className="dc-3d-nameplate">
            <div className="dc-3d-nameplate-host">{hovered.hostname || hovered.id}</div>
            <div className="dc-3d-nameplate-meta">
              U{hovered.u_slot || '—'}
              {chassisMetrics(hovered).uHeight > 1 ? `–${(hovered.u_slot || 1) + chassisMetrics(hovered).uHeight - 1}` : ''}
              {` (${chassisMetrics(hovered).uHeight}U)`}
              {hovered.service_tag ? ` · ${hovered.service_tag}` : ''}
              {hovered.vendor ? ` · ${hovered.vendor}` : ''}
              {' · '}
              <span className={
                Object.values(hovered.components || {}).some((x) => x !== 'healthy')
                  ? 'dc-3d-np-bad'
                  : 'dc-3d-np-ok'
              }
              >
                {Object.values(hovered.components || {}).some((x) => x !== 'healthy') ? 'FAULT' : 'OK'}
              </span>
            </div>
            <div className="dc-3d-nameplate-hint">Click · field tablet · dbl-click BMC</div>
          </div>
        </Html>
      )}
      {/* Blanking panels over every empty U. Real halls seal the unused U or the
          hot aisle short-circuits back through the rack face; an unbroken column
          of black also reads as a *populated* rack instead of a floating stack. */}
      {free.map((u) => (
        <mesh key={`blank-${u}`} position={[0, (u - 1) * U_H + U_H * 0.5 + 0.05, RACK_D * 0.36]}>
          <boxGeometry args={[RACK_W * 0.86, U_H * 0.88, 0.012]} />
          <meshStandardMaterial color="#0b0f16" metalness={0.15} roughness={0.85} />
        </mesh>
      ))}
      <DistanceCullingHtml position={[0, RACK_H + 0.06, RACK_D * 0.5]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label">{42 - free.length}U used · {free.length}U free</div>
      </DistanceCullingHtml>
      {servers.map((s, i) => {
        const failed = Object.values(s.components || {}).some((x) => x !== 'healthy')
        const diskFail = (s.components || {}).disk === 'failed' || (s.components || {}).disk === 'degraded'
        const powered = s.power_state === 'on'
        const m = chassisMetrics(s)
        return (
          <ServerFaceDetail
            key={s.id}
            server={s}
            index={i}
            // Faceplate detail hangs off the BOTTOM U of the chassis so a 4U box
            // does not float its LEDs at its vertical centre.
            y={(m.slot - 1) * U_H + U_H * 0.5 + 0.05}
            seatZRef={seatZ}
            installTRef={installT}
            failed={failed}
            diskFail={diskFail}
            powered={powered}
            animBoost={animBoost}
          />
        )
      })}
    </group>
  )
}

/** Faceplate LEDs / fans that track chassis tray Z during install slide. */
function ServerFaceDetail({
  server: s, index: i, y, seatZRef, installTRef, failed, diskFail, powered, animBoost,
}) {
  const group = useRef()
  const htmlRef = useRef()
  const { camera } = useThree()
  const worldPos = useMemo(() => new THREE.Vector3(), [])
  useFrame(() => {
    if (!group.current) return
    const z = seatZRef.current[i] ?? -0.04
    group.current.position.set(0, y, z)
    const delay = i * 160
    // Same simulated clock as the instanced trays — see ServerStack.installT.
    const u = Math.min(1, Math.max(0, ((installTRef?.current ?? 0) - delay) / 850))
    // Cascade: power LED → drives → NIC glow after seat.
    group.current.userData.ledGate = u
    // Distance LOD — cull face detail (and Html earlier) when far from camera.
    group.current.getWorldPosition(worldPos)
    const dist = camera.position.distanceTo(worldPos)
    group.current.visible = dist <= FACE_DETAIL_MAX_DIST
    if (htmlRef.current) {
      htmlRef.current.visible = dist <= FACE_HTML_MAX_DIST
    }
  })
  const ledGate = 1 // StatusLed reads powered; gate via powered && seated approx in children
  return (
    <group ref={group} position={[0, y, -0.04]}>
      <StatusLed position={[RACK_W * 0.38, 0.02, RACK_D * 0.38]} failed={failed} powered={powered} />
      <StatusLed position={[RACK_W * 0.38, -0.025, RACK_D * 0.38]} failed={false} powered={powered} />
      <StatusLed position={[RACK_W * 0.32, -0.025, RACK_D * 0.38]} failed={(s.components || {}).power === 'failed'} powered={powered} />
      {[0, 1, 2, 3].map((di) => (
        <group key={di} position={[-RACK_W * 0.28 + di * 0.08, 0.01, RACK_D * 0.37]}>
          <mesh>
            <boxGeometry args={[0.05, 0.035, 0.02]} />
            <meshStandardMaterial color="#0f172a" metalness={0.5} />
          </mesh>
          <StatusLed
            position={[0.015, 0.012, 0.012]}
            failed={diskFail && di === 0}
            powered={powered && !diskFail}
            warning={diskFail && di === 1}
            size={0.005}
          />
        </group>
      ))}
      {[0, 1].map((ni) => (
        <mesh key={`nic-${ni}`} position={[RACK_W * 0.1 + ni * 0.07, -0.02, RACK_D * 0.37]}>
          <boxGeometry args={[0.04, 0.025, 0.025]} />
          <meshStandardMaterial
            color="#111827"
            emissive={powered ? '#38bdf8' : '#000'}
            emissiveIntensity={powered ? 0.35 + Math.sin(ni) * 0.1 : 0}
          />
        </mesh>
      ))}
      <FanSpinner
        position={[-RACK_W * 0.32, 0, RACK_D * 0.38]}
        powered={powered && animBoost > 0}
        rpmScale={failed ? 0.35 : 1}
        fault={(s.components || {}).fan === 'failed' || failed}
      />
      <FanSpinner
        position={[-RACK_W * 0.22, 0, RACK_D * 0.38]}
        powered={powered && animBoost > 0}
        rpmScale={0.85}
        fault={(s.components || {}).fan === 'failed'}
      />
      <group ref={htmlRef}>
        <Html distanceFactor={10} position={[0, U_H * 0.35, RACK_D * 0.4]} style={{ pointerEvents: 'none' }}>
          <div className="dc-3d-chip dc-3d-chip-sm">{s.hostname || s.id}</div>
        </Html>
      </group>
      {/* unused gate reserved for future cascade timing */}
      <mesh visible={false} userData={{ ledGate }} />
    </group>
  )
}

function RackInner({
  rack, servers, selectedId, expanded, onSelectRack, onSelectServer, onOpenBmc, tip, animBoost,
  arMode = 'off', arThermalLevel = 0,
}) {
  const anyFail = servers.some((s) => Object.values(s.components || {}).some((c) => c !== 'healthy'))
  const group = useRef()
  const open = expanded || servers.some((s) => s.id === selectedId)

  useFrame(({ clock }) => {
    if (!group.current || !tip) return
    group.current.rotation.z = Math.sin(clock.elapsedTime * 1.8) * 0.035
  })

  // AR Thermal overlay: tint healthy racks warmer as CRAC/ticket stress rises —
  // failed racks already read red, so leave that signal untouched.
  const thermalOn = arMode === 'thermal' && !anyFail && arThermalLevel > 0.04
  const rackColor = anyFail ? '#3f1d1d' : (thermalOn ? lerpHex('#0f141f', '#7c2d12', arThermalLevel) : '#0f141f')
  const rackEmissive = anyFail
    ? '#7f1d1d'
    : (thermalOn ? lerpHex('#0ea5e9', '#f97316', Math.min(1, arThermalLevel + 0.3)) : '#0ea5e9')
  const rackEmissiveIntensity = anyFail
    ? 0.28
    : (open ? 0.08 : 0.02) + (thermalOn ? arThermalLevel * 0.35 : 0)
  const metalMap = useMemo(() => makeBrushedMetalTexture({ base: '#475569' }), [])

  return (
    <group
      ref={group}
      // Crosshair registry entry — drives the `[E]` prompt and the real raycast.
      userData={{
        interact: {
          label: `Open rack ${rack.name || rack.id}`,
          action: () => onSelectRack?.(rack.id),
        },
      }}
      onClick={(e) => { e.stopPropagation(); onSelectRack?.(rack.id) }}
    >
      <RoundedBox args={[RACK_W, RACK_H, RACK_D]} radius={0.02} castShadow receiveShadow>
        <meshStandardMaterial
          map={metalMap}
          color={rackColor}
          metalness={0.55}
          roughness={0.35}
          emissive={rackEmissive}
          emissiveIntensity={rackEmissiveIntensity}
        />
      </RoundedBox>
      <mesh position={[-RACK_W / 2 + 0.02, 0, 0]}>
        <boxGeometry args={[0.03, RACK_H * 0.98, RACK_D * 0.95]} />
        <meshStandardMaterial map={metalMap} color="#334155" metalness={0.7} roughness={0.4} />
      </mesh>
      <mesh position={[RACK_W / 2 - 0.02, 0, 0]}>
        <boxGeometry args={[0.03, RACK_H * 0.98, RACK_D * 0.95]} />
        <meshStandardMaterial map={metalMap} color="#334155" metalness={0.7} roughness={0.4} />
      </mesh>
      <RackDoor open={open} side="left" />
      <RackDoor open={open} side="right" />
      <ServerStack servers={servers} onSelect={onSelectServer} onOpenBmc={onOpenBmc} animBoost={animBoost} />
      <SelectionAura active={!!selectedId && servers.some((s) => s.id === selectedId)} />
      <Html position={[0, RACK_H / 2 + 0.14, 0]} center distanceFactor={8} style={{ pointerEvents: 'none' }}>
        <div className={`dc-3d-label ${open ? 'dc-3d-label-hot' : ''}`}>
          {rack.id}
          {tip ? ' · TIP' : ''}
          {rack.physics?.mass_kg ? ` · ${rack.physics.mass_kg}kg` : ''}
        </div>
      </Html>
    </group>
  )
}

function RackMesh({
  rack, servers, index, selectedId, expandedRack, onSelectRack, onSelectServer, onOpenBmc, physicsEnabled, animBoost,
  arMode = 'off', arThermalLevel = 0,
}) {
  const tip = rack.physics?.tip_risk === 'high'
  const { x, z } = rackPosition(index)
  const wrap = useRef()
  // Simulated elapsed ms, advanced by clamped dt. Wall-clock deltas ran the drop-in
  // while the tab was hidden (useFrame is paused), so every rack was already seated
  // on return. Negative start = the per-rack stagger.
  const introT = useRef(-index * 110)

  useFrame((_, rawDt) => {
    if (!wrap.current) return
    introT.current += clampDt(rawDt) * 1000
    const u = Math.min(1, Math.max(0, introT.current / 950))
    const e = 1 - (1 - u) ** 3
    wrap.current.position.set(x, RACK_H / 2 - (1 - e) * 1.15, z)
    wrap.current.scale.setScalar(0.88 + e * 0.12)
  })

  const inner = (
    <RackInner
      rack={rack}
      servers={servers}
      selectedId={selectedId}
      expanded={expandedRack === rack.id}
      onSelectRack={onSelectRack}
      onSelectServer={onSelectServer}
      onOpenBmc={onOpenBmc}
      tip={tip}
      animBoost={animBoost}
      arMode={arMode}
      arThermalLevel={arThermalLevel}
    />
  )

  if (physicsEnabled && tip) {
    return (
      <group ref={wrap}>
        <RigidBody
          type="dynamic"
          colliders="cuboid"
          enabledRotations={[false, false, true]}
          linearDamping={4}
          angularDamping={6}
        >
          {inner}
        </RigidBody>
      </group>
    )
  }

  if (physicsEnabled) {
    return (
      <group ref={wrap}>
        <RigidBody type="fixed" colliders="cuboid">
          {inner}
        </RigidBody>
      </group>
    )
  }

  return (
    <group ref={wrap} rotation={[0, 0, tip ? 0.06 : 0]}>
      {inner}
    </group>
  )
}

function PulsingLight() {
  const ref = useRef()
  useFrame(({ clock }) => {
    if (ref.current) ref.current.intensity = 0.35 + Math.sin(clock.elapsedTime * 1.2) * 0.15
  })
  return <pointLight ref={ref} position={[-4, 3, -2]} color="#38bdf8" />
}

/**
 * Procedural image-based lighting for the hall — NO network fetch.
 *
 * Replaces `<Environment preset="warehouse" />`, which pulled
 * `empty_warehouse_01_1k.hdr` from a CDN at runtime. That fetch failing
 * (offline, air-gapped lab, CDN blocked, flaky network) threw inside the R3F
 * tree and knocked the whole twin into the failure banner — and because the
 * error message contains the literal string "Failed to fetch", it also tripped
 * the over-broad stale-chunk matcher in main.jsx and reloaded the page.
 *
 * drei's <Environment> renders its children into an offscreen cube target, so
 * Lightformers give us a real env map generated on the GPU with zero requests.
 * Tuned for a dark server hall: cool overhead strips down the cold aisle, a
 * warm bounce at floor level, and dim side rims so metal reads as metal.
 */
function HallEnvironment() {
  return (
    <Environment resolution={256} frames={1}>
      {/* Overhead cold-aisle strips — the dominant source, mirrors CeilingLights */}
      <Lightformer form="rect" intensity={2.2} color="#dbeafe" position={[0, 6, -2]} rotation={[Math.PI / 2, 0, 0]} scale={[10, 3, 1]} />
      <Lightformer form="rect" intensity={1.6} color="#e0f2fe" position={[0, 6, 3]} rotation={[Math.PI / 2, 0, 0]} scale={[10, 3, 1]} />
      {/* Side rims so rack metal and cable jackets catch a highlight */}
      <Lightformer form="rect" intensity={0.8} color="#93c5fd" position={[-7, 2.5, 0]} rotation={[0, Math.PI / 2, 0]} scale={[8, 3, 1]} />
      <Lightformer form="rect" intensity={0.8} color="#93c5fd" position={[7, 2.5, 0]} rotation={[0, -Math.PI / 2, 0]} scale={[8, 3, 1]} />
      {/* Warm floor bounce — keeps shadow sides from going pure black */}
      <Lightformer form="rect" intensity={0.35} color="#fbbf24" position={[0, -1, 0]} rotation={[-Math.PI / 2, 0, 0]} scale={[12, 8, 1]} />
      {/* Faint cyan ambient from equipment LEDs */}
      <Lightformer form="circle" intensity={0.5} color="#38bdf8" position={[-3, 1.2, -5]} scale={[3, 3, 1]} />
    </Environment>
  )
}

function TorSwitch({ position = [5.5, 0.95, -1.2], label = 'MDF / Agg', ports = 48 }) {
  const leds = useRef([])
  useFrame(({ clock }) => {
    leds.current.forEach((m, i) => {
      if (!m?.material) return
      const blink = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(clock.elapsedTime * (6 + (i % 7)) + i))
      m.material.emissiveIntensity = blink
    })
  })
  const cols = 12
  return (
    <Float speed={1.2} floatIntensity={0.1} rotationIntensity={0.04}>
      <group position={position}>
        <RoundedBox args={[1.1, 0.22, 0.55]} radius={0.015} castShadow>
          <meshStandardMaterial color="#0b1220" metalness={0.65} roughness={0.3} />
        </RoundedBox>
        <mesh position={[0.42, 0, 0.22]}>
          <boxGeometry args={[0.18, 0.16, 0.08]} />
          <meshStandardMaterial color="#1e293b" metalness={0.5} />
        </mesh>
        {Array.from({ length: ports }).map((_, i) => {
          const col = i % cols
          const row = Math.floor(i / cols)
          const x = -0.48 + col * 0.08
          const y = 0.04 - row * 0.07
          return (
            <mesh
              key={i}
              ref={(el) => { if (el) leds.current[i] = el }}
              position={[x, y, 0.28]}
            >
              <boxGeometry args={[0.05, 0.035, 0.02]} />
              <meshStandardMaterial
                color="#022c22"
                emissive={i % 5 === 0 ? '#f59e0b' : '#22c55e'}
                emissiveIntensity={0.6}
                metalness={0.4}
              />
            </mesh>
          )
        })}
        <Html position={[0, 0.22, 0]} center distanceFactor={8} style={{ pointerEvents: 'none' }}>
          <div className="dc-3d-label dc-3d-label-hot">{label} · {ports}p</div>
        </Html>
      </group>
    </Float>
  )
}

function CableTray() {
  return (
    <group position={[0, 2.55, -1.6]}>
      <mesh>
        <boxGeometry args={[12, 0.04, 0.55]} />
        <meshStandardMaterial color="#334155" metalness={0.7} roughness={0.4} />
      </mesh>
      {[-5, -2.5, 0, 2.5, 5].map((x) => (
        <mesh key={x} position={[x, -0.12, 0]}>
          <boxGeometry args={[0.04, 0.22, 0.55]} />
          <meshStandardMaterial color="#475569" metalness={0.6} />
        </mesh>
      ))}
      {[-0.12, 0, 0.12].map((z, i) => (
        <mesh key={z} position={[0, 0.04, z]}>
          <cylinderGeometry args={[0.025, 0.025, 11.5, 8]} />
          <meshStandardMaterial
            color={i === 1 ? '#38bdf8' : '#f97316'}
            emissive={i === 1 ? '#0ea5e9' : '#ea580c'}
            emissiveIntensity={0.25}
          />
        </mesh>
      ))}
    </group>
  )
}

/** Ticket objective marker — glowing beacon above the faulted rack/U (Steam quest marker). */
function TicketWaypoint({ ticket, racks, serversByRack, onSelectServer }) {
  const ref = useRef()
  const pos = useMemo(() => {
    const aid = ticket?.asset_id
    if (!aid) return null
    let rackIdx = -1
    let uy = 1.2
    racks.forEach((rack, i) => {
      const list = serversByRack[rack.id] || []
      const s = list.find((x) => x.id === aid)
      if (s) {
        rackIdx = i
        uy = ((s.u_slot || 1) - 1) * U_H + U_H * 0.5 + 0.35
      }
    })
    if (rackIdx < 0) return null
    const { x, z } = rackPosition(rackIdx)
    return [x, uy, z + RACK_D / 2 + 0.25]
  }, [ticket, racks, serversByRack])

  useFrame(({ clock }) => {
    if (!ref.current || !pos) return
    ref.current.position.y = pos[1] + Math.sin(clock.elapsedTime * 2.4) * 0.08
    ref.current.rotation.y = clock.elapsedTime * 1.2
  })
  if (!pos) return null
  const hot = Boolean(ticket?.sla_breached) || /critical|high/i.test(ticket?.priority || '')
  const slaLabel = ticket?.sla_breached
    ? 'SLA!'
    : (typeof ticket?.sla_remaining_sec === 'number'
      ? `${Math.max(0, Math.ceil(ticket.sla_remaining_sec / 60))}m`
      : '')
  return (
    <group
      ref={ref}
      position={pos}
      userData={{
        interact: {
          label: `Open ticket ${ticket?.id || ''}`.trim(),
          action: () => { if (ticket?.asset_id) onSelectServer?.(ticket.asset_id) },
        },
      }}
      onClick={(e) => {
        e.stopPropagation()
        if (ticket?.asset_id) onSelectServer?.(ticket.asset_id)
      }}
      onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer' }}
      onPointerOut={() => { document.body.style.cursor = 'default' }}
    >
      <mesh castShadow>
        <coneGeometry args={[0.12, 0.28, 4]} />
        <meshStandardMaterial
          color={hot ? '#ef4444' : '#f59e0b'}
          emissive={hot ? '#dc2626' : '#d97706'}
          emissiveIntensity={0.85}
          metalness={0.2}
          roughness={0.4}
        />
      </mesh>
      <DistanceCullingHtml center distanceFactor={8} style={{ pointerEvents: 'none' }}>
        <div className={`dc-3d-label ${hot ? 'dc-3d-label-hot' : ''}`}>
          {(ticket.id || 'TKT').slice(0, 12)}
          {slaLabel ? ` · ${slaLabel}` : ''}
          {' · '}{(ticket.summary || ticket.title || 'fault').slice(0, 22)}
        </div>
      </DistanceCullingHtml>
    </group>
  )
}

/** Corridor door portal into another campus room (walk-up, not room-tab only). */
function RoomPortal({ position, label, roomId, onEnterRoom, color = '#38bdf8' }) {
  const matRef = useRef()
  useFrame(({ clock }) => {
    if (!matRef.current) return
    matRef.current.emissiveIntensity = 0.25 + Math.sin(clock.elapsedTime * 2) * 0.12
  })
  return (
    <group
      position={position}
      userData={{ interact: { label: `Enter ${label}`, action: () => onEnterRoom?.({ id: roomId, name: label }) } }}
    >
      <mesh
        castShadow
        onClick={(e) => {
          e.stopPropagation()
          onEnterRoom?.({ id: roomId, name: label })
        }}
        onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { document.body.style.cursor = 'default' }}
      >
        <boxGeometry args={[1.1, 2.1, 0.08]} />
        <meshStandardMaterial
          ref={matRef}
          color="#0f172a"
          emissive={color}
          emissiveIntensity={0.3}
          metalness={0.5}
          roughness={0.35}
        />
      </mesh>
      <DistanceCullingHtml position={[0, 1.25, 0.1]} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label dc-3d-portal-label" style={{ '--portal-color': color }}>{label}</div>
      </DistanceCullingHtml>
    </group>
  )
}

/** Glowing badge desk near the mantrap — the in-world alternative to the toolbar
 *  Badge-in button. Walk up and press E (or click) to badge in. */
function BadgeDesk({ badgedIn, onBadgeIn }) {
  const matRef = useRef()
  useFrame(({ clock }) => {
    if (!matRef.current) return
    matRef.current.emissiveIntensity = 0.45 + Math.sin(clock.elapsedTime * 2.4) * 0.2
  })
  if (badgedIn) return null
  return (
    <group
      position={[-4.55, 0, 4.75]}
      userData={{ interact: { label: 'Badge in at the mantrap', action: () => onBadgeIn?.() } }}
    >
      <mesh castShadow receiveShadow position={[0, 0.5, 0]}>
        <boxGeometry args={[0.55, 1.0, 0.4]} />
        <meshStandardMaterial color="#1e293b" metalness={0.4} roughness={0.55} />
      </mesh>
      <mesh
        position={[0, 1.05, 0.16]}
        onClick={(e) => { e.stopPropagation(); onBadgeIn?.() }}
        onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { document.body.style.cursor = 'default' }}
      >
        <boxGeometry args={[0.16, 0.22, 0.06]} />
        <meshStandardMaterial ref={matRef} color="#0f172a" emissive="#fbbf24" emissiveIntensity={0.45} metalness={0.3} roughness={0.4} />
      </mesh>
      <Html position={[0, 1.42, 0.16]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label dc-3d-label-hot">Badge reader · tap E</div>
      </Html>
    </group>
  )
}

/** NOC wall stub — three small in-world monitor panels near the NOC portal,
 *  fed from live monitoring/ticket counts when available, else static numbers.
 *  Purely decorative — never forces a room switch. */
function NocWall({ metrics = {} }) {
  const panelRefs = useRef([])
  const panels = useMemo(() => ([
    { key: 'gpu', label: 'GPU util', value: `${Math.round(metrics.gpuUtil ?? 58)}%`, color: '#38bdf8' },
    { key: 'pue', label: 'PUE', value: Number(metrics.pue ?? 1.34).toFixed(2), color: '#34d399' },
    {
      key: 'tix',
      label: 'Tickets open',
      value: `${metrics.ticketsOpen ?? 3}`,
      color: (metrics.ticketsOpen ?? 3) > 5 ? '#f87171' : '#fbbf24',
    },
  ]), [metrics.gpuUtil, metrics.pue, metrics.ticketsOpen])

  useFrame(({ clock }) => {
    panelRefs.current.forEach((m, i) => {
      if (m?.material) m.material.emissiveIntensity = 0.35 + Math.sin(clock.elapsedTime * 1.6 + i) * 0.08
    })
  })

  return (
    <group position={[2.15, 1.55, 2.85]}>
      <mesh position={[0, 0, -0.03]} castShadow>
        <boxGeometry args={[1.5, 0.8, 0.04]} />
        <meshStandardMaterial color="#0b1220" metalness={0.5} roughness={0.4} />
      </mesh>
      {panels.map((p, i) => (
        <group key={p.key} position={[-0.48 + i * 0.48, 0, 0.01]}>
          <mesh ref={(el) => { if (el) panelRefs.current[i] = el }}>
            <planeGeometry args={[0.4, 0.62]} />
            <meshStandardMaterial color="#020617" emissive={p.color} emissiveIntensity={0.35} />
          </mesh>
          <Html center distanceFactor={8} position={[0, 0, 0.01]} style={{ pointerEvents: 'none' }}>
            <div className="dc-noc-wall-panel" style={{ '--noc-color': p.color }}>
              <span className="dc-noc-wall-label">{p.label}</span>
              <span className="dc-noc-wall-value">{p.value}</span>
            </div>
          </Html>
        </group>
      ))}
      <Html position={[0, 0.55, 0.01]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label">NOC wall</div>
      </Html>
    </group>
  )
}

function SceneContent({
  racks, serversByRack, network, cooling, pdus, selectedId, expandedRack,
  onSelectServer, onSelectRack, onOpenBmc, onUnplugCable, onPlugCable, physicsEnabled, onFps, animBoost, intro,
  walkMode = false, tickets = [], doorOpen = false, onEnterRoom, walkPaused = false, posRef,
  arMode = 'off', badgedIn = false, onBadgeIn, nocMetrics = {},
  dustCount = 90, shadowMapSize = 1024, look = DEFAULT_LOOK, binds = DEFAULT_BINDS, onPointerLockChange, pointerLocked = false, onInteractPrompt,
  spawn = null, onPosCommit,
}) {
  // Collider list is derived from the same counts the meshes are rendered from —
  // racks.map(...) and cooling.slice(0, 4) — so it cannot drift from the visuals.
  // doorOpen (badge-in) is the one dynamic collider: until you badge in, the
  // mantrap leaf is solid and the hall is genuinely unreachable on foot.
  const walkColliders = useMemo(() => buildHallColliders({
    rackCount: (racks || []).length,
    cracCount: Math.min(4, (cooling || []).length),
    doorOpen,
  }), [racks, cooling, doorOpen])

  const thermalStress = useMemo(() => {
    const units = cooling || []
    if (!units.length) return 0
    const failed = units.filter((c) => c.status !== 'running').length
    const hot = units.filter((c) => Number(c.temp_c) > 28).length
    return Math.min(1, failed / units.length + hot * 0.15)
  }, [cooling])

  // Alarm state = thermal runaway OR a lost power path. Deliberately latched above
  // a threshold rather than tracking stress linearly: a hall that pulses faintly red
  // for a single warm CRAC teaches the player to ignore the alarm.
  const alarmLevel = useMemo(() => {
    const breakerOpen = (pdus || []).some((p) => p.status === 'tripped' || p.breaker === 'open')
    if (thermalStress < 0.45 && !breakerOpen) return 0
    return Math.min(1, Math.max(breakerOpen ? 0.7 : 0, thermalStress))
  }, [thermalStress, pdus])

  const ticketHeat = useMemo(() => {
    const open = (tickets || []).filter((t) => !['closed', 'resolved'].includes((t.status || '').toLowerCase()))
    if (!open.length) return 0
    let score = 0
    open.forEach((t) => {
      const p = (t.priority || '').toLowerCase()
      const blob = `${t.summary || ''} ${t.component || ''} ${t.title || ''}`.toLowerCase()
      if (p === 'critical' || /thermal|overheat|hot.?aisle|gpu/.test(blob)) score += 0.45
      else if (p === 'high') score += 0.25
      else score += 0.1
    })
    return Math.min(1, score)
  }, [tickets])

  // Shared with the AR Thermal overlay so racks tint warmer under the same
  // CRAC/ticket stress signal that drives the hot-aisle haze.
  const arThermalLevel = useMemo(
    () => Math.min(1, thermalStress + ticketHeat * 0.6),
    [thermalStress, ticketHeat],
  )

  const dockBusy = useMemo(() => {
    return (tickets || []).some((t) => {
      const st = (t.status || '').toLowerCase()
      return st === 'awaiting_parts' || t.type === 'rma' || t._pending_dock_asn || t.rma?.status === 'parts_shipped'
    })
  }, [tickets])

  const switchCount = (network?.switches || []).length
  const mdfPos = useMemo(() => new THREE.Vector3(5.5, 1.05, -1.2), [])
  const topology = network?.cable_topology || []

  const cables = useMemo(() => {
    const links = []
    const serverIndex = {}
    racks.forEach((rack, i) => {
      const { x: sx, z: sz } = rackPosition(i)
      ;(serversByRack[rack.id] || []).forEach((s, si) => {
        const uy = ((s.u_slot || (si + 1)) - 1) * U_H - RACK_H / 2 + U_H / 2 + RACK_H / 2
        serverIndex[s.id] = new THREE.Vector3(sx + RACK_W * 0.22, uy, sz + RACK_D / 2)
        if (s.hostname) serverIndex[s.hostname] = serverIndex[s.id]
      })
    })

    // Prefer port-map topology from the engine (D14) over synthetic backbone.
    if (topology.length) {
      topology.forEach((t) => {
        const toPos = serverIndex[t.to]
        if (!toPos) return // switch↔switch / unknown peers stay in data, not drawn yet
        const fromRack = racks.findIndex((r) => (serversByRack[r.id] || []).some((s) => s.id === t.to || s.hostname === t.to))
        const { x: sx, z: sz } = fromRack >= 0 ? rackPosition(fromRack) : { x: 0, z: 0 }
        links.push({
          id: t.id,
          serverId: t.to,
          cableId: t.id,
          cableType: t.media === 'fiber' ? 'Fiber-LC' : 'Cat6A',
          from: toPos,
          to: new THREE.Vector3(sx, 1.55, sz + RACK_D / 2 + 0.08),
          loose: false,
          interactive: false,
          label: `${t.from}:${t.from_port} → ${t.to}`,
        })
      })
    }

    racks.forEach((rack, i) => {
      const { x: sx, z: sz } = rackPosition(i)
      const srvList = serversByRack[rack.id] || []
      const tray = new THREE.Vector3(sx, 2.45, -1.6)

      // Plant backbone only when no real topology (legacy visual fill).
      if (!topology.length && (switchCount > 0 || i <= 8)) {
        links.push({
          id: `${rack.id}-backbone`,
          serverId: srvList[0]?.id,
          cableId: `${rack.id}-uplink`,
          cableType: 'Fiber-LC',
          from: new THREE.Vector3(sx, 1.65, sz + RACK_D / 2),
          to: tray.clone(),
          loose: false,
          interactive: false,
        })
        links.push({
          id: `${rack.id}-mdf`,
          cableType: 'Fiber-LC',
          from: tray.clone(),
          to: mdfPos.clone(),
          loose: false,
          interactive: false,
        })
      }

      // Real NIC cables from hardware inventory — interactive plug/unplug
      srvList.forEach((s, si) => {
        const uy = ((s.u_slot || (si + 1)) - 1) * U_H - RACK_H / 2 + U_H / 2 + RACK_H / 2
        const port = new THREE.Vector3(sx + RACK_W * 0.22, uy, sz + RACK_D / 2)
        const hwCables = s.hardware?.cables || []
        if (!hwCables.length) {
          if (topology.length) return // topology already drew the access link
          links.push({
            id: `${s.id}-nic0`,
            serverId: s.id,
            cableId: 'NIC0-front',
            cableType: 'DAC',
            from: port,
            to: new THREE.Vector3(sx, 1.55, sz + RACK_D / 2 + 0.08),
            loose: (s.components || {}).nic === 'failed',
            interactive: true,
            label: `${s.hostname || s.id} · NIC0`,
          })
          return
        }
        hwCables.slice(0, 3).forEach((c, ci) => {
          const loose = ['loose', 'damaged', 'unseated'].includes(c.status)
          links.push({
            id: `${s.id}-${c.id}`,
            serverId: s.id,
            cableId: c.id,
            cableType: c.type || c.catalog_type || 'Cat6A',
            bendRadiusMm: c.bend_radius_mm,
            from: port.clone().add(new THREE.Vector3(ci * 0.04, 0, 0)),
            to: new THREE.Vector3(sx + ci * 0.05, 1.5 + ci * 0.05, sz + RACK_D / 2 + 0.1),
            loose,
            interactive: true,
            label: c.label || c.id,
          })
        })
      })
    })
    return links
  }, [racks, serversByRack, switchCount, mdfPos, topology])

  const cableAnchors = useMemo(
    () => cables.filter((c) => c.loose).map((c) => [
      (c.from.x + c.to.x) / 2,
      Math.max(0.2, (c.from.y + c.to.y) / 2 - 0.2),
      (c.from.z + c.to.z) / 2,
    ]),
    [cables],
  )

  return (
    <>
      <FpsMeter onFps={onFps} />
      {!walkMode && <CameraIntro enabled={intro} cinematic />}
      <WalkController
        enabled={walkMode}
        paused={walkPaused}
        posRef={posRef}
        look={look}
        binds={binds}
        onPointerLockChange={onPointerLockChange}
        colliders={walkColliders}
        spawn={spawn}
        onPosCommit={onPosCommit}
      />
      <CrosshairInteract
        enabled={walkMode}
        paused={walkPaused}
        locked={pointerLocked}
        binds={binds}
        onPrompt={onInteractPrompt}
      />
      <color attach="background" args={['#070a10']} />
      {/* Tight fog sells depth in first-person — hall falls off like a game level */}
      <fog attach="fog" args={['#070a10', walkMode ? 5.5 : 10, walkMode ? 18 : 28]} />
      <ambientLight intensity={0.22} />
      <directionalLight
        castShadow
        position={[6, 10, 4]}
        intensity={1.05}
        shadow-mapSize={[shadowMapSize, shadowMapSize]}
        shadow-camera-left={-12}
        shadow-camera-right={12}
        shadow-camera-top={12}
        shadow-camera-bottom={-12}
        shadow-camera-far={30}
        shadow-bias={-0.0002}
      />
      <directionalLight position={[-4, 6, -6]} intensity={0.4} color="#94a3b8" />
      <PulsingLight />
      <HallEnvironment />
      <Floor />
      <CorridorShell dockBusy={dockBusy} doorOpen={doorOpen} />
      <HallDust count={dustCount || (walkMode ? 140 : 90)} />
      <RoomPortal position={[-6.2, 1.05, 0.2]} label="Staging / dock" roomId="loading-dock" onEnterRoom={onEnterRoom} color="#f59e0b" />
      <RoomPortal position={[-5.2, 1.05, 3.2]} label="Reception" roomId="reception" onEnterRoom={onEnterRoom} color="#94a3b8" />
      <RoomPortal position={[5.8, 1.05, 0.4]} label="MDF" roomId="mdf" onEnterRoom={onEnterRoom} color="#38bdf8" />
      <RoomPortal position={[3.2, 1.05, 3.4]} label="NOC" roomId="noc" onEnterRoom={onEnterRoom} color="#a78bfa" />
      <NocWall metrics={nocMetrics} />
      <BadgeDesk badgedIn={badgedIn} onBadgeIn={onBadgeIn} />
      {(tickets || [])
        .filter((t) => t?.asset_id && !['closed', 'resolved'].includes((t.status || '').toLowerCase()))
        .slice(0, 8)
        .map((t) => (
          <TicketWaypoint
            key={t.id || t.asset_id}
            ticket={t}
            racks={racks}
            serversByRack={serversByRack}
            onSelectServer={onSelectServer}
          />
        ))}
      <CeilingLights alarm={alarmLevel} />
      <CableTray />
      <HotAisleGlow z={-1.6} />
      <HotAisleGlow z={-3.8} />
      <ThermalHaze stress={thermalStress} ticketHeat={ticketHeat} />
      {/* Fixed particle budget. Count used to scale with thermalStress (220 × up to
          2.4×, plus a second 80-particle system), so the frame rate was worst exactly
          during a thermal crisis — the moment the player most needs to read the hall.
          Stress is now expressed through velocity and colour inside AirflowParticles,
          which costs nothing extra. */}
      {animBoost > 0 && (
        <AirflowParticles
          count={Math.round(220 * animBoost)}
          stress={thermalStress}
        />
      )}
      <CracUnits cooling={cooling} />
      <PduStrips racks={racks} pdus={pdus} arMode={arMode} />
      <PduPsuCables racks={racks} pdus={pdus} />

      <TorSwitch position={[5.5, 0.95, -1.2]} label="MDF / Spine" ports={48} />
      <TorSwitch position={[5.5, 1.25, -1.2]} label="Leaf / Agg" ports={36} />
      <PatchPanel position={[4.15, 1.05, -1.2]} ports={24} />
      {/* Per-rack ToR — audit residual: ToR belongs in each rack, not only the MDF corner. */}
      {racks.map((rack, i) => {
        const { x, z } = rackPosition(i)
        return (
          <TorSwitch
            key={`tor-${rack.id}`}
            position={[x, RACK_H + 0.18, z]}
            label={`ToR · ${rack.name || rack.id}`}
            ports={24}
          />
        )
      })}

      <Bvh firstHitOnly>
        {racks.map((rack, i) => (
          <RackMesh
            key={rack.id}
            rack={rack}
            index={i}
            servers={serversByRack[rack.id] || []}
            selectedId={selectedId}
            expandedRack={expandedRack}
            onSelectRack={onSelectRack}
            onSelectServer={onSelectServer}
            onOpenBmc={onOpenBmc}
            physicsEnabled={physicsEnabled}
            animBoost={animBoost}
            arMode={arMode}
            arThermalLevel={arThermalLevel}
          />
        ))}
      </Bvh>

      {cables.map((c) => (
        <InteractiveCable
          key={c.id}
          from={c.from}
          to={c.to}
          loose={c.loose}
          traffic={animBoost > 0 && !c.loose}
          cableId={c.cableId || c.id}
          serverId={c.serverId}
          cableType={c.cableType || 'Cat6A'}
          bendRadiusMm={c.bendRadiusMm}
          label={c.label}
          onUnplug={c.interactive ? (payload) => onUnplugCable?.(payload) : undefined}
          onPlug={c.interactive ? (payload) => onPlugCable?.(payload) : undefined}
          arNetwork={arMode === 'network'}
        />
      ))}

      {physicsEnabled && <CablePhysicsBits anchors={cableAnchors} />}

      <ContactShadows position={[0, 0.01, 0]} opacity={0.45} scale={22} blur={2.2} far={8} />
      {!walkMode && (
        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.08}
          maxPolarAngle={Math.PI * 0.48}
          minDistance={3}
          maxDistance={18}
          target={[1, 0.8, -1.5]}
        />
      )}
    </>
  )
}

/** Fading coach mark shown once when the player takes control (Steam-style onboarding toast). */
function CoachMark({ show }) {
  if (!show) return null
  return (
    <div className="dc-3d-coachmark" key="coach">
      Day-one tour complete · <kbd>WASD</kbd> walk · mouse look · <kbd>E</kbd> interact · <kbd>V</kbd> AR · <kbd>Esc</kbd> menu
    </div>
  )
}

/** On-screen D-pad for coarse-pointer (phone/tablet) walk — residual polish after gamepad. */
export function TouchWalkPad({ active, onRequestGyro }) {
  useEffect(() => () => clearTouchHold(), [])
  if (!active) return null
  const hold = (key) => (e) => {
    e.preventDefault()
    setTouchHold({ [key]: true })
  }
  const release = (key) => (e) => {
    e.preventDefault()
    setTouchHold({ [key]: false })
  }
  const btn = (key, label, className) => (
    <button
      key={key}
      type="button"
      className={`dc-3d-touch-btn ${className || ''}`}
      aria-label={label}
      onPointerDown={hold(key)}
      onPointerUp={release(key)}
      onPointerLeave={release(key)}
      onContextMenu={(e) => e.preventDefault()}
    >
      {label}
    </button>
  )
  return (
    <div className="dc-3d-touch-pad" data-testid="dc-touch-pad" aria-label="Touch walk controls">
      <div className="dc-3d-touch-dpad">
        <span />
        {btn('forward', '▲', 'dc-3d-touch-n')}
        <span />
        {btn('left', '◀', 'dc-3d-touch-w')}
        <span className="dc-3d-touch-hub" />
        {btn('right', '▶', 'dc-3d-touch-e')}
        <span />
        {btn('back', '▼', 'dc-3d-touch-s')}
        <span />
      </div>
      <div className="dc-3d-touch-actions">
        {btn('sprint', 'Sprint', 'dc-3d-touch-sprint')}
        {btn('jump', 'Jump', 'dc-3d-touch-jump')}
        {onRequestGyro && (
          <button
            type="button"
            className="dc-3d-touch-btn dc-3d-touch-gyro"
            aria-label="Enable gyroscope look"
            onClick={(e) => { e.preventDefault(); onRequestGyro?.() }}
          >
            Gyro
          </button>
        )}
      </div>
      <div className="dc-3d-touch-look" aria-label="Look stick">
        <span />
        {btn('lookUp', '⌃', 'dc-3d-touch-look-n')}
        <span />
        {btn('lookLeft', '‹', 'dc-3d-touch-look-w')}
        <span className="dc-3d-touch-hub" />
        {btn('lookRight', '›', 'dc-3d-touch-look-e')}
        <span />
        {btn('lookDown', '⌄', 'dc-3d-touch-look-s')}
        <span />
      </div>
    </div>
  )
}

/** Always-visible control strip — Steam Data Center players always see how to move. */
function ControlsHud({ walkMode, quality, onQuality }) {
  return (
    <div className="dc-3d-controls-hud" aria-label="3D controls">

      <span><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> move</span>
      <span>Mouse look{walkMode ? ' (click canvas)' : ''}</span>
      <span><kbd>Shift</kbd> sprint</span>
      <span><kbd>E</kbd> interact</span>
      <span><kbd>V</kbd> AR</span>
      <span><kbd>1</kbd>–<kbd>4</kbd> rooms</span>
      <span><kbd>Esc</kbd> menu</span>
      <label className="dc-3d-quality">
        Quality
        <select value={quality} onChange={(e) => onQuality?.(e.target.value)} aria-label="3D quality preset">
          <option value="low">Low</option>
          <option value="med">Med</option>
          <option value="high">High</option>
        </select>
      </label>
    </div>
  )
}

/** Diegetic DCIM peek card — mirrors field-tablet overview until drawer opens. */
function InspectPeek({ server, onOpenBmc, onClose }) {
  if (!server) return null
  const failed = Object.entries(server.components || {}).filter(([, v]) => v !== 'healthy')
  return (
    <div className="dc-3d-inspect-peek">
      <div className="dc-3d-inspect-peek-head">
        <strong>{server.hostname || server.id}</strong>
        <button type="button" className="dc-3d-inspect-close" onClick={onClose} aria-label="Close peek">×</button>
      </div>
      <div className="dc-3d-inspect-peek-body">
        <div>{server.vendor} {server.model} · {server.rack} U{server.u_slot}</div>
        <div>ST {server.service_tag || '—'} · {server.power_state} · {server.os || 'linux'}</div>
        {failed.length > 0 ? (
          <div className="dc-3d-np-bad">Faults: {failed.map(([k]) => k).join(', ')}</div>
        ) : (
          <div className="dc-3d-np-ok">All components healthy</div>
        )}
      </div>
      <div className="dc-3d-inspect-peek-actions">
        <span className="dc-muted">Field tablet open →</span>
        <button type="button" className="dc-btn-outline dc-btn-xs" onClick={() => onOpenBmc?.(server.id)}>BMC</button>
      </div>
    </div>
  )
}

const RADAR_PORTALS = [
  { id: 'loading-dock', x: -6.2, z: 0.2, color: '#f59e0b', hotkey: '1' },
  { id: 'reception', x: -5.2, z: 3.2, color: '#94a3b8', hotkey: '2' },
  { id: 'mdf', x: 5.8, z: 0.4, color: '#38bdf8', hotkey: '3' },
  { id: 'noc', x: 3.2, z: 3.4, color: '#a78bfa', hotkey: '4' },
]

/** Lightweight top-down radar tip — player dot + the four room-portal beacons,
 *  plus a "you are here" room label above the ring. */
function Minimap({ posRef, currentRoomLabel = 'Data Hall A', rackCount = 0 }) {
  const dotRef = useRef()
  useEffect(() => {
    let raf
    const tick = () => {
      if (dotRef.current && posRef?.current) {
        const px = 50 + Math.max(-1, Math.min(1, posRef.current.x / 9)) * 42
        const pz = 50 + Math.max(-1, Math.min(1, posRef.current.z / 7)) * 42
        dotRef.current.style.left = `${px}%`
        dotRef.current.style.top = `${pz}%`
        // Heading was already tracked in posRef.yaw and simply never drawn, so the
        // dot could not tell you which way you were facing. World yaw 0 faces -Z
        // (up on the map), and screen rotation runs the opposite way from world yaw.
        dotRef.current.style.transform =
          `translate(-50%, -50%) rotate(${-(posRef.current.yaw || 0) * (180 / Math.PI)}deg)`
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [posRef])
  // Same layout function the 3D hall uses, so the map cannot drift from the world.
  const rackDots = useMemo(
    () => Array.from({ length: rackCount }, (_, i) => ({ i, ...rackPosition(i) })),
    [rackCount],
  )
  return (
    <div className="dc-3d-minimap" aria-hidden>
      <div className="dc-3d-minimap-label">{currentRoomLabel}</div>
      <div className="dc-3d-minimap-ring" />
      {/* Hall walls — without them the ring is an abstract circle with no geometry
          to orient against. Matches the WalkController soft bounds. */}
      <div className="dc-3d-minimap-walls" />
      {rackDots.map((r) => (
        <span
          key={`mm-rack-${r.i}`}
          className="dc-3d-minimap-rack"
          style={{
            left: `${50 + Math.max(-1, Math.min(1, r.x / 9)) * 42}%`,
            top: `${50 + Math.max(-1, Math.min(1, r.z / 7)) * 42}%`,
          }}
        />
      ))}
      {RADAR_PORTALS.map((p) => (
        <span
          key={p.id}
          className="dc-3d-minimap-dot"
          style={{
            left: `${50 + Math.max(-1, Math.min(1, p.x / 9)) * 42}%`,
            top: `${50 + Math.max(-1, Math.min(1, p.z / 7)) * 42}%`,
            background: p.color,
            boxShadow: `0 0 6px ${p.color}`,
          }}
          title={p.id}
        />
      ))}
      <span ref={dotRef} className="dc-3d-minimap-player" />
    </div>
  )
}

/** Current AR overlay mode chip — cycled with `V` (Off / Thermal / Power / Network). */
function ArModeChip({ mode }) {
  return (
    <div className={`dc-3d-ar-chip dc-3d-ar-chip-${mode}`}>
      <span>AR</span> {AR_MODE_LABELS[mode] || 'Off'}
    </div>
  )
}

/** Bottom "field kit" HUD — Badge · ESD · Cart · BMC quick actions. */
function FieldKitHud({
  badgedIn, onBadgeIn, esdOn, onToggleEsd, cartOpen, onToggleCart, onOpenBmc, esdToast,
}) {
  return (
    <div className="dc-3d-fieldkit">
      <div className="dc-3d-fieldkit-row">
        <button
          type="button"
          className={`dc-3d-kit-btn ${badgedIn ? 'dc-3d-kit-btn-done' : ''}`}
          onClick={() => onBadgeIn?.()}
          title="Badge in at the mantrap"
        >
          Badge{badgedIn ? ' ✓' : ''}
        </button>
        <button
          type="button"
          className={`dc-3d-kit-btn ${esdOn ? 'dc-3d-kit-btn-on' : 'dc-3d-kit-btn-off'}`}
          onClick={onToggleEsd}
          title="ESD wrist strap"
        >
          ESD {esdOn ? 'On' : 'Off'}
        </button>
        <button
          type="button"
          className={`dc-3d-kit-btn ${cartOpen ? 'dc-3d-kit-btn-on' : ''}`}
          onClick={onToggleCart}
          title="Parts cart"
        >
          Cart
        </button>
        <button type="button" className="dc-3d-kit-btn" onClick={() => onOpenBmc?.()} title="Open BMC console">
          BMC
        </button>
      </div>
      {esdToast && <div className="dc-3d-kit-toast">Wrist strap recommended</div>}
    </div>
  )
}

/** Full controls reference. Previously the only onboarding was a 5.2s toast shown
 *  once per mount, with no way to ever re-read it. */
export const CONTROL_BINDINGS = [
  { keys: ['W', 'A', 'S', 'D'], action: 'Move (arrow keys also work)', rebind: ['forward', 'left', 'back', 'right'] },
  { keys: ['Mouse'], action: 'Look — click the hall once to capture the pointer' },
  { keys: ['Shift'], action: 'Sprint (either shift)', rebind: ['sprint'] },
  { keys: ['Space'], action: 'Jump', rebind: ['jump'] },
  { keys: ['Ctrl', 'C'], action: 'Crouch — get under the cable tray / read low U', rebind: ['crouch'] },
  { keys: ['E'], action: 'Interact with whatever the crosshair names', rebind: ['interact'] },
  { keys: ['V'], action: 'Cycle AR overlay — Off / Thermal / Power / Network' },
  { keys: ['1', '2', '3', '4'], action: 'Fast-travel: Dock · Reception · MDF · NOC' },
  { keys: ['Esc'], action: 'Pause menu (releases the mouse)' },
]

function codeLabel(code) {
  if (!code) return '?'
  if (code.startsWith('Key')) return code.slice(3)
  if (code.startsWith('Digit')) return code.slice(5)
  if (code === 'Space') return 'Space'
  if (code.startsWith('Shift')) return 'Shift'
  if (code.startsWith('Control')) return 'Ctrl'
  if (code.startsWith('Arrow')) return code.replace('Arrow', '')
  return code
}

function ControlsPanel({ look, onLookChange, binds = DEFAULT_BINDS, onBindsChange }) {
  const [capturing, setCapturing] = useState(null)
  useEffect(() => {
    if (!capturing) return undefined
    const onKey = (e) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.code === 'Escape') { setCapturing(null); return }
      const next = { ...binds, [capturing]: e.code }
      onBindsChange?.(next)
      setCapturing(null)
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [capturing, binds, onBindsChange])

  return (
    <div className="dc-3d-controls-panel">
      <table className="dc-3d-controls-table">
        <tbody>
          {CONTROL_BINDINGS.map((b) => (
            <tr key={b.action}>
              <th scope="row">
                {(b.rebind || []).length
                  ? b.rebind.map((action) => (
                    <button
                      key={action}
                      type="button"
                      className={`dc-3d-rebind${capturing === action ? ' dc-3d-rebind-hot' : ''}`}
                      onClick={() => setCapturing(action)}
                      title={`Click then press a key to rebind ${action}`}
                    >
                      <kbd>{capturing === action ? '…' : codeLabel(binds[action])}</kbd>
                    </button>
                  ))
                  : b.keys.map((k) => <kbd key={k}>{k}</kbd>)}
              </th>
              <td>{b.action}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        type="button"
        className="dc-3d-menu-btn"
        onClick={() => onBindsChange?.({ ...DEFAULT_BINDS })}
      >
        Reset keybinds
      </button>
      <label className="dc-3d-controls-row" htmlFor="dc-3d-sens">
        <span>Mouse sensitivity</span>
        <input
          id="dc-3d-sens"
          type="range"
          min="0.0004"
          max="0.012"
          step="0.0002"
          value={look.sensitivity}
          onChange={(e) => onLookChange({ ...look, sensitivity: Number(e.target.value) })}
        />
        <output>{(look.sensitivity * 1000).toFixed(1)}</output>
      </label>
      <label className="dc-3d-controls-row" htmlFor="dc-3d-yscale">
        <span>Vertical scale</span>
        <input
          id="dc-3d-yscale"
          type="range"
          min="0.25"
          max="2.5"
          step="0.05"
          value={look.yScale}
          onChange={(e) => onLookChange({ ...look, yScale: Number(e.target.value) })}
        />
        <output>{look.yScale.toFixed(2)}×</output>
      </label>
      <label className="dc-3d-controls-row" htmlFor="dc-3d-inverty">
        <span>Invert Y axis</span>
        <input
          id="dc-3d-inverty"
          type="checkbox"
          checked={look.invertY}
          onChange={(e) => onLookChange({ ...look, invertY: e.target.checked })}
        />
      </label>
    </div>
  )
}

/** Esc-triggered pause menu — accessible exit from pointer-locked immersive mode.
 *  Doubles as the click-to-resume surface: the browser releases the pointer on Esc
 *  and only a user gesture can take it back, so "Resume walking" is that gesture. */
function ImmersiveMenu({
  open, onResume, onExitImmersive, onExitTo2D, onPhoto, badgedIn,
  look = DEFAULT_LOOK, onLookChange, binds = DEFAULT_BINDS, onBindsChange,
}) {
  const [tab, setTab] = useState('menu')
  // Always reopen on the menu tab — landing in Controls after an emergency Esc
  // would bury the Resume button.
  useEffect(() => { if (open) setTab('menu') }, [open])
  if (!open) return null
  return (
    <div className="dc-3d-menu-backdrop" onClick={onResume}>
      <div className="dc-3d-menu" onClick={(e) => e.stopPropagation()}>
        <div className="dc-3d-menu-title">Paused</div>
        {tab === 'controls' ? (
          <>
            <ControlsPanel
              look={look}
              onLookChange={onLookChange}
              binds={binds}
              onBindsChange={onBindsChange}
            />
            <button type="button" className="dc-3d-menu-btn" onClick={() => setTab('menu')}>
              Back
            </button>
          </>
        ) : (
          <>
            <button type="button" className="dc-3d-menu-btn dc-3d-menu-btn-primary" onClick={onResume}>
              Resume walking
            </button>
            <button type="button" className="dc-3d-menu-btn" onClick={() => setTab('controls')}>
              Controls &amp; sensitivity
            </button>
            {onPhoto && (
              <button type="button" className="dc-3d-menu-btn" onClick={onPhoto}>
                Photo mode — save PNG
              </button>
            )}
            <button type="button" className="dc-3d-menu-btn" onClick={onExitImmersive}>
              Exit immersive mode
            </button>
            <button type="button" className="dc-3d-menu-btn" onClick={onExitTo2D}>
              Switch to 2D floor
            </button>
          </>
        )}
        <div className="dc-3d-menu-hint">
          {badgedIn ? 'Badged in' : 'Not badged in'} · 1 Dock · 2 Reception · 3 MDF · 4 NOC · V AR
        </div>
      </div>
    </div>
  )
}

/** Explicit "click to play" gesture surface. Replaces the illegal programmatic
 *  auto-lock: Chrome throws SecurityError for requestPointerLock() without a user
 *  gesture, which used to be swallowed, leaving walk mode with no mouse look and
 *  no explanation. */
function ClickToPlay({ show, onEngage }) {
  if (!show) return null
  return (
    <button type="button" className="dc-3d-clicktoplay" onClick={onEngage}>
      <span className="dc-3d-clicktoplay-title">Click to capture mouse look</span>
      <span className="dc-3d-clicktoplay-sub">WASD to move · Esc for the pause menu</span>
    </button>
  )
}

function LoadingFallback() {
  return (
    <div className="dc-3d-loading">
      <div className="dc-3d-loading-spin" />
      Loading Lab Environment 3D twin…
    </div>
  )
}

const ROOM_HOTKEYS = {
  Digit1: { id: 'loading-dock', name: 'Staging / dock' },
  Digit2: { id: 'reception', name: 'Reception' },
  Digit3: { id: 'mdf', name: 'MDF' },
  Digit4: { id: 'noc', name: 'NOC' },
}

export default function DatacenterTwin3D({
  racks = [],
  serversByRack = {},
  network,
  cooling = [],
  pdus = [],
  tickets = [],
  access = null,
  objective = '',
  audioControl = null,
  onBadgeIn,
  onEnterRoom,
  onImmersiveChange,
  onExitTo2D,
  selectedServerId,
  expandedRack,
  onSelectServer,
  onSelectRack,
  onOpenBmc,
  onUnplugCable,
  onPlugCable,
  nocMetrics = {},
  currentRoomLabel = 'Data Hall A',
}) {
  const [physicsEnabled, setPhysicsEnabled] = useState(true)
  const [physicsNote, setPhysicsNote] = useState(null)
  const [animBoost, setAnimBoost] = useState(1)
  const [intro, setIntro] = useState(true)
  const [walkMode, setWalkMode] = useState(false)
  // FPS is written straight into a DOM text node — see fpsElRef usage below.
  const fpsElRef = useRef(null)
  const fpsLodSamples = useRef({ low: 0, high: 0, active: false })
  const [fpsLod, setFpsLod] = useState(false)
  const setFps = useMemo(() => (n) => {
    if (fpsElRef.current) {
      fpsElRef.current.textContent = fpsLodSamples.current.active ? `${n}·LOD` : String(n)
    }
    const next = nextFpsLodState(fpsLodSamples.current, n)
    fpsLodSamples.current = next
    setFpsLod((cur) => (cur === next.active ? cur : next.active))
  }, [])
  // Steam-class default: start immersive (game view) — heavy chrome stays collapsed.
  const [immersive, setImmersive] = useState(true)
  const [menuOpen, setMenuOpen] = useState(false)
  const [showCoach, setShowCoach] = useState(false)
  const [quality, setQuality] = useState(() => {
    try {
      const q = window.localStorage?.getItem('fixitlab.dc.quality')
      if (q === 'low' || q === 'med' || q === 'high') return q
    } catch { /* ignore */ }
    return 'med'
  })
  const [coarsePointer, setCoarsePointer] = useState(() => prefersCoarsePointer())
  const [gyroOn, setGyroOn] = useState(false)
  useEffect(() => {
    const mq = typeof window !== 'undefined' ? window.matchMedia('(pointer: coarse)') : null
    if (!mq) return undefined
    const sync = () => setCoarsePointer(!!mq.matches)
    sync()
    mq.addEventListener?.('change', sync)
    return () => mq.removeEventListener?.('change', sync)
  }, [])
  // AR HUD overlay cycle (Off / Thermal / Power / Network) — key `V`.
  const [arModeIdx, setArModeIdx] = useState(0)
  // Field kit HUD state — ESD wrist-strap toggle + cosmetic parts-cart marker.
  const [esdOn, setEsdOn] = useState(true)
  const [cartOpen, setCartOpen] = useState(false)
  const [esdToast, setEsdToast] = useState(false)
  // Mouse-look preferences (sensitivity / vertical scale / invert-Y) persist per
  // browser — an accessibility setting nobody wants to redial every session.
  const [look, setLook] = useState(() => readLookSettings(
    typeof window !== 'undefined' ? window.localStorage : null,
  ))
  const [binds, setBinds] = useState(() => readBinds(
    typeof window !== 'undefined' ? window.localStorage : null,
  ))
  // Authoritative pointer-lock state, fed by pointerlockchange/error. Drives both
  // the click-to-play overlay and the "E does nothing because you're unlocked" prompt.
  const [pointerLocked, setPointerLocked] = useState(false)
  const [interactPrompt, setInteractPrompt] = useState(null)
  const autoWalkStarted = useRef(false)
  const coachShown = useRef(false)
  const posRef = useRef({ x: SAFE_SPAWN.x, z: SAFE_SPAWN.z, yaw: 0 })

  // Restore where the player was standing in THIS room, validated against the
  // colliders the current rack layout produces — a scenario with a different rack
  // count would otherwise respawn them inside a cabinet.
  const spawn = useMemo(() => sanitizeSpawn(
    readPlayerPos(
      typeof window !== 'undefined' ? window.localStorage : null,
      access?.session_id,
      currentRoomLabel,
    ),
    buildHallColliders({
      rackCount: racks.length,
      cracCount: Math.min(4, cooling.length),
      doorOpen: true,
    }),
  ), [access?.session_id, currentRoomLabel, racks.length, cooling.length])

  const commitPos = useCallback((p) => {
    writePlayerPos(
      typeof window !== 'undefined' ? window.localStorage : null,
      access?.session_id,
      currentRoomLabel,
      p,
    )
  }, [access?.session_id, currentRoomLabel])

  const prevSelectedRef = useRef(null)
  const canvasElRef = useRef(null)

  const updateLook = (next) => {
    setLook(next)
    writeLookSettings(typeof window !== 'undefined' ? window.localStorage : null, next)
  }

  const updateBinds = (next) => {
    setBinds(next)
    writeBinds(typeof window !== 'undefined' ? window.localStorage : null, next)
  }

  const takePhoto = useCallback(() => {
    captureCanvasPng(canvasElRef.current, { filename: `fixitlab-dc-${Date.now()}.png` })
  }, [])

  // Called from a real user gesture (menu Resume / click-to-play), which is the
  // only context in which requestPointerLock is legal.
  const engagePointerLock = () => {
    try { canvasElRef.current?.requestPointerLock?.() } catch { /* gesture policy */ }
  }

  const arMode = AR_MODES[arModeIdx] || 'off'

  const badgedIn = useMemo(() => {
    const ev = access?.events || []
    return ev.some((e) => (e.type || '') === 'allow' || /ALLOW|badge/i.test(e.message || ''))
  }, [access])

  // Brief, non-blocking amber toast when a server tablet is opened without ESD protection.
  useEffect(() => {
    if (selectedServerId && selectedServerId !== prevSelectedRef.current && !esdOn) {
      setEsdToast(true)
      prevSelectedRef.current = selectedServerId
      const id = setTimeout(() => setEsdToast(false), 3200)
      return () => clearTimeout(id)
    }
    prevSelectedRef.current = selectedServerId
    return undefined
  }, [selectedServerId, esdOn])

  useEffect(() => {
    if (!intro || walkMode) return undefined
    // Shorter cinematic — get into WASD walk faster (game, not flyover).
    const id = setTimeout(() => setIntro(false), 2800)
    return () => clearTimeout(id)
  }, [intro, walkMode])

  // After cinematic enter, drop straight into first-person Walk (Steam FPS feel).
  // Badge-in still opens the mantrap door — it no longer blocks movement.
  useEffect(() => {
    if (intro || walkMode || !immersive || autoWalkStarted.current) return undefined
    const id = setTimeout(() => {
      autoWalkStarted.current = true
      setWalkMode(true)
    }, 180)
    return () => clearTimeout(id)
  }, [intro, walkMode, immersive])

  const inGame = immersive && walkMode

  useEffect(() => {
    if (!gyroOn || !inGame) return undefined
    const prev = { current: null }
    const onOrient = (e) => {
      gyroLookRef.current = deviceOrientationLookDelta(e, prev)
    }
    window.addEventListener('deviceorientation', onOrient)
    return () => {
      window.removeEventListener('deviceorientation', onOrient)
      gyroLookRef.current = { dx: 0, dy: 0 }
    }
  }, [gyroOn, inGame])

  const qualityCfg = useMemo(() => {
    let cfg
    if (quality === 'low') {
      cfg = { dpr: [1, 1], dust: 40, shadows: false, anim: 0.65, shadowMap: 1024, bloom: false, ssao: false, vignette: false, noise: false }
    } else if (quality === 'high') {
      cfg = { dpr: [1, 2], dust: 160, shadows: true, anim: 1, shadowMap: 2048, bloom: true, ssao: true, vignette: true, noise: true }
    } else {
      cfg = { dpr: [1, 1.5], dust: 90, shadows: true, anim: 1, shadowMap: 1024, bloom: true, ssao: false, vignette: true, noise: false }
    }
    return applyFpsLodCfg(cfg, fpsLod)
  }, [quality, fpsLod])

  // Rapier off while FPS LOD is active (particles already cut via qualityCfg).
  const effectivePhysics = physicsEnabled && !fpsLod

  const selectedServerIdRef = useRef(selectedServerId)
  selectedServerIdRef.current = selectedServerId

  // Opening the field tablet must release the mouse without opening the pause menu,
  // otherwise tablet + "Paused" stack and Walk/chrome feel dead.
  useEffect(() => {
    if (!selectedServerId) return undefined
    suppressPointerUnlockPause(800)
    try { document.exitPointerLock?.() } catch { /* */ }
    setMenuOpen(false)
    return undefined
  }, [selectedServerId])

  const selectedServer = useMemo(() => {
    if (!selectedServerId) return null
    for (const list of Object.values(serversByRack || {})) {
      const hit = (list || []).find((s) => s.id === selectedServerId)
      if (hit) return hit
    }
    return null
  }, [selectedServerId, serversByRack])

  const setQualityPersist = (q) => {
    setQuality(q)
    try { window.localStorage?.setItem('fixitlab.dc.quality', q) } catch { /* ignore */ }
  }

  useEffect(() => { onImmersiveChange?.(immersive) }, [immersive, onImmersiveChange])

  // Brief fading coach mark the first time the player takes control.
  useEffect(() => {
    if (!inGame || coachShown.current) return undefined
    coachShown.current = true
    setShowCoach(true)
    const id = setTimeout(() => setShowCoach(false), 5200)
    return () => clearTimeout(id)
  }, [inGame])

  const exitImmersive = () => {
    setMenuOpen(false)
    setImmersive(false)
    setWalkMode(false)
    try { document.exitPointerLock?.() } catch { /* */ }
  }

  const exitTo2D = () => {
    setMenuOpen(false)
    setWalkMode(false)
    try { document.exitPointerLock?.() } catch { /* */ }
    onExitTo2D?.()
  }

  // Resume = the user gesture that takes the pointer back. Esc released it (the
  // browser does that itself, we cannot prevent it), so closing the menu without
  // re-locking is what used to strand the player with live WASD and a dead mouse.
  const resumeWalking = () => {
    setMenuOpen(false)
    if (inGame && !selectedServerIdRef.current) engagePointerLock()
  }

  // Losing the pointer means losing mouse look, so surface the pause menu rather
  // than leaving a half-controllable player. Deliberately one-directional: this
  // only ever OPENS the menu. Esc below is also open-only, and only `resumeWalking`
  // closes it — otherwise the unlock-triggered open and an Esc toggle race each
  // other and the menu reopens itself on every unlock.
  // Cable drag + field tablet unlock intentionally suppress this (see DcCableSystem).
  const handlePointerLockChange = useMemo(() => (locked) => {
    setPointerLocked(locked)
    if (!locked) {
      if (isPointerUnlockPauseSuppressed() || selectedServerIdRef.current) return
      setMenuOpen((m) => m || true)
    }
  }, [])

  // In-world room hotkeys (1-4) + AR overlay cycle (V) + Esc pause menu — no tab bar needed while immersive.
  useEffect(() => {
    if (!immersive || intro) return undefined
    const handler = (e) => {
      if (e.code === 'Escape') {
        // Open-only. The browser has already released the pointer by the time we
        // see this; the menu is the click-to-resume surface.
        // Field tablet owns Esc/chrome while open — don't bury it under Paused.
        if (selectedServerIdRef.current) return
        setMenuOpen(true)
        return
      }
      if (menuOpen) return
      if (e.code === 'KeyV') {
        setArModeIdx((i) => (i + 1) % AR_MODES.length)
        return
      }
      const room = ROOM_HOTKEYS[e.code]
      if (room) onEnterRoom?.(room)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [immersive, intro, menuOpen, onEnterRoom])

  return (
    <div className={`dc-3d-root dc-3d-root-enter${immersive ? ' dc-3d-immersive' : ''}`}>
      <div className="dc-3d-toolbar">
        <span className="dc-twin-title">3D Lab Twin · Walk mode</span>
        <label className="dc-3d-toggle">
          <input
            type="checkbox"
            checked={immersive}
            onChange={(e) => setImmersive(e.target.checked)}
          />
          Immersive
        </label>
        <label className="dc-3d-toggle">
          <input
            type="checkbox"
            checked={physicsEnabled}
            onChange={(e) => setPhysicsEnabled(e.target.checked)}
            disabled={fpsLod}
          />
          Rapier{fpsLod ? ' (LOD)' : ''}
        </label>
        <label className="dc-3d-toggle">
          <input
            type="checkbox"
            checked={animBoost > 0}
            onChange={(e) => setAnimBoost(e.target.checked ? 1 : 0)}
          />
          Motions
        </label>
        <label className="dc-3d-toggle">
          <input
            type="checkbox"
            checked={walkMode}
            onChange={(e) => {
              const on = e.target.checked
              setWalkMode(on)
              if (on) setIntro(false)
            }}
          />
          Walk (WASD)
        </label>
        <button type="button" className="dc-btn-outline dc-btn-xs" onClick={() => { setWalkMode(false); setIntro(true) }}>
          Replay enter
        </button>
        {!badgedIn && (
          <button type="button" className="dc-btn-outline dc-btn-xs" onClick={() => onBadgeIn?.()}>
            Badge-in (open door)
          </button>
        )}
        <span className="dc-muted">
          {/* Ref-driven text node: setState here re-rendered <Canvas>'s children,
              so the entire SceneContent tree reconciled once per second. */}
          ~<span ref={fpsElRef}>—</span> FPS · {inGame
            ? (pointerLocked
              ? 'WASD · Shift sprint · E interact · Esc menu'
              : 'click the hall to capture mouse look')
            : walkMode
              ? 'WASD ready'
              : 'cinematic enter → auto Walk'}
        </span>
      </div>
      {!walkMode && !intro && !immersive && (
        <div className="dc-3d-immersion-hint">
          Tip: enable <strong>Immersive</strong> + <strong>Walk</strong> for first-person hall — ticket beacons mark DCOps faults on racks
        </div>
      )}
      <div className="dc-3d-canvas-wrap">
        {inGame && <div className="dc-3d-aisle-fog" aria-hidden />}
        {inGame && <div className="dc-3d-hud-crosshair" aria-hidden />}
        <ControlsHud walkMode={walkMode} quality={quality} onQuality={setQualityPersist} />
        {inGame && (
          <TouchWalkPad
            active={coarsePointer}
            onRequestGyro={async () => {
              const ok = await requestGyroPermission()
              setGyroOn(!!ok)
            }}
          />
        )}
        {physicsNote && (
          <div className="dc-3d-physics-note" role="status">
            Physics off ({physicsNote}) — hall still walkable
          </div>
        )}
        {selectedServer && (
          <InspectPeek
            server={selectedServer}
            onOpenBmc={onOpenBmc}
            onClose={() => onSelectServer?.(null)}
          />
        )}
        {inGame && (
          <div className="dc-3d-hud">
            {objective && <div className="dc-3d-hud-objective"><strong>Objective</strong> · {objective}</div>}
            <div>WASD move · mouse look · Shift sprint · E interact · click server for DCIM tablet</div>
            <div>1 Dock · 2 Reception · 3 MDF · 4 NOC · V AR overlay · Esc menu</div>
          </div>
        )}
        {inGame && (
          <Minimap posRef={posRef} currentRoomLabel={currentRoomLabel} rackCount={racks.length} />
        )}
        {inGame && <CoachMark show={showCoach} />}
        {inGame && pointerLocked && !menuOpen && (
          <InteractPrompt prompt={interactPrompt} interactKey={codeLabel(binds.interact)} />
        )}
        <ClickToPlay show={inGame && !pointerLocked && !menuOpen && !selectedServerId} onEngage={engagePointerLock} />
        {immersive && !intro && <ArModeChip mode={arMode} />}
        {immersive && !intro && (
          <FieldKitHud
            badgedIn={badgedIn}
            onBadgeIn={() => onBadgeIn?.()}
            esdOn={esdOn}
            onToggleEsd={() => setEsdOn((v) => !v)}
            cartOpen={cartOpen}
            onToggleCart={() => setCartOpen((v) => !v)}
            onOpenBmc={() => onOpenBmc?.()}
            esdToast={esdToast}
          />
        )}
        {immersive && (
          <div className="dc-3d-pinned-controls">
            {isValidElement(audioControl) ? cloneElement(audioControl, { posRef }) : audioControl}
            <button
              type="button"
              className="dc-3d-exit-btn"
              onClick={exitImmersive}
              title="Exit immersive mode — restore the full toolbar"
            >
              Exit immersive
            </button>
          </div>
        )}
        <ImmersiveMenu
          open={menuOpen}
          badgedIn={badgedIn}
          look={look}
          onLookChange={updateLook}
          binds={binds}
          onBindsChange={updateBinds}
          onPhoto={takePhoto}
          onResume={resumeWalking}
          onExitImmersive={exitImmersive}
          onExitTo2D={exitTo2D}
        />
        <Suspense fallback={<LoadingFallback />}>
          <Canvas
            shadows={qualityCfg.shadows}
            dpr={qualityCfg.dpr}
            camera={{ position: [12, 9, 14], fov: inGame ? 70 : 42, near: 0.1, far: 80 }}
            gl={{
              antialias: quality !== 'low',
              powerPreference: 'high-performance',
              failIfMajorPerformanceCaveat: false,
            }}
            onCreated={({ gl }) => {
              // Kept so the root can request pointer lock from a user gesture
              // (menu Resume / click-to-play) without reaching into R3F internals.
              canvasElRef.current = gl.domElement
              try {
                gl.setClearColor('#070a10')
              } catch { /* ignore */ }
            }}
          >
            <PhysicsSafe
              onFail={(err) => {
                setPhysicsEnabled(false)
                setPhysicsNote(err?.message || 'WASM init failed')
              }}
              fallback={(
                <SceneContent
                  racks={racks}
                  serversByRack={serversByRack}
                  network={network}
                  cooling={cooling}
                  pdus={pdus}
                  selectedId={selectedServerId}
                  expandedRack={expandedRack}
                  onSelectServer={onSelectServer}
                  onSelectRack={onSelectRack}
                  onOpenBmc={onOpenBmc}
                  onUnplugCable={onUnplugCable}
                  onPlugCable={onPlugCable}
                  physicsEnabled={false}
                  onFps={setFps}
                  animBoost={animBoost * qualityCfg.anim}
                  intro={intro}
                  walkMode={walkMode}
                  walkPaused={menuOpen || !!selectedServerId}
                  look={look}
                  binds={binds}
                  pointerLocked={pointerLocked}
                  onPointerLockChange={handlePointerLockChange}
                  onInteractPrompt={setInteractPrompt}
                  posRef={posRef}
                  spawn={spawn}
                  onPosCommit={commitPos}
                  tickets={tickets}
                  doorOpen={badgedIn}
                  onEnterRoom={onEnterRoom}
                  arMode={arMode}
                  badgedIn={badgedIn}
                  onBadgeIn={onBadgeIn}
                  nocMetrics={nocMetrics}
                  dustCount={qualityCfg.dust}
                  shadowMapSize={qualityCfg.shadowMap}
                />
              )}
            >
              {effectivePhysics ? (
                <Suspense fallback={null}>
                  <Physics gravity={[0, -9.81, 0]} colliders={false} paused={!effectivePhysics}>
                    <SceneContent
                      racks={racks}
                      serversByRack={serversByRack}
                      network={network}
                      cooling={cooling}
                      pdus={pdus}
                      selectedId={selectedServerId}
                      expandedRack={expandedRack}
                      onSelectServer={onSelectServer}
                      onSelectRack={onSelectRack}
                      onOpenBmc={onOpenBmc}
                      onUnplugCable={onUnplugCable}
                      onPlugCable={onPlugCable}
                      physicsEnabled={effectivePhysics}
                      onFps={setFps}
                      animBoost={animBoost * qualityCfg.anim}
                      intro={intro}
                      walkMode={walkMode}
                      walkPaused={menuOpen || !!selectedServerId}
                      look={look}
                      binds={binds}
                      pointerLocked={pointerLocked}
                      onPointerLockChange={handlePointerLockChange}
                      onInteractPrompt={setInteractPrompt}
                      posRef={posRef}
                      spawn={spawn}
                      onPosCommit={commitPos}
                      tickets={tickets}
                      doorOpen={badgedIn}
                      onEnterRoom={onEnterRoom}
                      arMode={arMode}
                      badgedIn={badgedIn}
                      onBadgeIn={onBadgeIn}
                      nocMetrics={nocMetrics}
                      dustCount={qualityCfg.dust}
                  shadowMapSize={qualityCfg.shadowMap}
                    />
                  </Physics>
                </Suspense>
              ) : (
                <SceneContent
                  racks={racks}
                  serversByRack={serversByRack}
                  network={network}
                  cooling={cooling}
                  pdus={pdus}
                  selectedId={selectedServerId}
                  expandedRack={expandedRack}
                  onSelectServer={onSelectServer}
                  onSelectRack={onSelectRack}
                  onOpenBmc={onOpenBmc}
                  onUnplugCable={onUnplugCable}
                  onPlugCable={onPlugCable}
                  physicsEnabled={false}
                  onFps={setFps}
                  animBoost={animBoost * qualityCfg.anim}
                  intro={intro}
                  walkMode={walkMode}
                  walkPaused={menuOpen || !!selectedServerId}
                  look={look}
                  binds={binds}
                  pointerLocked={pointerLocked}
                  onPointerLockChange={handlePointerLockChange}
                  onInteractPrompt={setInteractPrompt}
                  posRef={posRef}
                  spawn={spawn}
                  onPosCommit={commitPos}
                  tickets={tickets}
                  doorOpen={badgedIn}
                  onEnterRoom={onEnterRoom}
                  arMode={arMode}
                  badgedIn={badgedIn}
                  onBadgeIn={onBadgeIn}
                  nocMetrics={nocMetrics}
                  dustCount={qualityCfg.dust}
                  shadowMapSize={qualityCfg.shadowMap}
                />
              )}
            </PhysicsSafe>
            {(qualityCfg.bloom || qualityCfg.ssao || qualityCfg.vignette || qualityCfg.noise) && (
              <EffectComposer multisampling={0} enableNormalPass={qualityCfg.ssao}>
                {qualityCfg.bloom && (
                  <Bloom luminanceThreshold={0.82} intensity={0.55} mipmapBlur />
                )}
                {qualityCfg.ssao && (
                  <SSAO
                    samples={12}
                    radius={0.18}
                    intensity={25}
                    luminanceInfluence={0.45}
                    worldDistanceThreshold={24}
                    worldDistanceFalloff={8}
                    worldProximityThreshold={0.6}
                    worldProximityFalloff={0.2}
                  />
                )}
                {qualityCfg.vignette && (
                  <Vignette offset={0.28} darkness={0.55} />
                )}
                {qualityCfg.noise && (
                  <Noise opacity={0.035} premultiply />
                )}
              </EffectComposer>
            )}
          </Canvas>
        </Suspense>
      </div>
    </div>
  )
}
