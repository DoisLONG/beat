// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@import "./src/styles/styles.scss";`,
      },
    },
  },
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    allowedHosts: true,
    proxy: {
      '/v1/kbs': {
        target: 'http://localhost:7001',
        changeOrigin: true,
        secure: false
      },
      '/v1/chatqna': {
        target: 'http://localhost:8888',
        changeOrigin: true,
        secure: false
      },
      '/v1/chathistory': {
        target: 'http://localhost:8012',
        changeOrigin: true,
        secure: false
      },
      '/v1/chat': {
        target: 'http://localhost:9000',
        changeOrigin: true,
        secure: false
      },
      '/ekbafiles-': {
        target: 'http://localhost:9100',
        changeOrigin: true,
        secure: false
      }
    }
  },
  test: {
    globals: true,
    environment: "jsdom",
  },
  define: {
    "import.meta.env": process.env,
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
    },
  },
  publicDir: 'public',
});
