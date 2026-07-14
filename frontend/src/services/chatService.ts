const API_BASE_URL = import.meta.env.VITE_URL_BASE || "http://localhost:8000";

export interface StreamEvent {
  type: string;
  content: any;
}

export interface ChatParams {
  message: string;
  files?: File[];
  sessionId?: string | null;
}

let activeController: AbortController | null = null;

const chatService = {
  /**
   * Send a message to the chat endpoint with SSE streaming support.
   * Supports file attachments via FormData.
   * Yields parsed SSE events as StreamEvent objects.
   */
  async *sendMessage(params: ChatParams): AsyncGenerator<StreamEvent> {
    const { message, files, sessionId } = params;
    const controller = new AbortController();
    activeController = controller;

    const formData = new FormData();
    formData.append("message", message);
    if (sessionId) formData.append("session_id", sessionId);
    if (files && files.length > 0) {
      files.forEach((f) => formData.append("files", f));
    }

    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorBody = await response.text().catch(() => "");
      throw new Error(
        `HTTP ${response.status}: ${errorBody || response.statusText}`
      );
    }

    if (!response.body) {
      throw new Error("Response body is null — streaming not available");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          buffer += decoder.decode(); // Flush decoder residual bytes
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const lines = part.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              try {
                const parsed = JSON.parse(data);
                yield parsed as StreamEvent;
                if (parsed.type === "done" && parsed.content === "[DONE]") {
                  return;
                }
              } catch {
                console.warn("Malformed SSE JSON, skipping:", data);
              }
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        yield { type: "chunk", content: "*Transmisión cancelada.*" };
        return;
      }
      throw err;
    } finally {
      reader.releaseLock();
      activeController = null;
    }
  },

  /** Cancel an active stream by aborting the underlying fetch request. */
  cancelStream(): void {
    if (activeController) {
      activeController.abort();
      activeController = null;
    }
  },

  /** Delete the active conversation for a user in the backend. */
  async deleteConversation(userId: string): Promise<void> {
    const formData = new FormData();

    const response = await fetch(`${API_BASE_URL}/api/chat/delete-conversation`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Failed to delete conversation: ${response.statusText}`);
    }
  },
};

export default chatService;
