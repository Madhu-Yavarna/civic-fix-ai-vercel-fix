import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import pymupdf  # PyMuPDF
import faiss
from sentence_transformers import SentenceTransformer

from app.config import FAISS_DIR

logger = logging.getLogger("civicfix.rag")

INDEX_FILE = FAISS_DIR / "civic_faiss.index"
METADATA_FILE = FAISS_DIR / "civic_metadata.json"
MODEL_NAME = "all-MiniLM-L6-v2"

# Lazy-loaded global model instance
_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Check for cached snapshot first to ensure 100% offline and rapid execution
        snapshot_dir = (
            Path(os.path.expanduser("~"))
            / ".cache"
            / "huggingface"
            / "hub"
            / "models--sentence-transformers--all-MiniLM-L6-v2"
            / "snapshots"
            / "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
        )
        if snapshot_dir.exists():
            logger.info(f"Loading SentenceTransformer directly from local cache: {snapshot_dir}")
            _model = SentenceTransformer(str(snapshot_dir))
        else:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            logger.info(f"Loading SentenceTransformer model '{MODEL_NAME}' in local mode...")
            try:
                _model = SentenceTransformer(MODEL_NAME, local_files_only=True)
            except Exception:
                _model = SentenceTransformer(MODEL_NAME)
    return _model


class RAGEngine:
    def __init__(self):
        self.index_path = str(INDEX_FILE)
        self.meta_path = str(METADATA_FILE)
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[Dict[str, Any]] = []
        self._load_or_initialize()

    def _load_or_initialize(self):
        """Loads existing FAISS index and metadata or initializes empty structures."""
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors and {len(self.metadata)} metadata records.")
            except Exception as e:
                logger.error(f"Error loading existing index: {e}. Reinitializing.")
                self._initialize_empty()
        else:
            self._initialize_empty()

    def _initialize_empty(self):
        # 384 dimensions for all-MiniLM-L6-v2
        dim = 384
        self.index = faiss.IndexFlatIP(dim)
        self.metadata = []
        self._persist()

    def _persist(self):
        """Saves current index and metadata to disk."""
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def extract_and_chunk_pdf(
        self,
        pdf_path: str,
        doc_id: int,
        title: str,
        filename: str,
        category_tag: Optional[str] = None,
        chunk_size: int = 400,
        chunk_overlap: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Extracts text from PDF page-by-page using PyMuPDF and creates overlapping chunks.
        """
        doc = pymupdf.open(pdf_path)
        chunks: List[Dict[str, Any]] = []

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_no = page_idx + 1
            text = page.get_text("text") or ""
            # Clean up whitespace
            cleaned_text = " ".join(text.split())
            if not cleaned_text:
                continue

            # Sliding window chunking
            start = 0
            while start < len(cleaned_text):
                end = min(start + chunk_size, len(cleaned_text))
                chunk_str = cleaned_text[start:end].strip()

                if len(chunk_str) >= 40:  # Skip trivial fragments
                    chunks.append({
                        "doc_id": doc_id,
                        "document_title": title,
                        "filename": filename,
                        "category_tag": category_tag,
                        "page_number": page_no,
                        "text": chunk_str
                    })

                if end == len(cleaned_text):
                    break
                start += (chunk_size - chunk_overlap)

        doc.close()
        return chunks

    def add_document_chunks(self, chunks: List[Dict[str, Any]]):
        """Generates embeddings for chunks and adds them to FAISS index."""
        if not chunks:
            return

        model = get_embedding_model()
        texts = [c["text"] for c in chunks]

        # Generate normalized embeddings for cosine similarity via inner product
        embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        embeddings = embeddings.astype(np.float32)

        if self.index is None:
            self._initialize_empty()

        self.index.add(embeddings)
        self.metadata.extend(chunks)
        self._persist()
        logger.info(f"Added {len(chunks)} chunks to FAISS index. Total: {self.index.ntotal}")

    def rebuild_index_from_documents(self, documents: List[Dict[str, Any]]):
        """
        Rebuilds index completely from an active list of documents.
        Used after document deletion or modifications to ensure exact sync.
        """
        self._initialize_empty()
        all_chunks: List[Dict[str, Any]] = []

        for doc in documents:
            if os.path.exists(doc["file_path"]):
                chunks = self.extract_and_chunk_pdf(
                    pdf_path=doc["file_path"],
                    doc_id=doc["id"],
                    title=doc["title"],
                    filename=doc["filename"],
                    category_tag=doc.get("category_tag")
                )
                all_chunks.extend(chunks)

        if all_chunks:
            self.add_document_chunks(all_chunks)
        else:
            self._persist()

    def query_guidelines(
        self,
        query: str,
        top_k: int = 3,
        similarity_threshold: float = 0.30
    ) -> List[Dict[str, Any]]:
        """
        Searches FAISS for top_k relevant guideline chunks.
        Returns empty list if below threshold or if no documents exist.
        """
        if self.index is None or self.index.ntotal == 0 or not self.metadata:
            return []

        model = get_embedding_model()
        query_vec = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        query_vec = query_vec.astype(np.float32)

        k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_vec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            score = float(dist)
            # Check relevance threshold
            if score >= similarity_threshold:
                meta = self.metadata[idx]
                results.append({
                    "document_title": meta.get("document_title", "Government Guideline"),
                    "filename": meta.get("filename", "guideline.pdf"),
                    "page_number": meta.get("page_number", 1),
                    "score": round(score, 3),
                    "excerpt": meta.get("text", "")
                })

        return results


# Global singleton
rag_engine = RAGEngine()
