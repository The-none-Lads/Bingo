import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/games': 'http://localhost:8000',
      '/cards': 'http://localhost:8000',
      '/validate': 'http://localhost:8000'
    }
  }
})

