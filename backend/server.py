import uvicorn

if __name__ == "__main__":
    print("🚀 Starting RAG ChatGPT FastAPI Server on http://localhost:8000 ...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reloads when you save changes to your code
        log_level="info"
    )