/**
 * Mermaid integration for markdown rendering.
 *
 * Registers a `marked` extension that converts fenced code blocks with
 * language `mermaid` into `<div class="mermaid">` placeholders, and exposes
 * a `renderMermaid()` helper that runs Mermaid over the DOM after the HTML
 * has been injected (must be called from a `useEffect` in every component
 * that renders markdown).
 */
import { marked } from "marked";
import mermaid from "mermaid";

/* ------------------------------------------------------------------ */
/*  marked extension — intercept ```mermaid blocks                     */
/* ------------------------------------------------------------------ */

marked.use({
  renderer: {
    code(code: string, infostring: string): string | false {
      // marked v12 passes positional args (code, infostring, escaped),
      // not the token object.
      const lang = (infostring ?? "").trim();
      if (lang !== "mermaid") return false;
      // Escape HTML so the diagram text is read as textContent by Mermaid
      // (also prevents HTML/script injection inside the placeholder).
      const escaped = code
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      return `<div class="mermaid">${escaped}</div>\n`;
    },
  },
});

/* ------------------------------------------------------------------ */
/*  Mermaid initialization + DOM render                                 */
/* ------------------------------------------------------------------ */

let initialized = false;
let renderCounter = 0;

/**
 * Renders every `.mermaid` placeholder that is currently mounted in the DOM.
 *
 * Uses `mermaid.render()` per diagram (instead of `mermaid.run()`) so it does
 * NOT depend on the `data-processed` attribute — that attribute survives DOM
 * reuse when React re-renders/navigates between conversations and would make
 * `run()` skip diagrams that were reset to their raw text. `render()` always
 * redraws and replaces the container content with the generated SVG.
 */
export async function renderMermaid(): Promise<void> {
  if (!initialized) {
    mermaid.initialize({
      startOnLoad: false,
      suppressErrors: true,
      theme: "default",
    });
    initialized = true;
  }
  const elements = document.querySelectorAll<HTMLElement>(".mermaid");
  for (const el of elements) {
    // Already rendered to an SVG — skip to avoid flicker/re-render loops.
    if (el.querySelector("svg")) continue;
    try {
      const id = `mermaid-${renderCounter++}`;
      const { svg, bindFunctions } = await mermaid.render(
        id,
        el.textContent ?? "",
      );
      el.innerHTML = svg;
      bindFunctions?.(el);
    } catch (err) {
      // Never break the chat stream because of a diagram parse error.
      console.error("Mermaid render error:", err);
    }
  }
}

/* ------------------------------------------------------------------ */
/*  MutationObserver — render diagrams whenever they appear in the DOM  */
/* ------------------------------------------------------------------ */

let observerStarted = false;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleRender(): void {
  if (debounceTimer) clearTimeout(debounceTimer);
  // Small debounce so rapid streaming updates are batched into one render.
  debounceTimer = setTimeout(() => {
    void renderMermaid();
  }, 50);
}

/**
 * Watches the whole document and re-renders `.mermaid` placeholders whenever
 * they are added or changed. This is the robust path: it covers initial mount,
 * re-renders, navigating between conversations and streaming, without relying
 * on each component calling `renderMermaid()` from its own effect.
 */
function startObserver(): void {
  if (observerStarted || typeof document === "undefined") return;
  observerStarted = true;
  const observer = new MutationObserver(scheduleRender);
  observer.observe(document.body, { childList: true, subtree: true });
}

startObserver();
