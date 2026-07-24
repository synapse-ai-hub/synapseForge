import {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
  type KeyboardEvent,
} from "react";
import {
  Send,
  Square,
  Paperclip,
  X,
  User,
  Search,
  Bot,
  Menu,
  BarChart3,
  Copy,
  ChevronDown,
  Loader2,
  LogOut,
  BookOpen,
} from "lucide-react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import LogoImage from "../assets/logo_cliente.png";
import chatService from "../services/chatService";
import { Button } from "./ui/button";
import type { Message, SubagentEvent, ContentBlock } from "../App";

/* ------------------------------------------------------------------ */
/*  Exported welcome message for App initialization                   */
/* ------------------------------------------------------------------ */

export const WELCOME_MESSAGE: Message = {
  id: "welcome",
  type: "assistant",
  content: `¡Hola! Soy el **asistente de <tarea>nombre_tarea</tarea> de <cliente>nombre_cliente</cliente>**. 👋


¿En qué puedo ayudarte hoy?`,
};

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */



const ALLOWED_FILE_TYPES = [
  "text/csv",
  "text/plain",
  "text/markdown",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
  "application/json",
  "application/xml",
  "text/xml",
];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB per file
const MAX_FILES = 3;
const MAX_TOTAL_SIZE = 25 * 1024 * 1024; // 25 MB total

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

/** Generate a unique ID with safe fallback when crypto is unavailable. */
function generateId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                    */
/* ------------------------------------------------------------------ */

/** Bouncing-dots typing indicator. */
function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-1" role="status" aria-label="Escribiendo...">
      <span className="typing-dot h-2 w-2 rounded-full bg-app-primary-light" />
      <span className="typing-dot h-2 w-2 rounded-full bg-app-primary-light" />
      <span className="typing-dot h-2 w-2 rounded-full bg-app-primary-light" />
      <span className="text-xs text-app-text-secondary ml-1">
        Pensando...
      </span>
    </div>
  );
}


/** Warning banner for rejected files. */
function FileWarningBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <div
      className="flex items-center gap-2 px-4 py-2 mb-3 rounded-xl text-xs
                 bg-red-50 border border-red-200 text-red-700"
    >
      <span className="flex-1">{message}</span>
      <button
        onClick={onDismiss}
        className="shrink-0 rounded-full p-0.5 hover:bg-red-100 transition-colors"
        aria-label="Cerrar advertencia"
      >
        <X size={14} />
      </button>
    </div>
  );
}

/** File chip preview above the textarea. */
function FileChip({
  file,
  onRemove,
}: {
  file: File;
  onRemove: () => void;
}) {
  const sizeLabel =
    file.size < 1024 * 1024
      ? `${(file.size / 1024).toFixed(0)} KB`
      : `${(file.size / (1024 * 1024)).toFixed(1)} MB`;

  return (
    <div
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs
                 bg-app-primary/10 border border-app-primary/20 text-app-text"
    >
      <span className="truncate max-w-[120px] sm:max-w-[200px]">{file.name}</span>
      <span className="text-app-text-secondary shrink-0">{sizeLabel}</span>
      <button
        onClick={onRemove}
        className="shrink-0 rounded-full p-0.5 hover:bg-app-primary/15 transition-colors"
        aria-label={`Remove ${file.name}`}
      >
        <X size={12} />
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  MarkdownRenderer                                                  */
/* ------------------------------------------------------------------ */

/** Renders markdown content to HTML with XSS sanitization. */
function MarkdownRenderer({ content }: { content: string }) {
  if (!content) return null;
  try {
    const html = marked.parse(content, { async: false }) as string;
    const sanitized = DOMPurify.sanitize(html, { ADD_ATTR: ["target"] });
    return (
      <div
        className="markdown-content text-sm leading-relaxed text-app-text"
        dangerouslySetInnerHTML={{ __html: sanitized }}
      />
    );
  } catch {
    return <>{content}</>;
  }
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                    */
/* ------------------------------------------------------------------ */

interface ChatInterfaceProps {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  isStreaming: boolean;
  setIsStreaming: React.Dispatch<React.SetStateAction<boolean>>;
  onShowHistory: () => void;
  sessionId: string | null;
  onSessionStart: (id: string) => void;
  onNewChat: () => void;
  onToggleSidebar: () => void;
  onSessionEnd?: () => void;
  onShowMetrics: () => void;
  onSessionTitleUpdate?: (sessionId: string, title: string) => void;
  verboseMode: boolean;
}

export function ChatInterface({
  messages,
  setMessages,
  isStreaming,
  setIsStreaming,
  onShowHistory,
  sessionId,
  onSessionStart,
  onNewChat,
  onToggleSidebar,
  onSessionEnd,
  onShowMetrics,
  onSessionTitleUpdate,
  verboseMode,
}: ChatInterfaceProps) {
  /* ---- state ---- */
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [fileWarning, setFileWarning] = useState<string | null>(null);

  /* ---- refs ---- */
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ---- auto scroll ---- */
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const userInteractionRef = useRef(false);
  const userInteractionTimeoutRef = useRef<number | null>(null);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior,
      });
    }
  }, []);

  useEffect(() => {
    if (autoScrollEnabled) {
      scrollToBottom("smooth");
    }
  }, [messages, autoScrollEnabled, scrollToBottom]);

  const handleMessagesScroll = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
    setShowScrollButton(!nearBottom);

    // Solo cambiar autoScroll si NO hay interacción de usuario reciente
    if (!userInteractionRef.current) {
      setAutoScrollEnabled(nearBottom);
    }
  }, []);

  const handleMessagesWheel = useCallback(() => {
    // Marcar interacción de usuario
    userInteractionRef.current = true;
    setAutoScrollEnabled(false);

    // Limpiar flag después de 500ms
    if (userInteractionTimeoutRef.current) {
      clearTimeout(userInteractionTimeoutRef.current);
    }
    userInteractionTimeoutRef.current = window.setTimeout(() => {
      userInteractionRef.current = false;
      userInteractionTimeoutRef.current = null;
    }, 500);
  }, []);

  /* ---- abort stream on unmount ---- */
  useEffect(() => {
    return () => {
      chatService.cancelStream();
    };
  }, []);

  /* ---- shutdown app ---- */
  const handleShutdown = useCallback(async () => {
    if (!window.confirm("¿Cerrar la aplicación completamente?")) return;
    try {
      const API_BASE_URL = import.meta.env.VITE_URL_BASE || "http://localhost:8000";
      await fetch(`${API_BASE_URL}/api/shutdown`, { method: "POST" });
    } catch {
      // Ignore network errors - server is shutting down
    }
    // Close the window (works if opened by window.open or as PWA)
    window.close();
  }, []);

  /* ---- open docs in new tab ---- */
  const handleOpenDocs = useCallback(() => {
    const base = window.location.origin;
    window.open(`${base}/docs.html`, "_blank", "noopener,noreferrer");
  }, []);

  /* ---- auto-resize textarea ---- */
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${Math.min(ta.scrollHeight, 220)}px`;
    }
  }, [input]);

  /* ---- file validation ---- */
  const handleFilesSelected = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = Array.from(e.target.files || []);
      const valid: File[] = [];
      let warning: string | null = null;
      let currentTotalSize = files.reduce((sum, f) => sum + f.size, 0);

      for (const f of selected) {
        if (!ALLOWED_FILE_TYPES.includes(f.type) && !f.name.match(/\.(csv|xlsx|xls)$/i)) {
          warning = `Tipo de archivo no soportado: ${f.name}. Permitidos: PDF, DOCX, XLSX, TXT, CSV, JSON, XML.`;
          continue;
        }
        if (f.size > MAX_FILE_SIZE) {
          warning = `Archivo demasiado grande: ${f.name} (máx 10 MB).`;
          continue;
        }
        if (valid.length + files.length >= MAX_FILES) {
          warning = `Máximo ${MAX_FILES} archivos permitidos.`;
          break;
        }
        if (currentTotalSize + f.size > MAX_TOTAL_SIZE) {
          warning = `Tamaño total excede ${MAX_TOTAL_SIZE / (1024 * 1024)} MB.`;
          break;
        }
        valid.push(f);
        currentTotalSize += f.size;
      }
      if (warning) setFileWarning(warning);
      setFiles((prev) => [...prev, ...valid]);
      // Reset input so same file can be picked again
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [files],
  );

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  /* ---- auto-dismiss file warning after 6 seconds ---- */
  useEffect(() => {
    if (!fileWarning) return;
    const timer = setTimeout(() => setFileWarning(null), 6000);
    return () => clearTimeout(timer);
  }, [fileWarning]);

  /* ---- new conversation ---- */
  const handleNewConversation = useCallback(() => {
    chatService.cancelStream();
    setIsStreaming(false);
    setInput("");
    setFiles([]);
    setFileWarning(null);
    onNewChat();
  }, [onNewChat, setIsStreaming]);

  /* ---- send message ---- */
  const handleSend = useCallback(async () => {
    const _t0 = performance.now();
    // console.log(`[DEBUG_TIEMPO_SSE] handleSend called — t=${_t0}`);
    const text = input.trim();
    if (!text || isStreaming) return;

    // Ensure we have a session id for this conversation
    let activeSessionId = sessionId;
    if (!activeSessionId) {
      activeSessionId = generateId();
      onSessionStart(activeSessionId);
    }

    setInput("");
    const currentFiles = [...files];
    setFiles([]);

    // Add user message with attached files
    const userMessage: Message = {
      id: generateId(),
      type: "user",
      content: text,
      files: currentFiles.map((f) => ({ name: f.name, size: f.size })),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Create assistant placeholder
    const assistantId = generateId();
    // console.log(`[DEBUG_TIEMPO_SSE] assistantId created: ${assistantId} — t=${performance.now()}, elapsed=${performance.now() - _t0}`);
    const assistantMessage: Message = {
      id: assistantId,
      type: "assistant",
      content: "",
      isStreaming: true,
      blocks: [],
      toolCalls: [],
      toolResults: [],
    };
    // console.log(`[DEBUG_TIEMPO_SSE] assistantMessage id: ${assistantMessage.id} — t=${performance.now()}`);
    setMessages((prev) => [...prev, assistantMessage]);
    // Forzar auto-scroll al enviar mensaje (como ProspectingAgent)
    setAutoScrollEnabled(true);
    setIsStreaming(true);

    let accumulatedContent = "";
    let accumulatedReasoning = "";
    let accumulatedBlocks: ContentBlock[] = [];

    try {
      const eventStream = chatService.sendMessage({
        message: text,
        files: currentFiles,
        sessionId: activeSessionId,
      });

      for await (const event of eventStream) {
        // console.log(`[DEBUG_TIEMPO_SSE] event received type=${event.type} — t=${performance.now()}, elapsed=${performance.now() - _t0}`);
        switch (event.type) {
          case "router_status":
          case "reasoning":
            accumulatedReasoning += `\n${event.content}`;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, reasoning: accumulatedReasoning } : m,
              ),
            );
            break;

          case "tool_call":
            {
              // Validate tool_call payload before storing (always, even if verbose is off)
              const tcPayload =
                typeof event.content === "object" && event.content !== null
                  ? event.content
                  : typeof event.content === "string"
                    ? (() => {
                        try {
                          return JSON.parse(event.content);
                        } catch {
                          return { tool: event.content, parameters: {} };
                        }
                      })()
                    : { tool: String(event.content), parameters: {} };
              const validated: { tool: string; parameters: Record<string, any> } = {
                tool:
                  typeof tcPayload.name === "string"
                    ? tcPayload.name
                    : "unknown",
                parameters:
                  typeof tcPayload.args === "object" && tcPayload.args !== null
                    ? tcPayload.args
                    : typeof tcPayload.parameters === "object" && tcPayload.parameters !== null
                      ? tcPayload.parameters
                      : {},
              };
              accumulatedBlocks.push({
                type: "tool",
                name: validated.tool,
                args: validated.parameters,
                result: undefined,
              });
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  const tc = Array.isArray(m.toolCalls) ? m.toolCalls : [];
                  return { ...m, blocks: [...accumulatedBlocks], toolCalls: [...tc, validated] };
                }),
              );
              // Brief delay to break React 18's automatic batching between tool_call
              // and tool_result. Without this, consecutive setState calls in the same
              // async handler are batched into one render — the tool block appears
              // already with its result filled in, and the spinner is never visible.
              await new Promise(resolve => setTimeout(resolve, 0));
            }
            break;

          case "tool_result":
            if (event.content) {
              const payload =
                typeof event.content === "object" && event.content !== null
                  ? event.content
                  : { name: "unknown", result: event.content };
              const toolName =
                typeof payload.name === "string" ? payload.name : "unknown";
              const toolResultValue =
                "result" in payload ? payload.result : payload;
              // Update accumulatedBlocks
              for (let i = accumulatedBlocks.length - 1; i >= 0; i--) {
                if (accumulatedBlocks[i].type === "tool" && (accumulatedBlocks[i] as any).result === undefined) {
                  accumulatedBlocks[i] = { ...accumulatedBlocks[i], result: toolResultValue } as any;
                  break;
                }
              }
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  return {
                    ...m,
                    blocks: [...accumulatedBlocks],
                    toolResults: [
                      ...(Array.isArray(m.toolResults) ? m.toolResults : []),
                      { tool: toolName, result: toolResultValue },
                    ],
                  };
                }),
              );
            }
            break;

          case "subagent_event": {
            const payload =
              typeof event.content === "object" && event.content !== null
                ? event.content
                : {};
            const childId: string = payload.child_session_id || "";
            const agentName: string = payload.agent_name || "";
            const innerEvent: any = payload.event || {};

            if (!childId) break;

            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantId) return m;
                const current = { ...m };
                const events = { ...(current.subagentEvents || {}) };
                if (!events[childId]) {
                  events[childId] = {
                    child_session_id: childId,
                    agent_name: agentName,
                    tool_calls: [],
                    tool_results: [],
                    content: "",
                    reasoning: "",
                  };
                }
                const child = events[childId];
                let updatedChild = { ...child };

                switch (innerEvent.type) {
                  case "tool_call":
                    updatedChild.tool_calls = [
                      ...(child.tool_calls || []),
                      {
                        name: innerEvent.content?.name || "unknown",
                        args: innerEvent.content?.args || {},
                      },
                    ];
                    break;
                  case "tool_result":
                    updatedChild.tool_results = [
                      ...(child.tool_results || []),
                      {
                        name: innerEvent.content?.name || "unknown",
                        result: innerEvent.content?.result || "",
                      },
                    ];
                    break;
                  case "chunk":
                    updatedChild.content = (child.content || "") + (innerEvent.content || "");
                    break;
                  case "reasoning":
                    updatedChild.reasoning = (child.reasoning || "") + (innerEvent.content || "");
                    break;
                }

                return { ...current, subagentEvents: { ...events, [childId]: updatedChild } };
              }),
            );
            break;
          }

          case "session_title":
            if (activeSessionId && typeof event.content === "string") {
              onSessionTitleUpdate?.(activeSessionId, event.content);
            }
            break;

          case "chunk":
            accumulatedContent += event.content;
            {
              const chunk = event.content || "";
              const last = accumulatedBlocks[accumulatedBlocks.length - 1];
              if (last && last.type === "text") {
                accumulatedBlocks[accumulatedBlocks.length - 1] = {
                  ...last,
                  content: last.content + chunk,
                };
              } else {
                accumulatedBlocks.push({ type: "text", content: chunk });
              }
            }
            setMessages((prev) => {
              const matched = prev.some((m) => m.id === assistantId);
              // console.log(`[DEBUG_TIEMPO_SSE] chunk setMessages — assistantId=${assistantId}, matchFound=${matched}, prevLen=${prev.length}, t=${performance.now()}`);
              return prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: accumulatedContent, blocks: [...accumulatedBlocks] }
                  : m,
              );
            });
            break;

          case "usage":
            break;

          case "done":
            // console.log(`[DEBUG_TIEMPO_SSE] done event — assistantId=${assistantId}, t=${performance.now()}`);
            break;

          case "ask_discount":
            if (event.content) {
              const suffix = `\n\n---\n${event.content}\n---\n\n`;
              accumulatedContent += suffix;
              // Also append to last text block in accumulatedBlocks
              const lastBlock = accumulatedBlocks[accumulatedBlocks.length - 1];
              if (lastBlock && lastBlock.type === "text") {
                accumulatedBlocks[accumulatedBlocks.length - 1] = {
                  ...lastBlock,
                  content: lastBlock.content + suffix,
                };
              } else {
                accumulatedBlocks.push({ type: "text", content: suffix });
              }
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: accumulatedContent, blocks: [...accumulatedBlocks] }
                    : m,
                ),
              );
            }
            break;

          default:
            // Intentionally ignore unknown event types for forward compatibility
            break;
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      const errorMsg =
        err instanceof Error ? err.message : "Error desconocido";
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId) return m;
          const blocks = [...(m.blocks || accumulatedBlocks)];
          blocks.push({ type: "text", content: `*Error: ${errorMsg}*` });
          return { ...m, content: `*Error: ${errorMsg}*`, blocks };
        }),
      );
    } finally {
      // console.log(`[DEBUG_TIEMPO_SSE] finally — assistantId=${assistantId}, setIsStreaming(false), t=${performance.now()}, elapsed=${performance.now() - _t0}`);
      setIsStreaming(false);
      setMessages((prev) => {
        const matched = prev.some((m) => m.id === assistantId);
        // console.log(`[DEBUG_TIEMPO_SSE] finally setMessages — assistantId=${assistantId}, matchFound=${matched}, prevLen=${prev.length}, t=${performance.now()}`);
        return prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m));
      });
      onSessionEnd?.();
    }
  }, [input, isStreaming, files, setMessages, setIsStreaming, sessionId, onSessionStart, verboseMode]);

  /* ---- stop streaming ---- */
  const handleCancel = useCallback(() => {
    // console.log(`[DEBUG_TIEMPO_SSE] handleCancel called — t=${performance.now()}`);
    chatService.cancelStream();
  }, []);

  /* ---- keyboard ---- */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  /* ---- render ---- */
  return (
    <div className="flex flex-col h-full bg-app-bg transition-colors">
      {/* ========== HEADER (95px) ========== */}
      <header
        className="flex items-center px-6 sm:px-8 shrink-0 border-b border-app-border
                   bg-white"
        style={{ height: "95px" }}
      >
        {/* Left: hamburger */}
        <button
          type="button"
          onClick={onToggleSidebar}
          className="rounded-full p-1.5 text-app-text-secondary hover:bg-app-bg-secondary hover:text-app-text transition-colors shrink-0"
          aria-label="Mostrar conversaciones"
        >
          <Menu size={18} />
        </button>

        {/* Center: logo + title */}
        <div className="flex-1 flex items-center justify-center gap-2 sm:gap-3">
          <img
            src={LogoImage}
            alt={"<cliente>nombre_cliente</cliente> Logo"}
            className="h-9 sm:h-[95px] w-auto"
          />
          <h1 className="text-lg sm:text-2xl font-semibold text-app-text">
            {/* @ts-ignore */}
            <descripcion>Nombre del proyecto</descripcion>
          </h1>
        </div>

        {/* Right: docs + métricas + salir */}
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleOpenDocs}
            className="gap-1 sm:gap-1.5 text-xs h-7 sm:h-8"
            title="Documentación"
          >
            <BookOpen size={14} />
            <span className="hidden sm:inline">Docs</span>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={onShowMetrics}
            className="gap-1 sm:gap-1.5 text-xs h-7 sm:h-8"
          >
            <BarChart3 size={14} />
            <span className="hidden sm:inline">Métricas</span>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleShutdown}
            className="gap-1 sm:gap-1.5 text-xs h-7 sm:h-8 text-app-error hover:bg-red-50 hover:text-app-error"
            title="Cerrar aplicación"
          >
            <LogOut size={14} />
            <span className="hidden sm:inline">Salir</span>
          </Button>
        </div>

      </header>

      {/* ========== MESSAGES AREA ========== */}
      <div className="flex-1 min-h-0 relative">
        {showScrollButton && (
          <div className="absolute left-1/2 transform -translate-x-1/2 z-10" style={{ bottom: '30px' }}>
            <button
              type="button"
              onClick={() => {
                setAutoScrollEnabled(true);
                scrollToBottom("smooth");
              }}
              className="w-10 h-10 rounded-full transition-all duration-200 flex items-center justify-center border border-app-primary/20 bg-app-primary/10 text-app-primary hover:bg-app-primary/20 hover:text-app-primary shadow-sm"
              title="Ir al final"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            </button>
          </div>
        )}

        <div
          ref={messagesContainerRef}
          onScroll={handleMessagesScroll}
          onWheel={handleMessagesWheel}
          className="h-full overflow-y-auto px-3 sm:px-4 py-4 sm:py-6 pr-3 sm:pr-5"
          style={{
            scrollbarWidth: "thin",
            scrollbarColor: "#d9d7d9 transparent",
          }}
        >
          <div className="relative max-w-full sm:max-w-3xl lg:max-w-4xl mx-auto space-y-4 sm:space-y-6">
            {messages.map((msg) => (
              <MessageRow key={msg.id} message={msg} verboseMode={verboseMode} />
            ))}

            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>

      {/* ========== INPUT AREA ========== */}
      <div
        className="shrink-0 border-t border-app-border bg-white
                   px-3 sm:px-4 py-3 sm:py-4"
      >
        <div className="max-w-full sm:max-w-3xl lg:max-w-4xl mx-auto">
          {/* File warning banner */}
          {fileWarning && (
            <FileWarningBanner
              message={fileWarning}
              onDismiss={() => setFileWarning(null)}
            />
          )}

          {/* File chips */}
          {files.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {files.map((f, i) => (
                <FileChip key={`${f.name}-${i}`} file={f} onRemove={() => removeFile(i)} />
              ))}
            </div>
          )}

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".csv,.xlsx,.xls,.pdf,.docx,.doc,.txt,.md,.json,.xml"
            className="hidden"
            onChange={handleFilesSelected}
          />

          {/* Textarea wrapper with buttons inside */}
          <div className="relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Escribí tu consulta..."
              rows={1}
              className="w-full resize-none rounded-2xl border border-app-border
                         bg-white
                         text-app-text placeholder:text-app-text-secondary
                         focus:outline-none focus:ring-2 focus:ring-app-primary/30 focus:border-app-primary
                         transition-colors
                         pt-3 sm:pt-4 pb-[52px] sm:pb-[64px] pr-12 sm:pr-12 pl-12 sm:pl-12
                         min-h-[80px] sm:min-h-[100px]"
              style={{
                maxHeight: "220px",
              }}
            />

{/* Attach button - bottom left */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
               className="absolute bottom-3 left-3 w-7 h-7 sm:w-8 sm:h-8 rounded-full
                          flex items-center justify-center
                          bg-app-primary/10 hover:bg-app-primary/20
                          text-app-primary transition-all duration-150"
              aria-label="Adjuntar archivos"
            >
              <Paperclip size={16} />
            </button>

            {/* Send / Stop button - bottom right */}
            {isStreaming ? (
              <button
                type="button"
                onClick={handleCancel}
                className="absolute bottom-3 right-3 w-7 h-7 sm:w-8 sm:h-8 rounded-full
                           flex items-center justify-center
                           bg-app-primary/20 hover:bg-app-primary/30
                           text-app-primary
                           hover:opacity-90 active:scale-95
                           transition-all duration-150 shadow-sm"
                aria-label="Detener generación"
              >
                <Square size={14} />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim()}
                className="absolute bottom-3 right-3 w-7 h-7 sm:w-8 sm:h-8 rounded-full
                           flex items-center justify-center
                           bg-gradient-to-r from-app-primary to-app-primary-light
                           hover:opacity-90 active:scale-95
                           transition-all duration-150 shadow-sm
                           disabled:opacity-40 disabled:cursor-not-allowed"
                 aria-label="Enviar mensaje"
              >
                <Send size={14} className="text-white" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ToolCallBlock                                                     */
/* ------------------------------------------------------------------ */

function ToolCallBlock({
  toolCall,
  result,
  isStreaming = false,
  waitingForChunk = false,
  subagentEvents,
  isLatestTool = true,
}: {
  toolCall: { tool: string; parameters?: Record<string, any> };
  result?: { tool: string; result: any };
  isStreaming?: boolean;
  waitingForChunk?: boolean;
  subagentEvents?: Record<string, SubagentEvent>;
  isLatestTool?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [childTools, setChildTools] = useState<Array<{ tool: string; parameters?: Record<string, any>; result?: any }>>([]);
  const fetchedRef = useRef(false);

  // Determine status: 'calling' | 'success' | 'error'
  const isTask = toolCall.tool === "task";
  const hasResult = !!result;
  const isError = hasResult && result.result && (
    (typeof result.result === "string" && result.result.toLowerCase().includes("error")) ||
    (typeof result.result === "object" && result.result !== null && "error" in result.result)
  );
  
  // Status logic:
  // - If waiting for first chunk: keep calling (spinner) until text arrives
  // - If has result: success or error based on content
  // - If no result, isStreaming and isLatestTool: calling (spinner)
  // - If no result, isStreaming but NOT latest tool: done (no spinner, closed by newer tool)
  // - If no result and NOT streaming (historical): error (red, no spinner)
  const status = waitingForChunk
    ? "calling"
    : hasResult
      ? (isError ? "error" : "success")
      : (isStreaming && isLatestTool ? "calling" : (isStreaming ? "done" : "error"));

  // Status colors (done = previous tool closed by a newer one)
  const statusColors = {
    calling: "text-app-text-secondary",
    success: "text-emerald-600",
    error: "text-red-600",
    done: "text-app-text-secondary/50",
  };

  // Find matching child session ID from real-time events or result XML
  const childSessionId = useMemo(() => {
    // First try to find from real-time events
    if (subagentEvents && isTask) {
      const ids = Object.keys(subagentEvents);
      if (ids.length > 0) return ids[0];
    }
    // Fall back to parsing from result XML
    if (isTask && hasResult && typeof result?.result === "string") {
      const match = result.result.match(/<task\s+id="([^"]+)"/);
      return match ? match[1] : null;
    }
    return null;
  }, [subagentEvents, isTask, hasResult, result]);

  // Build child tools list from real-time events (priority) or lazy fetch
  const realtimeChildTools = useMemo(() => {
    if (!childSessionId || !subagentEvents?.[childSessionId]) return null;
    const child = subagentEvents[childSessionId];
    const tools: Array<{ tool: string; parameters?: Record<string, any>; result?: any }> = [];
    if (child.tool_calls) {
      child.tool_calls.forEach((tc, i) => {
        tools.push({
          tool: tc.name,
          parameters: tc.args,
          result: child.tool_results?.[i]?.result,
        });
      });
    }
    return tools;
  }, [childSessionId, subagentEvents]);

  // Fetch child session tools on demand (when user expands task) - fallback for historical sessions
  const fetchChildTools = useCallback(async () => {
    if (fetchedRef.current || !isTask || !hasResult || realtimeChildTools) return;
    fetchedRef.current = true;

    const resultStr = result?.result;
    if (typeof resultStr !== "string") return;

    const match = resultStr.match(/<task\s+id="([^"]+)"/);
    if (!match) return;

    const childId = match[1];
    try {
      const API_BASE_URL = import.meta.env.VITE_URL_BASE || "http://localhost:8000";
      const response = await fetch(`${API_BASE_URL}/api/sessions/${encodeURIComponent(childId)}`);
      const data = await response.json();
      if (data?.data?.messages) {
        const tools: Array<{ tool: string; parameters?: Record<string, any>; result?: any }> = [];
        data.data.messages.forEach((msg: any) => {
          if (msg.type !== "assistant") return;
          // New blocks format
          if (msg.blocks) {
            msg.blocks.forEach((b: any) => {
              if (b.type === "tool") {
                tools.push({
                  tool: b.name ?? "unknown",
                  parameters: b.args ?? {},
                  result: b.result,
                });
              }
            });
          }
          // Legacy toolCalls format
          if (msg.toolCalls) {
            msg.toolCalls.forEach((tc: any, i: number) => {
              tools.push({
                tool: tc.name ?? "unknown",
                parameters: tc.args ?? {},
                result: msg.toolResults?.[i]?.result,
              });
            });
          }
        });
        setChildTools(tools);
      }
    } catch {
      // Silently fail - child tools just won't show
    }
  }, [isTask, hasResult, result, realtimeChildTools]);

  const handleToggle = () => {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (nextOpen) {
      fetchChildTools();
    }
  };

  // Determine child tool status
  const getChildStatus = (childResult?: any) => {
    if (!childResult) return "calling";
    if (
      (typeof childResult === "string" && childResult.toLowerCase().includes("error")) ||
      (typeof childResult === "object" && childResult !== null && "error" in childResult)
    ) return "error";
    return "success";
  };

  const childStatusColors = {
    calling: "text-app-text-secondary",
    success: "text-emerald-600",
    error: "text-red-600",
  };

  // Child tools to display: real-time if available, otherwise lazy-fetched
  const displayChildTools = realtimeChildTools ?? childTools;

  // Child text content (from real-time chunks)
  const childContent = useMemo(() => {
    if (!childSessionId || !subagentEvents?.[childSessionId]) return null;
    return subagentEvents[childSessionId].content || null;
  }, [childSessionId, subagentEvents]);

  return (
    <div className="rounded-lg border border-app-border bg-app-bg-tertiary p-2.5">
      <button
        type="button"
        onClick={handleToggle}
        className="flex w-full items-center justify-between gap-2 text-left text-xs hover:text-app-primary"
      >
        <span className={`font-medium ${statusColors[status]}`}>
          {status === "calling" && <Loader2 className="h-4 w-4 animate-spin inline-block mr-1" />}
          {status === "success" && <span className="text-emerald-600">✓ </span>}
          {status === "error" && <span className="text-red-600">✗ </span>}
          🔧 {toolCall.tool}
        </span>
        <ChevronDown
          size={14}
          className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {toolCall.parameters && Object.keys(toolCall.parameters).length > 0 && (
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-app-text-secondary">
                Args
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-white p-2 text-[11px] text-app-text">
                {JSON.stringify(toolCall.parameters, null, 2)}
              </pre>
            </div>
          )}

          {/* Child text content (real-time from sub-agent chunks) */}
          {isTask && childContent && (
            <div className="border-t border-app-border pt-2">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-app-text-secondary">
                Respuesta del sub-agente
              </div>
              <div className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-white p-2 text-[11px] text-app-text">
                {childContent}
              </div>
            </div>
          )}

          {/* Child tools (for task) - real-time if streaming, otherwise lazy-fetched */}
          {isTask && displayChildTools.length > 0 && (
            <div className="border-t border-app-border pt-2 space-y-2">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-app-text-secondary">
                Herramientas del sub-agente
              </div>
              {displayChildTools.map((ct, i) => {
                const childStatus = getChildStatus(ct.result);
                return (
                  <div key={i} className="ml-3 pl-2 border-l-2 border-app-border space-y-1">
                    <div className="flex items-center gap-1 text-[11px]">
                      <span className={childStatusColors[childStatus]}>
                        {childStatus === "success" && "✓"}
                        {childStatus === "error" && "✗"}
                        {childStatus === "calling" && "⏳"}
                      </span>
                      <span className="font-medium">{ct.tool}</span>
                    </div>
                    {ct.parameters && Object.keys(ct.parameters).length > 0 && (
                      <pre className="ml-4 overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-white p-1.5 text-[10px] text-app-text">
                        {JSON.stringify(ct.parameters, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          )}

{/* Result for non-task tools */}
          {result && !isTask && (
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-app-text-secondary">
                Resultado
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-white p-2 text-[11px] text-app-text">
                {typeof result.result === "string"
                  ? result.result
                  : JSON.stringify(result.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  MessageRow                                                        */
/* ------------------------------------------------------------------ */
/*  MessageRow                                                        */
/* ------------------------------------------------------------------ */

function MessageRow({ message, verboseMode }: { message: Message; verboseMode: boolean }) {
  const [showReasoning, setShowReasoning] = useState(false);
  const panelId = `reasoning-${message.id}`;
  const isAssistant = message.type === "assistant";

  // Determine if the assistant is waiting for its first text chunk (affects spinner logic)
  const hasTextBlock = message.blocks?.some((b) => b.type === "text");
  const waitingForChunk = message.isStreaming && !hasTextBlock;

  if (isAssistant) {
    return (
      <div className="flex gap-3 sm:gap-4 items-start">
        {/* Avatar 8x8 mobile → 64x64 desktop */}
        <div className="shrink-0">
          <div
            className="h-4 w-4 sm:h-10 sm:w-10 rounded-xl flex items-center justify-center
                        bg-app-avatar-asistente text-white"
          >
            <Bot size={20} className="text-white" />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 pt-1">
          {/* Reasoning toggle */}
          {message.reasoning && (
            <div className="mb-2">
              <button
                onClick={() => setShowReasoning(!showReasoning)}
                aria-expanded={showReasoning}
                aria-controls={panelId}
                className="flex items-center gap-1 text-xs text-app-text-secondary
                           hover:text-app-primary transition-colors"
              >
                <svg
                  className={`h-3 w-3 transition-transform ${showReasoning ? "rotate-90" : ""}`}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path d="M9 18l6-6-6-6" />
                </svg>
                Razonamiento
              </button>
              {showReasoning && (
                <div
                  id={panelId}
                  className="mt-1 text-xs text-app-text-secondary bg-app-bg-tertiary
                            
                             rounded-lg p-3 whitespace-pre-wrap border border-app-border
                            "
                >
                  {message.reasoning}
                </div>
              )}
            </div>
          )}

          {/* Blocks in order: text interleaved with tools */}
          {message.blocks && message.blocks.length > 0 ? (
            <div className="space-y-2">
              {message.blocks.map((block, i) => {
                if (block.type === "text") {
                  return (
                    <div key={i}>
                      <MarkdownRenderer content={block.content} />
                    </div>
                  );
                }
                if (block.type === "tool") {
                  if (!verboseMode) return null;
                  return (
                    <ToolCallBlock
                      key={i}
                      toolCall={{ tool: block.name, parameters: block.args }}
                      result={block.result !== undefined ? { tool: block.name, result: block.result } : undefined}
                      isStreaming={message.isStreaming}
                      waitingForChunk={waitingForChunk}
                      subagentEvents={message.subagentEvents}
                      isLatestTool={i === (message.blocks?.length ?? 0) - 1}
                    />
                  );
                }
                return null;
              })}
            </div>
          ) : (
            /* Fallback for legacy messages without blocks (welcome, very old sessions) */
            <>
              <MarkdownRenderer content={message.content} />
              {/* Tool calls from legacy format */}
              {verboseMode && message.toolCalls && message.toolCalls.length > 0 && (
                <div className="mt-2 space-y-2">
                  {message.toolCalls.map((tc, i) => (
                    <ToolCallBlock
                      key={`${tc.tool}-${i}`}
                      toolCall={tc}
                      result={message.toolResults?.[i]}
                      isStreaming={false}
                      subagentEvents={undefined}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {/* Copy button (only when there's actual text content) */}
          {message.type === "assistant" && !message.isStreaming && message.id !== "welcome" && (
            (message.content || (message.blocks && message.blocks.some((b) => b.type === "text"))) && (
              <button
                type="button"
                onClick={() => {
                  const text = message.blocks
                    ? message.blocks.filter((b) => b.type === "text").map((b) => (b as any).content).join("\n\n")
                    : message.content || "";
                  navigator.clipboard?.writeText(text);
                }}
                className="mt-2 inline-flex items-center gap-1 rounded-full border border-app-primary/20 bg-app-primary/10 px-2 py-1 text-[11px] text-app-primary transition-colors hover:bg-app-primary/15"
              >
                <Copy size={12} />
                Copiar
              </button>
            )
          )}

          {/* TypingIndicator:
              Verbose OFF — always show typing during streaming (user sees activity).
              Verbose ON  — typing only when no text AND no tool blocks (tools have own spinner). */}
          {message.isStreaming && (
            (!verboseMode) ||
            (verboseMode && !message.blocks?.some((b) => b.type === "text") && !message.blocks?.some((b) => b.type === "tool"))
          ) && <TypingIndicator />}
        </div>
      </div>
    );
  }

  /* ---- User message ---- */
  return (
    <div className="flex gap-3 items-start justify-end">
      {/* Bubble */}
      <div
        className="rounded-2xl border border-app-border
                   bg-white
                   px-4 py-3 max-w-[85%] sm:max-w-[75%] shadow-sm"
      >
        <MarkdownRenderer content={message.content} />
      </div>

      {/* Avatar gradient */}
      <div
        className="w-10 h-10 sm:w-10 sm:h-10 rounded-full shrink-0 flex items-center justify-center
                   bg-app-avatar-usuario text-white"
      >
        <User size={14} />
      </div>
    </div>
  );
}

export default ChatInterface;
