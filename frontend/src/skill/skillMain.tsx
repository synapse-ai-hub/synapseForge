import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { SkillInterface } from "./SkillInterface";
import "../index.css";
import "../createColors.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SkillInterface />
  </StrictMode>
);
