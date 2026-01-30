/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Venn Brand Colors - Warm Amber Palette
        venn: {
          // Dark tones
          black: '#0a0a0a',      // Near black - deepest
          navy: '#0f1419',       // Deep navy - primary dark
          slate: '#1a1f26',      // Dark slate - secondary dark
          charcoal: '#2d333b',   // Charcoal - tertiary
          // Warm accents (from venn.city)
          amber: '#d4a574',      // Warm amber - primary accent
          copper: '#c9956c',     // Copper - hover accent
          gold: '#e8b886',       // Light gold - highlight
          orange: '#e07a3d',     // Warm orange - attention
          // Supporting colors
          cream: '#f5f0e8',      // Warm cream - light bg
          sand: '#e8e2d9',       // Sand - borders
          // Semantic colors
          success: '#22c55e',    // Green - good
          warning: '#f59e0b',    // Amber - warning
          danger: '#ef4444',     // Red - critical
          info: '#3b82f6',       // Blue - info
          // AI/Intelligence
          purple: '#8b5cf6',     // Purple - AI features
          violet: '#a78bfa',     // Light violet - AI hover
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        'venn': '0 4px 6px -1px rgba(10, 20, 25, 0.15), 0 2px 4px -1px rgba(10, 20, 25, 0.1)',
        'venn-lg': '0 10px 25px -5px rgba(10, 20, 25, 0.2), 0 8px 10px -6px rgba(10, 20, 25, 0.1)',
        'venn-card': '0 1px 3px rgba(10, 20, 25, 0.06), 0 1px 2px rgba(10, 20, 25, 0.04)',
        'venn-glow': '0 0 40px rgba(212, 165, 116, 0.15)',
        'venn-glow-sm': '0 0 20px rgba(212, 165, 116, 0.1)',
      },
      borderRadius: {
        'venn': '12px',
        'venn-lg': '16px',
        'venn-xl': '20px',
      },
      backgroundImage: {
        'venn-gradient': 'linear-gradient(135deg, #0f1419 0%, #1a1f26 50%, #0f1419 100%)',
        'venn-gradient-warm': 'linear-gradient(135deg, rgba(212, 165, 116, 0.1) 0%, transparent 50%, rgba(212, 165, 116, 0.05) 100%)',
        'venn-radial-glow': 'radial-gradient(ellipse at top center, rgba(212, 165, 116, 0.15) 0%, transparent 50%)',
      },
    },
  },
  plugins: [],
}
