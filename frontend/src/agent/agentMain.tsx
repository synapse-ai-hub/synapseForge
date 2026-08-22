import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AgentInterface } from "./AgentInterface";
import "../index.css";
import "../createColors.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AgentInterface />
  </StrictMode>
);
