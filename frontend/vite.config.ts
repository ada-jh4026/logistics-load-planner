import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 求解器 8000、智能体 8001，前端只通过同源代理访问，不在浏览器里写死服务地址。
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    fs: { allow: ['..'] }, // 允许直接引用 ../docs/playbook/examples 的样例 JSON（单一数据源）
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/agent': { target: 'http://127.0.0.1:8001', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
