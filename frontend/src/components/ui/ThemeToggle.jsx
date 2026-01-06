import React from 'react'
import { Sun, Moon, Monitor } from 'lucide-react'
import { useLocalStorage } from '@/hooks'

/**
 * ThemeToggle - Switch between light/dark/system themes
 */
export function ThemeToggle({ variant = 'icon' }) {
  const [theme, setTheme] = useLocalStorage('theme', 'system')

  // Apply theme on mount and change
  React.useEffect(() => {
    const root = document.documentElement
    
    if (theme === 'system') {
      root.removeAttribute('data-theme')
      // Let CSS media query handle it
    } else {
      root.setAttribute('data-theme', theme)
    }
  }, [theme])

  const themes = [
    { value: 'light', icon: Sun, label: 'Light' },
    { value: 'dark', icon: Moon, label: 'Dark' },
    { value: 'system', icon: Monitor, label: 'System' },
  ]

  const currentTheme = themes.find(t => t.value === theme)
  const CurrentIcon = currentTheme?.icon || Sun

  // Cycle through themes
  const cycleTheme = () => {
    const currentIndex = themes.findIndex(t => t.value === theme)
    const nextIndex = (currentIndex + 1) % themes.length
    setTheme(themes[nextIndex].value)
  }

  if (variant === 'icon') {
    return (
      <button
        onClick={cycleTheme}
        className="btn btn-ghost btn-icon"
        title={`Current: ${currentTheme?.label}. Click to change.`}
        aria-label={`Theme: ${currentTheme?.label}`}
      >
        <CurrentIcon size={20} />
      </button>
    )
  }

  // Full toggle with all options
  return (
    <div 
      className="flex items-center gap-1 p-1 rounded-lg"
      style={{ background: 'var(--bg-tertiary)' }}
      role="radiogroup"
      aria-label="Theme selection"
    >
      {themes.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          onClick={() => setTheme(value)}
          className={`
            flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium
            transition-all duration-200
            ${theme === value ? 'shadow-sm' : ''}
          `}
          style={{
            background: theme === value ? 'var(--bg-primary)' : 'transparent',
            color: theme === value ? 'var(--text-primary)' : 'var(--text-secondary)',
          }}
          role="radio"
          aria-checked={theme === value}
        >
          <Icon size={16} />
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  )
}

/**
 * useTheme hook - Get current theme and setter
 */
export function useTheme() {
  const [theme, setTheme] = useLocalStorage('theme', 'system')

  const resolvedTheme = React.useMemo(() => {
    if (theme !== 'system') return theme
    if (typeof window === 'undefined') return 'light'
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }, [theme])

  return {
    theme,
    setTheme,
    resolvedTheme,
    isDark: resolvedTheme === 'dark',
    isLight: resolvedTheme === 'light',
    isSystem: theme === 'system',
  }
}

export default ThemeToggle
