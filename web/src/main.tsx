import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

const raw = import.meta.env.BASE_URL;
const basename = raw.endsWith("/") ? raw.slice(0, -1) : raw;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename={basename || "/"}>
      <App />
    </BrowserRouter>
  </StrictMode>
);
