/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const browserApiBase = process.env.VITE_BROWSER_API_BASE || 'http://127.0.0.1:8000'

const browserProxy = {
  '/browser': {
    target: browserApiBase,
    changeOrigin: true,
  },
  '/adjudication': {
    target: browserApiBase,
    changeOrigin: true,
  },
  '/rag': {
    target: browserApiBase,
    changeOrigin: true,
  },
} as const

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { ...browserProxy },
  },
  /** `vite preview` (Playwright e2e) must proxy the same API routes as dev server. */
  preview: {
    host: '127.0.0.1',
    proxy: { ...browserProxy },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    passWithNoTests: true,
    css: true,
    setupFiles: ['./src/test/setup.ts'],
    pool: 'threads',
    fileParallelism: false,
  },
})
