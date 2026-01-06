import { useEffect, useRef, useCallback, useState } from 'react'

/**
 * useInterval - setInterval hook with auto cleanup
 */
export function useInterval(callback, delay, immediate = false) {
  const savedCallback = useRef(callback)

  useEffect(() => {
    savedCallback.current = callback
  }, [callback])

  useEffect(() => {
    if (delay === null) return

    if (immediate) {
      savedCallback.current()
    }

    const id = setInterval(() => savedCallback.current(), delay)
    return () => clearInterval(id)
  }, [delay, immediate])
}

/**
 * useDebounce - Debounce a value
 */
export function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}

/**
 * useToggle - Simple boolean toggle
 */
export function useToggle(initialValue = false) {
  const [value, setValue] = useState(initialValue)
  
  const toggle = useCallback(() => setValue(v => !v), [])
  const setTrue = useCallback(() => setValue(true), [])
  const setFalse = useCallback(() => setValue(false), [])

  return [value, toggle, { setTrue, setFalse, setValue }]
}

// Export all hooks
export { useApi } from './useApi'
export { useWallet } from './useWallet'
export { useSniper } from './useSniper'
export { usePosition } from './usePosition'
export { useLocalStorage } from './useLocalStorage'
export { default as useCapabilities } from './useCapabilities'
