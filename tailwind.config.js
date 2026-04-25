/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  safelist: [
    {
      // This keeps all bg-* and border-* classes with 50/500/600 shades
      pattern: /(bg|border)-(.*)-(500|600)\/30/,
    },
  ],
  plugins: [],
};
