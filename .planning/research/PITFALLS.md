# Domain Pitfalls

**Domain:** WebGL/Three.js Premium Trading Dashboard
**Researched:** 2026-02-05
**Confidence:** HIGH (verified with official docs and current sources)

## Critical Pitfalls

Mistakes that cause rewrites, major performance issues, or data corruption.

### Pitfall 1: Three.js Memory Leaks in React Components

**What goes wrong:** WebGL resources (geometries, materials, textures, buffers) are not automatically garbage-collected. Components mount/unmount without disposing resources, causing VRAM leaks that crash browsers after extended use.

**Why it happens:** Developers assume React's cleanup handles everything. Three.js creates GPU-side resources that JavaScript's GC cannot touch. React Three Fiber's automatic disposal can be insufficient for complex scenes.

**Consequences:**
- Browser memory grows unbounded
- GPU memory exhaustion causes WebGL context loss
- Mobile devices crash within minutes
- Users must refresh to recover

**Prevention:**
```typescript
// WRONG - No cleanup
useEffect(() => {
  const texture = new THREE.TextureLoader().load(url);
  material.map = texture;
}, []);

// RIGHT - Proper disposal
useEffect(() => {
  const texture = new THREE.TextureLoader().load(url);
  material.map = texture;
  return () => {
    texture.dispose();
    material.dispose();
    geometry.dispose();
  };
}, []);
```

For GLTF models, traverse and dispose:
```typescript
scene.traverse((object) => {
  if (object.isMesh) {
    object.geometry?.dispose();
    if (Array.isArray(object.material)) {
      object.material.forEach(mat => {
        mat.map?.dispose();
        mat.dispose();
      });
    } else {
      object.material?.map?.dispose();
      object.material?.dispose();
    }
  }
});
```

**Detection:**
- Monitor `renderer.info.memory` - if counts keep growing, you have leaks
- Chrome DevTools > Performance > Memory shows JS heap growth
- GPU memory visible in `chrome://gpu` or browser task manager

**Phase to address:** Phase 1 (Foundation) - establish disposal patterns before any 3D components

**Sources:**
- [Three.js Forum: Dispose things correctly](https://discourse.threejs.org/t/dispose-things-correctly-in-three-js/6534)
- [React Three Fiber: Automatic disposal](https://gracious-keller-98ef35.netlify.app/docs/api/automatic-disposal/)
- [Roger Chi: Tips on preventing memory leak in Three.js](https://roger-chi.vercel.app/blog/tips-on-preventing-memory-leak-in-threejs-scene)

---

### Pitfall 2: setState in Animation Loops Causing 60fps Re-renders

**What goes wrong:** Using React state (`useState`, Redux, Zustand selectors) for values that update every frame causes React to reconcile 60 times per second, destroying performance.

**Why it happens:** React's mental model is declarative - developers naturally reach for state. Three.js operates via mutation in a render loop, fundamentally incompatible with React's diffing.

**Consequences:**
- Frame drops from 60fps to 5-15fps
- Main thread blocked by React reconciliation
- Price updates feel laggy and unresponsive
- Battery drain on mobile devices

**Prevention:**
```typescript
// WRONG - Triggers 60 React re-renders/second
const [position, setPosition] = useState({ x: 0, y: 0 });
useFrame(() => setPosition({ x: Math.sin(clock), y: 0 }));

// RIGHT - Mutate refs directly
const meshRef = useRef();
useFrame((state, delta) => {
  meshRef.current.position.x = Math.sin(state.clock.elapsedTime);
});
return <mesh ref={meshRef} />;

// For state stores, fetch in frame loop, not via selectors
useFrame(() => {
  meshRef.current.position.x = useStore.getState().x;
});
```

**Detection:**
- React DevTools Profiler shows constant re-renders
- `stats-gl` shows frame time spikes
- CPU usage high even for static scenes

**Phase to address:** Phase 1 (Foundation) - architecture decision before any animation code

**Sources:**
- [React Three Fiber: Performance Pitfalls](https://r3f.docs.pmnd.rs/advanced/pitfalls)

---

### Pitfall 3: WebSocket Race Conditions with Price Updates

**What goes wrong:** WebSocket messages arrive during React renders, state updates race with UI updates, stale prices display, or prices "jump" erratically.

**Why it happens:** WebSocket callbacks fire asynchronously. Without synchronization, a rapid stream of price updates can interleave with React's rendering cycle unpredictably.

**Consequences:**
- Displayed price doesn't match actual price (data inconsistency)
- Trades execute at different price than shown
- UI flickers between old and new values
- Lost updates during component mount

**Prevention:**
```typescript
// Event cache pattern - buffer until ready
const eventCache = useRef<PriceUpdate[]>([]);
const isReady = useRef(false);

useEffect(() => {
  const ws = new WebSocket(url);

  ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    if (isReady.current) {
      // Process immediately
      processUpdate(update);
    } else {
      // Buffer until mounted
      eventCache.current.push(update);
    }
  };

  // After mount, flush cache
  isReady.current = true;
  eventCache.current.forEach(processUpdate);
  eventCache.current = [];

  return () => ws.close();
}, []);

// Fetch fresh state after reconnect
const reconnect = () => {
  fetchCurrentPrices().then(syncState);
  connectWebSocket();
};
```

**Detection:**
- Price mismatches between UI and API
- Console logs show out-of-order updates
- Sporadic "jumps" in price display

**Phase to address:** Phase 2 (Data Layer) - establish WebSocket architecture early

**Sources:**
- [Real-time State Management in React Using WebSockets](https://moldstud.com/articles/p-real-time-state-management-in-react-using-websockets-boost-your-apps-performance)
- [Handling Race Conditions in Real-Time Apps](https://dev.to/mattlewandowski93/handling-race-conditions-in-real-time-apps-49c8)

---

### Pitfall 4: WebGL Context Loss Without Recovery

**What goes wrong:** GPU resource pressure, driver issues, or system events cause WebGL context loss. Without handling, the entire 3D scene goes black and never recovers.

**Why it happens:** Browsers can revoke WebGL contexts to free GPU memory. Mobile browsers do this aggressively. Developers don't test for this scenario.

**Consequences:**
- Black/blank canvas with no error visible to user
- Application appears frozen
- Trading dashboard becomes unusable
- Must refresh entire page to recover

**Prevention:**
```typescript
useEffect(() => {
  const canvas = canvasRef.current;

  const handleContextLost = (event: WebGLContextEvent) => {
    event.preventDefault(); // Critical - allows restoration
    console.warn('WebGL context lost, preparing for restore...');
    // Pause rendering, show fallback UI
    setContextLost(true);
  };

  const handleContextRestored = () => {
    console.log('WebGL context restored, reinitializing...');
    // Recreate all WebGL resources
    reinitializeScene();
    setContextLost(false);
  };

  canvas.addEventListener('webglcontextlost', handleContextLost);
  canvas.addEventListener('webglcontextrestored', handleContextRestored);

  return () => {
    canvas.removeEventListener('webglcontextlost', handleContextLost);
    canvas.removeEventListener('webglcontextrestored', handleContextRestored);
  };
}, []);

// Show fallback during recovery
{contextLost && <FallbackPriceDisplay />}
```

**Detection:**
- Test with `WEBGL_lose_context` extension
- Monitor for black canvas states
- Add error boundary around 3D components

**Phase to address:** Phase 1 (Foundation) - must be in base Canvas wrapper

**Sources:**
- [Khronos: HandlingContextLost](https://www.khronos.org/webgl/wiki/HandlingContextLost)
- [MDN: webglcontextrestored event](https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/webglcontextrestored_event)
- [React Three Fiber Discussion #723](https://github.com/pmndrs/react-three-fiber/discussions/723)

---

### Pitfall 5: Next.js SSR/Hydration Errors with WebGL

**What goes wrong:** Three.js code runs during server-side rendering where `window`, `document`, and WebGL APIs don't exist. Hydration fails because server HTML doesn't match client.

**Why it happens:** Next.js renders components on server by default. WebGL is client-only. Without explicit handling, builds fail or hydration mismatches occur.

**Consequences:**
- Build failures with "window is not defined"
- Hydration mismatch warnings/errors
- Blank content until client hydrates
- SEO impact from hydration failures

**Prevention:**
```typescript
// Use dynamic import with SSR disabled
import dynamic from 'next/dynamic';

const TradingChart3D = dynamic(
  () => import('../components/TradingChart3D'),
  {
    ssr: false,
    loading: () => <ChartSkeleton /> // Show while loading
  }
);

// Or use client-only wrapper
'use client';
import { Canvas } from '@react-three/fiber';

// With useEffect guard for any WebGL code
const [mounted, setMounted] = useState(false);
useEffect(() => setMounted(true), []);
if (!mounted) return <Skeleton />;
```

**Detection:**
- Build errors mentioning window/document
- Console hydration warnings
- Content flash on page load

**Phase to address:** Phase 1 (Foundation) - must be first decision for project structure

**Sources:**
- [Next.js: react-hydration-error](https://nextjs.org/docs/messages/react-hydration-error)
- [Next.js Hydration Errors in 2026](https://medium.com/@blogs-world/next-js-hydration-errors-in-2026-the-real-causes-fixes-and-prevention-checklist-4a8304d53702)
- [How to use ThreeJS in React & NextJS](https://dev.to/hnicolus/how-to-use-threejs-in-react-nextjs-4120)

---

## Moderate Pitfalls

Mistakes that cause delays, performance issues, or technical debt.

### Pitfall 6: Object Allocation in Render Loop

**What goes wrong:** Creating new objects (Vector3, Color, Matrix4) every frame causes garbage collection pauses and memory pressure.

**Prevention:**
```typescript
// WRONG - new allocation every frame
useFrame(() => {
  mesh.current.position.lerp(new THREE.Vector3(x, y, z), 0.1);
});

// RIGHT - reuse pre-allocated object
const tempVec = useMemo(() => new THREE.Vector3(), []);
useFrame(() => {
  mesh.current.position.lerp(tempVec.set(x, y, z), 0.1);
});
```

**Phase to address:** Phase 2 (3D Components) - establish pattern in first animation code

**Sources:**
- [React Three Fiber: Performance Pitfalls](https://r3f.docs.pmnd.rs/advanced/pitfalls)

---

### Pitfall 7: Component Mount/Unmount Instead of Visibility Toggle

**What goes wrong:** Conditionally rendering 3D components triggers expensive buffer/shader recompilation on every mount.

**Prevention:**
```typescript
// WRONG - triggers recompilation
{showChart && <PriceChart3D />}

// RIGHT - use visibility
<PriceChart3D visible={showChart} />

// Or use display none for HTML overlays
<div style={{ display: showOverlay ? 'block' : 'none' }}>
  <InfoPanel />
</div>
```

**Phase to address:** Phase 2 (3D Components) - design component API early

---

### Pitfall 8: WebSocket Reconnection Without State Sync

**What goes wrong:** After reconnection, client has stale data. Subscriptions need re-sending. Price state diverges from server.

**Prevention:**
```typescript
const reconnect = async () => {
  // 1. Reconnect socket
  await connectWebSocket();

  // 2. Re-subscribe to all symbols
  currentSubscriptions.forEach(symbol => {
    ws.send(JSON.stringify({ action: 'subscribe', symbol }));
  });

  // 3. Fetch fresh state to fill any gap
  const freshPrices = await fetchCurrentPrices();
  syncState(freshPrices);
};

// Implement exponential backoff
const backoff = (attempt: number) =>
  Math.min(1000 * Math.pow(2, attempt), 30000);
```

**Phase to address:** Phase 2 (Data Layer)

**Sources:**
- [WebSockets for Real-Time Distributed Systems](https://www.geeksforgeeks.org/system-design/websockets-for-real-time-distributed-systems/)

---

### Pitfall 9: No Throttling on High-Frequency Price Updates

**What goes wrong:** Processing every WebSocket message at full speed (100+ updates/second) overwhelms the render pipeline.

**Prevention:**
```typescript
// Throttle to 60fps max (16ms)
const lastUpdate = useRef(0);
const pendingUpdate = useRef<PriceData | null>(null);

const handlePriceUpdate = (data: PriceData) => {
  pendingUpdate.current = data; // Always capture latest

  const now = performance.now();
  if (now - lastUpdate.current >= 16) {
    applyUpdate(pendingUpdate.current);
    lastUpdate.current = now;
  }
};

// Or use requestAnimationFrame for batching
const scheduleUpdate = () => {
  if (!pendingRaf.current) {
    pendingRaf.current = requestAnimationFrame(() => {
      applyAllPendingUpdates();
      pendingRaf.current = null;
    });
  }
};
```

**Phase to address:** Phase 2 (Data Layer)

**Sources:**
- [JavaScript Debounce vs. Throttle](https://www.syncfusion.com/blogs/post/javascript-debounce-vs-throttle)
- [Enhance React Performance: Debounce and Throttle](https://medium.com/front-end-weekly/enhance-react-performance-beginners-guide-to-debounce-and-throttle-650dfd40e0c6)

---

### Pitfall 10: Continuous Render Loop for Static Scenes

**What goes wrong:** Calling `renderer.render()` 60 times per second even when nothing changes wastes CPU/GPU and drains battery.

**Prevention:**
```typescript
// React Three Fiber - use frameloop="demand"
<Canvas frameloop="demand">
  <Scene />
</Canvas>

// Then invalidate only when needed
import { invalidate } from '@react-three/fiber';

const handlePriceChange = (price) => {
  updatePrice(price);
  invalidate(); // Request single re-render
};

// Or use conditional rendering
let needsRender = true;
useFrame(() => {
  if (needsRender) {
    // ... update scene
    needsRender = false;
  }
});
```

**Phase to address:** Phase 1 (Foundation) - configure Canvas correctly from start

**Sources:**
- [100 Three.js Best Practices (2026)](https://www.utsubo.com/blog/threejs-best-practices-100-tips)
- [Three.js Performance Guide](https://gist.github.com/iErcann/2a9dfa51ed9fc44854375796c8c24d92)

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable.

### Pitfall 11: Missing Loading States for Assets

**What goes wrong:** GLTF models, textures, and fonts load asynchronously. Without Suspense boundaries, components crash or show nothing.

**Prevention:**
```typescript
<Suspense fallback={<LoadingSpinner />}>
  <TradingChart3D />
</Suspense>

// Use useLoader for caching
const texture = useLoader(TextureLoader, url);
```

**Phase to address:** Phase 2 (3D Components)

---

### Pitfall 12: Duplicate Material/Geometry Creation

**What goes wrong:** Each mesh instance creates its own material and geometry, wasting memory and compilation time.

**Prevention:**
```typescript
// Share geometry and material across instances
const geom = useMemo(() => new THREE.BoxGeometry(), []);
const mat = useMemo(() => new THREE.MeshStandardMaterial(), []);

return items.map((item, i) => (
  <mesh key={i} geometry={geom} material={mat} position={item.pos} />
));

// For many instances, use instancing
<instancedMesh args={[geometry, material, count]}>
  {/* Set instance matrices */}
</instancedMesh>
```

**Phase to address:** Phase 2 (3D Components)

---

### Pitfall 13: Mobile WebGL Performance Assumptions

**What goes wrong:** Desktop-optimized 3D scenes render at 5fps on mobile devices due to GPU limitations.

**Prevention:**
- Reduce polygon counts by 50-80% for mobile
- Use lower-resolution textures (512px vs 2048px)
- Implement Level of Detail (LOD)
- Reduce draw calls via instancing/batching
- Test on actual mobile devices early

```typescript
const isMobile = /iPhone|iPad|Android/i.test(navigator.userAgent);
const quality = isMobile ? 'low' : 'high';

<Canvas dpr={isMobile ? 1 : [1, 2]}>
  <QualityContext.Provider value={quality}>
    <Scene />
  </QualityContext.Provider>
</Canvas>
```

**Phase to address:** Phase 3 (Polish) - but consider in architecture

**Sources:**
- [WebGL in Mobile Development: Challenges and Solutions](https://blog.pixelfreestudio.com/webgl-in-mobile-development-challenges-and-solutions/)

---

### Pitfall 14: Not Using Delta Time for Animations

**What goes wrong:** Animations run at different speeds on 60Hz vs 120Hz vs 144Hz displays.

**Prevention:**
```typescript
// WRONG - speed depends on refresh rate
useFrame(() => {
  mesh.current.rotation.y += 0.01;
});

// RIGHT - consistent across all displays
useFrame((state, delta) => {
  mesh.current.rotation.y += delta * 0.5; // radians per second
});
```

**Phase to address:** Phase 2 (3D Components)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Foundation (Phase 1) | SSR hydration errors | Use `dynamic import { ssr: false }` from day 1 |
| Foundation (Phase 1) | Context loss not handled | Add event listeners to base Canvas component |
| Foundation (Phase 1) | Continuous render loop | Configure `frameloop="demand"` |
| Data Layer (Phase 2) | WebSocket race conditions | Implement event cache pattern |
| Data Layer (Phase 2) | Price update flooding | Throttle to 60fps max |
| 3D Components (Phase 2) | Memory leaks | Establish dispose patterns in first component |
| 3D Components (Phase 2) | setState in animations | Use refs and direct mutation |
| Interactivity (Phase 3) | Mount/unmount churn | Use visibility toggle |
| Mobile (Phase 3) | Performance collapse | Test on real devices early, implement quality tiers |

---

## Quick Reference: Anti-Pattern Checklist

Before code review, check for these patterns:

- [ ] `useState` or `useSelector` in `useFrame` callback
- [ ] `new THREE.Vector3()` inside render loop
- [ ] Missing `dispose()` calls in useEffect cleanup
- [ ] Conditional rendering of 3D components (`{show && <Mesh />}`)
- [ ] WebSocket message handlers setting state directly
- [ ] Missing `Suspense` boundary around loaders
- [ ] No delta time in animation calculations
- [ ] Canvas without context loss event handlers
- [ ] No `ssr: false` on Three.js dynamic imports

---

## Sources Summary

**Official Documentation:**
- [React Three Fiber: Performance Pitfalls](https://r3f.docs.pmnd.rs/advanced/pitfalls) - VERIFIED, HIGH confidence
- [Khronos WebGL Wiki: HandlingContextLost](https://www.khronos.org/webgl/wiki/HandlingContextLost) - VERIFIED, HIGH confidence
- [Next.js: Hydration Error](https://nextjs.org/docs/messages/react-hydration-error) - VERIFIED, HIGH confidence
- [MDN: webglcontextrestored](https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/webglcontextrestored_event) - VERIFIED, HIGH confidence

**Community Resources:**
- [Three.js Forum Discussions](https://discourse.threejs.org/) - Multiple threads on memory management
- [React Three Fiber GitHub Discussions](https://github.com/pmndrs/react-three-fiber/discussions) - Context loss, disposal patterns
- [100 Three.js Best Practices (2026)](https://www.utsubo.com/blog/threejs-best-practices-100-tips) - Comprehensive optimization guide

**Trading/Real-time Specific:**
- [WebSockets for Real-Time Distributed Systems](https://www.geeksforgeeks.org/system-design/websockets-for-real-time-distributed-systems/)
- [Real-time State Management in React Using WebSockets](https://moldstud.com/articles/p-real-time-state-management-in-react-using-websockets-boost-your-apps-performance)
- [Real-Time Dashboard Performance: WebGL vs Canvas](https://dev3lop.com/real-time-dashboard-performance-webgl-vs-canvas-rendering-benchmarks/)

**Mobile WebGL:**
- [WebGL in Mobile Development](https://blog.pixelfreestudio.com/webgl-in-mobile-development-challenges-and-solutions/)
