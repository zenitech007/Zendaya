"""
zendaya_vector_memory.py
========================
Persistent semantic memory backed by Chroma. Every conversation turn is
embedded and stored; at retrieval time we pull the top-K turns most relevant
to the current query, plus the most recent N turns (recency).

Falls back to a no-op if chromadb isn't installed — caller code stays the same.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any

try:
    import chromadb
    from chromadb.config import Settings
    _CHROMA_READY = True
except Exception as _e:
    _CHROMA_READY = False
    _CHROMA_ERR = str(_e)


_CLIENT = None
_COLLECTION = None
_DB_PATH = str(Path(__file__).resolve().parent.parent / "zendaya_logs" / "chroma")


def _ensure_collection():
    global _CLIENT, _COLLECTION
    if not _CHROMA_READY:
        return None
    if _COLLECTION is not None:
        return _COLLECTION
    try:
        os.makedirs(_DB_PATH, exist_ok=True)
        _CLIENT = chromadb.PersistentClient(
            path=_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        _COLLECTION = _CLIENT.get_or_create_collection(
            name="zendaya_history",
            metadata={"hnsw:space": "cosine"},
        )
        return _COLLECTION
    except Exception as e:
        print(f"(vector memory init failed: {e})")
        return None


def add_turn(role: str, text: str) -> None:
    """Persist a single turn. Safe to call from anywhere; never throws."""
    if not text or not text.strip():
        return
    col = _ensure_collection()
    if col is None:
        return
    try:
        ts = time.time()
        doc_id = f"{int(ts*1000)}-{role}"
        col.add(
            ids=[doc_id],
            documents=[text.strip()],
            metadatas=[{"role": role, "ts": ts}],
        )
    except Exception as e:
        print(f"(vector add failed: {e})")


def retrieve_relevant(query: str, k: int = 5, min_age_seconds: float = 60.0) -> List[Dict[str, Any]]:
    """
    Return up to k past turns or document chunks most semantically relevant to `query`.
    Excludes chat turns that are very recent to avoid duplicating prompt lines.
    """
    if not query or not query.strip():
        return []
    col = _ensure_collection()
    if col is None:
        return []
    try:
        n = col.count()
        if n == 0:
            return []
        res = col.query(
            query_texts=[query.strip()],
            n_results=min(k * 3, max(1, n)),
            include=["documents", "metadatas", "distances"],
        )
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        now = time.time()
        out: List[Dict[str, Any]] = []
        for doc, meta, dist in zip(docs, metas, dists):
            role = (meta or {}).get("role", "user")
            ts = float((meta or {}).get("ts", 0))
            
            # Skip recent chat turns, but keep document chunks regardless of age
            if role != "system_document" and (now - ts < min_age_seconds):
                continue
                
            out.append({
                "role": role,
                "text": doc,
                "ts": ts,
                "source": (meta or {}).get("source", ""),
                "score": 1.0 - float(dist),
            })
            if len(out) >= k:
                break
        return out
    except Exception as e:
        print(f"(vector query failed: {e})")
        return []


def format_for_prompt(turns: List[Dict[str, Any]]) -> str:
    if not turns:
        return ""
    lines = []
    for t in turns:
        if t['role'] == "system_document":
            src = t.get('source', 'local document')
            lines.append(f"[Local Context from {src}]: {t['text']}")
        else:
            lines.append(f"{t['role']}: {t['text']}")
    return "Possibly relevant past context / local knowledge:\n" + "\n".join(lines)


def add_document(doc_id: str, content: str, source: str) -> None:
    """Index a large document by chunking it and adding it to Chroma for local RAG."""
    col = _ensure_collection()
    if col is None or not content.strip():
        return
    
    # Simple chunking strategy (1000 chars)
    chunk_size = 1000
    overlap = 100
    chunks = []
    for i in range(0, len(content), chunk_size - overlap):
        chunks.append(content[i:i + chunk_size])
        
    try:
        ids = [f"{doc_id}-chunk-{i}" for i in range(len(chunks))]
        documents = chunks
        metadatas = [{"role": "system_document", "source": source, "ts": time.time()} for _ in chunks]
        col.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"[vector memory] indexed document '{source}' into {len(chunks)} chunks.")
    except Exception as e:
        print(f"(vector index failed: {e})")


def index_directory(directory_path: str, ext_filter: tuple = (".txt", ".md", ".py")) -> None:
    """Recursively read and index all text files in a directory."""
    path = Path(directory_path)
    if not path.is_dir():
        print(f"(vector memory) invalid directory: {directory_path}")
        return
        
    for p in path.rglob("*"):
        if p.is_file() and p.suffix.lower() in ext_filter:
            try:
                content = p.read_text(encoding="utf-8")
                doc_id = str(p.relative_to(path)).replace("\\", "_")
                add_document(doc_id, content, source=str(p.name))
            except Exception:
                pass


def stats() -> str:
    col = _ensure_collection()
    if col is None:
        if not _CHROMA_READY:
            return f"vector memory: DISABLED (chromadb missing: {_CHROMA_ERR})"
        return "vector memory: DISABLED (init failed)"
    try:
        return f"vector memory: {col.count()} embeddings stored at {_DB_PATH}"
    except Exception as e:
        return f"vector memory: ERROR ({e})"


def diagnostics() -> str:
    return stats()


if __name__ == "__main__":
    print(diagnostics())
