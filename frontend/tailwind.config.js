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
          primary: '#111827',    // Pure dark text (Airbnb style)
          secondary: '#FF385C', // Airbnb red accent
          accent: '#717171',    // Neutral gray
          dark: '#FFFFFF',      // Pure white
          darker: '#FFFFFF',    // Pure white
        }
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(0,0,0,0.05), 0 0 10px rgba(0,0,0,0.02)' },
          '100%': { boxShadow: '0 0 10px rgba(0,0,0,0.08), 0 0 20px rgba(0,0,0,0.04)' },
        }
      }
    },
  },
  plugins: [],
}
