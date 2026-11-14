import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Match FastAPI's 127.0.0.1 bind; localhost resolves to ::1 first here.
    proxy: {
      '/observation-query': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/assessments': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/observations': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/experimental': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/alerts': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/safety-cases': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/analytics': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/reports': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
