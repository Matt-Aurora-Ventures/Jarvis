import { useState, useEffect } from 'react'

/**
 * Breakpoint definitions (matches Tailwind CSS)
 */
export const BREAKPOINTS = {
  xs: 0,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
}

/**
 * useMediaQuery Hook
 * Returns true if the media query matches
 *
 * @param {string} query - CSS media query string
 * @returns {boolean} - Whether the query matches
 */
export function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia(query).matches
  })

  useEffect(() => {
    if (typeof window === 'undefined') return

    const mediaQuery = window.matchMedia(query)
    setMatches(mediaQuery.matches)

    const handler = (event) => setMatches(event.matches)

    // Use addListener for older browsers
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handler)
    } else {
      mediaQuery.addListener(handler)
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handler)
      } else {
        mediaQuery.removeListener(handler)
      }
    }
  }, [query])

  return matches
}

/**
 * useBreakpoint Hook
 * Returns the current breakpoint name
 *
 * @returns {string} - Current breakpoint ('xs', 'sm', 'md', 'lg', 'xl', '2xl')
 */
export function useBreakpoint() {
  const [breakpoint, setBreakpoint] = useState('md')

  useEffect(() => {
    if (typeof window === 'undefined') return

    const updateBreakpoint = () => {
      const width = window.innerWidth
      if (width < BREAKPOINTS.sm) setBreakpoint('xs')
      else if (width < BREAKPOINTS.md) setBreakpoint('sm')
      else if (width < BREAKPOINTS.lg) setBreakpoint('md')
      else if (width < BREAKPOINTS.xl) setBreakpoint('lg')
      else if (width < BREAKPOINTS['2xl']) setBreakpoint('xl')
      else setBreakpoint('2xl')
    }

    updateBreakpoint()
    window.addEventListener('resize', updateBreakpoint)
    return () => window.removeEventListener('resize', updateBreakpoint)
  }, [])

  return breakpoint
}

/**
 * useIsMobile Hook
 * Returns true if the viewport is mobile-sized (< 768px)
 *
 * @returns {boolean}
 */
export function useIsMobile() {
  return useMediaQuery(`(max-width: ${BREAKPOINTS.md - 1}px)`)
}

/**
 * useIsTablet Hook
 * Returns true if the viewport is tablet-sized (768px - 1023px)
 *
 * @returns {boolean}
 */
export function useIsTablet() {
  return useMediaQuery(
    `(min-width: ${BREAKPOINTS.md}px) and (max-width: ${BREAKPOINTS.lg - 1}px)`
  )
}

/**
 * useIsDesktop Hook
 * Returns true if the viewport is desktop-sized (>= 1024px)
 *
 * @returns {boolean}
 */
export function useIsDesktop() {
  return useMediaQuery(`(min-width: ${BREAKPOINTS.lg}px)`)
}

/**
 * useResponsiveValue Hook
 * Returns different values based on breakpoint
 *
 * @param {object} values - Object with breakpoint keys
 * @returns {any} - The value for the current breakpoint
 *
 * @example
 * const columns = useResponsiveValue({ xs: 1, sm: 2, md: 3, lg: 4 })
 */
export function useResponsiveValue(values) {
  const breakpoint = useBreakpoint()
  const breakpointOrder = ['xs', 'sm', 'md', 'lg', 'xl', '2xl']

  // Find the value for current breakpoint or the closest smaller one
  const index = breakpointOrder.indexOf(breakpoint)
  for (let i = index; i >= 0; i--) {
    const bp = breakpointOrder[i]
    if (values[bp] !== undefined) {
      return values[bp]
    }
  }

  // Fallback to first defined value
  return values[breakpointOrder.find(bp => values[bp] !== undefined)]
}

/**
 * useOrientation Hook
 * Returns the current device orientation
 *
 * @returns {'portrait' | 'landscape'}
 */
export function useOrientation() {
  const [orientation, setOrientation] = useState('portrait')

  useEffect(() => {
    if (typeof window === 'undefined') return

    const updateOrientation = () => {
      setOrientation(
        window.innerHeight > window.innerWidth ? 'portrait' : 'landscape'
      )
    }

    updateOrientation()
    window.addEventListener('resize', updateOrientation)
    window.addEventListener('orientationchange', updateOrientation)

    return () => {
      window.removeEventListener('resize', updateOrientation)
      window.removeEventListener('orientationchange', updateOrientation)
    }
  }, [])

  return orientation
}

/**
 * usePrefersDarkMode Hook
 * Returns true if the user prefers dark mode
 *
 * @returns {boolean}
 */
export function usePrefersDarkMode() {
  return useMediaQuery('(prefers-color-scheme: dark)')
}

/**
 * usePrefersReducedMotion Hook
 * Returns true if the user prefers reduced motion
 *
 * @returns {boolean}
 */
export function usePrefersReducedMotion() {
  return useMediaQuery('(prefers-reduced-motion: reduce)')
}

/**
 * useHasTouchScreen Hook
 * Returns true if the device has a touch screen
 *
 * @returns {boolean}
 */
export function useHasTouchScreen() {
  const [hasTouch, setHasTouch] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return

    setHasTouch(
      'ontouchstart' in window ||
      navigator.maxTouchPoints > 0 ||
      navigator.msMaxTouchPoints > 0
    )
  }, [])

  return hasTouch
}

export default useMediaQuery
