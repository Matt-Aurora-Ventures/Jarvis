'use client';

import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';

function useIsMobileLayout(): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(max-width: 1023px)').matches;
  });

  useEffect(() => {
    // Match Tailwind's `lg` breakpoint: < 1024px is "mobile/tablet" for this app.
    const mq = window.matchMedia('(max-width: 1023px)');

    const apply = () => setIsMobile(mq.matches);
    apply();

    // Some older WebViews only support addListener/removeListener.
    const mql: any = mq;
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', apply);
      return () => mql.removeEventListener('change', apply);
    }
    mql.addListener?.(apply);
    return () => mql.removeListener?.(apply);
  }, []);

  return isMobile;
}

export function ResponsiveToaster() {
  const [mounted, setMounted] = useState(false);
  const isMobile = useIsMobileLayout();

  useEffect(() => setMounted(true), []);

  // Sonner is a purely client-side overlay; avoid SSR markup mismatches and ensure
  // we pick the correct position before the first toast paints.
  if (!mounted) return null;

  return (
    <Toaster
      position={isMobile ? 'top-center' : 'bottom-right'}
      offset={isMobile ? { top: 'calc(env(safe-area-inset-top) + 12px)' } : 16}
      toastOptions={{
        style: {
          background: '#1a1a2e',
          color: '#e0e0e0',
          border: '1px solid #2a2a3e',
        },
      }}
      richColors
      expand
    />
  );
}
