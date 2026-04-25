# zendaya_backend/services/rag_chat.py
"""
RAGChatService: A Retrieval-Augmented Generation chat service
that extends the base ChatService.

Features:
 - Inherits from ChatService.
 - Uses sentence-transformers for embeddings (configurable model).
 - Uses FAISS for fast vector similarity (falls back to numpy brute-force).
 - Persists all vectors and metadata to a robust SQLite database.
 - Uses FAISS as a high-speed cache, rebuilt from SQLite.
 - Overrides `process_message` to augment chat logic with retrieved context.
 - "Summarization-ready" hook (`_summarize_context`).
 - "Emotion-aware" metadata support.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np
import json
import logging
import asyncio
import sqlite3
from datetime import datetime, timedelta

# --- Optional Imports ---
try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    faiss = None
    FAISS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SBER_AVAILABLE = True
except Exception:
    SentenceTransformer = None
    SBER_AVAILABLE = False

# --- Base Service (Mock for Standalone) ---
try:
    # Attempt to import the "real" service
    from zendaya_backend.services.chat import ChatService
except ImportError:
    logging.info("Mocking ChatService as zendaya_backend.services.chat not found.")
    class ChatService:
        """Mock/Fallback ChatService if base chat is unavailable."""
        def __init__(self):
            self.history: Dict[str, List[Dict[str, Any]]] = {}
            self.active_sessions: Dict[str, Any] = {}

        async def get_history(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
            return self.history.get(user_id, [])[-limit:]

        async def send_message(self, user_id: str, content: str, sender: str = "user", metadata: Optional[Dict] = None):
            if user_id not in self.history:
                self.history[user_id] = []
            msg = {"sender": sender, "content": content, "timestamp": now_iso(), **(metadata or {})}
            self.history[user_id].append(msg)
            self.active_sessions[user_id] = True
            logging.info(f"Mock send_message user={user_id} sender={sender} msg={content}")

        async def process_message(self, message: str, user: Any = None, context: Optional[Dict] = None) -> Dict:
            logging.info(f"Mock process_message msg={message} context={context}")
            return {"text": f"Mock response to: {message}", "context": context, "timestamp": now_iso()}

# --- Setup & Config ---
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
RAG_DATA_DIR = BASE_DIR / "data" / "rag"
RAG_DATA_DIR.mkdir(parents=True, exist_ok=True)

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"  # small, fast, good quality
EMBED_DIM = 384  # Auto-detected, but good to have a default

DB_FILE = RAG_DATA_DIR / "vector_store.sqlite3"
FAISS_INDEX_FILE = RAG_DATA_DIR / "faiss.index" # This is now a CACHE

# -----------------------
# Utilities
# -----------------------
def now_iso() -> str:
    return datetime.utcnow().isoformat()

# -----------------------
# Persistent Vector Store
# -----------------------
class SQLiteVectorStore:
    """
    Handles persistent storage of vectors and metadata in SQLite.
    NOTE: All methods are SYNCHRONOUS and must be called with
    `asyncio.to_thread` to avoid blocking the server event loop.
    This class is now thread-safe as it creates a new connection
    for each operation.
    """
    def __init__(self, db_path: Path, dim: int):
        self.db_path = db_path
        self._dim = dim
        logger.info(f"[SQLiteStore] Initialized. DB path: {self.db_path}")

    def connect_and_create(self):
        """Connects and ensures tables exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    topic TEXT,
                    emotion TEXT,
                    text TEXT NOT NULL,
                    vector BLOB NOT NULL
                );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON vectors (timestamp);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON vectors (user_id);")
                conn.commit()
        except Exception as e:
            logger.error(f"[SQLiteStore] Failed to connect or create tables: {e}")
            raise


    def add_batch(self, metas: List[Dict[str, Any]], vectors: np.ndarray):
        """Adds a batch of new embeddings to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for meta, vec in zip(metas, vectors):
                    vec_blob = vec.astype(np.float32).tobytes()
                    cursor.execute("""
                    INSERT INTO vectors (user_id, sender, timestamp, topic, emotion, text, vector)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        meta.get("user_id"),
                        meta.get("sender"),
                        meta.get("timestamp"),
                        meta.get("topic"),
                        meta.get("emotion"),
                        meta.get("text"),
                        vec_blob
                    ))
                conn.commit()

        except Exception as e:
            logger.error(f"[SQLiteStore] Failed to add batch: {e}")

    def load_all(self) -> Tuple[np.ndarray | None, List[Dict[str, Any]]]:
        """Loads all vectors and metadata from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT id, user_id, sender, timestamp, topic, emotion, text, vector FROM vectors")
                rows = cursor.fetchall()

            if not rows:
                return None, []

            metas = []
            vectors = []
            for row in rows:
                db_id, user_id, sender, timestamp, topic, emotion, text, vec_blob = row
                meta = {
                    "db_id": db_id,
                    "user_id": user_id,
                    "sender": sender,
                    "timestamp": timestamp,
                    "topic": topic,
                    "emotion": emotion,
                    "text": text
                }
                metas.append(meta)
                vectors.append(np.frombuffer(vec_blob, dtype=np.float32).reshape(1, self._dim))

            return np.vstack(vectors), metas
        except Exception as e:
            logger.error(f"[SQLiteStore] Failed to load all vectors: {e}")
            return None, []

    def prune(self, cutoff_iso: str) -> int:
        """Deletes entries older than the cutoff timestamp."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM vectors WHERE timestamp < ?", (cutoff_iso,))
                rowcount = cursor.rowcount
                conn.commit()
                return rowcount

        except Exception as e:
            logger.error(f"[SQLiteStore] Failed to prune: {e}")
            return 0

    def count(self) -> int:
        """Returns the total number of vectors in the store."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(id) FROM vectors")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"[SQLiteStore] Failed to count: {e}")
            return 0


# -----------------------
# RAG-enabled Chat Service
# -----------------------
class RAGChatService(ChatService):
    """
    Retrieval-Augmented Generation Chat Service
    Extends ChatService to enhance responses with external knowledge retrieval.
    All blocking I/O is wrapped in asyncio.to_thread.

    """
    def __init__(self, model_name: str = EMBED_MODEL_NAME):
        super().__init__() # Initialize the base ChatService
        self.model_name = model_name
        self._embed_model: SentenceTransformer | None = None
        self._dim: int = EMBED_DIM
        self._lock = asyncio.Lock()
        self.store: SQLiteVectorStore | None = None
        self.is_ready: bool = False


        # In-memory search representations (built from SQLite)
        self._embeddings: np.ndarray | None = None  # numpy array shape (N, D)
        self._meta: List[Dict[str, Any]] = []  # parallel metadata for each vector
        self._index: faiss.Index | None = None # FAISS index (cache)

        logger.info("RAGChatService initialized (not yet ready). Call initialize() to load models.")


    # -----------------------
    # Initialization helpers
    # -----------------------
    async def initialize(self):
        """
        Asynchronously loads models, connects to DB, and builds
        the index without blocking the server.
        """
        global SBER_AVAILABLE
        if self.is_ready:
            logger.info("[RAG] Already initialized.")
            return

        logger.info("[RAG] Starting asynchronous initialization...")

        # 1. Load SentenceTransformer model (in a thread)
        if SBER_AVAILABLE and self._embed_model is None:
            try:
                def _load_model():
                    model = SentenceTransformer(self.model_name)
                    dim = model.get_sentence_embedding_dimension()
                    return model, dim

                logger.info(f"[RAG] Loading embedding model '{self.model_name}' in background thread...")
                self._embed_model, model_dim = await asyncio.to_thread(_load_model)

                if model_dim is not None:
                    self._dim = model_dim
                logger.info(f"[RAG] Embedding model loaded: {self.model_name} (dim={self._dim})")
            except Exception as e:
                logger.warning(f"[RAG] Failed to load SentenceTransformer: {e}")
                self._embed_model = None
                SBER_AVAILABLE = False # Mark as unavailable

        # 2. Initialize SQLite Store (in a thread)
        self.store = SQLiteVectorStore(DB_FILE, self._dim)
        await asyncio.to_thread(self.store.connect_and_create)
        logger.info("[RAG] SQLite store connected and tables ensured.")

        # 3. Load vectors/meta from SQLite (in a thread)
        self._embeddings, self._meta = await asyncio.to_thread(self.store.load_all)
        if self._embeddings is not None:
            logger.info(f"[RAG] Loaded {len(self._meta)} vectors from SQLite.")
            # 4. Build FAISS index (as a cache)
            await self._build_faiss_index() # This is now async
        else:
            logger.info("[RAG] No vectors found in SQLite. Index is empty.")

        self.is_ready = True
        logger.info(f"[RAG] Service is now ready. Loaded {len(self._meta)} total vectors.")


    async def _build_faiss_index(self):

        """Builds or rebuilds the FAISS index from in-memory embeddings."""
        if not FAISS_AVAILABLE:
            logger.warning("[RAG] FAISS not available. Falling back to NumPy search.")
            return

        if self._embeddings is None:
            logger.info("[RAG] Cannot build FAISS index: No embeddings loaded.")
            return

        # Try to load from cache first (in a thread)
        def _load_cache():
            if FAISS_INDEX_FILE.exists():
                try:
                    return faiss.read_index(str(FAISS_INDEX_FILE))
                except Exception as e:
                    logger.warning(f"[RAG] Failed to load FAISS cache: {e}. Rebuilding.")
            return None

        cached_index = await asyncio.to_thread(_load_cache)
        if cached_index and cached_index.ntotal == len(self._meta):
            self._index = cached_index
            logger.info(f"[RAG] Loaded FAISS index from cache ({self._index.ntotal} vectors).")
            return

        # Build new index (in a thread)
        logger.info(f"[RAG] Building new FAISS index for {len(self._meta)} vectors...")
        try:
            def _build_and_save(embeddings, dim):
                idx = faiss.IndexFlatIP(dim)
                emb_norm = self._normalize(embeddings).astype(np.float32)
                idx.add(emb_norm)
                faiss.write_index(idx, str(FAISS_INDEX_FILE)) # Save cache
                return idx

            self._index = await asyncio.to_thread(_build_and_save, self._embeddings, self._dim)

            logger.info("[RAG] Built and cached new FAISS index.")
        except Exception as e:
            logger.error(f"[RAG] Failed to build FAISS index: {e}")
            self._index = None

    def _normalize(self, emb: np.ndarray) -> np.ndarray:
        """L2 normalize rows to unit vectors for dot-product similarity."""
        if emb.ndim == 1:
             emb = emb.reshape(1, -1)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return emb / norms

    # -----------------------
    # Embedding helpers
    # -----------------------
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embeds a list of texts (SYNCHRONOUS).
        This is a CPU-bound task, so it should be called with `to_thread`.
        """

        if self._embed_model:
            try:
                emb = np.array(self._embed_model.encode(texts, convert_to_numpy=True, show_progress_bar=False))
                return emb
            except Exception as e:
                logger.error(f"[RAG] SentenceTransformer failed to encode: {e}")

        # Fallback: very weak text->vector
        logger.warning("[RAG] Using fallback embeddings (low quality). Install `sentence-transformers`.")

        emb_list = []
        for t in texts:
            h = np.array([hash(c) for c in t], dtype=np.float32)
            if len(h) == 0:
                h = np.zeros(self._dim, dtype=np.float32)
            if len(h) < self._dim:
                h = np.pad(h, (0, self._dim - len(h)), 'constant')
            else:
                h = h[:self._dim]
            if np.any(h):
                h = h / np.linalg.norm(h)
            emb_list.append(h)

        arr = np.array(emb_list, dtype=np.float32)
        return arr.reshape(len(texts), self._dim)



    async def _add_embeddings(self, texts: List[str], metas: List[Dict[str, Any]]):
        """Embeds texts, writes to SQLite, and updates in-memory/FAISS index."""
        if not texts or self.store is None:
            return

        try:
            # 1. Embed texts (in a thread)

            emb = await asyncio.to_thread(self.embed_texts, texts)
            if emb.shape[1] != self._dim:
                logger.error(f"[RAG] Dimension mismatch! Model dim {emb.shape[1]} != Store dim {self._dim}.")
                return

            async with self._lock:
                # 2. Write to persistent store (in a thread)
                await asyncio.to_thread(self.store.add_batch, metas, emb)

                # 3. Update in-memory copy (fast, no thread needed)

                if self._embeddings is None:
                    self._embeddings = emb
                    self._meta = metas
                else:
                    self._embeddings = np.vstack([self._embeddings, emb])
                    self._meta.extend(metas)

                # 4. Update FAISS cache (in a thread)
                if FAISS_AVAILABLE and self._index is not None:
                    def _add_to_faiss_and_save(embeddings):
                        emb_norm = self._normalize(embeddings).astype(np.float32)
                        self._index.add(emb_norm)
                        faiss.write_index(self._index, str(FAISS_INDEX_FILE))

                    await asyncio.to_thread(_add_to_faiss_and_save, emb)


        except Exception as e:
            logger.error(f"[RAG] Failed during _add_embeddings: {e}")

    # -----------------------
    # Public API: Indexing
    # -----------------------
    async def index_messages_from_history(self, user_id: str, limit: int = 100):
        """Take recent history for user and add to embedding index (non-blocking)."""
        history = await self.get_history(user_id=user_id, limit=limit)
        texts = []
        metas = []
        for h in history:
            texts.append(f"{h['sender']}: {h['content']}")
            metas.append({
                "user_id": user_id,
                "sender": h["sender"],
                "timestamp": h["timestamp"],
                "topic": h.get("topic"),
                "emotion": h.get("emotion"),
                "text": h["content"]
            })
        if texts:
            await self._add_embeddings(texts, metas)

    # -----------------------
    # Retrieval
    # -----------------------
    def _search_numpy(self, query_emb: np.ndarray, top_k: int) -> List[Tuple[int, float]]:
        """
        Brute-force search on numpy (SYNCHRONOUS).
        CPU-bound, call with `to_thread`.
        """

        if self._embeddings is None or len(self._embeddings) == 0:
            return []
        emb_norm = self._normalize(self._embeddings)
        q = self._normalize(query_emb)
        scores = emb_norm.dot(q.T).flatten()

        k_actual = min(top_k, len(scores))
        if k_actual == 0: return []

        best_idx = np.argsort(-scores)[:k_actual]
        return [(int(i), float(scores[i])) for i in best_idx]

    def _search_faiss(self, query_emb: np.ndarray, top_k: int) -> List[Tuple[int, float]]:
        """
        Search FAISS index (SYNCHRONOUS).
        CPU-bound, call with `to_thread`.
        """

        if self._index is None:
            return []

        k_actual = min(top_k, self._index.ntotal)
        if k_actual == 0: return []

        q_norm = self._normalize(query_emb).astype(np.float32)
        D, I = self._index.search(q_norm, k_actual)

        results = []
        for i, score in zip(I[0], D[0]):
            if i < 0: continue
            results.append((int(i), float(score)))
        return results

    async def retrieve_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return top-k metadata entries for a query text."""
        if not self.is_ready or self._embeddings is None or len(self._embeddings) == 0:
            return []

        # 1. Embed query (in a thread)
        q_emb = await asyncio.to_thread(self.embed_texts, [query])

        # 2. Search (in a thread)
        if FAISS_AVAILABLE and self._index is not None:
            hits = await asyncio.to_thread(self._search_faiss, q_emb, top_k)
        else:
            hits = await asyncio.to_thread(self._search_numpy, q_emb, top_k)

        # 3. Process results (fast, no thread needed)

        results = []
        for idx, score in hits:
            try:
                if idx < len(self._meta):
                    meta_copy = self._meta[idx].copy()
                    meta_copy["_score"] = score
                    results.append(meta_copy)
                else:
                    logger.warning(f"[RAG] Retrieved index {idx} out of bounds for meta (len={len(self._meta)})")
            except Exception as e:
                logger.warning(f"[RAG] Error processing retrieved hit: {e}")
        return results

    # -----------------------
    # Summarization Hook
    # -----------------------
    async def _summarize_context(self, docs: List[Dict[str, Any]]) -> str:
        """
        Hook for summarizing retrieved documents.
        TODO: Replace with an actual LLM call for true summarization.
        """
        # Placeholder: simple concatenation
        summary_sentences = []
        for r in docs:
            txt = r.get("text") or ""
            sender = r.get("sender", "unknown")
            summary_sentences.append(f"{sender}: {txt[:150]}")

        return " | ".join(summary_sentences)

    # -----------------------
    # Core Message Processing
    # -----------------------
    async def process_message(
        self, message: str, user: Any | None = None, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Overrides base process_message to inject RAG context.
        """
        if not self.is_ready:
            logger.warning("[RAG] process_message called but service is not ready.")
            return {
                "text": "The AI service is still initializing. Please wait a moment and try again.",
                "timestamp": now_iso(),
                "context": context,
                "clarification_needed": True
            }


        context = context or {}
        user_id = getattr(user, "username", "guest")
        if user is None:
             user = type('MockUser', (object,), {'username': user_id})()

        # 1. Store user message (using base class method)
        await self.send_message(user_id, message, sender="user", metadata=context)

        # 2. Index user message (with topic/emotion)
        topic = context.get("topic")
        emotion = context.get("emotion") # Hook for voice system
        meta = {
            "user_id": user_id,
            "sender": "user",
            "timestamp": now_iso(),
            "topic": topic,
            "emotion": emotion,
            "text": message
        }
        # Run this in the background, don't wait for it
        asyncio.create_task(self._add_embeddings([f"user: {message}"], [meta]))


        # 3. Retrieve relevant context
        retrieved = await self.retrieve_context(message, top_k=6)

        # 4. Summarize context (using new hook)
        retrieved_summary = await self._summarize_context(retrieved)

        # 5. Augment context for the base class
        augmented_context = dict(context)
        augmented_context["_retrieved_summary"] = retrieved_summary
        augmented_context["_retrieved_items"] = retrieved

        # 6. Call the base class's process_message (the "generation" step)
        response = await super().process_message(message, user=user, context=augmented_context)

        # 7. Index assistant reply (run in background)
        assistant_text = response.get("text", "")
        if assistant_text:
            await self.send_message(user_id, assistant_text, sender="assistant", metadata={"source":"assistant_rag"})
            asyncio.create_task(self._add_embeddings([f"assistant: {assistant_text}"], [{

                "user_id": user_id,
                "sender": "assistant",
                "timestamp": now_iso(),
                "topic": topic, # Carry over topic
                "text": assistant_text
            }]))


        return response

    # -----------------------
    # Maintenance APIs
    # -----------------------
    async def reindex_all(self, user_limit: Optional[int] = None):
        """Rebuilds the entire store and index from chat history."""
        if self.store is None:
            logger.error("[RAG] Store not initialized, cannot reindex.")
            return

        async with self._lock:
            self.is_ready = False # Mark as not ready during reindex
            logger.info("[RAG] Starting reindex_all... Clearing all vector data...")

            # 1. Clear persistent store (in a thread)
            def _clear_disk():
                DB_FILE.unlink(missing_ok=True)
                FAISS_INDEX_FILE.unlink(missing_ok=True)

            await asyncio.to_thread(_clear_disk)

            # 2. Re-initialize store and in-memory caches
            self.store = SQLiteVectorStore(DB_FILE, self._dim)
            await asyncio.to_thread(self.store.connect_and_create)

            self._embeddings = None
            self._meta = []
            self._index = None

            # 3. Iterate users and re-index
            users = list(self.active_sessions.keys())
            if not users and hasattr(self, 'history'): # Fallback for mock
                 users = list(self.history.keys())

            if user_limit:
                users = users[:user_limit]

            logger.info(f"[RAG] Reindexing for {len(users)} users: {users}")
            for u in users:
                # This is already async and handles its own threading
                await self.index_messages_from_history(u, limit=500)

            # 4. Rebuild FAISS index from the newly populated data
            self._embeddings, self._meta = await asyncio.to_thread(self.store.load_all)
            if self._embeddings is not None:
                logger.info(f"[RAG] Re-loaded {len(self._meta)} vectors from new DB.")
                await self._build_faiss_index() # This is async

            self.is_ready = True
            logger.info("[RAG] Reindex complete.")

    async def prune_old(self, max_age_days: int = 365):
        """Removes vectors older than `max_age_days` from SQLite and rebuilds index."""
        if self.store is None or not self.is_ready:
            logger.warning("[RAG] Store not ready, skipping prune.")

            return

        cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).isoformat()

        async with self._lock:
            self.is_ready = False # Mark as not ready during prune

            pruned_count = await asyncio.to_thread(self.store.prune, cutoff)

            if pruned_count > 0:
                logger.info(f"[RAG] Pruned {pruned_count} old vectors from SQLite.")
                # Reload all data and rebuild the FAISS cache from scratch
                self._embeddings, self._meta = await asyncio.to_thread(self.store.load_all)
                await self._build_faiss_index() # Rebuilds & saves cache
            else:
                logger.info("[RAG] Prune: No old items found to remove.")

            self.is_ready = True
            logger.info("[RAG] Prune complete.")


# -----------------------
# Example Usage (Standalone Test)
# -----------------------
async def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("RAG Chat Service Example")

    if not SBER_AVAILABLE:
        logger.error("SentenceTransformers not found. pip install sentence-transformers")
    if not FAISS_AVAILABLE:
        logger.warning("FAISS not found. pip install faiss-cpu (or faiss-gpu)")

    # Clean up old data for fresh test
    DB_FILE.unlink(missing_ok=True)
    FAISS_INDEX_FILE.unlink(missing_ok=True)

    rag_service = RAGChatService()

    # Wait for model to load (async)
    await rag_service.initialize()


    # Simulate some history by calling send_message directly
    await rag_service.send_message("user1", "What is the capital of France?", "user")
    await rag_service.send_message("user1", "Paris.", "assistant")
    await rag_service.send_message("user1", "I like apples.", "user", metadata={"topic": "food", "emotion": "happy"})
    await rag_service.send_message("user1", "Apples are healthy.", "assistant", metadata={"topic": "food"})

    # Index history
    await rag_service.index_messages_from_history("user1", limit=10)

    logger.info("--- History indexed ---")

    # Process a new message
    logger.info("--- Processing 'What fruit do I like?' (with context) ---")
    response1 = await rag_service.process_message(
        "What fruit do I like?",
        user=type('MockUser', (object,), {'username': 'user1'})(),
        context={"topic": "food", "emotion": "curious"}
    )
    logger.info(f"Response: {response1['text']}")
    logger.info(f"Retrieved Summary: {response1['context'].get('_retrieved_summary')}")

    # Test re-loading from disk
    logger.info("--- Testing persistence (reloading service) ---")

    rag_service_new = RAGChatService()
    await rag_service_new.initialize() # allow init


    logger.info("--- Processing 'Tell me about France' (new service) ---")
    response3 = await rag_service_new.process_message(
        "Tell me about France",
        user=type('MockUser', (object,), {'username': 'user1'})()
    )
    logger.info(f"Response: {response3['text']}")
    logger.info(f"Retrieved Summary: {response3['context'].get('_retrieved_summary')}")

    # Test pruning
    logger.info("--- Testing prune (setting age to 0 days) ---")
    await rag_service_new.prune_old(max_age_days=0)

    logger.info("--- Processing 'What fruit do I like?' (after prune) ---")
    response4 = await rag_service_new.process_message(
        "What fruit do I like?",
        user=type('MockUser', (object,), {'username': 'user1'})()
    )
    logger.info(f"Response: {response4['text']}")
    # Note: The summary will be weak/empty because the previous entries were pruned
    logger.info(f"Retrieved Summary: {response4['context'].get('_retrieved_summary')}")



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed to run main async test: {e}")
