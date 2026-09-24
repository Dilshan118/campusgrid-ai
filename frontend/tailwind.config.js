/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        page: token('page'),
        surface: { DEFAULT: token('surface'), 2: token('surface-2'), 3: token('surface-3') },
        ink: { DEFAULT: token('ink'), 2: token('ink-2'), 3: token('ink-3') },
        line: { DEFAULT: token('line'), strong: token('line-strong') },
        accent: { DEFAULT: token('accent'), hover: token('accent-hover'), text: token('accent-text'), soft: token('accent-soft') },
        good: { DEFAULT: token('good'), text: token('good-text'), soft: token('good-soft') },
        warn: { DEFAULT: token('warn'), text: token('warn-text'), soft: token('warn-soft') },
        critical: { DEFAULT: token('critical'), text: token('critical-text'), soft: token('critical-soft') },
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
