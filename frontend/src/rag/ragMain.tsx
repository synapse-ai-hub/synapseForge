import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RagInterface } from "./RagInterface";
import "../index.css";
import "../createColors.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RagInterface />
  </StrictMode>
);
