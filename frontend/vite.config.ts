import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/respaldos': 'http://localhost:8000',
      '/sesion': 'http://localhost:8000',
      '/performance': 'http://localhost:8000',
      '/auditoria': 'http://localhost:8000',
      '/seguridad': 'http://localhost:8000',
    },
  },
  test: { environment: 'jsdom' },
})
