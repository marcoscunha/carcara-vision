import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import pkg from './package.json' with { type: 'json' }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    // Exposed as import.meta.env.VITE_APP_VERSION at build time.
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(pkg.version),
  },
})
