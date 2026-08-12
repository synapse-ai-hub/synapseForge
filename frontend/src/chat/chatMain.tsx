import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "../App";
import "../index.css";

async function loadColors() {
  try {
    const res = await fetch("/colors.json", { cache: "no-store" });
    if (!res.ok) return;
    const colors = await res.json();
    const root = document.documentElement;
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
