/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { claygNoEval } from './vite-plugins/claygl-no-eval.js'

const backend = process.env.VITE_BACKEND_URL ?? 'http://backend:8000'

export default defineConfig({
  plugins: [claygNoEval(), react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/ws': { target: backend, ws: true },
    },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], globals: true },
})
