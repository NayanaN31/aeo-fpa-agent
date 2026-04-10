import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// GitHub Pages project site: /repo-name/  — user repo root site: /
const base = process.env.VITE_BASE_PATH || '/';

const apiProxy = {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
};

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: 'all',
    proxy: apiProxy,
  },
  preview: {
    host: true,
    allowedHosts: 'all',
    proxy: apiProxy,
  },
});
