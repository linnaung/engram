import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/chat': { target: 'http://127.0.0.1:8420', bypass: (req: any) => { if (req.method === 'GET' && req.headers.accept?.includes('text/html')) return req.url; } },
      '/sessions': 'http://127.0.0.1:8420',
      '/ingest': 'http://127.0.0.1:8420',
      '/recall': 'http://127.0.0.1:8420',
      '/synthesize': 'http://127.0.0.1:8420',
      '/status': 'http://127.0.0.1:8420',
      '/episodes': 'http://127.0.0.1:8420',
      '/concepts': 'http://127.0.0.1:8420',
      '/facts': 'http://127.0.0.1:8420',
      '/beliefs': 'http://127.0.0.1:8420',
      '/context': 'http://127.0.0.1:8420',
      '/simulate': 'http://127.0.0.1:8420',
      '/forget': 'http://127.0.0.1:8420',
      '/health': 'http://127.0.0.1:8420',
    },
  },
})
