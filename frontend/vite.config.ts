import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget =
    env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8001'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: true,
      port: 5173,
      // Docker Desktop on Windows often misses bind-mount file events without polling.
      watch: {
        usePolling: true,
        interval: 1000,
      },
      proxy: {
        '/api': apiProxyTarget,
        '/ws': {
          target: apiProxyTarget,
          ws: true,
        },
      },
    },
  }
})
