import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Deploy estático: public_html/projetos/Pilotgram/ (mesmo padrão do Leads AI)
export default defineConfig({
  plugins: [react()],
  base: "/projetos/Pilotgram/",
  server: { port: 5173 },
});
