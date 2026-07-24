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
    Object.entries(colors).forEach(([key, value]) => {
      root.style.setProperty(`--color-app-${key}`, value as string);
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