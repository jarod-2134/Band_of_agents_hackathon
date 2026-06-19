import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    allowedHosts: true, // Allows ngrok tunnels to pass the host check
    proxy: {
      // Forward all /api calls to the local backend
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Forward all /orgs calls to the local backend
      '/orgs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Forward WebSocket connections to the local backend
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})