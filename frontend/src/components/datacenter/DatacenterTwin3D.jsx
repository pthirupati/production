/**
 * Phase 7+ — Animated Lab Environment 3D digital twin (R3F + Rapier).
 * Camera intro, rack doors, LED/power pulse, fans, cable packets, airflow.
 */
import {
  Suspense, cloneElement, isValidElement, useEffect, useMemo, useRef, useState,
} from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import {
  OrbitControls, Html, Environment, ContactShadows, RoundedBox, Float, Bvh,
} from '@react-three/drei'
import { Physics, RigidBody } from '@react-three/rapier'
import { motion } from 'framer-motion'
import * as THREE from 'three'
import { StatusLed, InteractiveCable, CablePhysicsBits } from './DcCableSystem'

const RACK_W = 0.6
const RACK_D = 1.05
const RACK_H = 2.0
const U_H = RACK_H / 42

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
function WalkController({ enabled, paused = false, posRef }) {
  const { camera, gl } = useThree()
  const keys = useRef({})
  const yaw = useRef(0)
  const pitch = useRef(-0.12)
  const pos = useRef(new THREE.Vector3(5.2, 1.55, 4.5))
  const bobPhase = useRef(0)
  const bobAmount = useRef(0)

  useEffect(() => {
    if (!enabled) return undefined
    const down = (e) => { keys.current[e.code] = true }
    const up = (e) => { keys.current[e.code] = false }
    const move = (e) => {
      if (paused) return
      if (document.pointerLockElement !== gl.domElement) return
      yaw.current -= e.movementX * 0.0026
      pitch.current = Math.max(-1.25, Math.min(1.25, pitch.current - e.movementY * 0.0026))
    }
    const click = () => { if (!paused) gl.domElement.requestPointerLock?.() }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('mousemove', move)
    gl.domElement.addEventListener('click', click)
    camera.position.copy(pos.current)
    // Auto-grab mouse look on walk start (game FPS feel); browsers may still
    // require a click if gesture policy blocks programmatic lock.
    const lockId = setTimeout(() => {
      try { if (!paused) gl.domElement.requestPointerLock?.() } catch { /* */ }
    }, 120)
    return () => {
      clearTimeout(lockId)
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      window.removeEventListener('mousemove', move)
      gl.domElement.removeEventListener('click', click)
      try { document.exitPointerLock?.() } catch { /* */ }
    }
  }, [enabled, camera, gl, paused])

  useFrame((_, dt) => {
    if (!enabled) return
    if (paused) { keys.current = {}; return }
    const sprinting = !!keys.current.ShiftLeft
    const speed = (sprinting ? 6.1 : 3.15) * dt
    const forward = new THREE.Vector3(-Math.sin(yaw.current), 0, -Math.cos(yaw.current))
    const right = new THREE.Vector3(Math.cos(yaw.current), 0, -Math.sin(yaw.current))
    let moving = false
    if (keys.current.KeyW || keys.current.ArrowUp) { pos.current.addScaledVector(forward, speed); moving = true }
    if (keys.current.KeyS || keys.current.ArrowDown) { pos.current.addScaledVector(forward, -speed); moving = true }
    if (keys.current.KeyA || keys.current.ArrowLeft) { pos.current.addScaledVector(right, -speed); moving = true }
    if (keys.current.KeyD || keys.current.ArrowRight) { pos.current.addScaledVector(right, speed); moving = true }
    // Soft bounds inside hall + corridor
    pos.current.x = Math.max(-8.5, Math.min(7.5, pos.current.x))
    pos.current.z = Math.max(-5.5, Math.min(6.5, pos.current.z))

    // Game-style boot-fall head-bob — stronger while sprinting.
    const bobFreq = sprinting ? 15.5 : 9.5
    const bobTarget = moving ? (sprinting ? 0.09 : 0.055) : 0
    bobAmount.current += (bobTarget - bobAmount.current) * Math.min(1, dt * 12)
    if (moving) bobPhase.current += dt * bobFreq
    const bob = Math.sin(bobPhase.current) * bobAmount.current
    const sway = Math.cos(bobPhase.current * 0.5) * bobAmount.current * 0.7

    camera.position.set(pos.current.x + sway, pos.current.y + bob, pos.current.z)
    pos.current.y = 1.55
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

/** "E" key fires a synthetic click at the crosshair (screen center) so mouse-locked
 *  players can interact with racks / portals / cables without unlocking the pointer. */
function CrosshairInteract({ enabled }) {
  const { gl } = useThree()
  useEffect(() => {
    if (!enabled) return undefined
    const handler = (e) => {
      if (e.code !== 'KeyE') return
      if (document.pointerLockElement !== gl.domElement) return
      const rect = gl.domElement.getBoundingClientRect()
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      const opts = { clientX: cx, clientY: cy, bubbles: true, cancelable: true }
      gl.domElement.dispatchEvent(new MouseEvent('click', opts))
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [enabled, gl])
  return null
}

/** Raised floor: 600mm tiles + perforated cold-aisle openings. */
function Floor() {
  const mat = useRef()
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

/** Overhead LED fixtures along cold aisles. */
function CeilingLights() {
  const fixtures = useMemo(() => {
    const list = []
    for (let x = -5; x <= 5; x += 2.5) {
      list.push([x, 3.35, -1.6], [x, 3.35, -3.8])
    }
    return list
  }, [])
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
              color="#f8fafc"
              emissive="#e2e8f0"
              emissiveIntensity={0.85}
              toneMapped={false}
            />
          </mesh>
          <pointLight color="#e8f0ff" intensity={0.35} distance={8} decay={2} position={[0, -0.2, 0]} />
        </group>
      ))}
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

  useFrame((_, dt) => {
    const mesh = ref.current
    if (!mesh) return
    const pos = mesh.geometry.attributes.position.array
    const boost = 1 + stress * 1.8
    for (let i = 0; i < count; i++) {
      pos[i * 3 + 1] += speeds[i] * dt * boost
      pos[i * 3] += Math.sin(performance.now() * 0.001 + i) * 0.002 * boost
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
            <Html position={[0, 0.85, 0]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
              <div className={`dc-3d-label ${failed ? 'dc-3d-label-hot' : ''}`}>
                {c.id} · {c.temp_c ?? '—'}°C
              </div>
            </Html>
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

function PduStrips({ racks = [], pdus = [], onSelectPdu, arMode = 'off' }) {
  const powerBoost = arMode === 'power'
  return (
    <group>
      {racks.map((rack, i) => {
        const { x, z } = rackPosition(i)
        const pdu = pdus.find((p) => p.rack === rack.id) || {}
        const tripped = pdu.status === 'tripped' || pdu.breaker === 'open'
        const load = Math.min(1, (pdu.load_amps || pdu.amps || 12) / 32)
        return (
          <group key={`pdu-${rack.id}`} position={[x + RACK_W / 2 + 0.08, RACK_H / 2, z]}>
            <mesh
              castShadow
              onClick={(e) => { e.stopPropagation(); onSelectPdu?.(pdu.id || rack.id) }}
            >
              <boxGeometry args={[0.09, RACK_H * 0.92, 0.14]} />
              <meshStandardMaterial
                color={tripped ? '#7f1d1d' : '#1e293b'}
                emissive={tripped ? '#ef4444' : '#22c55e'}
                emissiveIntensity={tripped ? 0.55 : (powerBoost ? 0.4 : 0.12)}
                metalness={0.65}
              />
            </mesh>
            {/* C13/C19 outlet LEDs along the strip */}
            {Array.from({ length: 12 }).map((_, oi) => {
              const oy = -RACK_H * 0.4 + oi * (RACK_H * 0.78 / 11)
              const lit = !tripped && oi / 12 < load + 0.15
              return (
                <mesh key={oi} position={[0.05, oy, 0.04]}>
                  <boxGeometry args={[0.02, 0.035, 0.03]} />
                  <meshStandardMaterial
                    color={lit ? '#0f172a' : '#334155'}
                    emissive={tripped ? '#ef4444' : lit ? '#22c55e' : '#000'}
                    emissiveIntensity={tripped ? 0.7 : lit ? (powerBoost ? 0.85 : 0.45) : (powerBoost ? 0.12 : 0)}
                  />
                </mesh>
              )
            })}
            <Html distanceFactor={8} position={[0.12, RACK_H * 0.42, 0]} style={{ pointerEvents: 'none' }}>
              <div className="dc-3d-chip">{tripped ? 'PDU TRIP' : `${Math.round(load * 100)}%`}</div>
            </Html>
          </group>
        )
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
function ServerStack({ servers, onSelect, animBoost = 1, onOpenBmc }) {
  const meshRef = useRef()
  const installStart = useRef(performance.now())
  const geo = useMemo(() => new THREE.BoxGeometry(RACK_W * 0.88, U_H * 0.9, RACK_D * 0.72), [])
  const mat = useMemo(() => new THREE.MeshStandardMaterial({ metalness: 0.45, roughness: 0.35, vertexColors: true }), [])
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const color = useMemo(() => new THREE.Color(), [])
  const count = servers.length
  const seatZ = useRef(new Float32Array(Math.max(count, 1)))

  useFrame(({ clock }) => {
    const mesh = meshRef.current
    if (!mesh || !count) return
    const pulse = 0.08 + Math.sin(clock.elapsedTime * 2.5) * 0.04
    const now = performance.now()
    servers.forEach((s, i) => {
      const failed = Object.values(s.components || {}).some((x) => x !== 'healthy')
      const powered = s.power_state === 'on'
      const y = ((s.u_slot || 1) - 1) * U_H + U_H * 0.5 + 0.05
      const delay = i * 160
      const u = Math.min(1, Math.max(0, (now - installStart.current - delay) / 850))
      const e = 1 - (1 - u) ** 3
      const slide = (1 - e) * 0.62
      seatZ.current[i] = -0.04 + slide
      const bob = powered && animBoost && e > 0.98 ? Math.sin(clock.elapsedTime * 1.4 + i) * 0.008 : 0
      dummy.position.set(0, y + bob, seatZ.current[i])
      // Slight nose-up while sliding, then level on the rails.
      dummy.rotation.x = (1 - e) * -0.12
      dummy.scale.set(1, 1, 0.92 + e * 0.08)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
      if (failed) color.set('#ef4444')
      else if (!powered) color.set('#475569')
      else if (e < 1) color.set('#94a3b8')
      else color.set(vendorColor(s.vendor))
      mesh.setColorAt(i, color)
    })
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
    mesh.material.emissiveIntensity = pulse * animBoost
  })

  if (!count) return null
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
        onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { document.body.style.cursor = 'default' }}
      />
      {servers.map((s, i) => {
        const failed = Object.values(s.components || {}).some((x) => x !== 'healthy')
        const diskFail = (s.components || {}).disk === 'failed' || (s.components || {}).disk === 'degraded'
        const powered = s.power_state === 'on'
        const y = ((s.u_slot || 1) - 1) * U_H + U_H * 0.5 + 0.05
        return (
          <ServerFaceDetail
            key={s.id}
            server={s}
            index={i}
            y={y}
            seatZRef={seatZ}
            installStart={installStart}
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
  server: s, index: i, y, seatZRef, installStart, failed, diskFail, powered, animBoost,
}) {
  const group = useRef()
  useFrame(() => {
    if (!group.current) return
    const z = seatZRef.current[i] ?? -0.04
    group.current.position.set(0, y, z)
    const delay = i * 160
    const u = Math.min(1, Math.max(0, (performance.now() - installStart.current - delay) / 850))
    // Cascade: power LED → drives → NIC glow after seat.
    group.current.userData.ledGate = u
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
      <Html distanceFactor={10} position={[0, U_H * 0.35, RACK_D * 0.4]} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-chip dc-3d-chip-sm">{s.hostname || s.id}</div>
      </Html>
      {/* unused gate reserved for future cascade timing */}
      <mesh visible={false} userData={{ ledGate }} />
    </group>
  )
}

function rackPosition(index) {
  return {
    x: (index % 4) * 1.4 - 2.1,
    z: Math.floor(index / 4) * -2.2 - 0.5,
  }
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

  return (
    <group
      ref={group}
      onClick={(e) => { e.stopPropagation(); onSelectRack?.(rack.id) }}
    >
      <RoundedBox args={[RACK_W, RACK_H, RACK_D]} radius={0.02} castShadow receiveShadow>
        <meshStandardMaterial
          color={rackColor}
          metalness={0.55}
          roughness={0.35}
          emissive={rackEmissive}
          emissiveIntensity={rackEmissiveIntensity}
        />
      </RoundedBox>
      <mesh position={[-RACK_W / 2 + 0.02, 0, 0]}>
        <boxGeometry args={[0.03, RACK_H * 0.98, RACK_D * 0.95]} />
        <meshStandardMaterial color="#334155" metalness={0.7} />
      </mesh>
      <mesh position={[RACK_W / 2 - 0.02, 0, 0]}>
        <boxGeometry args={[0.03, RACK_H * 0.98, RACK_D * 0.95]} />
        <meshStandardMaterial color="#334155" metalness={0.7} />
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
  const start = useRef(performance.now() + index * 110)

  useFrame(() => {
    if (!wrap.current) return
    const u = Math.min(1, Math.max(0, (performance.now() - start.current) / 950))
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
  const hot = /critical|high/i.test(ticket?.priority || '')
  return (
    <group
      ref={ref}
      position={pos}
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
      <Html center distanceFactor={8} style={{ pointerEvents: 'none' }}>
        <div className={`dc-3d-label ${hot ? 'dc-3d-label-hot' : ''}`}>
          {(ticket.id || 'TKT').slice(0, 12)} · {(ticket.summary || ticket.title || 'fault').slice(0, 28)}
        </div>
      </Html>
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
    <group position={position}>
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
      <Html position={[0, 1.25, 0.1]} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label dc-3d-portal-label" style={{ '--portal-color': color }}>{label}</div>
      </Html>
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
    <group position={[-4.55, 0, 4.75]}>
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
}) {
  const thermalStress = useMemo(() => {
    const units = cooling || []
    if (!units.length) return 0
    const failed = units.filter((c) => c.status !== 'running').length
    const hot = units.filter((c) => Number(c.temp_c) > 28).length
    return Math.min(1, failed / units.length + hot * 0.15)
  }, [cooling])

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

  const cables = useMemo(() => {
    const links = []
    racks.forEach((rack, i) => {
      const { x: sx, z: sz } = rackPosition(i)
      const srvList = serversByRack[rack.id] || []
      const tray = new THREE.Vector3(sx, 2.45, -1.6)

      // Plant backbone: rack → tray → MDF (always visible wiring)
      if (switchCount > 0 || i <= 8) {
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
  }, [racks, serversByRack, switchCount, mdfPos])

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
      <WalkController enabled={walkMode} paused={walkPaused} posRef={posRef} />
      <CrosshairInteract enabled={walkMode && !walkPaused} />
      <color attach="background" args={['#070a10']} />
      {/* Tight fog sells depth in first-person — hall falls off like a game level */}
      <fog attach="fog" args={['#070a10', walkMode ? 5.5 : 10, walkMode ? 18 : 28]} />
      <ambientLight intensity={0.22} />
      <directionalLight castShadow position={[6, 10, 4]} intensity={1.05} shadow-mapSize={[1024, 1024]} />
      <directionalLight position={[-4, 6, -6]} intensity={0.4} color="#94a3b8" />
      <PulsingLight />
      <Environment preset="warehouse" />
      <Floor />
      <CorridorShell dockBusy={dockBusy} doorOpen={doorOpen} />
      <HallDust count={walkMode ? 140 : 90} />
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
      <CeilingLights />
      <CableTray />
      <HotAisleGlow z={-1.6} />
      <HotAisleGlow z={-3.8} />
      <ThermalHaze stress={thermalStress} ticketHeat={ticketHeat} />
      {animBoost > 0 && (
        <AirflowParticles
          count={Math.round(220 * animBoost * (1 + thermalStress * 1.4))}
          stress={thermalStress}
        />
      )}
      {animBoost > 0 && thermalStress > 0.2 && (
        <AirflowParticles
          count={Math.round(80 * animBoost)}
          stress={1}
        />
      )}
      <CracUnits cooling={cooling} />
      <PduStrips racks={racks} pdus={pdus} arMode={arMode} />

      <TorSwitch position={[5.5, 0.95, -1.2]} label="MDF / Spine" ports={48} />
      <TorSwitch position={[5.5, 1.25, -1.2]} label="Leaf / ToR agg" ports={36} />

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
      Walk the cold aisle · <kbd>E</kbd> interact · <kbd>V</kbd> AR overlay · <kbd>Esc</kbd> menu
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
function Minimap({ posRef, currentRoomLabel = 'Data Hall A' }) {
  const dotRef = useRef()
  useEffect(() => {
    let raf
    const tick = () => {
      if (dotRef.current && posRef?.current) {
        const px = 50 + Math.max(-1, Math.min(1, posRef.current.x / 9)) * 42
        const pz = 50 + Math.max(-1, Math.min(1, posRef.current.z / 7)) * 42
        dotRef.current.style.left = `${px}%`
        dotRef.current.style.top = `${pz}%`
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [posRef])
  return (
    <div className="dc-3d-minimap" aria-hidden>
      <div className="dc-3d-minimap-label">{currentRoomLabel}</div>
      <div className="dc-3d-minimap-ring" />
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

/** Esc-triggered pause menu — accessible exit from pointer-locked immersive mode. */
function ImmersiveMenu({ open, onResume, onExitImmersive, onExitTo2D, badgedIn }) {
  if (!open) return null
  return (
    <div className="dc-3d-menu-backdrop" onClick={onResume}>
      <div className="dc-3d-menu" onClick={(e) => e.stopPropagation()}>
        <div className="dc-3d-menu-title">Paused</div>
        <button type="button" className="dc-3d-menu-btn dc-3d-menu-btn-primary" onClick={onResume}>
          Resume walking
        </button>
        <button type="button" className="dc-3d-menu-btn" onClick={onExitImmersive}>
          Exit immersive mode
        </button>
        <button type="button" className="dc-3d-menu-btn" onClick={onExitTo2D}>
          Switch to 2D floor
        </button>
        <div className="dc-3d-menu-hint">
          {badgedIn ? 'Badged in' : 'Not badged in'} · 1 Dock · 2 Reception · 3 MDF · 4 NOC · V AR
        </div>
      </div>
    </div>
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
  const [animBoost, setAnimBoost] = useState(1)
  const [intro, setIntro] = useState(true)
  const [walkMode, setWalkMode] = useState(false)
  const [fps, setFps] = useState(0)
  // Steam-class default: start immersive (game view) — heavy chrome stays collapsed.
  const [immersive, setImmersive] = useState(true)
  const [menuOpen, setMenuOpen] = useState(false)
  const [showCoach, setShowCoach] = useState(false)
  // AR HUD overlay cycle (Off / Thermal / Power / Network) — key `V`.
  const [arModeIdx, setArModeIdx] = useState(0)
  // Field kit HUD state — ESD wrist-strap toggle + cosmetic parts-cart marker.
  const [esdOn, setEsdOn] = useState(true)
  const [cartOpen, setCartOpen] = useState(false)
  const [esdToast, setEsdToast] = useState(false)
  const autoWalkStarted = useRef(false)
  const coachShown = useRef(false)
  const posRef = useRef({ x: 5.2, z: 4.5, yaw: 0 })
  const prevSelectedRef = useRef(null)

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

  // In-world room hotkeys (1-4) + AR overlay cycle (V) + Esc pause menu — no tab bar needed while immersive.
  useEffect(() => {
    if (!immersive || intro) return undefined
    const handler = (e) => {
      if (e.code === 'Escape') {
        setMenuOpen((m) => !m)
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
    <motion.div
      className={`dc-3d-root${immersive ? ' dc-3d-immersive' : ''}`}
      initial={{ opacity: 0, scale: 0.985 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.55, ease: 'easeOut' }}
    >
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
          />
          Rapier
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
          ~{fps || '—'} FPS · {inGame
            ? 'click canvas to look · WASD · Shift sprint · Esc menu'
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
        {inGame && (
          <div className="dc-3d-hud">
            {objective && <div className="dc-3d-hud-objective"><strong>Objective</strong> · {objective}</div>}
            <div>WASD move · mouse look · Shift sprint · E interact</div>
            <div>1 Dock · 2 Reception · 3 MDF · 4 NOC · V AR overlay · Esc menu</div>
          </div>
        )}
        {inGame && <Minimap posRef={posRef} currentRoomLabel={currentRoomLabel} />}
        {inGame && <CoachMark show={showCoach} />}
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
          onResume={() => setMenuOpen(false)}
          onExitImmersive={exitImmersive}
          onExitTo2D={exitTo2D}
        />
        <Suspense fallback={<LoadingFallback />}>
          <Canvas
            shadows
            dpr={[1, Math.min(2, typeof window !== 'undefined' ? window.devicePixelRatio : 1.5)]}
            camera={{ position: [12, 9, 14], fov: inGame ? 70 : 42, near: 0.1, far: 80 }}
            gl={{ antialias: true, powerPreference: 'high-performance' }}
          >
            <Physics gravity={[0, -9.81, 0]} colliders={false} paused={!physicsEnabled}>
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
                physicsEnabled={physicsEnabled}
                onFps={setFps}
                animBoost={animBoost}
                intro={intro}
                walkMode={walkMode}
                walkPaused={menuOpen}
                posRef={posRef}
                tickets={tickets}
                doorOpen={badgedIn}
                onEnterRoom={onEnterRoom}
                arMode={arMode}
                badgedIn={badgedIn}
                onBadgeIn={onBadgeIn}
                nocMetrics={nocMetrics}
              />
            </Physics>
          </Canvas>
        </Suspense>
      </div>
    </motion.div>
  )
}
