import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Router } from "wouter";
import { App } from "@/src/app";
import "@/src/styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("Elemento radice LAGGENTE non trovato");

createRoot(root).render(
  <StrictMode>
    <Router>
      <App />
    </Router>
  </StrictMode>,
);
