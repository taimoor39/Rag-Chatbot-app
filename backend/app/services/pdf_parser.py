import re
import logging
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader
from app.core.config import settings

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """Normalize whitespace and remove non-printable characters."""
    if not text:
        return ""
    # Replace multiple newlines or spaces with single whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks using word boundaries where possible."""
    if not text:
        return []
    
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        if end >= text_length:
            chunks.append(text[start:].strip())
            break
        
        # Try finding a natural break point (space, period, newline)
        split_point = text.rfind(" ", start, end)
        if split_point == -1 or split_point <= start:
            split_point = end
        
        chunk = text[start:split_point].strip()
        if chunk:
            chunks.append(chunk)
        
        start = max(start + 1, split_point - chunk_overlap)

    return chunks

def extract_chunks_from_pdf(
    file_path: str,
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP
) -> List[Dict[str, Any]]:
    """
    Extract text from a PDF file page by page and generate chunks with metadata.
    Returns a list of dicts with:
      - text: chunk text
      - page_number: 1-indexed page
      - chunk_index: index within the document
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    reader = PdfReader(str(path))
    total_pages = len(reader.pages)
    logger.info(f"Parsing PDF {path.name} with {total_pages} pages")

    all_chunks: List[Dict[str, Any]] = []
    global_chunk_idx = 0

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
            cleaned = clean_text(raw_text)
            if not cleaned:
                continue

            page_chunks = chunk_text(cleaned, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            for chunk_str in page_chunks:
                if len(chunk_str) < 20:  # Skip trivial fragments
                    continue
                all_chunks.append({
                    "text": chunk_str,
                    "page_number": page_idx,
                    "chunk_index": global_chunk_idx,
                })
                global_chunk_idx += 1
        except Exception as e:
            logger.warning(f"Error parsing page {page_idx} of {path.name}: {e}")

    logger.info(f"Extracted {len(all_chunks)} chunks from {path.name}")
    return all_chunks
