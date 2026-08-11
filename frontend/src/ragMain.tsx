import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RagInterface } from "./components/RagInterface";
import "./index.css";
import "./skillColors.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RagInterface />
  </StrictMode>
);