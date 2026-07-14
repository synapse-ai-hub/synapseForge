import {
  useState,
  useRef,
  useEffect,
  useCallback,
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
} from "lucide-react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import LogoImage from "../assets/logo_cliente.png";
import chatService from "../services/chatService";
import { Button } from "./ui/button";
import type { Message } from "../App";

/* ------------------------------------------------------------------ */
/*  Exported welcome message for App initialization                   */
/* ------------------------------------------------------------------ */

export const WELCOME_MESSAGE: Message = {
  id: "welcome",
  type: "assistant",
  content: `¡Hola! Soy el **asistente de cotización de <cliente>nombre_cliente</cliente> SRL**. 👋

Estoy aquí para ayudarte con:

- 📋 **Consultas de precios** de productos industriales
- 📦 **Búsqueda** de productos por grupo o código
- 💰 **Cálculo de cotizaciones** con descuentos

¿En qué puedo ayudarte hoy?`,
};

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const SUGGESTIONS = [
  "Consultar precio de un producto",
  "Buscar productos por grupo",
  "Calcular cotización con descuento",
  "Mostrar productos disponibles",
];

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
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB (~300 000 caracteres de texto plano)

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

/** 2-column suggestions grid shown after the welcome message. */
function SuggestionsGrid({ onSelect }: { onSelect: (text: string) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 sm:mt-4 max-w-full sm:max-w-xl md:max-w-3xl lg:max-w-4xl mx-auto w-full">
      {SUGGESTIONS.map((text) => (
        <button
          key={text}
          onClick={() => onSelect(text)}
          className="px-4 py-3 text-sm text-left rounded-2xl border border-app-border bg-white
                     hover:bg-app-bg-secondary hover:border-app-primary-light
                     active:scale-[0.98] transition-all duration-150
                     text-app-text shadow-sm"
        >
          {text}
        </button>
      ))}
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
                 bg-[rgba(215,111,16,0.08)] border border-[rgba(215,111,16,0.2)] text-app-text"
    >
      <span className="truncate max-w-[120px] sm:max-w-[200px]">{file.name}</span>
      <span className="text-app-text-secondary shrink-0">{sizeLabel}</span>
      <button
        onClick={onRemove}
        className="shrink-0 rounded-full p-0.5 hover:bg-[rgba(215,111,16,0.15)] transition-colors"
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
      for (const f of selected) {
        if (!ALLOWED_FILE_TYPES.includes(f.type) && !f.name.match(/\.(csv|xlsx|xls)$/i)) {
          warning = `Tipo de archivo no soportado: ${f.name}. Permitidos: PDF, DOCX, XLSX, TXT, CSV, JSON, XML.`;
          continue;
        }
        if (f.size > MAX_FILE_SIZE) {
          warning = `Archivo demasiado grande: ${f.name} (máx 10 MB).`;
          continue;
        }
        valid.push(f);
      }
      if (warning) setFileWarning(warning);
      setFiles((prev) => [...prev, ...valid]);
      // Reset input so same file can be picked again
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [],
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

    // Add user message
    const userMessage: Message = {
      id: generateId(),
      type: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMessage]);

    // Create assistant placeholder
    const assistantId = generateId();
    const assistantMessage: Message = {
      id: assistantId,
      type: "assistant",
      content: "",
      isStreaming: true,
    };
    setMessages((prev) => [...prev, assistantMessage]);
    // Forzar auto-scroll al enviar mensaje (como ProspectingAgent)
    setAutoScrollEnabled(true);
    setIsStreaming(true);

    try {
      const eventStream = chatService.sendMessage({
        message: text,
        files: currentFiles,
        sessionId: activeSessionId,
      });

      let accumulatedContent = "";
      let accumulatedReasoning = "";

      for await (const event of eventStream) {
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
              // Validate tool_call payload before storing
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
              setMessages((prev) =>
                prev.map((m) => {
                  const tc = Array.isArray(m.toolCalls) ? m.toolCalls : [];
                  return m.id === assistantId
                    ? { ...m, toolCalls: [...tc, validated] }
                    : m;
                }),
              );
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
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolResults: [
                          ...(Array.isArray(m.toolResults) ? m.toolResults : []),
                          { tool: toolName, result: toolResultValue },
                        ],
                      }
                    : m,
                ),
              );
            }
            break;

          case "session_title":
            if (activeSessionId && typeof event.content === "string") {
              onSessionTitleUpdate?.(activeSessionId, event.content);
            }
            break;

          case "chunk":
            accumulatedContent += event.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: accumulatedContent } : m,
              ),
            );
            break;

          case "usage":
            break;

          case "done":
            break;

          case "ask_discount":
            if (event.content) {
              accumulatedContent += `\n\n---\n${event.content}\n---\n\n`;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: accumulatedContent } : m,
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
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `*Error: ${errorMsg}*` }
            : m,
        ),
      );
    } finally {
      setIsStreaming(false);
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m)),
      );
      onSessionEnd?.();
    }
  }, [input, isStreaming, files, setMessages, setIsStreaming, sessionId, onSessionStart]);

  /* ---- stop streaming ---- */
  const handleCancel = useCallback(() => {
    chatService.cancelStream();
  }, []);

  /* ---- suggestion click ---- */
  const handleSuggestion = useCallback((text: string) => {
    setInput(text);
    textareaRef.current?.focus();
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

  /* ---- derive state ---- */
  const showSuggestions =
    messages.length === 1 && messages[0]?.id === "welcome";

  /* ---- render ---- */
  return (
    <div className="flex flex-col h-full bg-app-bg transition-colors">
      {/* ========== HEADER (60px) ========== */}
      <header
        className="flex items-center justify-between px-4 sm:px-6 shrink-0 border-b border-app-border
                   bg-white"
        style={{ height: "60px" }}
      >
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="rounded-full p-1.5 text-app-text-secondary hover:bg-app-bg-secondary hover:text-app-text transition-colors"
            aria-label="Mostrar conversaciones"
          >
            <Menu size={18} />
          </button>
          <img
            src={LogoImage}
            alt="<cliente>nombre_cliente</cliente> SRL Logo"
            className="h-7 sm:h-15 w-auto"
          />
          <h1 className="text-sm sm:text-lg font-semibold text-app-text">
            <descripcion>nombre_proyecto</descripcion>
          </h1>
        </div>

        <div className="flex items-center gap-1 sm:gap-2">
          {/* Cotizaciones (historial de cotizaciones) */}
          <Button
            variant="outline"
            size="sm"
            onClick={onShowHistory}
            className="gap-1 sm:gap-1.5 text-xs h-7 sm:h-8"
          >
            <Search size={14} />
            <span className="hidden sm:inline">Cotizaciones</span>
          </Button>

          {/* Métricas */}
          <Button
            variant="outline"
            size="sm"
            onClick={onShowMetrics}
            className="gap-1 sm:gap-1.5 text-xs h-7 sm:h-8"
          >
            <BarChart3 size={14} />
            <span className="hidden sm:inline">Métricas</span>
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
              className="w-10 h-10 rounded-full transition-all duration-200 flex items-center justify-center border border-app-border bg-app-bg-secondary text-app-text-secondary hover:bg-app-bg hover:text-app-primary shadow-sm"
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
            scrollbarColor: "var(--color-app-accent) transparent",
          }}
        >
          <div className="relative max-w-full sm:max-w-3xl lg:max-w-4xl mx-auto space-y-4 sm:space-y-6">
            {messages.map((msg) => (
              <MessageRow key={msg.id} message={msg} />
            ))}

            {/* Suggestions grid */}
            {showSuggestions && (
              <SuggestionsGrid onSelect={handleSuggestion} />
            )}

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
                         focus:outline-none focus:ring-2 focus:ring-[#D76F10]/30 focus:border-[#D76F10]
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
                         bg-[rgba(215,111,16,0.1)] hover:bg-[rgba(215,111,16,0.2)]
                         text-[#D76F10] transition-all duration-150"
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
                           bg-gradient-to-r from-[#ef4444] to-[#f97316]
                           hover:opacity-90 active:scale-95
                           transition-all duration-150 shadow-sm"
                aria-label="Detener generación"
              >
                <Square size={14} className="text-white" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim()}
                className="absolute bottom-3 right-3 w-7 h-7 sm:w-8 sm:h-8 rounded-full
                           flex items-center justify-center
                           bg-gradient-to-r from-[#D76F10] to-[#F0A347]
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
}: {
  toolCall: { tool: string; parameters?: Record<string, any> };
  result?: { tool: string; result: any };
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-app-border bg-app-bg-tertiary p-2.5">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between gap-2 text-left text-xs text-app-text-secondary hover:text-app-primary"
      >
        <span className="font-medium text-app-text">🔧 {toolCall.tool}</span>
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

          {result && (
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

function MessageRow({ message }: { message: Message }) {
  const [showReasoning, setShowReasoning] = useState(false);
  const panelId = `reasoning-${message.id}`;
  const isAssistant = message.type === "assistant";

  if (isAssistant) {
    return (
      <div className="flex gap-3 sm:gap-4 items-start">
        {/* Avatar 8x8 mobile → 64x64 desktop */}
        <div className="shrink-0">
          <div
            className="h-4 w-4 sm:h-10 sm:w-10 rounded-xl flex items-center justify-center
                        bg-gradient-to-br from-[#D76F10] to-[#F0A347] border border-[rgba(215,111,16,0.3)]"
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

          {/* Tool calls */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mb-3 space-y-2">
              {message.toolCalls.map((tc, i) => (
                <ToolCallBlock
                  key={`${tc.tool}-${i}`}
                  toolCall={tc}
                  result={message.toolResults?.[i]}
                />
              ))}
            </div>
          )}

          {/* Markdown content */}
          <MarkdownRenderer content={message.content} />

          {message.type === "assistant" && !message.isStreaming && message.id !== "welcome" && message.content && (
            <button
              type="button"
              onClick={() => navigator.clipboard?.writeText(message.content || "")}
              className="mt-2 inline-flex items-center gap-1 rounded-full border border-[rgba(215,111,16,0.2)] bg-[rgba(215,111,16,0.08)] px-2 py-1 text-[11px] text-app-primary transition-colors hover:bg-[rgba(215,111,16,0.15)]"
            >
              <Copy size={12} />
              Copiar
            </button>
          )}

          {/* Streaming cursor */}
          {message.isStreaming && !message.content && (
            <TypingIndicator />
          )}
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
                   bg-gradient-to-br from-[#D76F10] to-[#F0A347] text-white"
      >
        <User size={14} />
      </div>
    </div>
  );
}

export default ChatInterface;
