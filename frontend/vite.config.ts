import path from 'node:path'
import basicSsl from '@vitejs/plugin-basic-ssl'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [
      react(),
      tailwindcss(),
      // HTTPS is needed to use the microphone from a phone over the LAN
      // (set VITE_HTTPS=false to serve plain HTTP, e.g. for local browser testing)
      env.VITE_HTTPS !== 'false' && basicSsl(),
      VitePWA({
        registerType: 'autoUpdate',
        manifest: {
          name: 'El Setero Manolo CRM',
          short_name: 'El Setero',
          lang: 'es',
          start_url: '/',
          display: 'standalone',
          background_color: '#F6F8F5',
          theme_color: '#536942',
          icons: [
            { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
            { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: { navigateFallbackDenylist: [/^\/api\//] },
      }),
    ],
    resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
    server: {
      host: true,
      port: 5173,
      proxy: { '/api': env.VITE_API_PROXY_TARGET || 'http://localhost:8000' },
    },
  }
})
