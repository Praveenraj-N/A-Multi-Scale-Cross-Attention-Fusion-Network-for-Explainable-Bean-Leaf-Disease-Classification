import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Matches the CORS origins allowed by the FastAPI backend
    host: "localhost",
    port: 5173,
    strictPort: true
  }
});
