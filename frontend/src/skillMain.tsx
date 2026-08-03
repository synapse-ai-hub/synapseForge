import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { SkillInterface } from "./components/SkillInterface";
import "./index.css";
import "./skillColors.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SkillInterface />
  </StrictMode>
);
