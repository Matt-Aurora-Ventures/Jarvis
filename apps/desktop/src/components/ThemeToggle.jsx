import React from 'react';
import { useTheme } from '../contexts/ThemeContext';

/**
 * Theme toggle button component.
 * Switches between light and dark modes.
 */
export function ThemeToggle({ size = 'md', showLabel = false, className = '' }) {
  const { theme, toggleTheme, isDark } = useTheme();

  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
  };

  const iconSize = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  };

  return (
    <button
      onClick={toggleTheme}
      className={`
        ${sizeClasses[size]}
        flex items-center justify-center gap-2
        rounded-lg
        transition-all duration-200
        ${isDark
          ? 'bg-gray-800 hover:bg-gray-700 text-yellow-400'
          : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
        }
        ${className}
      `}
      aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
      title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
    >
      {isDark ? (
        // Sun icon for switching to light mode
        <svg
          className={iconSize[size]}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      ) : (
        // Moon icon for switching to dark mode
        <svg
          className={iconSize[size]}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      )}
      {showLabel && (
        <span className="text-sm font-medium">
          {isDark ? 'Light' : 'Dark'}
        </span>
      )}
    </button>
  );
}

/**
 * Theme toggle with animated switch appearance.
 */
export function ThemeSwitch({ className = '' }) {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={`
        relative w-14 h-7 rounded-full
        transition-colors duration-300
        ${isDark ? 'bg-gray-700' : 'bg-gray-300'}
        ${className}
      `}
      aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
    >
      {/* Track icons */}
      <span className="absolute inset-0 flex items-center justify-between px-1.5">
        {/* Sun */}
        <svg
          className={`w-4 h-4 transition-opacity ${isDark ? 'opacity-30' : 'opacity-100'}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
            clipRule="evenodd"
          />
        </svg>
        {/* Moon */}
        <svg
          className={`w-4 h-4 transition-opacity ${isDark ? 'opacity-100' : 'opacity-30'}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
      </span>

      {/* Sliding knob */}
      <span
        className={`
          absolute top-0.5 w-6 h-6 rounded-full
          bg-white shadow-md
          transition-transform duration-300 ease-in-out
          ${isDark ? 'translate-x-7' : 'translate-x-0.5'}
        `}
      />
    </button>
  );
}

/**
 * Theme selector dropdown with system option.
 */
export function ThemeSelector({ className = '' }) {
  const { theme, setTheme, useSystemTheme, systemTheme } = useTheme();
  const [isOpen, setIsOpen] = React.useState(false);

  const options = [
    { value: 'light', label: 'Light', icon: 'sun' },
    { value: 'dark', label: 'Dark', icon: 'moon' },
    { value: 'system', label: 'System', icon: 'computer' },
  ];

  const icons = {
    sun: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    ),
    moon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
      </svg>
    ),
    computer: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  };

  const handleSelect = (value) => {
    if (value === 'system') {
      useSystemTheme();
    } else {
      setTheme(value);
    }
    setIsOpen(false);
  };

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center gap-2 px-3 py-2 rounded-lg
          transition-colors
          ${theme === 'dark'
            ? 'bg-gray-800 hover:bg-gray-700 text-gray-200'
            : 'bg-gray-100 hover:bg-gray-200 text-gray-800'
          }
        `}
      >
        {icons[theme === 'dark' ? 'moon' : 'sun']}
        <span className="text-sm font-medium capitalize">{theme}</span>
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className={`
            absolute right-0 mt-2 w-40 rounded-lg shadow-lg z-20
            ${theme === 'dark' ? 'bg-gray-800 border border-gray-700' : 'bg-white border border-gray-200'}
          `}>
            {options.map((option) => (
              <button
                key={option.value}
                onClick={() => handleSelect(option.value)}
                className={`
                  w-full flex items-center gap-2 px-3 py-2 text-left text-sm
                  first:rounded-t-lg last:rounded-b-lg
                  transition-colors
                  ${theme === 'dark'
                    ? 'hover:bg-gray-700 text-gray-200'
                    : 'hover:bg-gray-100 text-gray-800'
                  }
                  ${(theme === option.value || (option.value === 'system' && theme === systemTheme))
                    ? (theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100')
                    : ''
                  }
                `}
              >
                {icons[option.icon]}
                <span>{option.label}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default ThemeToggle;
