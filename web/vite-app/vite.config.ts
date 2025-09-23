import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  server: {
    allowedHosts: ['.modal.host'],
    headers: {
      'X-Frame-Options': 'ALLOWALL',
    },
  },
  plugins: [react(), tailwindcss()],
})
