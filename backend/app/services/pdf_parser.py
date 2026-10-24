import re
import logging
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """Normalize whitespace and remove non-printable characters."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()

def extract_documents_from_pdf(
    file_path: str,
    document_id: str,
    filename: str,
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP,
) -> List[Document]:
    """
    Extract text from PDF and split into LangChain Document objects using RecursiveCharacterTextSplitter.
    Each Document contains page_content and rich metadata for vector retrieval.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    reader = PdfReader(str(path))
    raw_docs: List[Document] = []

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
            cleaned = clean_text(text)
            if cleaned and len(cleaned) >= 20:
                raw_docs.append(
                    Document(
                        page_content=cleaned,
                        metadata={
                            "document_id": document_id,
                            "filename": filename,
                            "page_number": page_idx,
                        }
                    )
                )
        except Exception as e:
            logger.warning(f"Error extracting page {page_idx} of {filename}: {e}")

    if not raw_docs:
        return []

    # Use LangChain's RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    split_docs = text_splitter.split_documents(raw_docs)
    for idx, doc in enumerate(split_docs):
        doc.metadata["chunk_index"] = idx

    logger.info(f"LangChain split {filename} into {len(split_docs)} chunk documents")
    return split_docs

# Helper function for test backward-compatibility
def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)
