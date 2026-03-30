import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Deploy estático: public_html/projetos/pilotgram/ (minúsculas = pasta no cPanel Linux)
export default defineConfig({
  plugins: [react()],
  base: "/projetos/pilotgram/",
  server: { port: 5173 },
});
