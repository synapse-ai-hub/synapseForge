import { useState, useMemo, memo, useId } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import type { Message } from "../App";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { User, Brain, ChevronDown, ChevronRight, Terminal, Paperclip } from "lucide-react";

interface MessageBubbleProps {
  message: Message;
}

// Render markdown safely with XSS sanitization
function renderMarkdown(content: string): string {
  try {
    const html = marked.parse(content, { async: false }) as string;
    return DOMPurify.sanitize(html);
  } catch {
    return content;
  }
}

function MessageBubbleInner({ message }: MessageBubbleProps) {
  const [showReasoning, setShowReasoning] = useState(false);
  const [showToolResults, setShowToolResults] = useState<Record<number, boolean>>({});
  const id = useId();
  const panelId = `reasoning-panel-${id}`;
  const isAssistant = message.type === "assistant";

  const toggleToolResult = (index: number) => {
    setShowToolResults(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const renderedHtml = useMemo(
    () => renderMarkdown(message.content),
    [message.content],
  );

  return (
    <div
      className={`flex gap-3 mb-4 ${isAssistant ? "flex-row" : "flex-row-reverse"}`}
    >
      {/* Avatar */}
      <Avatar className="mt-1 shrink-0" aria-label={isAssistant ? "Asistente" : "Usuario"}>
        <AvatarFallback
          className={
            isAssistant
              ? "bg-gradient-to-r from-app-primary to-app-gradient-secondary text-app-primary-text"
              : "bg-app-bg-tertiary text-app-text"
          }
        >
          {isAssistant ? (
            <Brain className="h-5 w-5" aria-hidden="true" />
          ) : (
            <User className="h-5 w-5" aria-hidden="true" />
          )}
        </AvatarFallback>
      </Avatar>

      {/* Message content */}
      <div
        className={`max-w-[75%] rounded-lg px-4 py-3 ${
          isAssistant
            ? "bg-app-bg-secondary text-app-text border border-app-border"
            : "bg-app-primary text-app-primary-text"
        }`}
      >
        {/* Reasoning (assistant only) */}
        {isAssistant && message.reasoning && (
          <div className="mb-2">
            <button
              onClick={() => setShowReasoning(!showReasoning)}
              aria-expanded={showReasoning}
              aria-controls={panelId}
              className="flex items-center gap-1 text-xs text-app-text-secondary hover:text-app-primary transition-colors"
            >
              {showReasoning ? (
                <ChevronDown className="h-3 w-3" aria-hidden="true" />
              ) : (
                <ChevronRight className="h-3 w-3" aria-hidden="true" />
              )}
              Razonamiento
            </button>
            {showReasoning && (
              <div
                id={panelId}
                className="mt-1 text-xs text-app-text-secondary bg-app-bg-tertiary rounded p-2 whitespace-pre-wrap"
              >
                {message.reasoning}
              </div>
            )}
          </div>
        )}

        {/* Tool calls + results (assistant only) - ONE COLLAPSIBLE PER TOOL with Args + Result */}
        {isAssistant && message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mb-2">
            {message.toolCalls.map((tc, i) => {
              const result = message.toolResults?.[i];
              return (
                <div key={`${tc.tool}-${i}`} className="mb-1">
                  <button
                    onClick={() => toggleToolResult(i)}
                    aria-expanded={showToolResults[i] || false}
                    className="flex items-center gap-1 text-xs text-app-text-secondary hover:text-app-primary transition-colors"
                  >
                    {showToolResults[i] ? (
                      <ChevronDown className="h-3 w-3" aria-hidden="true" />
                    ) : (
                      <ChevronRight className="h-3 w-3" aria-hidden="true" />
                    )}
                    <Terminal className="h-3 w-3" aria-hidden="true" />
                    {tc.tool}
                  </button>
                  {showToolResults[i] && (
                    <div className="mt-1 text-xs text-app-text-secondary bg-app-bg-tertiary rounded p-2 whitespace-pre-wrap max-h-60 overflow-auto break-words">
                      {tc.parameters && Object.keys(tc.parameters).length > 0 && (
                        <>
                          <span className="font-medium">Args:</span>
                          <pre className="mt-1 whitespace-pre-wrap break-words">
                            {JSON.stringify(tc.parameters, null, 2)}
                          </pre>
                        </>
                      )}
                      {result && (
                        <>
                          {tc.parameters && Object.keys(tc.parameters).length > 0 && <hr className="my-2 border-app-border" />}
                          <span className="font-medium">Resultado:</span>
                          <pre className="mt-1 whitespace-pre-wrap break-words">
                            {JSON.stringify(result.result, null, 2)}
                          </pre>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Message content with markdown */}
        <div
          className={`markdown-content text-sm leading-relaxed ${
            isAssistant ? "" : "text-app-primary-text"
          }`}
          dangerouslySetInnerHTML={{
            __html: renderedHtml,
          }}
        />

        {/* File attachments chips (user messages only) */}
        {!isAssistant && message.files && message.files.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {message.files.map((file, idx) => (
              <div
                key={`${file.name}-${idx}`}
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs
                           bg-app-primary-text/20 border border-app-primary-text/30 text-app-primary-text"
              >
                <Paperclip className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
                <span className="truncate max-w-[150px] font-medium">{file.name}</span>
                {file.size && (
                  <span className="text-app-primary-text/70 shrink-0">
                    {(file.size < 1024 * 1024
                      ? `${(file.size / 1024).toFixed(0)} KB`
                      : `${(file.size / (1024 * 1024)).toFixed(1)} MB`)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Streaming indicator (assistant only) */}
        {isAssistant && message.isStreaming && (
          <span
            className="inline-block w-2 h-4 ml-1 bg-app-primary-light animate-pulse"
            role="status"
            aria-label="Pensando..."
          />
        )}
      </div>
    </div>
  );
}

export const MessageBubble = memo(MessageBubbleInner);

export default MessageBubble;
