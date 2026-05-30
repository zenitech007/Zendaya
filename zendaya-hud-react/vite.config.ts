import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5180, strictPort: true },
  build: {
    target: "es2022",
    sourcemap: true,
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("three") && !id.includes("@react-three")) return "three";
          if (id.includes("@react-three/postprocessing") || id.includes("postprocessing")) return "r3f-post";
          if (id.includes("@react-three")) return "r3f";
          if (id.includes("gsap")) return "gsap";
          if (id.includes("framer-motion")) return "framer";
          if (id.includes("zustand")) return "zustand";
          if (id.includes("react-dom") || id.includes("scheduler") || /[\\/]react[\\/]/.test(id))
            return "react";
        },
      },
    },
  },
});
