import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = 3000;

// API代理到后端服务
app.use('/api', createProxyMiddleware({
  target: process.env.API_URL || 'http://backend:5000',
  changeOrigin: true,
  // SSE支持
  onProxyReq: (proxyReq, req) => {
    proxyReq.setHeader('Connection', 'keep-alive');
  },
}));

// 静态文件
app.use(express.static(path.join(__dirname, 'dist')));

// SPA路由回退
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend server running on port ${PORT}`);
  console.log(`API proxy target: ${process.env.API_URL || 'http://backend:5000'}`);
});
