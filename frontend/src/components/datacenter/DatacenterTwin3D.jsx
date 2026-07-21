/**
 * Phase 7 — Lab Environment 3D digital twin (R3F + Rapier).
 * Lazy-loaded from DatacenterSimulator; CSS 2D floor remains the default.
 */
import { Suspense, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Html, Environment, ContactShadows, RoundedBox } from '@react-three/drei'
import { Physics, RigidBody, BallCollider } from '@react-three/rapier'
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

function Floor() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[24, 16]} />
      <meshStandardMaterial color="#1a1f2e" roughness={0.92} metalness={0.05} />
    </mesh>
  )
}

function HotAisleGlow({ z }) {
  return (
    <mesh position={[0, 0.02, z]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[18, 0.35]} />
      <meshBasicMaterial color="#f97316" transparent opacity={0.12} />
    </mesh>
  )
}

/** Shared box geometry for U-slot chassis (LOD: simple boxes). */
function ServerStack({ servers, onSelect }) {
  const geo = useMemo(() => new THREE.BoxGeometry(RACK_W * 0.88, U_H * 0.9, RACK_D * 0.82), [])
  return (
    <group>
      {servers.map((s) => {
        const failed = Object.values(s.components || {}).some((x) => x !== 'healthy')
        const y = ((s.u_slot || 1) - 1) * U_H + U_H * 0.5 + 0.05
        let color = vendorColor(s.vendor)
        if (s.power_state !== 'on') color = '#475569'
        if (failed) color = '#ef4444'
        return (
          <mesh
            key={s.id}
            geometry={geo}
            position={[0, y, 0]}
            castShadow
            onClick={(e) => { e.stopPropagation(); onSelect?.(s.id) }}
          >
            <meshStandardMaterial
              color={color}
              metalness={0.4}
              roughness={0.4}
              emissive={failed ? '#7f1d1d' : '#000000'}
              emissiveIntensity={failed ? 0.35 : 0}
            />
          </mesh>
        )
      })}
    </group>
  )
}

function CableStrand({ from, to, color = '#94a3b8', loose = false }) {
  const curve = useMemo(() => {
    const mid = new THREE.Vector3().addVectors(from, to).multiplyScalar(0.5)
    mid.y -= loose ? 0.35 : 0.12
    mid.x += loose ? 0.15 : 0
    return new THREE.CatmullRomCurve3([from, mid, to])
  }, [from, to, loose])
  return (
    <mesh>
      <tubeGeometry args={[curve, 16, 0.012, 6, false]} />
      <meshStandardMaterial
        color={color}
        roughness={0.7}
        emissive={loose ? '#b45309' : '#000000'}
        emissiveIntensity={loose ? 0.4 : 0}
      />
    </mesh>
  )
}

function CablePhysicsBits({ anchors }) {
  return (
    <group>
      {anchors.map((a, i) => (
        <RigidBody key={i} position={a} colliders={false} restitution={0.1} linearDamping={2} angularDamping={2}>
          <BallCollider args={[0.04]} />
          <mesh>
            <sphereGeometry args={[0.035, 8, 8]} />
            <meshStandardMaterial color="#64748b" metalness={0.6} />
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

function RackInner({ rack, servers, selectedId, onSelectRack, onSelectServer, tip }) {
  const anyFail = servers.some((s) => Object.values(s.components || {}).some((c) => c !== 'healthy'))
  return (
    <group onClick={(e) => { e.stopPropagation(); onSelectRack?.(rack.id) }}>
      <RoundedBox args={[RACK_W, RACK_H, RACK_D]} radius={0.02} castShadow receiveShadow>
        <meshStandardMaterial
          color={anyFail ? '#3f1d1d' : '#0f141f'}
          metalness={0.55}
          roughness={0.35}
          emissive={anyFail ? '#7f1d1d' : '#000000'}
          emissiveIntensity={anyFail ? 0.25 : 0}
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
      <ServerStack servers={servers} onSelect={onSelectServer} />
      <Html position={[0, RACK_H / 2 + 0.12, 0]} center distanceFactor={8} style={{ pointerEvents: 'none' }}>
        <div className="dc-3d-label">
          {rack.id}
          {tip ? ' · TIP' : ''}
          {rack.physics?.mass_kg ? ` · ${rack.physics.mass_kg}kg` : ''}
        </div>
      </Html>
      {selectedId && servers.some((s) => s.id === selectedId) && (
        <mesh position={[0, 0, RACK_D / 2 + 0.02]}>
          <planeGeometry args={[RACK_W * 1.05, RACK_H * 1.02]} />
          <meshBasicMaterial color="#f97316" transparent opacity={0.15} side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  )
}

function RackMesh({ rack, servers, index, selectedId, onSelectRack, onSelectServer, physicsEnabled }) {
  const tip = rack.physics?.tip_risk === 'high'
  const { x, z } = rackPosition(index)

  if (physicsEnabled && tip) {
    return (
      <RigidBody
        type="dynamic"
        position={[x, RACK_H / 2, z]}
        colliders="cuboid"
        enabledRotations={[false, false, true]}
        linearDamping={4}
        angularDamping={6}
      >
        <RackInner
          rack={rack}
          servers={servers}
          selectedId={selectedId}
          onSelectRack={onSelectRack}
          onSelectServer={onSelectServer}
          tip={tip}
        />
      </RigidBody>
    )
  }

  if (physicsEnabled) {
    return (
      <RigidBody type="fixed" position={[x, RACK_H / 2, z]} colliders="cuboid">
        <RackInner
          rack={rack}
          servers={servers}
          selectedId={selectedId}
          onSelectRack={onSelectRack}
          onSelectServer={onSelectServer}
          tip={tip}
        />
      </RigidBody>
    )
  }

  return (
    <group position={[x, RACK_H / 2, z]} rotation={[0, 0, tip ? 0.08 : 0]}>
      <RackInner
        rack={rack}
        servers={servers}
        selectedId={selectedId}
        onSelectRack={onSelectRack}
        onSelectServer={onSelectServer}
        tip={tip}
      />
    </group>
  )
}

function SceneContent({
  racks, serversByRack, network, selectedId, onSelectServer, onSelectRack, physicsEnabled, onFps,
}) {
  const cables = useMemo(() => {
    const links = []
    const switches = network?.switches || []
    racks.forEach((rack, i) => {
      if (!switches.length) return
      const { x: sx, z: sz } = rackPosition(i)
      const srv = (serversByRack[rack.id] || [])[0]
      const loose = (srv?.hardware?.cables || []).some((c) => c.status === 'loose' || c.status === 'damaged')
      links.push({
        id: `${rack.id}-uplink`,
        from: new THREE.Vector3(sx, 1.6, sz + RACK_D / 2),
        to: new THREE.Vector3(5.5, 1.4, -1.2),
        loose,
        color: loose ? '#f59e0b' : '#38bdf8',
      })
    })
    return links
  }, [racks, serversByRack, network])

  const cableAnchors = useMemo(
    () => cables.map((c) => [
      (c.from.x + c.to.x) / 2,
      Math.max(0.2, (c.from.y + c.to.y) / 2 - 0.2),
      (c.from.z + c.to.z) / 2,
    ]),
    [cables],
  )

  return (
    <>
      <FpsMeter onFps={onFps} />
      <color attach="background" args={['#0b0e14']} />
      <ambientLight intensity={0.35} />
      <directionalLight
        castShadow
        position={[6, 10, 4]}
        intensity={1.15}
        shadow-mapSize={[1024, 1024]}
      />
      <pointLight position={[-4, 3, -2]} intensity={0.4} color="#38bdf8" />
      <Environment preset="warehouse" />
      <Floor />
      <HotAisleGlow z={-1.6} />
      <HotAisleGlow z={-3.8} />

      <group position={[5.5, 0.9, -1.2]}>
        <RoundedBox args={[0.7, 1.8, 0.9]} radius={0.02} castShadow>
          <meshStandardMaterial color="#111827" metalness={0.5} roughness={0.4} />
        </RoundedBox>
        <Html position={[0, 1.05, 0]} center distanceFactor={8} style={{ pointerEvents: 'none' }}>
          <div className="dc-3d-label">MDF / Agg</div>
        </Html>
      </group>

      {racks.map((rack, i) => (
        <RackMesh
          key={rack.id}
          rack={rack}
          index={i}
          servers={serversByRack[rack.id] || []}
          selectedId={selectedId}
          onSelectRack={onSelectRack}
          onSelectServer={onSelectServer}
          physicsEnabled={physicsEnabled}
        />
      ))}

      {cables.map((c) => (
        <CableStrand key={c.id} from={c.from} to={c.to} color={c.color} loose={c.loose} />
      ))}

      {physicsEnabled && <CablePhysicsBits anchors={cableAnchors} />}

      <ContactShadows position={[0, 0.01, 0]} opacity={0.45} scale={22} blur={2.2} far={8} />
      <OrbitControls
        makeDefault
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
  selectedServerId,
  onSelectServer,
  onSelectRack,
}) {
  const [physicsEnabled, setPhysicsEnabled] = useState(true)
  const [fps, setFps] = useState(0)

  return (
    <div className="dc-3d-root">
      <div className="dc-3d-toolbar">
        <span className="dc-twin-title">3D Lab Twin · Orbit drag · click chassis</span>
        <label className="dc-3d-toggle">
          <input
            type="checkbox"
            checked={physicsEnabled}
            onChange={(e) => setPhysicsEnabled(e.target.checked)}
          />
          Rapier physics
        </label>
        <span className="dc-muted">~{fps || '—'} FPS · shared U-geo · cable strands</span>
      </div>
      <div className="dc-3d-canvas-wrap">
        <Suspense fallback={<LoadingFallback />}>
          <Canvas
            shadows
            dpr={[1, 1.75]}
            camera={{ position: [6, 5, 7], fov: 42, near: 0.1, far: 80 }}
            gl={{ antialias: true, powerPreference: 'high-performance' }}
          >
            <Physics gravity={[0, -9.81, 0]} colliders={false} paused={!physicsEnabled}>
              <SceneContent
                racks={racks}
                serversByRack={serversByRack}
                network={network}
                selectedId={selectedServerId}
                onSelectServer={onSelectServer}
                onSelectRack={onSelectRack}
                physicsEnabled={physicsEnabled}
                onFps={setFps}
              />
            </Physics>
          </Canvas>
        </Suspense>
      </div>
    </div>
  )
}
