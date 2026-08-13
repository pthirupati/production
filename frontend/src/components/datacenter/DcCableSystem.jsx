/**
 * Interactive plant cabling for the 3D twin:
 * RJ45/DAC/QSFP connectors, sagging tubes, drag-to-unplug + snap-to-plug.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import { DistanceCullingHtml } from './DcLod'
import { RigidBody, BallCollider } from '@react-three/rapier'
import * as THREE from 'three'

export function StatusLed({ position, failed, powered, warning = false, size = 0.018, boost = 1 }) {
  const mat = useRef()
  useFrame(({ clock }) => {
    if (!mat.current) return
    const t = clock.elapsedTime
    if (failed) {
      mat.current.emissiveIntensity = (0.35 + (Math.sin(t * 10) > 0 ? 0.65 : 0)) * boost
      mat.current.color.set('#ef4444')
      mat.current.emissive.set('#ef4444')
    } else if (warning) {
      mat.current.emissiveIntensity = (0.3 + (Math.sin(t * 6) > 0 ? 0.55 : 0.1)) * boost
      mat.current.color.set('#f59e0b')
      mat.current.emissive.set('#f59e0b')
    } else if (powered) {
      mat.current.emissiveIntensity = (0.55 + Math.sin(t * 2.2) * 0.12) * boost
      mat.current.color.set('#34d399')
      mat.current.emissive.set('#34d399')
    } else {
      mat.current.emissiveIntensity = 0.02 * boost
      mat.current.color.set('#475569')
      mat.current.emissive.set('#000000')
    }
  })
  return (
    <mesh position={position}>
      <sphereGeometry args={[size, 10, 10]} />
      <meshStandardMaterial ref={mat} color="#34d399" emissive="#34d399" toneMapped={false} />
    </mesh>
  )
}

function CableConnector({ color = '#e2e8f0', kind = 'RJ45' }) {
  const w = kind === 'QSFP' ? 0.038 : kind === 'LC' ? 0.022 : 0.028
  const h = kind === 'QSFP' ? 0.022 : 0.016
  const d = kind === 'QSFP' ? 0.055 : 0.042
  return (
    <group>
      <mesh castShadow>
        <boxGeometry args={[w, h, d]} />
        <meshStandardMaterial color={color} metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0, d * 0.42]}>
        <boxGeometry args={[w * 0.7, h * 0.55, 0.012]} />
        <meshStandardMaterial color="#0f172a" metalness={0.8} />
      </mesh>
      <mesh position={[0, 0, -d * 0.55]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.008, 0.011, 0.03, 8]} />
        <meshStandardMaterial color={kind === 'LC' ? '#22c55e' : '#f97316'} roughness={0.6} />
      </mesh>
    </group>
  )
}

function PortJack({ position, linked, activity, label, arNetwork = false }) {
  const glowRef = useRef()
  useFrame(({ clock }) => {
    if (!glowRef.current) return
    glowRef.current.material.opacity = arNetwork ? 0.35 + Math.sin(clock.elapsedTime * 2.6) * 0.15 : 0
  })
  return (
    <group position={position}>
      <mesh>
        <boxGeometry args={[0.04, 0.028, 0.03]} />
        <meshStandardMaterial color="#0f172a" metalness={0.4} roughness={0.5} />
      </mesh>
      <mesh position={[0, 0, 0.012]}>
        <boxGeometry args={[0.028, 0.016, 0.01]} />
        <meshStandardMaterial color="#1e293b" />
      </mesh>
      <StatusLed position={[0.018, 0.014, 0.016]} failed={false} powered={linked} warning={!linked} size={0.006} boost={arNetwork ? 1.7 : 1} />
      {activity && linked && (
        <StatusLed position={[-0.018, 0.014, 0.016]} failed={false} powered size={0.005} boost={arNetwork ? 1.7 : 1} />
      )}
      {arNetwork && (
        <mesh ref={glowRef} position={[0, 0, 0.02]}>
          <ringGeometry args={[0.026, 0.036, 16]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.3} depthWrite={false} side={THREE.DoubleSide} />
        </mesh>
      )}
      {label && (
        <DistanceCullingHtml position={[0, 0.045, 0]} center distanceFactor={14} style={{ pointerEvents: 'none' }}>
          <div className="dc-3d-chip dc-3d-chip-sm">{label}</div>
        </DistanceCullingHtml>
      )}
    </group>
  )
}

function connectorKind(cableType = '') {
  const t = String(cableType).toLowerCase()
  if (t.includes('qsfp') || t.includes('dac') || t.includes('aoc')) return 'QSFP'
  if (t.includes('fiber') || t.includes('lc') || t.includes('mpo')) return 'LC'
  return 'RJ45'
}

function cableColor(cableType = '', loose = false) {
  if (loose) return '#f59e0b'
  const t = String(cableType).toLowerCase()
  if (t.includes('fiber') || t.includes('lc')) return '#a3e635'
  if (t.includes('dac') || t.includes('qsfp')) return '#22d3ee'
  if (t.includes('power') || t.includes('c13')) return '#000000'
  return '#38bdf8'
}

// Decay rates for the unplug recoil and the snap-to-plug flash. These used to be
// React state decremented inside useFrame, which re-rendered the cable ~60x/sec.
const RECOIL_DECAY = 2.2
const SNAP_DECAY = 3

/** Default minimum bend radius (mm) when the cable catalog does not specify one. */
export const DEFAULT_MIN_BEND_RADIUS_MM = 25

/**
 * Brief window after an intentional unlock (cable drag / tablet) during which
 * WalkController's pointerlockchange must NOT open the Esc pause menu — otherwise
 * drag/plug UI is buried under "Paused".
 */
let _suppressPauseUntil = 0
export function suppressPointerUnlockPause(ms = 600) {
  const now = typeof performance !== 'undefined' ? performance.now() : Date.now()
  _suppressPauseUntil = now + Math.max(0, ms || 0)
}
export function isPointerUnlockPauseSuppressed() {
  const now = typeof performance !== 'undefined' ? performance.now() : Date.now()
  return now < _suppressPauseUntil
}

/** Frame-rate independent decay, clamped at 0. Pure so it can be tested. */
export function decay(value, dt, rate) {
  if (!(value > 0)) return 0
  const next = value - (Number.isFinite(dt) ? dt : 0) * rate
  return next > 0 ? next : 0
}

/**
 * Approximate bend radius (mm) from span chord + mid sag (metres).
 * Uses sag/chord sharpness rather than a full-span circumcircle — a jacket kink
 * is local, and the circle-through-endpoints formula never drops near Cat6's
 * 25mm floor for hall-scale distances.
 */
export function estimateBendRadiusMm(chordM, sagM) {
  const chord = Math.max(0.01, Math.abs(Number(chordM) || 0))
  const sag = Math.max(0.01, Math.abs(Number(sagM) || 0))
  const ratio = sag / chord
  // ratio ≈ 3.2 → ~25mm (warn); ratio ≈ 1 → ~80mm (fine).
  return 80 / Math.max(0.25, ratio)
}

/** Catalog floor for bend radius by connector family. */
export function minBendRadiusMm(cableType = '', catalogMm) {
  const fromCatalog = Number(catalogMm)
  if (Number.isFinite(fromCatalog) && fromCatalog > 0) return fromCatalog
  const t = String(cableType).toLowerCase()
  if (t.includes('fiber') || t.includes('lc') || t.includes('mpo')) return 30
  if (t.includes('dac') || t.includes('qsfp') || t.includes('aoc')) return 35
  if (t.includes('power') || t.includes('c13')) return 40
  return DEFAULT_MIN_BEND_RADIUS_MM
}

/**
 * Resting world position of the draggable connector tip.
 * Writes into `out` instead of allocating: this runs every frame while a cable
 * recoils, and the old useMemo version cloned three Vector3s per call.
 */
export function computeTipWorld(out, { to, loose, dragging, tipOffset, recoil }) {
  out.copy(to)
  if (loose || dragging || recoil > 0) {
    out.y -= loose ? 0.55 : 0.08
    out.x += loose ? 0.22 : 0
    if (tipOffset) out.add(tipOffset)
    if (recoil > 0) out.y -= recoil * 0.25
  }
  return out
}

/**
 * Rewrites the four control points of an existing CatmullRomCurve3 in place.
 * Mutating is what lets us keep one curve + one TubeGeometry for the lifetime of
 * the cable; callers that captured `curve` (the packet animation) keep reading
 * the live object rather than a stale closure.
 */
export function updateCurvePoints(curve, { from, tip, loose, dragging }) {
  const [a, mid1, mid2, b] = curve.points
  a.copy(from)
  b.copy(tip)
  mid1.lerpVectors(a, b, 0.33)
  mid1.y -= loose || dragging ? 0.42 : 0.12
  mid1.x += loose ? 0.15 : 0.04
  mid2.lerpVectors(a, b, 0.66)
  mid2.y -= loose || dragging ? 0.55 : 0.18
  // CatmullRomCurve3 caches arc lengths for getPointAt(); without this the
  // packets would keep pathing along the previous frame's geometry.
  curve.updateArcLengths()
  return curve
}

/**
 * Interactive plant cable with drag plug/unplug.
 * from = chassis port, to = tray / switch end.
 */
export function InteractiveCable({
  from,
  to,
  loose = false,
  traffic = true,
  cableId,
  serverId,
  cableType = 'Cat6A',
  bendRadiusMm,
  onUnplug,
  onPlug,
  label,
  arNetwork = false,
}) {
  const packetRef = useRef()
  const packetRef2 = useRef()
  const tipRef = useRef()
  const [dragging, setDragging] = useState(false)
  const [tipOffset, setTipOffset] = useState(() => new THREE.Vector3())
  const [bendWarn, setBendWarn] = useState(false)
  // recoil/snapFlash decay every frame. They are refs, not state, because as
  // state each tick re-rendered the cable and rebuilt curve + TubeGeometry(36x8)
  // — a new GPU buffer per frame per cable, none of them disposed.
  const snapFlash = useRef(0)
  const recoil = useRef(0)
  const tipMatRef = useRef()
  const tubeMatRef = useRef()
  const dragStart = useRef(null)
  const controls = useThree((s) => s.controls)
  const { camera, gl } = useThree()
  const plane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), [])
  const hit = useMemo(() => new THREE.Vector3(), [])
  const raycaster = useMemo(() => new THREE.Raycaster(), [])
  const ndc = useMemo(() => new THREE.Vector2(), [])
  const camDir = useMemo(() => new THREE.Vector3(), [])
  const kind = connectorKind(cableType)
  const color = cableColor(cableType, loose)
  const minBend = minBendRadiusMm(cableType, bendRadiusMm)

  // One curve and one tube for the life of the cable. Both are mutated in place
  // below; `curve.points` are pre-allocated so no frame ever allocates a Vector3.
  const tipWorld = useMemo(() => new THREE.Vector3(), [])
  const curve = useMemo(
    () =>
      new THREE.CatmullRomCurve3([
        new THREE.Vector3(),
        new THREE.Vector3(),
        new THREE.Vector3(),
        new THREE.Vector3(),
      ]),
    [],
  )
  const tube = useMemo(() => new THREE.TubeGeometry(curve, 36, 0.013, 8, false), [curve])

  // syncTube runs inside useFrame and must see the current loose/dragging values
  // without being rebuilt (and without re-running the effect) on every change.
  const loosePropRef = useRef(loose)
  const draggingRef = useRef(dragging)
  loosePropRef.current = loose
  draggingRef.current = dragging

  // Rewrites the tube's existing position/normal buffers from the current curve.
  // TubeGeometry has no update() method, so we build a throwaway on the same
  // topology (identical segment counts => identical buffer lengths), copy the
  // arrays across and dispose it immediately. That keeps ONE long-lived GPU
  // allocation per cable instead of one per frame.
  const syncTube = useMemo(
    () => () => {
      const radius = loosePropRef.current || draggingRef.current ? 0.011 : 0.013
      const next = new THREE.TubeGeometry(curve, 36, radius, 8, false)
      for (const name of ['position', 'normal']) {
        tube.attributes[name].copy(next.attributes[name])
        tube.attributes[name].needsUpdate = true
      }
      tube.computeBoundingSphere()
      next.dispose()
    },
    [curve, tube],
  )

  // TubeGeometry allocates real GPU buffers and R3F does not own this one (it
  // came from useMemo, not JSX), so nothing disposed it. The twin also unmounts
  // on every 2D/3D toggle and room switch, so this leaked per toggle.
  useEffect(() => () => tube.dispose(), [tube])

  // Keep the tube in sync with prop-driven changes (rack moves, plug/unplug)
  // even on a paused/idle frame loop.
  useEffect(() => {
    computeTipWorld(tipWorld, { to, loose, dragging, tipOffset, recoil: recoil.current })
    updateCurvePoints(curve, { from, tip: tipWorld, loose, dragging })
    syncTube()
    if (tipRef.current) tipRef.current.position.copy(tipWorld)
  }, [from, to, loose, dragging, tipOffset, tipWorld, curve, syncTube])

  useFrame(({ clock }, dt) => {
    const t = clock.elapsedTime
    // Decay first so the geometry we build this frame reflects this frame's recoil.
    const hadMotion = recoil.current > 0 || snapFlash.current > 0
    recoil.current = decay(recoil.current, dt, RECOIL_DECAY)
    snapFlash.current = decay(snapFlash.current, dt, SNAP_DECAY)

    if (hadMotion) {
      computeTipWorld(tipWorld, { to, loose, dragging, tipOffset, recoil: recoil.current })
      updateCurvePoints(curve, { from, tip: tipWorld, loose, dragging })
      syncTube()
      // tipWorld is mutated in place and is the same object R3F copies into the
      // tip group and drei's Html wrapper, so both overlays track it without a
      // re-render. tipRef is written directly for the frames React never sees.
      if (tipRef.current) tipRef.current.position.copy(tipWorld)
      // These read snapFlash, which no longer re-renders: drive them imperatively.
      if (tipMatRef.current) tipMatRef.current.emissiveIntensity = 0.9 + snapFlash.current + (arNetwork ? 0.45 : 0)
      if (tubeMatRef.current && !loose) tubeMatRef.current.emissiveIntensity = 0.18 + snapFlash.current * 0.5
    }

    if (packetRef.current && traffic && !loose && !dragging) {
      const u = (t * 0.4) % 1
      packetRef.current.position.copy(curve.getPointAt(u))
      packetRef.current.visible = true
      packetRef.current.material.emissiveIntensity = 0.8 + Math.sin(t * 12) * 0.4
    } else if (packetRef.current) {
      packetRef.current.visible = false
    }
    if (packetRef2.current && traffic && !loose && !dragging) {
      const u2 = (t * 0.4 + 0.5) % 1
      packetRef2.current.position.copy(curve.getPointAt(u2))
      packetRef2.current.visible = true
      packetRef2.current.material.emissiveIntensity = 0.5 + Math.sin(t * 12 + Math.PI) * 0.3
    } else if (packetRef2.current) {
      packetRef2.current.visible = false
    }
    if (tipRef.current) tipRef.current.scale.setScalar(1 + snapFlash.current * 0.35)
  })

  const projectPointer = (clientX, clientY) => {
    const rect = gl.domElement.getBoundingClientRect()
    ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1
    ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(ndc, camera)
    camera.getWorldDirection(camDir)
    plane.normal.copy(camDir).negate()
    plane.constant = -plane.normal.dot(tipWorld)
    if (!raycaster.ray.intersectPlane(plane, hit)) {
      hit.copy(tipWorld)
    }
    return hit.clone()
  }

  const refreshBendWarn = (tip) => {
    const chord = from.distanceTo(tip)
    const sag = Math.max(0.05, Math.abs(from.y - tip.y) * 0.55 + (loose || dragging ? 0.35 : 0.12))
    const radius = estimateBendRadiusMm(chord, sag)
    setBendWarn(Number.isFinite(radius) && radius < minBend)
  }

  const endDrag = (clientX, clientY) => {
    if (!dragStart.current) return
    const started = dragStart.current
    dragStart.current = null
    setDragging(false)
    if (controls) controls.enabled = true
    document.body.style.cursor = 'default'

    const distMoved = Math.hypot(clientX - started.x, clientY - started.y)
    if (distMoved < 18) {
      setBendWarn(false)
      return
    }

    if (!loose && onUnplug) {
      recoil.current = 1
      setTipOffset(new THREE.Vector3(0.15, -0.35, 0.12))
      onUnplug({ serverId, cableId })
      return
    }
    if (loose && onPlug) {
      const tip = projectPointer(clientX, clientY)
      if (tip.distanceTo(from) < 0.55) {
        setTipOffset(new THREE.Vector3())
        snapFlash.current = 1
        setBendWarn(false)
        onPlug({ serverId, cableId })
      } else {
        refreshBendWarn(tip)
      }
    }
  }

  return (
    <group>
      <PortJack
        position={from}
        linked={!loose && !dragging}
        activity={traffic && !loose}
        label={label || cableId}
        arNetwork={arNetwork}
      />
      <mesh geometry={tube}>
        <meshStandardMaterial
          ref={tubeMatRef}
          color={color}
          emissive={loose ? '#f59e0b' : color}
          emissiveIntensity={loose ? 0.35 : 0.18}
          metalness={0.25}
          roughness={0.55}
          toneMapped={false}
        />
      </mesh>
      <group position={from}>
        <CableConnector color="#cbd5e1" kind={kind} />
      </group>
      <group
        ref={tipRef}
        position={tipWorld}
        onPointerDown={(e) => {
          e.stopPropagation()
          // Pointer-lock freezes clientX/Y near canvas center — exit so drag works,
          // and suppress the Esc pause menu that unlock would otherwise open.
          suppressPointerUnlockPause(700)
          try { document.exitPointerLock?.() } catch { /* */ }
          dragStart.current = { x: e.clientX, y: e.clientY }
          setDragging(true)
          if (controls) controls.enabled = false
          document.body.style.cursor = 'grabbing'
          e.target.setPointerCapture?.(e.pointerId)
        }}
        onPointerMove={(e) => {
          if (!dragStart.current) return
          e.stopPropagation()
          const p = projectPointer(e.clientX, e.clientY)
          const base = loose
            ? to.clone().add(new THREE.Vector3(0.22, -0.55, 0))
            : to.clone()
          setTipOffset(p.clone().sub(base))
          refreshBendWarn(p)
        }}
        onPointerUp={(e) => {
          e.stopPropagation()
          endDrag(e.clientX, e.clientY)
        }}
        onPointerOver={(e) => {
          e.stopPropagation()
          document.body.style.cursor = 'grab'
        }}
        onPointerOut={() => {
          if (!dragging) document.body.style.cursor = 'default'
        }}
      >
        <CableConnector color={loose ? '#fbbf24' : '#f8fafc'} kind={kind} />
        <mesh position={[0, 0.03, 0]}>
          <sphereGeometry args={[0.012, 8, 8]} />
          <meshStandardMaterial
            ref={tipMatRef}
            color="#fff"
            emissive={loose ? '#f59e0b' : '#38bdf8'}
            emissiveIntensity={0.9 + (arNetwork ? 0.45 : 0)}
            toneMapped={false}
          />
        </mesh>
      </group>
      <mesh ref={packetRef}>
        <sphereGeometry args={[0.026, 8, 8]} />
        <meshStandardMaterial color="#fff" emissive="#38bdf8" emissiveIntensity={1.1} toneMapped={false} />
      </mesh>
      <mesh ref={packetRef2}>
        <sphereGeometry args={[0.018, 8, 8]} />
        <meshStandardMaterial color="#fff" emissive={color} emissiveIntensity={0.8} toneMapped={false} />
      </mesh>
      {(loose || dragging) && (
        <Html position={tipWorld} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
          <div className={`dc-3d-chip${bendWarn ? ' dc-3d-chip-warn' : ''}`}>
            {bendWarn
              ? `Bend < ${minBend}mm — ease the pull`
              : dragging
                ? (loose ? 'Drop on port to plug' : 'Release to unplug')
                : 'Drag connector'}
          </div>
        </Html>
      )}
    </group>
  )
}

export function CablePhysicsBits({ anchors }) {
  return (
    <group>
      {anchors.map((a, i) => (
        <RigidBody key={i} position={a} colliders={false} restitution={0.15} linearDamping={1.5} angularDamping={1.5}>
          <BallCollider args={[0.045]} />
          <mesh>
            <sphereGeometry args={[0.038, 8, 8]} />
            <meshStandardMaterial color="#64748b" metalness={0.65} />
          </mesh>
        </RigidBody>
      ))}
    </group>
  )
}

export { connectorKind, cableColor }
