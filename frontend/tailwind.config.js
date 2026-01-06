/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        jarvis: {
          primary: '#6366F1',    // Indigo (matches V3)
          secondary: '#10B981', // Green success
          accent: '#8B5CF6',    // Purple
          dark: '#F9FAFB',      // Light gray (was dark #1E293B)
          darker: '#FFFFFF',    // White (was dark blue #0F172A)
        }
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px #3B82F6, 0 0 10px #3B82F6' },
          '100%': { boxShadow: '0 0 20px #3B82F6, 0 0 30px #3B82F6' },
        }
      }
    },
  },
  plugins: [],
}
