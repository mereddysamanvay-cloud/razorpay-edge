/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#315BFF', dark: '#2548D6', soft: '#EAF0FF' },
        navy: '#172B4D', bg: '#F7F9FC', ink: '#182B49', mute: '#64748B', line: '#E5EAF2',
        ok: '#19A974', warn: '#E9A23B', bad: '#E05252',
      },
      fontFamily: { sans: ['"Inter Variable"', 'Inter', 'system-ui', 'sans-serif'] },
      boxShadow: { card: '0 1px 2px rgba(23,43,77,0.05)', pop: '0 8px 24px rgba(23,43,77,0.12)' },
    },
  },
  plugins: [],
}
