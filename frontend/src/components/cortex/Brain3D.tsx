import React, { Suspense, useMemo, useRef, useState, type ReactNode } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useGLTF, ContactShadows } from '@react-three/drei';
import * as THREE from 'three';
import type { BrainRegions, TribeNeurologicalMetrics } from '@/types/simulation';

// ─── colors ────────────────────────────────────────────────────────

const REGION_HEX: Record<string, string> = {
  prefrontal_cortex: '#4a9eff',
  anterior_cingulate: '#ffb74d',
  hippocampus: '#81c784',
  amygdala: '#ef5350',
  insula: '#ce93d8',
  temporoparietal_junction: '#4dd0e1',
};

const REGION_POSITIONS: Record<string, [number, number, number]> = {
  prefrontal_cortex: [0, 48, 32],
  anterior_cingulate: [0, 22, 18],
  hippocampus: [-26, -16, -12],
  amygdala: [-22, -4, -16],
  insula: [38, 6, 0],
  temporoparietal_junction: [46, -42, 14],
};

// ─── WebGL check ────────────────────────────────────────────────────

function hasWebGL(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch { return false; }
}

// ─── Brain mesh with vertex colors ──────────────────────────────────

function BrainMesh() {
  const { scene } = useGLTF('/brain.glb');
  const processed = useMemo(() => {
    const cloned = scene.clone();
    cloned.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.material = new THREE.MeshStandardMaterial({
          vertexColors: true,
          roughness: 0.45,
          metalness: 0.02,
        });
      }
    });
    return cloned;
  }, [scene]);
  return <primitive object={processed} />;
}

// ─── Glowing region sphere ──────────────────────────────────────────

function GlowSphere({
  position,
  color,
  value,
  mirrored,
}: {
  position: [number, number, number];
  color: string;
  value: number;
  mirrored?: boolean;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const pos: [number, number, number] = mirrored
    ? [-position[0], position[1], position[2]]
    : position;
  const radius = 3 + value * 4;
  const opacity = 0.35 + value * 0.5;
  const emissiveIntensity = 0.3 + value * 0.5;

  useFrame(({ clock }) => {
    if (ref.current) {
      const pulse = 1 + Math.sin(clock.elapsedTime * 2.5) * 0.12 * (0.5 + value * 0.5);
      ref.current.scale.setScalar(pulse);
      const mat = ref.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = emissiveIntensity * (0.85 + Math.sin(clock.elapsedTime * 3) * 0.15);
    }
  });

  return (
    <mesh ref={ref} position={pos}>
      <sphereGeometry args={[radius, 32, 32]} />
      <meshStandardMaterial
        color={color}
        transparent
        opacity={opacity}
        emissive={color}
        emissiveIntensity={emissiveIntensity}
        roughness={0.2}
      />
    </mesh>
  );
}

// ─── Brain scene ────────────────────────────────────────────────────

function BrainScene({ regions, paused }: { regions: BrainRegions | null; paused: boolean }) {
  const controlsRef = useRef<any>(null);

  useFrame(() => {
    if (controlsRef.current && !paused) {
      controlsRef.current.autoRotate = true;
      controlsRef.current.autoRotateSpeed = 0.35;
    }
  });

  const spheres = useMemo(() => {
    if (!regions) return [];
    return Object.entries(REGION_POSITIONS).map(([key, basePos]) => ({
      key,
      position: basePos,
      color: REGION_HEX[key] ?? '#888',
      value: regions[key as keyof BrainRegions] ?? 0.05,
    }));
  }, [regions]);

  return (
    <>
      <color attach="background" args={['#0a0e14']} />

      <OrbitControls
        ref={controlsRef}
        enablePan
        enableZoom
        minDistance={50}
        maxDistance={250}
        autoRotate
        autoRotateSpeed={0.35}
        target={[0, -10, 10]}
      />

      <ambientLight intensity={0.7} />
      <hemisphereLight args={['#ccddff', '#334455', 0.8]} />
      <directionalLight position={[60, 60, 60]} intensity={1.4} color="#ffffff" />
      <directionalLight position={[-40, 10, -50]} intensity={0.6} color="#cc9966" />

      <Suspense fallback={
        // Loading indicator — shows while GLB loads
        <mesh>
          <sphereGeometry args={[20, 16, 16]} />
          <meshBasicMaterial color="#1a2a4a" wireframe />
        </mesh>
      }>
        <group scale={[0.7, 0.7, 0.7]} position={[0, 5, 0]}>
          <BrainMesh />
        </group>
      </Suspense>

      {spheres.map((s) => (
        <React.Fragment key={s.key}>
          <GlowSphere position={s.position} color={s.color} value={s.value} />
          <GlowSphere position={s.position} color={s.color} value={s.value * 0.88} mirrored />
        </React.Fragment>
      ))}

      <ContactShadows position={[0, -68, 0]} opacity={0.15} scale={120} blur={3} far={80} />
    </>
  );
}

// ─── Public component ───────────────────────────────────────────────

export const Brain3D = ({
  regions,
  metrics,
}: {
  regions?: BrainRegions | null;
  metrics?: TribeNeurologicalMetrics | null;
}) => {
  const [paused, setPaused] = useState(false);
  const [status, setStatus] = useState<'checking' | 'ready' | 'error'>('checking');

  const webglOk = useMemo(() => hasWebGL(), []);

  function handleCreated() { setStatus('ready'); }
  function handleError() { setStatus('error'); }

  if (!webglOk) {
    return (
      <div className="rounded-[20px] border border-white/[0.08] bg-bg-deep/45 p-6 h-[420px] flex items-center justify-center">
        <p className="text-[12px] text-text-muted">WebGL not available — using 2D brain below</p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="rounded-[20px] border border-white/[0.08] bg-bg-deep/45 p-6 h-[420px] flex items-center justify-center">
        <p className="text-[12px] text-text-muted">3D brain unavailable — using 2D</p>
      </div>
    );
  }

  return (
    <div
      className="relative h-[420px] w-full rounded-[28px] border border-white/10 bg-[#0a0e14] overflow-hidden"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <Canvas
        camera={{ position: [0, 20, 130], fov: 35, near: 1, far: 600 }}
        gl={{ antialias: true, alpha: false, preserveDrawingBuffer: true }}
        dpr={[1, 1.5]}
        onCreated={handleCreated}
        onError={handleError}
      >
        <BrainScene regions={regions ?? null} paused={paused} />
      </Canvas>

      {status === 'checking' && (
        <div className="absolute inset-0 flex items-center justify-center z-20 pointer-events-none bg-[#0a0e14]/50">
          <p className="text-[12px] text-text-muted">Initializing 3D brain...</p>
        </div>
      )}

      {regions && (
        <div className="absolute bottom-3 left-3 right-3 flex flex-wrap gap-1.5 pointer-events-none z-10">
          {Object.entries(REGION_HEX).map(([key, hex]) => {
            const value = regions[key as keyof BrainRegions] ?? 0;
            const label = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
            return (
              <div key={key} className="rounded-[6px] border border-white/[0.08] bg-black/60 px-2 py-1 text-[9px] font-mono" style={{ color: hex }}>
                {label.split(' ').map(w => w[0]).join('')} {value.toFixed(2)}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
