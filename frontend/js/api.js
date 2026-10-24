/**
 * Platform-Native API Client for RAG Chatbot Backend
 * 100% Vanilla JS (No jQuery dependency)
 */

const API = {
  baseUrl: "",

  async _request(endpoint, options = {}) {
    const res = await fetch(`${this.baseUrl}${endpoint}`, options);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed with status ${res.status}`);
    }
    return res.json();
  },

  /**
   * Health check
   */
  async checkHealth() {
    return this._request("/api/health");
  },

  /**
   * Upload PDF document to initiate background Valkey task
   */
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append("file", file);

    return this._request("/api/docs/upload", {
      method: "POST",
      body: formData,
    });
  },

  /**
   * Poll Valkey indexing task status
   */
  async getTaskStatus(taskId) {
    return this._request(`/api/docs/status/${encodeURIComponent(taskId)}`);
  },

  /**
   * List all indexed documents from Qdrant
   */
  async listDocuments() {
    return this._request("/api/docs");
  },

  /**
   * Delete document chunks from Qdrant
   */
  async deleteDocument(documentId) {
    return this._request(`/api/docs/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
    });
  },

  /**
   * Stream RAG Chat Completion via Server-Sent Events (SSE)
   */
  async streamChat({ message, conversationHistory = [], docIds = null, onSources, onToken, onDone, onError }) {
    try {
      const response = await fetch(`${this.baseUrl}/api/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify({
          message: message,
          conversation_history: conversationHistory,
          doc_ids: docIds,
        }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop();

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue;

          let eventName = "message";
          let dataStr = "";

          const lines = eventBlock.split("\n");
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventName = line.replace("event:", "").trim();
            } else if (line.startsWith("data:")) {
              dataStr += line.replace("data:", "").trim();
            }
          }

          if (eventName === "sources" && onSources) {
            try {
              const sources = JSON.parse(dataStr);
              onSources(sources);
            } catch (e) {
              console.error("Failed to parse sources JSON:", e);
            }
          } else if (eventName === "token" && onToken) {
            try {
              const payload = JSON.parse(dataStr);
              onToken(payload.token);
            } catch (e) {
              console.error("Failed to parse token JSON:", e);
            }
          } else if (eventName === "done" && onDone) {
            onDone();
          }
        }
      }

      if (onDone) onDone();
    } catch (err) {
      console.error("Stream error:", err);
      if (onError) onError(err);
    }
  }
};
