# zendaya_backend/services/memory_service.py
import os
import threading
import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

# Optional imports
try:
    from sentence_transformers import SentenceTransformer
    EMB_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    EMB_DIM = EMB_MODEL.get_sentence_embedding_dimension()
except Exception:
    EMB_MODEL = None
    EMB_DIM = 384  # fallback dimension for random vectors

try:
    import faiss
except Exception:
    faiss = None

# Storage paths
DATA_DIR = os.environ.get("ZENDAYA_DATA_DIR", "zendaya_backend/data")
os.makedirs(DATA_DIR, exist_ok=True)
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "memory_index.faiss")
META_PATH = os.path.join(DATA_DIR, "memory_meta.json")
ORDERED_IDS_PATH = os.path.join(DATA_DIR, "memory_ordered_ids.json")

class MemoryService:
    def __init__(self):
        self.lock = threading.RLock()
        self.index = None
        self.meta: Dict[str, Dict[str, Any]] = {}
        self.ordered_ids: List[str] = []
        self._init_index_and_meta()

    def _init_index_and_meta(self):
        # Load meta and ordered ids first
        if os.path.exists(META_PATH):
            try:
                with open(META_PATH, "r", encoding="utf-8") as f:
                    self.meta = json.load(f)
            except Exception as e:
                logger.warning("Failed to load memory_meta.json: %s", e)
                self.meta = {}

        if os.path.exists(ORDERED_IDS_PATH):
            try:
                with open(ORDERED_IDS_PATH, "r", encoding="utf-8") as f:
                    self.ordered_ids = json.load(f)
            except Exception as e:
                logger.warning("Failed to load memory_ordered_ids.json: %s", e)
                self.ordered_ids = list(self.meta.keys())

        # Initialize or load FAISS
        if faiss is None:
            logger.warning("FAISS not available; vector retrieval disabled.")
            self.index = None
            return

        if os.path.exists(FAISS_INDEX_PATH):
            try:
                self.index = faiss.read_index(FAISS_INDEX_PATH)
                logger.info("MemoryService: loaded FAISS index.")
                return
            except Exception as e:
                logger.warning("Failed to read FAISS index: %s — creating new index", e)

        # create new index (cosine via inner product on normalized vectors)
        self.index = faiss.IndexFlatIP(EMB_DIM)
        logger.info("MemoryService: created new FAISS index (dim=%d)", EMB_DIM)

        # If we have meta and ordered_ids but empty index, rebuild
        if self.ordered_ids and self.meta:
            try:
                texts = [self.meta[mid]["raw"] for mid in self.ordered_ids if mid in self.meta]
                if texts:
                    vecs = self._embed(texts).astype("float32")
                    with self.lock:
                        self.index.add(vecs)
                        self._persist_index()
            except Exception as e:
                logger.exception("Failed to rebuild FAISS from meta: %s", e)

    def _persist_index(self):
        # Save index and metadata atomically
        if faiss is None or self.index is None:
            # just persist meta
            with open(META_PATH, "w", encoding="utf-8") as f:
                json.dump(self.meta, f, ensure_ascii=False, indent=2)
            with open(ORDERED_IDS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.ordered_ids, f, ensure_ascii=False, indent=2)
            return

        with self.lock:
            try:
                faiss.write_index(self.index, FAISS_INDEX_PATH)
            except Exception as e:
                logger.exception("Failed to write faiss index: %s", e)
            # save meta & ordered ids
            with open(META_PATH, "w", encoding="utf-8") as f:
                json.dump(self.meta, f, ensure_ascii=False, indent=2)
            with open(ORDERED_IDS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.ordered_ids, f, ensure_ascii=False, indent=2)

    def _embed(self, texts: List[str]):
        if EMB_MODEL:
            vecs = EMB_MODEL.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            # normalize
            norm = np.linalg.norm(vecs, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            return vecs / norm
        logger.warning("Embedding model unavailable; using random vectors.")
        return np.random.randn(len(texts), EMB_DIM).astype("float32")

    def ingest_memory(self, content: str, user_id: Optional[str] = None, source: str = "conversation",
                      mtype: str = "utterance", summary: Optional[str] = None, privacy_level: str = "default",
                      metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Store a memory (persist meta + add vector to faiss).
        Returns stored metadata.
        """
        if metadata is None:
            metadata = {}
        memory_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        summary_text = (summary or (content[:300] + ("..." if len(content) > 300 else "")))

        entry = {
            "id": memory_id,
            "user_id": user_id,
            "source": source,
            "type": mtype,
            "raw": content,
            "summary": summary_text,
            "privacy_level": privacy_level,
            "metadata": metadata,
            "created_at": now,
            "updated_at": now
        }

        # store meta
        with self.lock:
            self.meta[memory_id] = entry
            self.ordered_ids.append(memory_id)

        # add to vector index (async-safe: we do CPU-bound work inline; caller can wrap in to_thread)
        try:
            vecs = self._embed([content]).astype("float32")
            if self.index is not None:
                with self.lock:
                    self.index.add(vecs)
        except Exception as e:
            logger.exception("MemoryService: embedding/index error: %s", e)

        # persist
        self._persist_index()
        return entry

    def retrieve(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """
        Return top-k memories relevant to query (ordered most relevant first).
        If index is None, returns empty list.
        """
        if self.index is None:
            return []

        qv = self._embed([query]).astype("float32")
        with self.lock:
            try:
                D, I = self.index.search(qv, top_k)
            except Exception as e:
                logger.exception("Faiss search failed: %s", e)
                return []

        results = []
        with self.lock:
            ids_snapshot = list(self.ordered_ids)
            for pos in I[0]:
                if pos < 0 or pos >= len(ids_snapshot):
                    continue
                mid = ids_snapshot[pos]
                if mid in self.meta:
                    results.append(self.meta[mid])
        return results

    def compact_summaries(self, max_chars: int = 2000) -> str:
        """
        Build a compact persona summary (heuristic).
        Uses last N memories, dedupes, and truncates.
        """
        with self.lock:
            items = [self.meta[mid] for mid in self.ordered_ids[-500:] if mid in self.meta]
        seen = set()
        lines = []
        for it in reversed(items):  # recent-first
            s = it.get("summary") or it.get("raw")
            if not s:
                continue
            key = s[:120]
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- {s}")
            if sum(len(l) for l in lines) > max_chars:
                break
        return "\n".join(lines)[:max_chars]

    def clear_user_memories(self, user_id: str):
        with self.lock:
            keys = [k for k,v in self.meta.items() if v.get("user_id")==user_id]
            for k in keys:
                del self.meta[k]
            self.ordered_ids = [i for i in self.ordered_ids if i not in keys]
            # rebuild index
            if self.index is not None:
                texts = [self.meta[i]["raw"] for i in self.ordered_ids]
                self.index.reset()
                if texts:
                    vecs = self._embed(texts).astype("float32")
                    self.index.add(vecs)
            self._persist_index()

# Singleton instance for app wiring
memory_service = MemoryService()
