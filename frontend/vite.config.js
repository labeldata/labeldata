import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, '../v1/static/label_editor'),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        label_editor: path.resolve(__dirname, 'src/label_editor/main.jsx'),
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: '[name]-[hash].js',
        assetFileNames: '[name][extname]',
      },
    },
  },
});
