import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // host: true — слушать все сетевые интерфейсы (0.0.0.0), а не только
    // localhost, чтобы приложение было доступно с других компьютеров сети.
    host: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  preview: {
    port: 5173,
    host: true,
  },
});
