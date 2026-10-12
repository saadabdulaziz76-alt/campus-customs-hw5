import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The desk talks to the FastAPI backend on 8000 by absolute URL (see src/api.ts),
// so no proxy is needed — the backend names this origin in its CORS allow-list.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
})
