/**
 * Platform-Native Frontend Utility Functions
 */

const Utils = {
  /**
   * Escape HTML to prevent XSS vulnerabilities.
   */
  escapeHtml(text) {
    if (!text) return "";
    const map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    };
    return text.toString().replace(/[&<>"']/g, (m) => map[m]);
  },

  /**
   * Render Markdown text into HTML safely.
   */
  renderMarkdown(text) {
    if (!text) return "";
    if (window.marked && typeof window.marked.parse === "function") {
      try {
        return window.marked.parse(text);
      } catch (e) {
        console.error("Marked parsing error:", e);
      }
    }
    // Fallback basic markdown
    return Utils.escapeHtml(text)
      .replace(/\n\n/g, "<br><br>")
      .replace(/\n/g, "<br>")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }
};
