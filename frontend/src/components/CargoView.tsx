import { useEffect, useMemo, useRef } from 'react'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Edges, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import type { Route, Vehicle } from '../protocol/contract'
import type { Derived } from '../lib/derive'
import { placeBox, vehicleScene, type SceneBox } from '../lib/geometry'
import { stopColor } from '../lib/palette'

interface Props {
  vehicle: Vehicle
  route: Route | null
  derived: Derived
  /** 已卸下的箱件 ID（按当前步骤） */
  unloadedIds: Set<string>
  currentBoxId: string | null
  selectedBoxId: string | null
  onSelectBox: (id: string | null) => void
  resetKey: number
  /** 额外高亮的箱件（修复事件联动） */
  highlightIds?: Set<string>
}

/** 码头黄黑斜纹贴图，只用于后门标记。 */
function useHazardTexture() {
  return useMemo(() => {
    const c = document.createElement('canvas')
    c.width = 64
    c.height = 64
    const g = c.getContext('2d')!
    g.fillStyle = '#f2b600'
    g.fillRect(0, 0, 64, 64)
    g.fillStyle = '#1c1c1c'
    g.beginPath()
    for (let i = -64; i < 128; i += 64) {
      g.moveTo(i, 64)
      g.lineTo(i + 32, 64)
      g.lineTo(i + 64, 0)
      g.lineTo(i + 32, 0)
      g.closePath()
    }
    g.fill()
    const t = new THREE.CanvasTexture(c)
    t.wrapS = t.wrapT = THREE.RepeatWrapping
    t.colorSpace = THREE.SRGBColorSpace
    return t
  }, [])
}

/** 画布文字 → 精灵；用于车头/后门方位标签。 */
function TextSprite({ text, position, widthM = 0.7 }: { text: string; position: [number, number, number]; widthM?: number }) {
  const texture = useMemo(() => {
    const c = document.createElement('canvas')
    c.width = 256
    c.height = 80
    const g = c.getContext('2d')!
    g.fillStyle = 'rgba(255,255,255,0.88)'
    g.fillRect(0, 0, c.width, c.height)
    g.fillStyle = '#4f5b68'
    g.font = '500 36px Barlow, "Microsoft YaHei", sans-serif'
    g.textAlign = 'center'
    g.textBaseline = 'middle'
    g.fillText(text, c.width / 2, c.height / 2 + 2)
    const t = new THREE.CanvasTexture(c)
    t.colorSpace = THREE.SRGBColorSpace
    return t
  }, [text])
  return (
    <sprite position={position} scale={[widthM, widthM * (80 / 256), 1]}>
      <spriteMaterial map={texture} depthTest={false} />
    </sprite>
  )
}

function CameraRig({ vehicle }: { vehicle: Vehicle }) {
  const { camera } = useThree()
  const controls = useRef<OrbitControlsImpl>(null)
  const { size, center } = vehicleScene(vehicle)
  useEffect(() => {
    const [L, H, W] = size
    camera.position.set(-L * 0.9 - 1.2, H * 1.4 + 0.8, W * 1.5 + 1.2)
    camera.near = 0.05
    camera.far = 200
    camera.updateProjectionMatrix()
    if (controls.current) {
      controls.current.target.set(center[0], center[1], center[2])
      controls.current.update()
    }
  }, [camera, size, center])
  return <OrbitControls ref={controls} makeDefault enableDamping={false} minDistance={0.5} maxDistance={60} />
}

function Truck({ vehicle }: { vehicle: Vehicle }) {
  const { size, center } = vehicleScene(vehicle)
  const [L, H, W] = size
  const stripe = useHazardTexture()
  stripe.repeat.set(Math.max(1, Math.round(W / 0.25)), 1)
  return (
    <group>
      {/* 车厢线框 */}
      <mesh position={center}>
        <boxGeometry args={size} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
        <Edges color="#4f5b68" lineWidth={1} />
      </mesh>
      {/* 地板 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[L / 2, -0.002, W / 2]}>
        <planeGeometry args={[L, W]} />
        <meshStandardMaterial color="#dfe4ea" roughness={1} />
      </mesh>
      {/* 后门：x=0 处的黄黑斜纹地槛 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0.06, 0.001, W / 2]}>
        <planeGeometry args={[0.12, W]} />
        <meshBasicMaterial map={stripe} />
      </mesh>
      <TextSprite text="后门 x=0" position={[0, H + 0.18, W / 2]} widthM={0.42} />
      <TextSprite text="车头" position={[L, H + 0.18, W / 2]} widthM={0.3} />
    </group>
  )
}

function BoxMesh({
  sb,
  color,
  state,
  onClick,
}: {
  sb: SceneBox
  color: string
  state: 'normal' | 'unloaded' | 'current' | 'selected'
  onClick: () => void
}) {
  const unloaded = state === 'unloaded'
  const emphasised = state === 'current' || state === 'selected'
  const meshRef = useRef<THREE.Mesh>(null)
  const matRef = useRef<THREE.MeshStandardMaterial>(null)
  // 卸货动画：已卸箱件沿 −x 从后门滑出车厢并淡出；尊重系统「减少动态效果」设置
  const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const target = useMemo<[number, number, number]>(
    () => (unloaded ? [-(sb.size[0] / 2) - 0.45, sb.center[1], sb.center[2]] : sb.center),
    [unloaded, sb],
  )
  const targetOpacity = unloaded ? 0.12 : 1
  useFrame((_, dt) => {
    const m = meshRef.current
    const mat = matRef.current
    if (!m || !mat) return
    const k = reduced ? 1 : Math.min(1, dt * 7)
    m.position.x += (target[0] - m.position.x) * k
    m.position.y += (target[1] - m.position.y) * k
    m.position.z += (target[2] - m.position.z) * k
    mat.opacity += (targetOpacity - mat.opacity) * k
    mat.depthWrite = mat.opacity > 0.5
  })
  return (
    <mesh
      ref={meshRef}
      position={sb.center}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      onPointerOver={(e) => {
        e.stopPropagation()
        document.body.style.cursor = 'pointer'
      }}
      onPointerOut={() => {
        document.body.style.cursor = ''
      }}
    >
      <boxGeometry args={sb.size} />
      <meshStandardMaterial
        ref={matRef}
        color={color}
        transparent
        opacity={1}
        roughness={0.85}
        metalness={0}
        emissive={emphasised ? '#ffffff' : '#000000'}
        emissiveIntensity={emphasised ? 0.25 : 0}
      />
      {sb.box.fragile ? (
        <Edges color="#d03b3b" lineWidth={2} />
      ) : (
        <Edges color={emphasised ? '#1c2733' : '#ffffff'} lineWidth={emphasised ? 2 : 1} />
      )}
    </mesh>
  )
}

export function CargoView({ vehicle, route, derived, unloadedIds, currentBoxId, selectedBoxId, onSelectBox, resetKey, highlightIds }: Props) {
  const sceneBoxes = useMemo(() => {
    if (!route) return [] as SceneBox[]
    return route.placements
      .map((p) => {
        const box = derived.boxesById.get(p.box_id)
        return box ? placeBox(box, p) : null
      })
      .filter((x): x is SceneBox => x !== null)
  }, [route, derived])

  const stopCount = route?.store_ids.length ?? 0

  return (
    <div className="stage-canvas" data-cargo-canvas>
      <Canvas
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true }}
        camera={{ fov: 42 }}
        onPointerMissed={() => onSelectBox(null)}
      >
        <color attach="background" args={['#f3f5f7']} />
        <ambientLight intensity={0.9} />
        <directionalLight position={[-4, 8, 6]} intensity={1.1} />
        <directionalLight position={[6, 4, -4]} intensity={0.4} />
        <CameraRig key={`${vehicle.id}-${resetKey}`} vehicle={vehicle} />
        <Truck vehicle={vehicle} />
        {route &&
          sceneBoxes.map((sb) => {
            const idx = route.store_ids.indexOf(sb.box.store_id)
            const state = unloadedIds.has(sb.box.id)
              ? 'unloaded'
              : sb.box.id === currentBoxId
                ? 'current'
                : sb.box.id === selectedBoxId || highlightIds?.has(sb.box.id)
                  ? 'selected'
                  : 'normal'
            return (
              <BoxMesh
                key={sb.box.id}
                sb={sb}
                color={stopColor(idx, stopCount)}
                state={state}
                onClick={() => onSelectBox(sb.box.id)}
              />
            )
          })}
        <gridHelper args={[40, 40, '#d7dde4', '#e6eaef']} position={[0, -0.004, 0]} />
      </Canvas>
    </div>
  )
}
