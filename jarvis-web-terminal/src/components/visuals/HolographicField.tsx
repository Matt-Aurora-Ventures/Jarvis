'use client';

import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Points, PointMaterial } from '@react-three/drei';
import * as random from 'maath/random/dist/maath-random.esm';

function ParticleField(props: any) {
    const ref = useRef<any>(null);
    // Generate 2000 random points in a sphere
    const sphere = useMemo(() => random.inSphere(new Float32Array(2000 * 3), { radius: 1.5 }), []);

    useFrame((state, delta) => {
        if (ref.current) {
            ref.current.rotation.x -= delta / 10;
            ref.current.rotation.y -= delta / 15;
        }
    });

    return (
        <group rotation={[0, 0, Math.PI / 4]}>
            <Points ref={ref} positions={sphere} stride={3} frustumCulled={false} {...props}>
                <PointMaterial
                    transparent
                    color="#22c55e"
                    size={0.005} // Very fine points for premium feel
                    sizeAttenuation={true}
                    depthWrite={false}
                    opacity={0.6}
                />
            </Points>
        </group>
    );
}

export function HolographicField() {
    return (
        <div className="absolute inset-0 -z-10 bg-theme-dark">
            <Canvas camera={{ position: [0, 0, 1] }}>
                <ParticleField />
            </Canvas>
            {/* Overlay gradient for fade effect */}
            <div className="absolute inset-0 bg-gradient-to-t from-theme-dark via-transparent to-transparent opacity-80" />
        </div>
    );
}
