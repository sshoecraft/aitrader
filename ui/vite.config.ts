import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Relative asset base so the built bundle works whether it's served at the
  // origin root (direct mode, http://host:2500/) OR under a path prefix (portd
  // mode, https://host/aitrader/ with Caddy stripping the prefix). Safe here
  // because the dashboard is a single page with NO client-side router — there
  // are no deep routes that would break relative asset resolution.
  base: './',
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
  },
})
