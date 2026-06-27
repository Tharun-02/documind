# app/core/ingestion/embedder.py
#
# WHY THIS FILE EXISTS:
# Takes text chunks (from Day 3) and converts them to embeddings via OpenAI API.
# Embeddings are vectors (1536 numbers) that represent meaning.
# Stores vectors in Pinecone (vector database) with metadata.
#
# PIPELINE:
# chunks in Postgres → embed with OpenAI → store in Pinecone → ready for search

from typing import List, Dict, Any
import time
from openai import OpenAI
from app.config import settings


class EmbeddingService:
    """
    Embeds text using OpenAI's text-embedding-3-small model.
    
    Why text-embedding-3-small?
    - Fast (milliseconds per chunk)
    - Cheap ($0.02 per 1M tokens)
    - Good quality (1536 dimensions)
    - Industry standard for RAG
    
    Alternatives:
    - text-embedding-3-large: better quality but slower/expensive
    - Local models (HuggingFace): free but slower on CPU
    """

    def __init__(self):
        # Initialize OpenAI client with API key from .env
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"

    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.
        
        Args:
            text: the text to embed (a chunk, a question, etc.)
        
        Returns:
            List of 1536 floats representing the embedding
        
        Example:
            embedder = EmbeddingService()
            vec = embedder.embed_text("The contract expires on December 31st")
            # vec = [0.123, -0.456, 0.789, ..., 0.234]  (1536 numbers)
        """

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=1536,  # standard for this model
            )

            # response.data[0].embedding is the vector (List of floats)
            embedding = response.data[0].embedding

            return embedding

        except Exception as e:
            raise ValueError(f"Failed to embed text: {str(e)}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts efficiently.
        OpenAI API accepts batches, which is cheaper than individual calls.
        
        Args:
            texts: list of strings to embed
        
        Returns:
            List of embeddings (each is a list of 1536 floats)
        
        Example:
            texts = ["chunk 1...", "chunk 2...", "chunk 3..."]
            embeddings = embedder.embed_batch(texts)
            # embeddings = [[0.1, 0.2, ...], [0.3, 0.4, ...], ...]
        """

        if not texts:
            return []

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,  # OpenAI batches multiple texts
                dimensions=1536,
            )

            # response.data is a list of Embedding objects
            # Each has an embedding attribute
            embeddings = [item.embedding for item in response.data]

            return embeddings

        except Exception as e:
            raise ValueError(f"Failed to embed batch: {str(e)}")


class PineconeService:
    """
    Stores embeddings in Pinecone vector database.
    Pinecone is a managed vector DB that:
    - Stores high-dimensional vectors
    - Provides ultra-fast similarity search
    - Handles scaling automatically
    - Stores metadata alongside vectors
    """

    def __init__(self):
        # Import Pinecone at method level to avoid hard dependency
        try:
            from pinecone import Pinecone
        except ImportError:
            raise ImportError("Install pinecone: pip install pinecone-client")

        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)

        # Connect to the index (pre-created via Pinecone web UI)
        # Index name must be created in Pinecone before running this
        self.index = self.pc.Index(settings.PINECONE_INDEX_NAME)

    def upsert_chunks(
        self,
        chunks_with_embeddings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Store vectors in Pinecone with metadata.
        "Upsert" = update if exists, insert if new.
        
        Args:
            chunks_with_embeddings: list of dicts like:
            [
                {
                    "id": "doc_1_chunk_0",
                    "embedding": [0.1, 0.2, ...],
                    "metadata": {
                        "document_id": 1,
                        "chunk_index": 0,
                        "page_number": 1,
                        "content": "The contract...",
                    }
                },
                ...
            ]
        
        Returns:
            {"upserted_count": 50, "success": True}
        
        Why metadata?
        When we retrieve vectors, we only get IDs back initially.
        Metadata lets us include the actual text + source info.
        """

        try:
            vectors_to_upsert = []

            for item in chunks_with_embeddings:
                vector_id = item["id"]
                embedding = item["embedding"]
                metadata = item["metadata"]

                # Pinecone expects: (id, vector, metadata)
                vectors_to_upsert.append((vector_id, embedding, metadata))

            # Upsert to Pinecone (batch operation)
            # Pinecone handles the actual indexing/search setup
            upsert_response = self.index.upsert(
                vectors=vectors_to_upsert,
                # namespace=... (optional, for multi-tenant)
            )

            return {
                "upserted_count": len(vectors_to_upsert),
                "success": True,
            }

        except Exception as e:
            raise ValueError(f"Failed to upsert to Pinecone: {str(e)}")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search Pinecone for vectors similar to query_embedding.
        
        Args:
            query_embedding: the embedded question (1536 floats)
            top_k: how many results to return (default 5)
        
        Returns:
            [
                {
                    "id": "doc_1_chunk_0",
                    "score": 0.95,  # cosine similarity (higher = more similar)
                    "metadata": {
                        "document_id": 1,
                        "chunk_index": 0,
                        "content": "The contract...",
                    }
                },
                ...
            ]
        
        How Pinecone search works:
        1. Compute cosine distance between query and all vectors
        2. Return top_k closest (most similar)
        3. Include metadata for each result
        """

        try:
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
            )

            # Format results for easier use
            formatted_results = []
            for match in results.matches:
                formatted_results.append({
                    "id": match.id,
                    "score": match.score,  # 0-1, higher is better
                    "metadata": match.metadata,
                })

            return formatted_results

        except Exception as e:
            raise ValueError(f"Failed to search Pinecone: {str(e)}")

    def delete_by_document_id(self, document_id: int) -> Dict[str, Any]:
        """
        Delete all vectors for a document (when user deletes a document).
        
        Why separate method?
        When user deletes a document from Postgres (Day 3),
        we also need to remove it from Pinecone.
        Otherwise searches still retrieve it.
        
        Implementation note:
        Pinecone doesn't have direct "delete by metadata" query.
        You'd need to track vector IDs separately or iterate + delete.
        For simplicity, we'll track this in a companion metadata table.
        """
        # This is left for Day 5+ when we handle cleanup
        pass
