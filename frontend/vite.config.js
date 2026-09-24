import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The app calls relative /api/... URLs; in development they are forwarded to FastAPI.
    proxy: {
      // CAMPUSGRID_API points the dev server at a backend on another port (default :8000).
      '/api': { target: process.env.CAMPUSGRID_API || 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    // Recharts and its d3 dependencies are ~550 kB on their own; they get a chunk of their own.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (/node_modules\/(recharts|d3-|victory-vendor|lodash|decimal\.js)/.test(id)) return 'charts';
          return 'vendor';
        },
      },
    },
  },
});
