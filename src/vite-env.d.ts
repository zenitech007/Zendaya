import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path' // Import the 'path' module from Node.js

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // This is the crucial part:
      // It tells Vite that any import starting with "@/"
      // should be resolved relative to the 'src' directory.
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
