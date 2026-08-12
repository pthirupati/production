/**
 * Distance-culled drei Html — skip CSS-projected DOM labels when far from camera.
 * Shared by Twin3D + cable ports so D10 can close an honest half without a sprite atlas.
 */
import { useFrame, useThree } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'

/** Default cull distance for non-faceplate Html overlays (metres). */
export const HTML_LABEL_MAX_DIST = 7

export function DistanceCullingHtml({
  maxDist = HTML_LABEL_MAX_DIST,
  children,
  ...props
}) {
  const group = useRef()
  const { camera } = useThree()
  const worldPos = useMemo(() => new THREE.Vector3(), [])
  useFrame(() => {
    if (!group.current) return
    group.current.getWorldPosition(worldPos)
    group.current.visible = camera.position.distanceTo(worldPos) <= maxDist
  })
  return (
    <group ref={group}>
      <Html {...props}>{children}</Html>
    </group>
  )
}
