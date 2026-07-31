import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/docs': 'http://127.0.0.1:8765',
      '/plugins': 'http://127.0.0.1:8765',
    },
  },
  build: {
    outDir: 'dist',
  },
})
