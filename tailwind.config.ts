import type { Config } from 'tailwindcss'

const config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f2f7ff',
          100: '#e2ecff',
          200: '#c7d9ff',
          300: '#9db9ff',
          400: '#708cff',
          500: '#4b5ff1',
          600: '#3846d4',
          700: '#2f39a8',
          800: '#2a3488',
          900: '#232a69'
        },
        slate: {
          950: '#0b1120'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif']
      }
    }
  },
  plugins: []
} satisfies Config

export default config
