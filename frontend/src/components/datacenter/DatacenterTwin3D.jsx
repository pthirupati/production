/**
 * Phase 7+ — Animated Lab Environment 3D digital twin (R3F + Rapier).
 * Camera intro, rack doors, LED/power pulse, fans, cable packets, airflow.
 */
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import {
  OrbitControls, Html, Environment, ContactShadows, RoundedBox, Float, Bvh,
} from '@react-three/drei'
import { Physics, RigidBody, BallCollider } from '@react-three/rapier'
import { motion } from 'framer-motion'
import * as THREE from 'three'

const RACK_W = 0.6
const RACK_D = 1.05
const RACK_H = 2.0
const U_H = RACK_H / 42

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
function CameraIntro({ enabled }) {
  const { camera } = useThree()
  const controls = useThree((s) => s.controls)
  const t0 = useRef(null)
  const done = useRef(false)
  const from = useMemo(() => new THREE.Vector3(12, 9, 14), [])
  const to = useMemo(() => new THREE.Vector3(6, 5, 7), [])
  const look = useMemo(() => new THREE.Vector3(1, 0.8, -1.5), [])

  useEffect(() => {
    if (!enabled) return
    t0.current = performance.now()
    done.current = false
    camera.position.copy(from)
    camera.lookAt(look)
  }, [enabled, camera, from, look])

  useFrame(() => {
    if (!enabled || done.current || t0.current == null) return
    const u = Math.min(1, (performance.now() - t0.current) / 2200)
    const e = 1 - (1 - u) ** 3
    camera.position.lerpVectors(from, to, e)
    camera.lookAt(look)
    if (controls?.target) controls.target.lerp(look, 0.08)
    if (u >= 1) done.current = true
  })
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

function FanSpinner({ position, powered, rpmScale = 1 }) {
  const hub = useRef()
  const blades = useRef()
  useFrame((_, dt) => {
    if (!blades.current || !powered) return
    blades.current.rotation.z += dt * (14 + rpmScale * 10)
  })
  return (
    <group position={position}>
      <mesh ref={hub}>
        <cylinderGeometry args={[0.018, 0.018, 0.008, 10]} />
        <meshStandardMaterial color="#0f172a" metalness={0.7} />
      </mesh>
      <group ref={blades}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <mesh key={i} rotation={[0, 0, (i / 6) * Math.PI * 2]} position={[0, 0, 0.001]}>
            <boxGeometry args={[0.055, 0.012, 0.003]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.55} roughness={0.35} />
          </mesh>
        ))}
      </group>
      <mesh position={[0, 0, 0.006]}>
        <ringGeometry args={[0.05, 0.056, 16]} />
        <meshStandardMaterial color="#334155" metalness={0.6} />
      </mesh>
    </group>
  )
}

function PduStrips({ racks = [], pdus = [], onSelectPdu }) {
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
                emissiveIntensity={tripped ? 0.55 : 0.12}
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
                    emissiveIntensity={tripped ? 0.7 : lit ? 0.45 : 0}
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

function StatusLed({ position, failed, powered }) {
  const mat = useRef()
  useFrame(({ clock }) => {
    if (!mat.current) return
    if (failed) {
      mat.current.emissiveIntensity = 0.6 + Math.sin(clock.elapsedTime * 8) * 0.4
      mat.current.color.set('#ef4444')
      mat.current.emissive.set('#ef4444')
    } else if (powered) {
      mat.current.emissiveIntensity = 0.45 + Math.sin(clock.elapsedTime * 3) * 0.25
      mat.current.color.set('#34d399')
      mat.current.emissive.set('#34d399')
    } else {
      mat.current.emissiveIntensity = 0.05
      mat.current.color.set('#64748b')
      mat.current.emissive.set('#000000')
    }
  })
  return (
    <mesh position={position}>
      <sphereGeometry args={[0.018, 8, 8]} />
      <meshStandardMaterial ref={mat} color="#34d399" emissive="#34d399" emissiveIntensity={0.5} />
    </mesh>
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

/** Per-U chassis with drive-bay LEDs, dual PSU glow, NIC activity, fans. */
function ServerStack({ servers, onSelect, animBoost = 1, onOpenBmc }) {
  const meshRef = useRef()
  const geo = useMemo(() => new THREE.BoxGeometry(RACK_W * 0.88, U_H * 0.9, RACK_D * 0.72), [])
  const mat = useMemo(() => new THREE.MeshStandardMaterial({ metalness: 0.45, roughness: 0.35, vertexColors: true }), [])
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const color = useMemo(() => new THREE.Color(), [])
  const count = servers.length

  useFrame(({ clock }) => {
    const mesh = meshRef.current
    if (!mesh || !count) return
    const pulse = 0.08 + Math.sin(clock.elapsedTime * 2.5) * 0.04
    servers.forEach((s, i) => {
      const failed = Object.values(s.components || {}).some((x) => x !== 'healthy')
      const powered = s.power_state === 'on'
      const y = ((s.u_slot || 1) - 1) * U_H + U_H * 0.5 + 0.05
      const bob = powered && animBoost ? Math.sin(clock.elapsedTime * 1.4 + i) * 0.008 : 0
      dummy.position.set(0, y + bob, -0.04)
      dummy.scale.set(1, 1, 1)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
      if (failed) color.set('#ef4444')
      else if (!powered) color.set('#475569')
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
      {servers.map((s) => {
        const failed = Object.values(s.components || {}).some((x) => x !== 'healthy')
        const diskFail = (s.components || {}).disk === 'failed' || (s.components || {}).disk === 'degraded'
        const powered = s.power_state === 'on'
        const y = ((s.u_slot || 1) - 1) * U_H + U_H * 0.5 + 0.05
        return (
          <group key={s.id} position={[0, y, -0.04]}>
            <StatusLed position={[RACK_W * 0.38, 0.02, RACK_D * 0.38]} failed={failed} powered={powered} />
            {/* Dual PSU status LEDs */}
            <StatusLed position={[RACK_W * 0.38, -0.025, RACK_D * 0.38]} failed={false} powered={powered} />
            <StatusLed position={[RACK_W * 0.32, -0.025, RACK_D * 0.38]} failed={(s.components || {}).power === 'failed'} powered={powered} />
            {/* Drive bay activity row */}
            {[0, 1, 2, 3].map((di) => (
              <mesh key={di} position={[-RACK_W * 0.28 + di * 0.08, 0.01, RACK_D * 0.37]}>
                <boxGeometry args={[0.05, 0.035, 0.02]} />
                <meshStandardMaterial
                  color="#0f172a"
                  emissive={diskFail && di === 0 ? '#ef4444' : powered ? '#22c55e' : '#000'}
                  emissiveIntensity={diskFail && di === 0 ? 0.8 : powered ? 0.25 + (di % 2) * 0.15 : 0}
                />
              </mesh>
            ))}
            {/* NIC RJ45 / SFP cages */}
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
            <FanSpinner position={[-RACK_W * 0.32, 0, RACK_D * 0.38]} powered={powered && !failed && animBoost > 0} rpmScale={failed ? 0.4 : 1} />
            <FanSpinner position={[-RACK_W * 0.22, 0, RACK_D * 0.38]} powered={powered && animBoost > 0} rpmScale={0.85} />
            <Html distanceFactor={10} position={[0, U_H * 0.35, RACK_D * 0.4]} style={{ pointerEvents: 'none' }}>
              <div className="dc-3d-chip dc-3d-chip-sm">{s.hostname || s.id}</div>
            </Html>
          </group>
        )
      })}
    </group>
  )
}

function CableStrand({ from, to, color = '#94a3b8', loose = false, traffic = true, onUnplug }) {
  const groupRef = useRef()
  const packetRef = useRef()
  const drag = useRef(null)
  const curve = useMemo(() => {
    const mid = new THREE.Vector3().addVectors(from, to).multiplyScalar(0.5)
    mid.y -= loose ? 0.38 : 0.14
    mid.x += loose ? 0.18 : 0.04
    return new THREE.CatmullRomCurve3([from.clone(), mid, to.clone()])
  }, [from, to, loose])
  const tube = useMemo(() => new THREE.TubeGeometry(curve, 20, 0.012, 6, false), [curve])

  useFrame(({ clock }) => {
    const t = clock.elapsedTime
    if (groupRef.current && loose) {
      groupRef.current.rotation.z = Math.sin(t * 2.2) * 0.04
      groupRef.current.position.y = Math.sin(t * 1.7) * 0.03
    }
    if (packetRef.current && traffic && !loose) {
      const u = (t * 0.35) % 1
      packetRef.current.position.copy(curve.getPointAt(u))
      packetRef.current.visible = true
    } else if (packetRef.current) {
      packetRef.current.visible = false
    }
  })

  return (
    <group ref={groupRef}>
      <mesh
        geometry={tube}
        onPointerDown={(e) => {
          e.stopPropagation()
          drag.current = { x: e.clientX, y: e.clientY }
          e.target.setPointerCapture?.(e.pointerId)
        }}
        onPointerUp={(e) => {
          e.stopPropagation()
          if (!drag.current) return
          const dx = e.clientX - drag.current.x
          const dy = e.clientY - drag.current.y
          drag.current = null
          if (Math.hypot(dx, dy) > 28) onUnplug?.()
        }}
        onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'grab' }}
        onPointerOut={() => { document.body.style.cursor = 'default' }}
      >
        <meshStandardMaterial
          color={color}
          emissive={loose ? '#f59e0b' : color}
          emissiveIntensity={loose ? 0.45 : 0.2}
          metalness={0.3}
          roughness={0.55}
        />
      </mesh>
      {/* Port terminations */}
      <mesh position={from}>
        <sphereGeometry args={[0.022, 8, 8]} />
        <meshStandardMaterial color="#f8fafc" emissive={color} emissiveIntensity={0.5} />
      </mesh>
      <mesh position={to}>
        <sphereGeometry args={[0.022, 8, 8]} />
        <meshStandardMaterial color="#f8fafc" emissive={color} emissiveIntensity={0.5} />
      </mesh>
      <mesh ref={packetRef}>
        <sphereGeometry args={[0.028, 8, 8]} />
        <meshStandardMaterial color="#fff" emissive="#38bdf8" emissiveIntensity={1.2} />
      </mesh>
      {loose && (
        <Html position={curve.getPointAt(0.5)} distanceFactor={10} style={{ pointerEvents: 'none' }}>
          <div className="dc-3d-chip">Drag to unplug</div>
        </Html>
      )}
    </group>
  )
}

function CablePhysicsBits({ anchors }) {
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

function rackPosition(index) {
  return {
    x: (index % 4) * 1.4 - 2.1,
    z: Math.floor(index / 4) * -2.2 - 0.5,
  }
}

function RackInner({
  rack, servers, selectedId, expanded, onSelectRack, onSelectServer, onOpenBmc, tip, animBoost,
}) {
  const anyFail = servers.some((s) => Object.values(s.components || {}).some((c) => c !== 'healthy'))
  const group = useRef()
  const open = expanded || servers.some((s) => s.id === selectedId)

  useFrame(({ clock }) => {
    if (!group.current || !tip) return
    group.current.rotation.z = Math.sin(clock.elapsedTime * 1.8) * 0.035
  })

  return (
    <group
      ref={group}
      onClick={(e) => { e.stopPropagation(); onSelectRack?.(rack.id) }}
    >
      <RoundedBox args={[RACK_W, RACK_H, RACK_D]} radius={0.02} castShadow receiveShadow>
        <meshStandardMaterial
          color={anyFail ? '#3f1d1d' : '#0f141f'}
          metalness={0.55}
          roughness={0.35}
          emissive={anyFail ? '#7f1d1d' : '#0ea5e9'}
          emissiveIntensity={anyFail ? 0.28 : open ? 0.08 : 0.02}
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

function SceneContent({
  racks, serversByRack, network, cooling, pdus, selectedId, expandedRack,
  onSelectServer, onSelectRack, onOpenBmc, onUnplugCable, physicsEnabled, onFps, animBoost, intro,
}) {
  const thermalStress = useMemo(() => {
    const units = cooling || []
    if (!units.length) return 0
    const failed = units.filter((c) => c.status !== 'running').length
    const hot = units.filter((c) => Number(c.temp_c) > 28).length
    return Math.min(1, failed / units.length + hot * 0.15)
  }, [cooling])

  const switchCount = (network?.switches || []).length
  const mdfPos = useMemo(() => new THREE.Vector3(5.5, 1.05, -1.2), [])

  const cables = useMemo(() => {
    const links = []
    racks.forEach((rack, i) => {
      // Always draw plant cabling — not only when switch inventory is seeded.
      if (switchCount === 0 && i > 8) return
      const { x: sx, z: sz } = rackPosition(i)
      const srvList = serversByRack[rack.id] || []
      const srv = srvList[0]
      const loose = (srv?.hardware?.cables || []).some((c) => c.status === 'loose' || c.status === 'damaged')
      const tray = new THREE.Vector3(sx, 2.45, -1.6)
      links.push({
        id: `${rack.id}-to-tray`,
        from: new THREE.Vector3(sx, 1.65, sz + RACK_D / 2),
        to: tray,
        loose,
        color: loose ? '#f59e0b' : '#22d3ee',
      })
      links.push({
        id: `${rack.id}-tray-mdf`,
        from: tray,
        to: mdfPos.clone(),
        loose: false,
        color: '#38bdf8',
      })
      srvList.slice(0, 2).forEach((s, si) => {
        const uy = ((s.u_slot || (si + 1)) - 1) * U_H - RACK_H / 2 + U_H / 2
        links.push({
          id: `${s.id}-nic0`,
          from: new THREE.Vector3(sx + RACK_W * 0.2, uy + RACK_H / 2, sz + RACK_D / 2),
          to: new THREE.Vector3(sx, 1.55, sz + RACK_D / 2 + 0.08),
          loose: (s.hardware?.cables || []).some((c) => c.status === 'loose'),
          color: '#a78bfa',
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
      <CameraIntro enabled={intro} />
      <color attach="background" args={['#0b0e14']} />
      <fog attach="fog" args={['#0b0e14', 12, 32]} />
      <ambientLight intensity={0.28} />
      <directionalLight castShadow position={[6, 10, 4]} intensity={0.95} shadow-mapSize={[1024, 1024]} />
      <directionalLight position={[-4, 6, -6]} intensity={0.35} color="#94a3b8" />
      <PulsingLight />
      <Environment preset="warehouse" />
      <Floor />
      <CeilingLights />
      <CableTray />
      <HotAisleGlow z={-1.6} />
      <HotAisleGlow z={-3.8} />
      {animBoost > 0 && (
        <AirflowParticles
          count={Math.round(140 * animBoost * (1 + thermalStress))}
          stress={thermalStress}
        />
      )}
      <CracUnits cooling={cooling} />
      <PduStrips racks={racks} pdus={pdus} />

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
          />
        ))}
      </Bvh>

      {cables.map((c) => (
        <CableStrand
          key={c.id}
          from={c.from}
          to={c.to}
          color={c.color}
          loose={c.loose}
          traffic={animBoost > 0}
          onUnplug={c.loose ? () => onUnplugCable?.(c.id) : undefined}
        />
      ))}

      {physicsEnabled && <CablePhysicsBits anchors={cableAnchors} />}

      <ContactShadows position={[0, 0.01, 0]} opacity={0.45} scale={22} blur={2.2} far={8} />
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        maxPolarAngle={Math.PI * 0.48}
        minDistance={3}
        maxDistance={18}
        target={[1, 0.8, -1.5]}
      />
    </>
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

export default function DatacenterTwin3D({
  racks = [],
  serversByRack = {},
  network,
  cooling = [],
  pdus = [],
  selectedServerId,
  expandedRack,
  onSelectServer,
  onSelectRack,
  onOpenBmc,
  onUnplugCable,
}) {
  const [physicsEnabled, setPhysicsEnabled] = useState(true)
  const [animBoost, setAnimBoost] = useState(1)
  const [intro, setIntro] = useState(true)
  const [fps, setFps] = useState(0)

  useEffect(() => {
    if (!intro) return undefined
    const id = setTimeout(() => setIntro(false), 2400)
    return () => clearTimeout(id)
  }, [intro])

  return (
    <motion.div
      className="dc-3d-root"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.45 }}
    >
      <div className="dc-3d-toolbar">
        <span className="dc-twin-title">3D Lab Twin · plant-linked</span>
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
        <button type="button" className="dc-btn-outline dc-btn-xs" onClick={() => setIntro(true)}>
          Replay intro
        </button>
        <span className="dc-muted">
          ~{fps || '—'} FPS · drag loose cables to unplug · double-click chassis → BMC
        </span>
      </div>
      <div className="dc-3d-canvas-wrap">
        <Suspense fallback={<LoadingFallback />}>
          <Canvas
            shadows
            dpr={[1, Math.min(2, typeof window !== 'undefined' ? window.devicePixelRatio : 1.5)]}
            camera={{ position: [12, 9, 14], fov: 42, near: 0.1, far: 80 }}
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
                physicsEnabled={physicsEnabled}
                onFps={setFps}
                animBoost={animBoost}
                intro={intro}
              />
            </Physics>
          </Canvas>
        </Suspense>
      </div>
    </motion.div>
  )
}
