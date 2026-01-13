# Frontend & UX Improvements (31-45)

## 31. TypeScript Migration

```typescript
// frontend/src/types/index.ts
export interface Trade {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  amount: number;
  price: number;
  status: 'pending' | 'filled' | 'cancelled';
  createdAt: Date;
}

export interface Position {
  symbol: string;
  size: number;
  entryPrice: number;
  unrealizedPnl: number;
}

// Convert App.jsx → App.tsx with proper typing
```

## 32. Enhanced Error Boundaries

```jsx
// frontend/src/components/ErrorBoundary.jsx
import { Component } from 'react';

class ErrorBoundary extends Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('Error caught:', error, info);
    // Send to error tracking service
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-fallback p-8 text-center">
          <h2 className="text-xl font-bold text-red-500">Something went wrong</h2>
          <button onClick={() => this.setState({ hasError: false })} className="mt-4 btn">
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

## 33. Skeleton Loading States

```jsx
// frontend/src/components/ui/Skeleton.jsx
export const Skeleton = ({ className = '', variant = 'text' }) => {
  const baseClass = 'animate-pulse bg-gray-700 rounded';
  const variants = {
    text: 'h-4 w-full',
    circle: 'h-12 w-12 rounded-full',
    rect: 'h-24 w-full',
    card: 'h-32 w-full rounded-lg',
  };
  return <div className={`${baseClass} ${variants[variant]} ${className}`} />;
};

export const TradeSkeleton = () => (
  <div className="space-y-3">
    {[...Array(5)].map((_, i) => (
      <div key={i} className="flex gap-4">
        <Skeleton variant="circle" />
        <div className="flex-1 space-y-2">
          <Skeleton className="w-3/4" />
          <Skeleton className="w-1/2" />
        </div>
      </div>
    ))}
  </div>
);
```

## 34. Form Validation with React Hook Form

```jsx
// frontend/src/components/trading/OrderForm.jsx
import { useForm } from 'react-hook-form';

export const OrderForm = ({ onSubmit }) => {
  const { register, handleSubmit, formState: { errors } } = useForm();

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <input
          {...register('amount', { required: 'Amount required', min: { value: 0.001, message: 'Min 0.001' } })}
          type="number" step="0.001" placeholder="Amount"
          className={`input ${errors.amount ? 'border-red-500' : ''}`}
        />
        {errors.amount && <span className="text-red-500 text-sm">{errors.amount.message}</span>}
      </div>
      <button type="submit" className="btn btn-primary w-full">Place Order</button>
    </form>
  );
};
```

## 35. Keyboard Shortcuts

```jsx
// frontend/src/hooks/useKeyboardShortcuts.js
import { useEffect } from 'react';

export const useKeyboardShortcuts = (shortcuts) => {
  useEffect(() => {
    const handler = (e) => {
      const key = `${e.ctrlKey ? 'ctrl+' : ''}${e.shiftKey ? 'shift+' : ''}${e.key.toLowerCase()}`;
      if (shortcuts[key]) {
        e.preventDefault();
        shortcuts[key]();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [shortcuts]);
};

// Usage: useKeyboardShortcuts({ 'ctrl+k': openSearch, 'ctrl+b': toggleSidebar });
```

## 36. Theme System

```jsx
// frontend/src/contexts/ThemeContext.jsx
import { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggle: () => setTheme(t => t === 'dark' ? 'light' : 'dark') }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
```

## 37. Responsive Design Utilities

```css
/* frontend/src/styles/responsive.css */
.container-responsive {
  @apply w-full px-4 mx-auto;
  @apply sm:max-w-sm md:max-w-md lg:max-w-4xl xl:max-w-6xl;
}

.grid-responsive {
  @apply grid grid-cols-1 gap-4;
  @apply sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4;
}

.hide-mobile { @apply hidden sm:block; }
.hide-desktop { @apply block sm:hidden; }
```

## 38. PWA Support

```json
// frontend/public/manifest.json
{
  "name": "Jarvis Trading",
  "short_name": "Jarvis",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#00d4ff",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

## 39. State Persistence

```js
// frontend/src/stores/persistedStore.js
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const usePersistedStore = create(
  persist(
    (set) => ({
      watchlist: [],
      addToWatchlist: (symbol) => set((s) => ({ watchlist: [...s.watchlist, symbol] })),
      removeFromWatchlist: (symbol) => set((s) => ({ watchlist: s.watchlist.filter(s => s !== symbol) })),
    }),
    { name: 'jarvis-storage' }
  )
);
```

## 40. WebSocket Reconnection

```js
// frontend/src/hooks/useReconnectingWebSocket.js
import { useEffect, useRef, useState } from 'react';

export const useReconnectingWebSocket = (url) => {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeout = useRef(null);

  const connect = () => {
    wsRef.current = new WebSocket(url);
    wsRef.current.onopen = () => setIsConnected(true);
    wsRef.current.onclose = () => {
      setIsConnected(false);
      reconnectTimeout.current = setTimeout(connect, 3000);
    };
  };

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [url]);

  return { ws: wsRef.current, isConnected };
};
```

## 41. Optimistic Updates

```js
// frontend/src/hooks/useOptimisticUpdate.js
export const useOptimisticUpdate = (mutationFn, queryKey) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onMutate: async (newData) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData(queryKey, (old) => [...old, newData]);
      return { previous };
    },
    onError: (err, newData, context) => {
      queryClient.setQueryData(queryKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });
};
```

## 42. Virtual Scrolling

```jsx
// frontend/src/components/VirtualList.jsx
import { useVirtualizer } from '@tanstack/react-virtual';

export const VirtualList = ({ items, renderItem, itemHeight = 50 }) => {
  const parentRef = useRef(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => itemHeight,
  });

  return (
    <div ref={parentRef} className="h-full overflow-auto">
      <div style={{ height: virtualizer.getTotalSize() }} className="relative">
        {virtualizer.getVirtualItems().map((virtualRow) => (
          <div key={virtualRow.key} style={{ position: 'absolute', top: virtualRow.start, height: itemHeight }}>
            {renderItem(items[virtualRow.index], virtualRow.index)}
          </div>
        ))}
      </div>
    </div>
  );
};
```

## 43. Image Optimization

```jsx
// frontend/src/components/OptimizedImage.jsx
export const OptimizedImage = ({ src, alt, width, height, ...props }) => (
  <img
    src={src}
    alt={alt}
    width={width}
    height={height}
    loading="lazy"
    decoding="async"
    {...props}
  />
);
```

## 44. Code Splitting

```jsx
// frontend/src/App.jsx
import { lazy, Suspense } from 'react';

const Trading = lazy(() => import('./pages/Trading'));
const Research = lazy(() => import('./pages/Research'));
const Settings = lazy(() => import('./pages/Settings'));

// In routes:
<Suspense fallback={<LoadingSpinner />}>
  <Route path="/trading" element={<Trading />} />
</Suspense>
```

## 45. Accessibility Improvements

```jsx
// frontend/src/components/AccessibleButton.jsx
export const AccessibleButton = ({ children, onClick, ariaLabel, disabled }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    aria-label={ariaLabel}
    aria-disabled={disabled}
    className="focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
    onKeyDown={(e) => e.key === 'Enter' && onClick?.()}
  >
    {children}
  </button>
);
```
