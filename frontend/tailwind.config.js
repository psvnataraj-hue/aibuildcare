/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#1f6feb', dark: '#1a5fd0' },
      },
    },
  },
  plugins: [],
}
