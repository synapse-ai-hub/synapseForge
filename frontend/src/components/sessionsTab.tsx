import { Plus, MessageSquare, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import sessionService, { type ChatSession } from "../services/sessionService";

type SidebarTab = "sessions" | "config" | "agent" | "create";

interface SidebarProps {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  refreshTrigger: number;
}

function formatTimestamp(value: string): string {
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function SessionsTab({
  activeSessionId,
  onSelectSession,
  onNewChat,
  refreshTrigger,
  sessions,
  isLoading,
  deletingId,
  handleDelete,
}: {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  refreshTrigger: number;
  sessions: ChatSession[];
  isLoading: boolean;
  deletingId: string | null;
  handleDelete: (id: string, e: React.MouseEvent) => Promise<void>;
}) {
  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* New chat */}
      <div className="p-3 border-b border-app-border bg-white">
        <Button onClick={onNewChat} className="w-full gap-2 bg-app-btn-nuevo-chat-bg text-app-btn-nuevo-chat-text hover:bg-app-btn-nuevo-chat-bg/90">
          <Plus size={16} />
          Nuevo Chat
        </Button>
      </div>

      {/* Session list*/}
      <div className="flex-1 flex flex-col min-h-0">
        {/* History - 70% */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1.5 min-h-0" style={{ maxHeight: "70%" }}>
          {isLoading ? (
            <div className="text-center py-4 text-sm text-app-text-secondary">
              Cargando...
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-4 text-sm text-app-text-secondary">
              No hay conversaciones todavía.
            </div>
          ) : (
            sessions.map((s) => {
              const isActive = activeSessionId === s.session_id;
              return (
                <div
                  key={s.session_id}
                  onClick={() => onSelectSession(s.session_id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectSession(s.session_id);
                    }
                  }}
                  className={`group w-full text-left p-2.5 rounded-lg border cursor-pointer transition-colors ${
                    isActive
                      ? "border-app-primary bg-white"
                      : "border-transparent bg-white hover:bg-app-bg-tertiary"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare
                      size={14}
                      className="mt-0.5 shrink-0 text-app-primary"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-app-text truncate">
                        {s.title}
                      </div>
                      {s.preview ? (
                        <div className="text-[11px] text-app-text-secondary truncate mt-0.5">
                          {s.preview}
                        </div>
                      ) : null}
                      <div className="text-[11px] text-app-text-secondary mt-0.5">
                        {formatTimestamp(s.updated_at)}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => handleDelete(s.session_id, e)}
                      disabled={deletingId === s.session_id}
                      className="shrink-0 rounded p-1 text-app-text-secondary opacity-0 group-hover:opacity-100 hover:bg-red-100 hover:text-app-error transition-all"
                      aria-label="Eliminar conversación"
                    >
                      {deletingId === s.session_id ? (
                        <div
                          style={{ width: "14px", height: "14px", border: "2px solid #9ca3af", borderTop: "2px solid #C2413D", borderRadius: "50%", animation: "spin 1s linear infinite" }}
                        />
                      ) : (
                        <Trash2 size={14} />
                      )}
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default SessionsTab;