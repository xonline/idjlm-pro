import { defineConfig } from 'vite';
import { resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

// IDJLM 0.4 — Vite builds/serves the JS bundle only. Flask remains the page
// host (renders templates/index.html) in dev, prod, and inside Tauri; this
// config never needs Tauri/Flask to know about an HTML entry.
export default defineConfig({
  root: resolve(__dirname, 'frontend'),
  server: {
    port: 5173,
    strictPort: true,
    cors: true,
    origin: 'http://localhost:5173',
  },
  build: {
    outDir: resolve(__dirname, 'app/static/dist'),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, 'frontend/main.js'),
      output: {
        entryFileNames: 'main.js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name][extname]',
      },
    },
  },
});
