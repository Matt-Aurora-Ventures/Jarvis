'use client';

import { useTheme } from '@/context/ThemeContext';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useState } from 'react';

export function ThemeToggle() {
    const { theme, toggleTheme, setTheme, mounted } = useTheme();
    const [showMenu, setShowMenu] = useState(false);

    if (!mounted) {
        return (
            <div className="w-10 h-10 rounded-lg bg-theme-dark/30 animate-pulse" />
        );
    }

    return (
        <div className="relative">
            {/* Toggle Button */}
            <button
                onClick={() => setShowMenu(!showMenu)}
                className={`
                    relative w-10 h-10 rounded-lg flex items-center justify-center
                    transition-all duration-300 overflow-hidden
                    border border-theme-border/30 hover:border-theme-cyan/50
                    ${theme === 'dark' ? 'bg-theme-dark/50' : 'bg-white/10'}
                `}
                title={`Current: ${theme} mode`}
            >
                {/* Sun icon for light mode */}
                <Sun
                    className={`
                        absolute w-5 h-5 transition-all duration-300
                        ${theme === 'light'
                            ? 'scale-100 rotate-0 text-amber-500'
                            : 'scale-0 rotate-90 text-theme-muted'}
                    `}
                />
                {/* Moon icon for dark mode */}
                <Moon
                    className={`
                        absolute w-5 h-5 transition-all duration-300
                        ${theme === 'dark'
                            ? 'scale-100 rotate-0 text-theme-cyan'
                            : 'scale-0 -rotate-90 text-theme-muted'}
                    `}
                />
            </button>

            {/* Dropdown Menu */}
            {showMenu && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 z-40"
                        onClick={() => setShowMenu(false)}
                    />

                    {/* Menu */}
                    <div className="absolute right-0 top-12 z-50 w-40 py-2 rounded-lg bg-theme-dark/95 border border-theme-border/50 backdrop-blur-xl shadow-xl">
                        <button
                            onClick={() => {
                                setTheme('light');
                                setShowMenu(false);
                            }}
                            className={`
                                w-full px-4 py-2 flex items-center gap-3 text-left text-sm
                                transition-colors hover:bg-theme-cyan/10
                                ${theme === 'light' ? 'text-theme-cyan' : 'text-theme-muted'}
                            `}
                        >
                            <Sun className="w-4 h-4" />
                            Light
                            {theme === 'light' && (
                                <span className="ml-auto w-2 h-2 rounded-full bg-theme-cyan" />
                            )}
                        </button>

                        <button
                            onClick={() => {
                                setTheme('dark');
                                setShowMenu(false);
                            }}
                            className={`
                                w-full px-4 py-2 flex items-center gap-3 text-left text-sm
                                transition-colors hover:bg-theme-cyan/10
                                ${theme === 'dark' ? 'text-theme-cyan' : 'text-theme-muted'}
                            `}
                        >
                            <Moon className="w-4 h-4" />
                            Dark
                            {theme === 'dark' && (
                                <span className="ml-auto w-2 h-2 rounded-full bg-theme-cyan" />
                            )}
                        </button>

                        <div className="border-t border-theme-border/30 my-1" />

                        <button
                            onClick={() => {
                                // Use system preference
                                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                                setTheme(prefersDark ? 'dark' : 'light');
                                setShowMenu(false);
                            }}
                            className="w-full px-4 py-2 flex items-center gap-3 text-left text-sm text-theme-muted transition-colors hover:bg-theme-cyan/10"
                        >
                            <Monitor className="w-4 h-4" />
                            System
                        </button>
                    </div>
                </>
            )}
        </div>
    );
}

/**
 * Simple inline toggle (for header)
 */
export function ThemeToggleInline() {
    const { theme, toggleTheme, mounted } = useTheme();

    if (!mounted) return null;

    return (
        <button
            onClick={toggleTheme}
            className={`
                relative w-14 h-7 rounded-full transition-colors duration-300
                ${theme === 'dark'
                    ? 'bg-theme-dark/50 border border-theme-border'
                    : 'bg-amber-100 border border-amber-200'}
            `}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
            {/* Slider */}
            <span
                className={`
                    absolute top-0.5 w-6 h-6 rounded-full
                    flex items-center justify-center
                    transition-all duration-300 ease-out
                    ${theme === 'dark'
                        ? 'left-0.5 bg-theme-dark'
                        : 'left-7 bg-white shadow-sm'}
                `}
            >
                {theme === 'dark' ? (
                    <Moon className="w-3.5 h-3.5 text-theme-cyan" />
                ) : (
                    <Sun className="w-3.5 h-3.5 text-amber-500" />
                )}
            </span>
        </button>
    );
}
