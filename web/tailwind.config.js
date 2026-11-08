/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#355CFF', dark: '#2A49D4', soft: '#EAF0FF' },
        navy: '#10213E', bg: '#F5F7FB', ink: '#10213E', mute: '#5B6B82', line: '#E3E8F0',
        // ok / warn / bad are text-safe shades (4.5:1 on white). The *-fill shades are for bars, dots and charts.
        ok: '#0E7F61', warn: '#9A5B00', bad: '#C23B3B', 'ok-fill': '#17A67D', 'warn-fill': '#E9A23B',
      },
      fontFamily: { sans: ['"Inter Variable"', 'Inter', 'system-ui', 'sans-serif'] },
      boxShadow: { card: '0 1px 2px rgba(16,33,62,0.05)', pop: '0 8px 24px rgba(16,33,62,0.12)' },
    },
  },
  plugins: [],
}
