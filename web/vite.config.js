import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiPort = process.env.DATAFACTORY_API_PORT || '8766';
const apiHost = process.env.DATAFACTORY_API_HOST || '127.0.0.1';
const configuredApiTimeoutMs = Number(process.env.DATAFACTORY_API_TIMEOUT_MS || 30 * 60 * 1000);
const longApiTimeoutMs = Number.isFinite(configuredApiTimeoutMs) && configuredApiTimeoutMs >= 0 ? configuredApiTimeoutMs : 30 * 60 * 1000;
const longApiHeadersTimeoutMs = longApiTimeoutMs === 0 ? 0 : longApiTimeoutMs + 5000;

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'datafactory-long-api-timeout',
      configureServer(server) {
        if (!server.httpServer) return;
        server.httpServer.requestTimeout = longApiTimeoutMs;
        server.httpServer.timeout = longApiTimeoutMs;
        server.httpServer.keepAliveTimeout = longApiTimeoutMs;
        server.httpServer.headersTimeout = longApiHeadersTimeoutMs;
      },
    },
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://${apiHost}:${apiPort}`,
        changeOrigin: true,
        proxyTimeout: longApiTimeoutMs,
        timeout: longApiTimeoutMs,
      },
    },
  },
});
