import os
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from app.config import LEGAL_SOURCES_DIR, DATA_DIR, EMBEDDING_MODEL_NAME

class DocumentChunk:
    def __init__(self, text: str, source: str, chunk_id: int):
        self.text = text
        self.source = source
        self.chunk_id = chunk_id

class LegalRAG:
    def __init__(self):
        self.db_path = DATA_DIR / "vector_db.pkl"
        self._model = None
        self.chunks: List[DocumentChunk] = []
        self.embeddings: np.ndarray = None
        self.load_db()

    @property
    def model(self):
        if self._model is None:
            # Lazy load the embedding model to keep server start fast
            print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
            self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return self._model

    def load_db(self):
        """Load vector database from disk if it exists."""
        if self.db_path.exists():
            try:
                with open(self.db_path, "rb") as f:
                    data = pickle.load(f)
                    self.chunks = data.get("chunks", [])
                    self.embeddings = data.get("embeddings", None)
                print(f"Loaded vector DB with {len(self.chunks)} chunks.")
            except Exception as e:
                print(f"Error loading vector DB: {e}. Re-initialization required.")
                self.chunks = []
                self.embeddings = None
        else:
            print("No vector DB found. Ingestion required.")

    def save_db(self):
        """Save vector database to disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "wb") as f:
            pickle.dump({
                "chunks": self.chunks,
                "embeddings": self.embeddings
            }, f)
        print("Vector DB saved to disk.")

    def ingest_documents(self) -> Tuple[List[str], int]:
        """
        Scan LEGAL_SOURCES_DIR for PDF and TXT files, chunk them, 
        embed them, and save to the local vector DB.
        """
        if not LEGAL_SOURCES_DIR.exists():
            LEGAL_SOURCES_DIR.mkdir(parents=True, exist_ok=True)
            return [], 0

        new_chunks = []
        processed_files = []

        for file_path in LEGAL_SOURCES_DIR.iterdir():
            if file_path.suffix.lower() in ['.pdf', '.txt']:
                print(f"Processing {file_path.name}...")
                processed_files.append(file_path.name)
                
                text = ""
                if file_path.suffix.lower() == '.pdf':
                    try:
                        reader = PdfReader(file_path)
                        for page in reader.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                    except Exception as e:
                        print(f"Error reading PDF {file_path.name}: {e}")
                        continue
                else:  # .txt
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            text = f.read()
                    except Exception as e:
                        print(f"Error reading TXT {file_path.name}: {e}")
                        continue

                # Chunking strategy: split by double newlines or sections, fallback to paragraph groupings
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                
                # Combine paragraphs to target ~600-800 characters per chunk while keeping Q&A blocks intact
                current_chunk = []
                current_length = 0
                
                for para in paragraphs:
                    if para.startswith("Query:") and current_chunk:
                        # Flush existing chunk when encountering a new Query if length is sufficient
                        if current_length >= 400:
                            chunk_text = "\n\n".join(current_chunk)
                            new_chunks.append(DocumentChunk(
                                text=chunk_text,
                                source=file_path.name,
                                chunk_id=len(new_chunks)
                            ))
                            current_chunk = []
                            current_length = 0

                    current_chunk.append(para)
                    current_length += len(para)
                    
                    if current_length >= 800:
                        chunk_text = "\n\n".join(current_chunk)
                        new_chunks.append(DocumentChunk(
                            text=chunk_text,
                            source=file_path.name,
                            chunk_id=len(new_chunks)
                        ))
                        current_chunk = []
                        current_length = 0
                
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    new_chunks.append(DocumentChunk(
                        text=chunk_text,
                        source=file_path.name,
                        chunk_id=len(new_chunks)
                    ))

        if not new_chunks:
            return processed_files, 0

        self.chunks = new_chunks
        texts = [c.text for c in self.chunks]
        
        print(f"Generating embeddings for {len(texts)} chunks...")
        self.embeddings = self.model.encode(texts, show_progress_bar=True)
        self.save_db()
        
        return processed_files, len(self.chunks)

    def search(self, query: str, top_k: int = 3, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Embed the query and return the top_k most similar legal chunks
        using cosine similarity, optionally filtered by domain category.
        """
        if not self.chunks or self.embeddings is None:
            return []

        # Filter indices by category if specified
        valid_indices = []
        for idx, chunk in enumerate(self.chunks):
            src_lower = chunk.source.lower()
            if category == "POSH":
                # Exclude POCSO-only source documents
                if "pocso" in src_lower and "posh" not in src_lower:
                    continue
                valid_indices.append(idx)
            elif category == "POCSO":
                # Exclude POSH-only source documents
                if "posh" in src_lower and "pocso" not in src_lower:
                    continue
                valid_indices.append(idx)
            else:
                valid_indices.append(idx)

        if not valid_indices:
            return []

        # Embed query
        query_vector = self.model.encode([query])[0]

        # Calculate cosine similarity: (A . B) / (||A|| * ||B||)
        norm_query = np.linalg.norm(query_vector)
        
        # Filter embeddings and chunks based on category filter
        filtered_embeddings = self.embeddings[valid_indices]
        norm_embeddings = np.linalg.norm(filtered_embeddings, axis=1)
        
        # Guard against zero norm
        if norm_query == 0:
            return []
        
        dot_product = np.dot(filtered_embeddings, query_vector)
        similarities = dot_product / (norm_embeddings * norm_query)

        # Sort similarities in descending order
        top_k_actual = min(top_k, len(valid_indices))
        top_filtered_indices = np.argsort(similarities)[::-1][:top_k_actual]

        results = []
        for f_idx in top_filtered_indices:
            score = float(similarities[f_idx])
            actual_idx = valid_indices[f_idx]
            chunk = self.chunks[actual_idx]
            results.append({
                "source": chunk.source,
                "text_snippet": chunk.text,
                "relevance_score": score
            })
        return results
