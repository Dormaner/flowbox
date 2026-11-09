import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Tauri 那边要求固定端口，dev 时不清屏方便看日志
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 5173, strictPort: true },
  build: { target: 'chrome110', outDir: 'dist', emptyOutDir: true },
})
