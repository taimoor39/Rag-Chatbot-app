/**
 * Main RAG Chatbot Controller (Platform-Native Vanilla JS)
 * Zero jQuery - 100% Platform-Native APIs
 */

document.addEventListener("DOMContentLoaded", () => {
  // Application State
  const state = {
    conversationHistory: [],
    documents: [],
    activeTaskId: null,
    pollingInterval: null,
    isGenerating: false,
    selectedDocIds: [],
  };

  // DOM Elements
  const chatMessages = document.getElementById("chatMessages");
  const messagesInner = document.getElementById("messagesInner");
  const heroScreen = document.getElementById("heroScreen");
  const chatInput = document.getElementById("chatInput");
  const btnSend = document.getElementById("btnSend");
  const fileInput = document.getElementById("fileInput");
  const dropzone = document.getElementById("dropzone");
  const indexingCard = document.getElementById("indexingStatusCard");
  const indexingTitle = document.getElementById("indexingTitle");
  const indexingProgress = document.getElementById("indexingProgress");
  const docsList = document.getElementById("docsList");
  const docsCount = document.getElementById("docsCount");
  const btnNewChat = document.getElementById("btnNewChat");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const btnAttachFile = document.getElementById("btnAttachFile");

  // 1. Initialize Application
  initApp();

  function initApp() {
    checkBackendHealth();
    loadDocuments();
    setupEventListeners();
  }

  // 2. Health Check
  async function checkBackendHealth() {
    try {
      const health = await API.checkHealth();
      if (health.valkey_connected && health.qdrant_connected) {
        if (statusDot) statusDot.style.backgroundColor = "#10a37f";
        if (statusText) statusText.textContent = "Valkey & Qdrant Online";
      } else {
        if (statusDot) statusDot.style.backgroundColor = "#ff6b6b";
        if (statusText) statusText.textContent = "Services Degraded";
      }
    } catch (e) {
      if (statusDot) statusDot.style.backgroundColor = "#ff6b6b";
      if (statusText) statusText.textContent = "Backend Offline";
    }
  }

  // 3. Load Documents from Vector DB
  async function loadDocuments() {
    try {
      const res = await API.listDocuments();
      state.documents = res.documents || [];
      renderDocumentsList();
    } catch (e) {
      console.error("Failed to load documents:", e);
    }
  }

  function renderDocumentsList() {
    docsList.innerHTML = "";
    docsCount.textContent = state.documents.length;

    if (state.documents.length === 0) {
      docsList.innerHTML = `
        <div class="text-center p-3 text-muted" style="font-size: 0.8rem;">
          No PDF documents indexed yet.<br>Upload a PDF above to get started.
        </div>
      `;
      return;
    }

    state.documents.forEach((doc) => {
      const item = document.createElement("div");
      item.className = "doc-item";
      item.dataset.id = doc.document_id;
      item.innerHTML = `
        <div style="overflow: hidden;">
          <div class="doc-name" title="${Utils.escapeHtml(doc.filename)}">
            📄 ${Utils.escapeHtml(doc.filename)}
          </div>
          <div class="doc-meta">
            ${doc.chunk_count} chunks indexed
          </div>
        </div>
        <button class="btn-delete-doc" title="Delete document">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18m-2 0v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6m3 0V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
          </svg>
        </button>
      `;

      item.querySelector(".btn-delete-doc").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm(`Remove "${doc.filename}" from Qdrant vector database?`)) {
          await deleteDocument(doc.document_id);
        }
      });

      docsList.appendChild(item);
    });
  }

  async function deleteDocument(docId) {
    try {
      await API.deleteDocument(docId);
      await loadDocuments();
    } catch (e) {
      alert("Failed to delete document: " + e.message);
    }
  }

  // 4. File Upload & Valkey Queue Polling
  function setupFileUpload() {
    dropzone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", function () {
      if (this.files && this.files[0]) {
        handleFileSelection(this.files[0]);
        this.value = "";
      }
    });

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    ["dragleave", "drop"].forEach((ev) => {
      dropzone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (ev === "drop" && e.dataTransfer.files[0]) {
          handleFileSelection(e.dataTransfer.files[0]);
        }
      });
    });
  }

  async function handleFileSelection(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please upload a PDF (.pdf) file.");
      return;
    }

    try {
      indexingCard.style.display = "block";
      indexingTitle.textContent = `Uploading: ${file.name}`;
      indexingProgress.style.width = "10%";
      indexingProgress.style.backgroundColor = "";

      const res = await API.uploadDocument(file);
      state.activeTaskId = res.task_id;
      startPollingTask(res.task_id, file.name);
    } catch (err) {
      alert("Upload error: " + err.message);
      indexingCard.style.display = "none";
    }
  }

  function startPollingTask(taskId, filename) {
    if (state.pollingInterval) clearInterval(state.pollingInterval);

    state.pollingInterval = setInterval(async () => {
      try {
        const task = await API.getTaskStatus(taskId);
        const progress = task.progress || 15;
        indexingProgress.style.width = `${progress}%`;

        switch (task.status) {
          case "QUEUED":
            indexingTitle.textContent = `Queued in Valkey...`;
            break;
          case "PARSING":
            indexingTitle.textContent = `Parsing PDF pages...`;
            break;
          case "EMBEDDING":
            indexingTitle.textContent = `Generating OpenAI Embeddings...`;
            break;
          case "INDEXING":
            indexingTitle.textContent = `Indexing vectors into Qdrant...`;
            break;
          case "COMPLETED":
            clearInterval(state.pollingInterval);
            indexingProgress.style.width = "100%";
            indexingTitle.textContent = `Completed! (${task.total_chunks} chunks)`;
            setTimeout(() => {
              indexingCard.style.display = "none";
              loadDocuments();
            }, 2500);
            break;
          case "FAILED":
            clearInterval(state.pollingInterval);
            indexingTitle.textContent = `Failed: ${task.error || "Unknown error"}`;
            indexingProgress.style.backgroundColor = "#ff6b6b";
            setTimeout(() => {
              indexingCard.style.display = "none";
            }, 5000);
            break;
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    }, 1500);
  }

  // 5. Chat Interaction & Real-Time SSE Stream
  async function sendMessage(text) {
    const message = text || chatInput.value.trim();
    if (!message || state.isGenerating) return;

    state.isGenerating = true;
    btnSend.disabled = true;
    heroScreen.style.display = "none";

    // Reset input height
    chatInput.value = "";
    chatInput.style.height = "24px";

    // Append User Message
    appendUserMessage(message);
    state.conversationHistory.push({ role: "user", content: message });

    // Append Assistant Message container
    const { citationsBox, updateContent, finalize } = createAssistantMessage();

    let fullAnswer = "";

    await API.streamChat({
      message: message,
      conversationHistory: state.conversationHistory,
      docIds: state.selectedDocIds.length > 0 ? state.selectedDocIds : null,
      onSources: (sources) => {
        if (sources && sources.length > 0) {
          renderCitations(citationsBox, sources);
        }
      },
      onToken: (token) => {
        fullAnswer += token;
        updateContent(fullAnswer);
        scrollToBottom();
      },
      onDone: () => {
        finalize(fullAnswer);
        state.conversationHistory.push({ role: "assistant", content: fullAnswer });
        state.isGenerating = false;
        btnSend.disabled = false;
        chatInput.focus();
        scrollToBottom();
      },
      onError: (err) => {
        finalize(fullAnswer + `\n\n*[Error: ${err.message}]*`);
        state.isGenerating = false;
        btnSend.disabled = false;
      }
    });
  }

  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `<div class="message-bubble">${Utils.escapeHtml(text)}</div>`;
    messagesInner.appendChild(row);
    scrollToBottom();
  }

  function createAssistantMessage() {
    const row = document.createElement("div");
    row.className = "message-row bot";
    row.innerHTML = `
      <div class="message-avatar bot">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect width="16" height="12" x="4" y="8" rx="2"></rect>
          <path d="M12 8V4H8"></path>
        </svg>
      </div>
      <div class="message-bubble" style="width: 100%;">
        <div class="bubble-content streaming-cursor"></div>
        <div class="citations-box" style="display: none;"></div>
      </div>
    `;

    messagesInner.appendChild(row);
    const content = row.querySelector(".bubble-content");
    const citations = row.querySelector(".citations-box");

    return {
      bubble: row,
      citationsBox: citations,
      updateContent: (rawMarkdown) => {
        content.innerHTML = Utils.renderMarkdown(rawMarkdown);
      },
      finalize: (rawMarkdown) => {
        content.classList.remove("streaming-cursor");
        content.innerHTML = Utils.renderMarkdown(rawMarkdown);
      }
    };
  }

  function renderCitations(container, sources) {
    if (!sources || sources.length === 0) return;

    let itemsHtml = "";
    sources.forEach((s) => {
      itemsHtml += `
        <div class="citation-card">
          <div class="citation-card-header">
            <span class="citation-doc-title" title="${Utils.escapeHtml(s.filename)}">📄 ${Utils.escapeHtml(s.filename)}</span>
            <span class="citation-score-badge">${(s.score * 100).toFixed(1)}% match</span>
          </div>
          <div class="d-flex align-items-center gap-2">
            <span class="citation-tag">Page ${s.page_number}</span>
          </div>
          <div class="citation-card-text">
            ${Utils.escapeHtml(s.chunk_text)}
          </div>
        </div>
      `;
    });

    container.className = "citations-box";
    container.innerHTML = `
      <button class="citations-header-btn" type="button" title="Click to view/hide grounded source excerpts">
        <span class="citations-label">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
          </svg>
          <span>${sources.length} Grounded Sources</span>
          <span class="citations-badge-pill">Qdrant Verified</span>
        </span>
        <svg class="citations-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
      <div class="citations-grid">
        ${itemsHtml}
      </div>
    `;
    container.style.display = "block";

    const btn = container.querySelector(".citations-header-btn");
    btn.addEventListener("click", () => {
      container.classList.toggle("open");
    });
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // 6. Setup Event Listeners
  function setupEventListeners() {
    setupFileUpload();

    // Auto-resizing textarea
    chatInput.addEventListener("input", function () {
      this.style.height = "24px";
      this.style.height = Math.min(this.scrollHeight, 160) + "px";
      btnSend.disabled = this.value.trim().length === 0 || state.isGenerating;
    });

    // Enter sends message; Shift+Enter adds newline
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    btnSend.addEventListener("click", () => sendMessage());

    // Prompt suggestions
    document.querySelectorAll(".suggestion-card").forEach((card) => {
      card.addEventListener("click", () => {
        const prompt = card.dataset.prompt;
        if (prompt) {
          chatInput.value = prompt;
          sendMessage(prompt);
        }
      });
    });

    // New Chat button
    btnNewChat.addEventListener("click", () => {
      state.conversationHistory = [];
      messagesInner.querySelectorAll(".message-row").forEach((r) => r.remove());
      heroScreen.style.display = "block";
      chatInput.value = "";
      chatInput.focus();
    });

    // Attach shortcut button triggers file selection
    btnAttachFile.addEventListener("click", () => fileInput.click());
  }
});
