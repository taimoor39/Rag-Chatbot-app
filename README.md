# 🤖 Full-Stack ChatGPT RAG with Valkey & Qdrant

A production-grade, asynchronous Retrieval-Augmented Generation (RAG) conversational AI application. Built with **FastAPI**, **Valkey Queue (Docker)**, **Qdrant Vector Database (Docker)**, **OpenAI Embeddings & Chat Completion (Streaming)**, and a **ChatGPT-style UI (HTML, CSS, Bootstrap 5, Vanilla JS, and jQuery)**.

---

## 🌟 Key Features

- **Asynchronous Background Ingestion**: PDF uploads are non-blocking; document parsing, chunking, and embedding are enqueued and processed via **Valkey** queue workers.
- **Valkey Message Broker**: Uses official Docker image `valkey/valkey:latest` (high-performance Redis fork) for background tasks and live status tracking.
- **Qdrant Vector Database**: High-speed vector similarity search using `qdrant/qdrant:latest` with cosine similarity on OpenAI `text-embedding-3-small` (1536 dimensions).
- **ChatGPT Real-Time Streaming UI**: Built with HTML5, CSS3, Bootstrap 5, and jQuery, supporting Server-Sent Events (SSE) for word-by-word streaming responses.
- **Grounded Citations**: Responses automatically reference and display matching PDF document names, page numbers, and cosine similarity scores.

---

## 🏛️ System Architecture

```text
       ┌────────────────────────────────────────────────────────┐
       │     Frontend: HTML5 + Bootstrap 5 + JS/jQuery          │
       └───────────┬────────────────────────────────┬───────────┘
                   │ (1) PDF Upload                 │ (4) Chat Prompt (SSE Stream)
                   ▼                                ▼
       ┌───────────────────────┐        ┌───────────────────────┐
       │  FastAPI: /docs/upload│        │   FastAPI: /chat/stream│
       └───────────┬───────────┘        └───────────┬───────────┘
                   │ Enqueue Job                    │ Top-k Chunks
                   ▼                                ▼
       ┌───────────────────────┐        ┌───────────────────────┐
       │     Valkey Queue      │        │   Qdrant Vector DB    │
       │    (Docker Container) │        │   (Docker Container)  │
       └───────────┬───────────┘        └───────────▲───────────┘
                   │ Consume Task                   │ Upsert Vectors
                   ▼                                │
       ┌───────────────────────┐                    │
       │ Valkey Queue Worker   ├────────────────────┘
       │ (PDF Parse & Embed)   │
       └───────────────────────┘
```

---

## 📁 Project Structure

```text
rag-chatbot/
├── docker-compose.yml             # Valkey and Qdrant container configurations
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore rules for virtualenvs, keys, & data
├── README.md                      # Complete setup and architecture documentation
│
├── backend/
│   ├── requirements.txt           # Python backend dependencies
│   ├── server.py                  # Server runner script
│   ├── uploads/                   # Staged PDF storage directory
│   │
│   └── app/
│       ├── main.py                # FastAPI app setup, CORS, lifespan & static mount
│       ├── core/
│       │   ├── config.py          # App settings & environment validation
│       │   ├── valkey_conn.py     # Valkey connection pool & queue manager
│       │   └── qdrant_conn.py     # Qdrant client & collection initializer
│       ├── services/
│       │   ├── pdf_parser.py      # PDF text extractor & overlapping chunker
│       │   ├── openai_service.py  # Embeddings batching & token streaming
│       │   └── qdrant_service.py  # Vector upsert, cosine search & point deletion
│       ├── workers/
│       │   ├── tasks.py           # Multi-step ingestion task (Parse -> Embed -> Index)
│       │   └── worker.py          # Valkey background queue consumer
│       ├── schemas/
│       │   ├── chat_schema.py     # Pydantic models for chat & citations
│       │   └── document_schema.py # Pydantic models for docs & task progress
│       └── api/
│           ├── routes_docs.py     # Upload, task polling, and document endpoints
│           └── routes_chat.py     # RAG streaming & synchronous chat endpoints
│
└── frontend/
    ├── index.html                 # ChatGPT-style web interface
    ├── css/
    │   └── style.css              # Dark theme styling, animations & markdown formatting
    ├── js/
    │   ├── api.js                 # API abstraction & SSE streaming reader
    │   ├── utils.js               # Markdown parser & string formatters
    │   └── app.js                 # UI controller, dropzone, poller, & chat loop
    └── assets/
        └── icons/                 # SVG icons (bot, user, paperclip, send)
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- [Docker & Docker Compose](https://www.docker.com/)
- [Python 3.10+](https://www.python.org/)
- An [OpenAI API Key](https://platform.openai.com/api-keys)

---

### 2. Start Valkey & Qdrant Containers

Run Docker Compose from the root directory:

```bash
docker compose up -d
```

Verify that both containers are running healthy:

```bash
docker ps
```
You should see:
- `rag_valkey_queue` on port `6379`
- `rag_qdrant_vectordb` on ports `6333` & `6334`

---

### 3. Setup Backend Environment

Create and activate a Python virtual environment:

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

---

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and add your OpenAI API Key:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
OPENAI_API_KEY=sk-proj-yourActualOpenAIKeyHere
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o-mini

VALKEY_HOST=localhost
VALKEY_PORT=6379

QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=rag_documents
```

---

### 5. Start the Background Ingestion Worker

In your first terminal (with the virtual environment activated), start the Valkey background worker:

```bash
# From the project root
python backend/app/workers/worker.py
```

*Output:*
```text
[ValkeyWorker] 🚀 Valkey RAG Background Queue Worker Started
[ValkeyWorker] Connected to Valkey at: localhost:6379
[ValkeyWorker] Listening on Queue: 'rag_indexing_queue'
```

---

### 6. Start the FastAPI Web Server

In a second terminal (with the virtual environment activated), start the FastAPI server:

```bash
# From the project root
python backend/server.py
```

The server will initialize the Qdrant collection `rag_documents` and start on:
- **Application UI**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 💬 Usage Flow

1. **Upload Documents**: In the left sidebar, drag & drop any PDF document.
2. **Background Processing**: FastAPI sends the file to the Valkey queue. The background worker parses text, creates embeddings with OpenAI, and stores vectors into Qdrant. The progress bar reflects live status (`PARSING` -> `EMBEDDING` -> `INDEXING` -> `COMPLETED`).
3. **Chat**: Ask any question in the input box. The system retrieves relevant chunks from Qdrant, synthesizes the answer with `gpt-4o-mini`, and streams tokens with source citations!

---

## 🛠️ API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/docs/upload` | Upload a PDF document and enqueue indexing in Valkey. |
| `GET` | `/api/docs/status/{task_id}` | Poll asynchronous indexing progress from Valkey. |
| `GET` | `/api/docs` | List all unique documents stored in Qdrant. |
| `DELETE` | `/api/docs/{document_id}` | Delete document vectors and payloads from Qdrant. |
| `POST` | `/api/chat/stream` | Stream RAG completions via Server-Sent Events (SSE). |
| `POST` | `/api/chat` | Synchronous RAG completion fallback. |
| `GET` | `/api/health` | Health status of Valkey, Qdrant, and OpenAI connections. |

---

## 🛡️ License
MIT License.
