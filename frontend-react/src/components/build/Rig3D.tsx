import { Component, type ReactNode, useRef } from "react";
import { Canvas, useFrame, type RootState } from "@react-three/fiber";
import { Edges, OrbitControls } from "@react-three/drei";
import type * as THREE from "three";
import { retailerColor } from "../../config";
import { SLOTS, repProduct, type BuildState, type SlotId } from "../../lib/buildConfig";

type Vec3 = [number, number, number];

// Abstract layout of each part inside a tower chassis (code-only geometry).
const LAYOUT: Record<SlotId, { position: Vec3; size: Vec3 }> = {
  mobo: { position: [0.25, 0.45, -0.5], size: [2.2, 2.7, 0.06] },
  cpu: { position: [0.1, 1.0, -0.4], size: [0.55, 0.55, 0.12] },
  cooler: { position: [0.1, 1.0, -0.15], size: [0.8, 0.8, 0.55] },
  ram: { position: [1.15, 0.9, -0.42], size: [0.28, 1.5, 0.1] },
  gpu: { position: [0.05, -0.25, -0.05], size: [2.1, 0.4, 0.85] },
  psu: { position: [0.05, -1.65, 0.0], size: [2.3, 0.7, 1.0] },
  storage: { position: [-1.15, -0.7, 0.35], size: [0.5, 0.45, 0.12] },
  case: { position: [0, 0, 0], size: [3.1, 4.1, 1.5] }, // the frame itself
};

function Bay({
  position,
  size,
  filled,
  color,
  error,
}: {
  position: Vec3;
  size: Vec3;
  filled: boolean;
  color?: string;
  error: boolean;
}) {
  const ref = useRef<THREE.MeshStandardMaterial>(null);
  useFrame((state: RootState) => {
    if (error && ref.current) {
      ref.current.emissiveIntensity = 0.5 + Math.sin(state.clock.elapsedTime * 6) * 0.4;
    }
  });
  const c = error ? "#f43f4b" : color ?? "#3a3a48";
  const active = filled || error;
  return (
    <mesh position={position}>
      <boxGeometry args={size} />
      <meshStandardMaterial
        ref={ref}
        color={active ? c : "#15151d"}
        emissive={active ? c : "#000000"}
        emissiveIntensity={filled ? 0.55 : 0}
        transparent
        opacity={active ? 1 : 0.2}
        wireframe={!active}
        metalness={0.35}
        roughness={0.45}
      />
    </mesh>
  );
}

function Scene({ build, errorSlots }: { build: BuildState; errorSlots: Set<SlotId> }) {
  const caseProduct = repProduct(build.case);
  const caseFilled = !!caseProduct;
  const caseColor = caseFilled
    ? retailerColor(caseProduct!.cheapest_retailer ?? "")
    : "#2a2a36";

  return (
    <>
      <ambientLight intensity={0.55} />
      <pointLight position={[5, 6, 5]} intensity={120} />
      <pointLight position={[-5, -2, 3]} intensity={50} color="#6ba6ff" />
      <pointLight position={[0, 0, 6]} intensity={40} color="#f43f4b" />

      {/* Case frame (edges only so internals stay visible) */}
      <mesh position={LAYOUT.case.position}>
        <boxGeometry args={LAYOUT.case.size} />
        <meshBasicMaterial transparent opacity={0} />
        <Edges
          color={errorSlots.has("case") ? "#f43f4b" : caseColor}
          lineWidth={caseFilled ? 2 : 1}
        />
      </mesh>

      {/* Component bays */}
      {SLOTS.filter((s) => s.id !== "case").map((s) => {
        const product = repProduct(build[s.id]);
        return (
          <Bay
            key={s.id}
            position={LAYOUT[s.id].position}
            size={LAYOUT[s.id].size}
            filled={!!product}
            color={product ? retailerColor(product.cheapest_retailer ?? "") : undefined}
            error={errorSlots.has(s.id)}
          />
        );
      })}

      <OrbitControls
        enablePan={false}
        enableZoom
        minDistance={5}
        maxDistance={12}
        autoRotate
        autoRotateSpeed={0.9}
        minPolarAngle={Math.PI / 4}
        maxPolarAngle={Math.PI / 1.7}
      />
    </>
  );
}

// WebGL can fail (old GPU, blocked context). Catch and show a graceful fallback.
class GLBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export default function Rig3D({
  build,
  errorSlots,
}: {
  build: BuildState;
  errorSlots: Set<SlotId>;
}) {
  const fallback = (
    <div className="grid h-full place-items-center text-center text-sm text-ink-4">
      3D preview unavailable on this device.
    </div>
  );
  return (
    <GLBoundary fallback={fallback}>
      <Canvas camera={{ position: [4.5, 2.5, 6], fov: 45 }} dpr={[1, 1.8]}>
        <Scene build={build} errorSlots={errorSlots} />
      </Canvas>
    </GLBoundary>
  );
}
