import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

async function loadColors() {
  try {
    const res = await fetch("/colors.json", { cache: "no-store" });
    if (!res.ok) return;
    const colors = await res.json();
    const root = document.documentElement;
    // colors keys mapping:
    //   "primary"           → --color-app-primary
    //   "secondary"         → --color-app-primary-light
    //   "primary_text"      → --color-app-primary-text
    //   "gradient_secondary"→ --color-app-gradient-secondary
    //   "usar_gradiente"    → toggle class on root
    /* ── Simple 1:1 mapping ──────────────────────────────────────────
       JSON key            CSS variable
       ─────────────────────────────────────────
       primary             --color-app-primary
       secondary           --color-app-primary-light
       primary_text        --color-app-primary-text
       gradient_secondary  --color-app-gradient-secondary
       usar_gradiente      — not a CSS variable; the pipeline writes
                            the same value as primary when gradient
                            is OFF, so gradients appear solid.
    */
    const keyMapping: Record<string, string> = {
      primary: "primary",
      secondary: "primary-light",
      primary_text: "primary-text",
      gradient_secondary: "gradient-secondary",
    };
    Object.entries(colors).forEach(([key, value]) => {
      const cssKey = keyMapping[key];
      if (cssKey) {
        root.style.setProperty(`--color-app-${cssKey}`, value as string);
      }
    });
  } catch {
    // Silently fail - CSS defaults will be used
  }
}

loadColors().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
});