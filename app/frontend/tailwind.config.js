/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter Variable', 'Inter', 'SF Pro Display', '-apple-system', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['Berkeley Mono', 'ui-monospace', 'SF Mono', 'Menlo', 'monospace'],
      },
      colors: {
        surface: {
          0: '#08090a',
          1: '#0f1011',
          2: '#191a1b',
          3: '#28282c',
        },
        txt: {
          1: '#f7f8f8',
          2: '#d0d6e0',
          3: '#8a8f98',
          4: '#62666d',
        },
        accent: {
          DEFAULT: '#5e6ad2',
          light: '#7170ff',
          hover: '#828fff',
          muted: '#7a7fad',
        },
        border: {
          subtle: 'rgba(255,255,255,0.05)',
          DEFAULT: 'rgba(255,255,255,0.08)',
          solid: '#23252a',
          mid: '#34343a',
        },
        success: '#27a644',
        emerald: '#10b981',
      },
      borderRadius: {
        micro: '2px',
        std: '4px',
        btn: '6px',
        card: '8px',
        panel: '12px',
        pill: '9999px',
      },
    },
  },
  plugins: [],
};
