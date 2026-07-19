import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// Dev: проксируем /api на FastAPI (python app.py, :8000).
// Build: статика собирается в ../static/dist — её раздаёт FastAPI.
export default defineConfig({
  // По умолчанию корень "/" (Vercel: статика в корне CDN). Docker/FastAPI раздаёт под
  // /app/ — там Dockerfile задаёт VITE_BASE=/app/ на этапе сборки.
  base: process.env.VITE_BASE || "/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
})
