import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/vitest-setup.ts'],
    // 限制测试 worker 数量，避免多个 jsdom/Ant Design 测试在高并行下互相干扰。
    maxWorkers: 4,
    css: true,
    coverage: {
      provider: 'v8',
      include: ['src/components/**/*.{ts,tsx}'],
    },
  },
})
