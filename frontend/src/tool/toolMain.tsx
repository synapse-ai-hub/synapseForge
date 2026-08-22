import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ToolInterface } from "./ToolInterface";
import "../index.css";
import "../createColors.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ToolInterface />
  </StrictMode>
);
