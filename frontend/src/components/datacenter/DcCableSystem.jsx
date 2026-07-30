/**
 * Interactive plant cabling for the 3D twin:
 * RJ45/DAC/QSFP connectors, sagging tubes, drag-to-unplug + snap-to-plug.
 */
import { useMemo, useRef, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import { RigidBody, BallCollider } from '@react-three/rapier'
import * as THREE from 'three'

export function StatusLed({ position, failed, powered, warning = false, size = 0.018 }) {
  const mat = useRef()
  useFrame(({ clock }) => {
    if (!mat.current) return
    const t = clock.elapsedTime
    if (failed) {
      mat.current.emissiveIntensity = 0.35 + (Math.sin(t * 10) > 0 ? 0.65 : 0)
      mat.current.color.set('#ef4444')
      mat.current.emissive.set('#ef4444')
    } else if (warning) {
      mat.current.emissiveIntensity = 0.3 + (Math.sin(t * 6) > 0 ? 0.55 : 0.1)
      mat.current.color.set('#f59e0b')
      mat.current.emissive.set('#f59e0b')
    } else if (powered) {
      mat.current.emissiveIntensity = 0.55 + Math.sin(t * 2.2) * 0.12
      mat.current.color.set('#34d399')
      mat.current.emissive.set('#34d399')
    } else {
      mat.current.emissiveIntensity = 0.02
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

function PortJack({ position, linked, activity, label }) {
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
      <StatusLed position={[0.018, 0.014, 0.016]} failed={false} powered={linked} warning={!linked} size={0.006} />
      {activity && linked && (
        <StatusLed position={[-0.018, 0.014, 0.016]} failed={false} powered size={0.005} />
      )}
      {label && (
        <Html position={[0, 0.045, 0]} center distanceFactor={14} style={{ pointerEvents: 'none' }}>
          <div className="dc-3d-chip dc-3d-chip-sm">{label}</div>
        </Html>
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
  onUnplug,
  onPlug,
  label,
}) {
  const packetRef = useRef()
  const tipRef = useRef()
  const [dragging, setDragging] = useState(false)
  const [tipOffset, setTipOffset] = useState(() => new THREE.Vector3())
  const [snapFlash, setSnapFlash] = useState(0)
  const [recoil, setRecoil] = useState(0)
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

  const tipWorld = useMemo(() => {
    if (loose || dragging || recoil > 0) {
      const hang = to.clone()
      hang.y -= loose ? 0.55 : 0.08
      hang.x += loose ? 0.22 : 0
      hang.add(tipOffset)
      if (recoil > 0) hang.y -= recoil * 0.25
      return hang
    }
    return to.clone()
  }, [to, loose, dragging, tipOffset, recoil])

  const curve = useMemo(() => {
    const a = from.clone()
    const b = tipWorld.clone()
    const mid1 = new THREE.Vector3().lerpVectors(a, b, 0.33)
    mid1.y -= loose || dragging ? 0.42 : 0.12
    mid1.x += loose ? 0.15 : 0.04
    const mid2 = new THREE.Vector3().lerpVectors(a, b, 0.66)
    mid2.y -= loose || dragging ? 0.55 : 0.18
    return new THREE.CatmullRomCurve3([a, mid1, mid2, b])
  }, [from, tipWorld, loose, dragging])

  const tube = useMemo(
    () => new THREE.TubeGeometry(curve, 36, loose || dragging ? 0.011 : 0.013, 8, false),
    [curve, loose, dragging],
  )

  useFrame(({ clock }, dt) => {
    const t = clock.elapsedTime
    if (packetRef.current && traffic && !loose && !dragging) {
      const u = (t * 0.4) % 1
      packetRef.current.position.copy(curve.getPointAt(u))
      packetRef.current.visible = true
      packetRef.current.material.emissiveIntensity = 0.8 + Math.sin(t * 12) * 0.4
    } else if (packetRef.current) {
      packetRef.current.visible = false
    }
    if (recoil > 0) setRecoil((r) => Math.max(0, r - dt * 2.2))
    if (snapFlash > 0) setSnapFlash((s) => Math.max(0, s - dt * 3))
    if (tipRef.current) tipRef.current.scale.setScalar(1 + snapFlash * 0.35)
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

  const endDrag = (clientX, clientY) => {
    if (!dragStart.current) return
    const started = dragStart.current
    dragStart.current = null
    setDragging(false)
    if (controls) controls.enabled = true
    document.body.style.cursor = 'default'

    const distMoved = Math.hypot(clientX - started.x, clientY - started.y)
    if (distMoved < 18) return

    if (!loose && onUnplug) {
      setRecoil(1)
      setTipOffset(new THREE.Vector3(0.15, -0.35, 0.12))
      onUnplug({ serverId, cableId })
      return
    }
    if (loose && onPlug) {
      const tip = projectPointer(clientX, clientY)
      if (tip.distanceTo(from) < 0.55) {
        setTipOffset(new THREE.Vector3())
        setSnapFlash(1)
        onPlug({ serverId, cableId })
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
      />
      <mesh geometry={tube}>
        <meshStandardMaterial
          color={color}
          emissive={loose ? '#f59e0b' : color}
          emissiveIntensity={loose ? 0.35 : 0.18 + snapFlash * 0.5}
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
            color="#fff"
            emissive={loose ? '#f59e0b' : '#38bdf8'}
            emissiveIntensity={0.9 + snapFlash}
            toneMapped={false}
          />
        </mesh>
      </group>
      <mesh ref={packetRef}>
        <sphereGeometry args={[0.026, 8, 8]} />
        <meshStandardMaterial color="#fff" emissive="#38bdf8" emissiveIntensity={1.1} toneMapped={false} />
      </mesh>
      {(loose || dragging) && (
        <Html position={tipWorld} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
          <div className="dc-3d-chip">
            {dragging ? (loose ? 'Drop on port to plug' : 'Release to unplug') : 'Drag connector'}
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
