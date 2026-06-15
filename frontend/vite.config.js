import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // SSE流式响应：移除压缩和长度头，确保数据实时传输
            if (proxyRes.headers['content-type'] && proxyRes.headers['content-type'].includes('text/event-stream')) {
              delete proxyRes.headers['content-encoding']
              delete proxyRes.headers['content-length']
            }
          })
        },
      }
    }
  }
})
