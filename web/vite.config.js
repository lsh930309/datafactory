import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiPort = process.env.DATAFACTORY_API_PORT || '8766';
const apiHost = process.env.DATAFACTORY_API_HOST || '127.0.0.1';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://${apiHost}:${apiPort}`,
        changeOrigin: true,
      },
    },
  },
});
