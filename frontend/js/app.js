/**
 * Main RAG Chatbot Controller (Vanilla JS + jQuery)
 */

$(document).ready(function () {
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
  const $chatMessages = $("#chatMessages");
  const $messagesInner = $("#messagesInner");
  const $heroScreen = $("#heroScreen");
  const $chatInput = $("#chatInput");
  const $btnSend = $("#btnSend");
  const $fileInput = $("#fileInput");
  const $dropzone = $("#dropzone");
  const $indexingCard = $("#indexingStatusCard");
  const $indexingTitle = $("#indexingTitle");
  const $indexingProgress = $("#indexingProgress");
  const $docsList = $("#docsList");
  const $docsCount = $("#docsCount");
  const $btnNewChat = $("#btnNewChat");
  const $valkeyIndicator = $("#valkeyIndicator");
  const $qdrantIndicator = $("#qdrantIndicator");
  const $statusText = $("#statusText");

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
        $valkeyIndicator.css("background-color", "#10a37f");
        $qdrantIndicator.css("background-color", "#10a37f");
        $statusText.text("Valkey & Qdrant Online");
      } else {
        $valkeyIndicator.css("background-color", health.valkey_connected ? "#10a37f" : "#ff6b6b");
        $qdrantIndicator.css("background-color", health.qdrant_connected ? "#10a37f" : "#ff6b6b");
        $statusText.text("Services Degraded");
      }
    } catch (e) {
      $valkeyIndicator.css("background-color", "#ff6b6b");
      $qdrantIndicator.css("background-color", "#ff6b6b");
      $statusText.text("Backend Offline");
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
    $docsList.empty();
    $docsCount.text(state.documents.length);

    if (state.documents.length === 0) {
      $docsList.html(`
        <div class="text-center p-3 text-muted" style="font-size: 0.8rem;">
          No PDF documents indexed yet.<br>Upload a PDF above to get started.
        </div>
      `);
      return;
    }

    state.documents.forEach((doc) => {
      const $item = $(`
        <div class="doc-item" data-id="${doc.document_id}">
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
        </div>
      `);

      $item.find(".btn-delete-doc").on("click", async function (e) {
        e.stopPropagation();
        if (confirm(`Remove "${doc.filename}" from Qdrant vector database?`)) {
          await deleteDocument(doc.document_id);
        }
      });

      $docsList.append($item);
    });
  }

  async function deleteDocument(docId) {
    try {
      await API.deleteDocument(docId);
      await loadDocuments();
    } catch (e) {
      alert("Failed to delete document: " + (e.responseJSON?.detail || e.message));
    }
  }

  // 4. File Upload & Valkey Queue Polling
  function setupFileUpload() {
    $dropzone.on("click", () => $fileInput.trigger("click"));

    $fileInput.on("change", function () {
      if (this.files && this.files[0]) {
        handleFileSelection(this.files[0]);
        $fileInput.val("");
      }
    });

    $dropzone.on("dragover", function (e) {
      e.preventDefault();
      $(this).addClass("dragover");
    });

    $dropzone.on("dragleave drop", function (e) {
      e.preventDefault();
      $(this).removeClass("dragover");
      if (e.type === "drop" && e.originalEvent.dataTransfer.files[0]) {
        handleFileSelection(e.originalEvent.dataTransfer.files[0]);
      }
    });
  }

  async function handleFileSelection(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please upload a PDF (.pdf) file.");
      return;
    }

    try {
      $indexingCard.fadeIn();
      $indexingTitle.text(`Uploading: ${file.name}`);
      $indexingProgress.css("width", "10%").text("");

      const res = await API.uploadDocument(file);
      state.activeTaskId = res.task_id;
      startPollingTask(res.task_id, file.name);
    } catch (err) {
      alert("Upload error: " + (err.responseJSON?.detail || err.message));
      $indexingCard.fadeOut();
    }
  }

  function startPollingTask(taskId, filename) {
    if (state.pollingInterval) clearInterval(state.pollingInterval);

    state.pollingInterval = setInterval(async () => {
      try {
        const task = await API.getTaskStatus(taskId);
        const progress = task.progress || 15;
        $indexingProgress.css("width", `${progress}%`);

        switch (task.status) {
          case "QUEUED":
            $indexingTitle.text(`Queued in Valkey...`);
            break;
          case "PARSING":
            $indexingTitle.text(`Parsing PDF pages...`);
            break;
          case "EMBEDDING":
            $indexingTitle.text(`Generating OpenAI Embeddings...`);
            break;
          case "INDEXING":
            $indexingTitle.text(`Indexing vectors into Qdrant...`);
            break;
          case "COMPLETED":
            clearInterval(state.pollingInterval);
            $indexingProgress.css("width", "100%");
            $indexingTitle.text(`Completed! (${task.total_chunks} chunks)`);
            setTimeout(() => {
              $indexingCard.fadeOut();
              loadDocuments();
            }, 2500);
            break;
          case "FAILED":
            clearInterval(state.pollingInterval);
            $indexingTitle.text(`Failed: ${task.error || "Unknown error"}`);
            $indexingProgress.css("background", "#ff6b6b");
            setTimeout(() => $indexingCard.fadeOut(), 5000);
            break;
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    }, 1500);
  }

  // 5. Chat Interaction & Real-Time SSE Stream
  async function sendMessage(text) {
    const message = text || $chatInput.val().trim();
    if (!message || state.isGenerating) return;

    state.isGenerating = true;
    $btnSend.prop("disabled", true);
    $heroScreen.hide();

    // Reset input height
    $chatInput.val("").css("height", "24px");

    // Append User Bubble
    appendUserMessage(message);
    state.conversationHistory.push({ role: "user", content: message });

    // Append Assistant Bubble container
    const { $bubble, $citationsBox, updateContent, finalize } = createAssistantMessage();

    let fullAnswer = "";

    await API.streamChat({
      message: message,
      conversationHistory: state.conversationHistory,
      docIds: state.selectedDocIds.length > 0 ? state.selectedDocIds : null,
      onSources: (sources) => {
        if (sources && sources.length > 0) {
          renderCitations($citationsBox, sources);
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
        $btnSend.prop("disabled", false);
        $chatInput.focus();
        scrollToBottom();
      },
      onError: (err) => {
        finalize(fullAnswer + `\n\n*[Error: ${err.message}]*`);
        state.isGenerating = false;
        $btnSend.prop("disabled", false);
      }
    });
  }

  function appendUserMessage(text) {
    const $row = $(`
      <div class="message-row user">
        <div class="message-bubble">${Utils.escapeHtml(text)}</div>
      </div>
    `);
    $messagesInner.append($row);
    scrollToBottom();
  }

  function createAssistantMessage() {
    const $row = $(`
      <div class="message-row bot">
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
      </div>
    `);

    $messagesInner.append($row);
    const $content = $row.find(".bubble-content");
    const $citations = $row.find(".citations-box");

    return {
      $bubble: $row,
      $citationsBox: $citations,
      updateContent: (rawMarkdown) => {
        $content.html(Utils.renderMarkdown(rawMarkdown));
      },
      finalize: (rawMarkdown) => {
        $content.removeClass("streaming-cursor");
        $content.html(Utils.renderMarkdown(rawMarkdown));
      }
    };
  }

  function renderCitations($container, sources) {
    if (!sources || sources.length === 0) return;

    let itemsHtml = "";
    sources.forEach((s, idx) => {
      itemsHtml += `
        <div class="citation-item">
          <div class="citation-meta">
            [${idx + 1}] <strong>${Utils.escapeHtml(s.filename)}</strong> (Page ${s.page_number}, Score: ${(s.score * 100).toFixed(1)}%)
          </div>
          <div style="font-size: 0.74rem; color: #a0a0a0;">
            ${Utils.escapeHtml(s.chunk_text.substring(0, 180))}...
          </div>
        </div>
      `;
    });

    $container.html(`
      <div class="citations-header">
        <span>📚 Grounded Sources (${sources.length} matches from Qdrant)</span>
        <span class="citation-pill">RAG Verified</span>
      </div>
      <div class="citations-body">
        ${itemsHtml}
      </div>
    `).fadeIn();
  }

  function scrollToBottom() {
    $chatMessages.scrollTop($chatMessages[0].scrollHeight);
  }

  // 6. Setup Event Listeners
  function setupEventListeners() {
    setupFileUpload();

    // Auto-resizing textarea
    $chatInput.on("input", function () {
      this.style.height = "24px";
      this.style.height = Math.min(this.scrollHeight, 160) + "px";
      $btnSend.prop("disabled", this.value.trim().length === 0 || state.isGenerating);
    });

    // Enter sends message; Shift+Enter adds newline
    $chatInput.on("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    $btnSend.on("click", () => sendMessage());

    // Prompt suggestions
    $(".suggestion-card").on("click", function () {
      const prompt = $(this).data("prompt");
      if (prompt) {
        $chatInput.val(prompt);
        sendMessage(prompt);
      }
    });

    // New Chat button
    $btnNewChat.on("click", function () {
      state.conversationHistory = [];
      $messagesInner.find(".message-row").remove();
      $heroScreen.show();
      $chatInput.val("").focus();
    });

    // Attach shortcut button triggers file selection
    $("#btnAttachFile").on("click", () => $fileInput.trigger("click"));
  }
});
