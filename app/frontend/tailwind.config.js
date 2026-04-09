/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'SF Pro Display', '-apple-system', 'system-ui', 'Segoe UI', 'Roboto', 'PingFang SC', 'sans-serif'],
        mono: ['SF Mono', 'ui-monospace', 'Menlo', 'monospace'],
      },
      colors: {
        surface: {
          0: '#f7f7f5',
          1: '#ffffff',
          2: '#ffffff',
          3: '#f1f1ef',
        },
        txt: {
          1: '#37352f',
          2: '#55534e',
          3: '#787774',
          4: '#acaba9',
        },
        accent: {
          DEFAULT: '#5e6ad2',
          light: '#6c72cb',
          hover: '#4f5bc6',
          soft: '#eef0ff',
        },
        border: {
          subtle: '#f0efed',
          DEFAULT: '#e3e2e0',
          solid: '#d3d1cb',
          mid: '#c4c3bf',
        },
        success: '#2ea44f',
        emerald: '#0d9373',
      },
      borderRadius: {
        micro: '3px',
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
