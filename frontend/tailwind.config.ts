import type { Config } from 'tailwindcss'

export default {
  content: [
    './app/**/*.{vue,js,ts}'
  ],
  theme: {
    extend: {
      colors: {
        ink: '#212826',
        muted: '#68736e',
        paper: '#f7f1e8',
        milk: '#fffaf1',
        signal: '#b9604b',
        steel: '#526f7a',
        mint: '#87a694',
        denim: '#526f7a',
        brass: '#b8925d',
        plum: '#6f5965',
        line: 'rgba(50, 58, 54, 0.14)'
      },
      fontFamily: {
        sans: ['Manrope', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Newsreader', 'Georgia', 'serif']
      },
      boxShadow: {
        panel: '0 28px 90px rgba(42, 48, 44, 0.14)',
        soft: '0 14px 42px rgba(42, 48, 44, 0.1)'
      }
    }
  }
} satisfies Config
