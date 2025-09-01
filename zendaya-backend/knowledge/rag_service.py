"""
RAG Service - Retrieval Augmented Generation with Pinecone
"""
import os
import hashlib
from typing import List, Dict, Any, Optional
import asyncio

from pinecone import Pinecone, ServerlessSpec
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class RAGService:
    def __init__(self):
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.index_name = "zendaya-knowledge"
        self.pc = None
        self.index = None
        self.embedding_model = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Pinecone and embedding model"""
        if not self.pinecone_api_key:
            print("Warning: PINECONE_API_KEY not found - RAG features disabled")
            return
        
        if not self.gemini_api_key:
            print("Warning: GEMINI_API_KEY not found - embedding features disabled")
            return
        
        try:
            # Initialize Pinecone
            self.pc = Pinecone(api_key=self.pinecone_api_key)
            
            # Create index if it doesn't exist
            if self.index_name not in self.pc.list_indexes().names():
                self.pc.create_index(
                    name=self.index_name,
                    dimension=768,  # Gemini embedding dimension
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
            
            self.index = self.pc.Index(self.index_name)
            
            # Initialize Gemini for embeddings
            genai.configure(api_key=self.gemini_api_key)
            self.embedding_model = genai.GenerativeModel("models/embedding-001")
            
            print("✅ RAG service initialized with Pinecone and Gemini embeddings")
            
        except Exception as e:
            print(f"❌ Failed to initialize RAG service: {e}")
    
    def is_ready(self) -> bool:
        """Check if RAG service is ready"""
        return self.index is not None and self.embedding_model is not None
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Gemini"""
        if not self.embedding_model:
            return []
        
        try:
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"Embedding generation error: {e}")
            return []
    
    async def ingest_document(self, filename: str, content: bytes) -> int:
        """Ingest a document into the knowledge base"""
        if not self.is_ready():
            raise Exception("RAG service not ready")
        
        try:
            # Convert bytes to text (assuming UTF-8)
            text_content = content.decode('utf-8')
            
            # Split into chunks (simple sentence-based chunking)
            chunks = self._chunk_text(text_content)
            
            # Generate embeddings and store
            vectors = []
            for i, chunk in enumerate(chunks):
                embedding = await self._generate_embedding(chunk)
                if embedding:
                    chunk_id = hashlib.md5(f"{filename}_{i}".encode()).hexdigest()
                    vectors.append({
                        "id": chunk_id,
                        "values": embedding,
                        "metadata": {
                            "filename": filename,
                            "chunk_index": i,
                            "content": chunk,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
            
            # Upsert to Pinecone
            if vectors:
                self.index.upsert(vectors=vectors)
            
            return len(vectors)
            
        except Exception as e:
            raise Exception(f"Document ingestion failed: {str(e)}")
    
    async def query(self, query_text: str, limit: int = 5) -> str:
        """Query the knowledge base for relevant context"""
        if not self.is_ready():
            return ""
        
        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query_text)
            if not query_embedding:
                return ""
            
            # Search Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=limit,
                include_metadata=True
            )
            
            # Format results
            context_chunks = []
            for match in results.matches:
                if match.score > 0.7:  # Relevance threshold
                    content = match.metadata.get("content", "")
                    filename = match.metadata.get("filename", "unknown")
                    context_chunks.append(f"[{filename}] {content}")
            
            return "\n\n".join(context_chunks) if context_chunks else ""
            
        except Exception as e:
            print(f"RAG query error: {e}")
            return ""
    
    def _chunk_text(self, text: str, max_chunk_size: int = 500) -> List[str]:
        """Simple text chunking by sentences"""
        sentences = text.replace('\n', ' ').split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk + sentence) < max_chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks