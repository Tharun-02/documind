# app/core/ingestion/embedder.py
# UPDATED for Day 4.5: Replace OpenAI with HuggingFace (FREE)
#
# This version supports multiple embedding providers:
# - HuggingFace Inference API (RECOMMENDED - FREE)
# - Cohere (Alternative - LIMITED FREE)
# - Google Generative AI (Alternative - FREE)
#
# Key difference from Day 4:
# - No OpenAI dependency (saves money)
# - Uses sentence-transformers via HuggingFace (free 30K/month)
# - Returns 384-dimensional vectors (vs OpenAI's 1536)
# - Same interface so retriever.py needs NO changes

from typing import List, Dict, Any
import requests
from app.config import settings


class EmbeddingService:
    """
    Embeds text using FREE alternatives to OpenAI.
    
    Supports:
      1. HuggingFace Inference API (RECOMMENDED)
         - 30K requests/month free
         - sentence-transformers/all-MiniLM-L6-v2 (384 dims)
         - No credit card needed
      
      2. Cohere Embeddings (ALTERNATIVE)
         - Limited free tier
         - 4096 dimensions (high quality)
      
      3. Google Generative AI (ALTERNATIVE)
         - Free tier available
         - Requires billing account
    """

    def __init__(self):
        provider = getattr(settings, 'EMBEDDING_PROVIDER', 'huggingface')
        
        if provider == 'huggingface':
            self.api_key = settings.HUGGINGFACE_API_KEY
            self.model = getattr(settings, 'HUGGINGFACE_MODEL', 
                               'sentence-transformers/all-MiniLM-L6-v2')
            self.provider = 'huggingface'
            
        elif provider == 'cohere':
            self.api_key = settings.COHERE_API_KEY
            self.provider = 'cohere'
            
        elif provider == 'google':
            self.api_key = settings.GOOGLE_API_KEY
            self.provider = 'google'
        else:
            raise ValueError(f"Unknown embedding provider: {provider}")

    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.
        
        Args:
            text: text to embed (a chunk or question)
        
        Returns:
            List of floats (embedding vector)
        
        Example:
            embedder = EmbeddingService()
            vec = embedder.embed_text("The contract expires December 31st")
            # Returns: [0.123, -0.456, ..., 0.234]  (384 floats if HuggingFace)
        """

        if self.provider == 'huggingface':
            return self._embed_huggingface(text)
        elif self.provider == 'cohere':
            return self._embed_cohere(text)
        elif self.provider == 'google':
            return self._embed_google(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts efficiently (cheaper than individual calls).
        
        Args:
            texts: list of strings to embed
        
        Returns:
            List of embeddings
        """

        if not texts:
            return []

        if self.provider == 'huggingface':
            return self._embed_batch_huggingface(texts)
        elif self.provider == 'cohere':
            return self._embed_batch_cohere(texts)
        elif self.provider == 'google':
            return self._embed_batch_google(texts)

    # ─────────────────────────────────────────────────────────────────────
    # HUGGINGFACE IMPLEMENTATION (RECOMMENDED)
    # ─────────────────────────────────────────────────────────────────────

    def _embed_huggingface(self, text: str) -> List[float]:
        """
        Embed using HuggingFace Inference API.
        
        Why HuggingFace?
        - 30,000 requests/month FREE
        - No credit card needed
        - Fast (milliseconds)
        - Good quality (sentence-transformers)
        - 384 dimensions (smaller than OpenAI's 1536)
        """

        try:
            url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model}"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "inputs": text,
            }

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code != 200:
                raise ValueError(
                    f"HuggingFace API error {response.status_code}: {response.text}"
                )

            embedding = response.json()

            # HuggingFace returns either a list or list of lists
            # For single text, extract the first element
            if isinstance(embedding[0], list):
                embedding = embedding[0]

            return embedding

        except Exception as e:
            raise ValueError(f"Failed to embed text with HuggingFace: {str(e)}")

    def _embed_batch_huggingface(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts using HuggingFace batch endpoint.
        More efficient than individual calls.
        """

        try:
            url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model}"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "inputs": texts,
            }

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=60,  # Batch might take longer
            )

            if response.status_code != 200:
                raise ValueError(
                    f"HuggingFace API error {response.status_code}: {response.text}"
                )

            embeddings = response.json()
            return embeddings

        except Exception as e:
            raise ValueError(f"Failed to embed batch with HuggingFace: {str(e)}")

    # ─────────────────────────────────────────────────────────────────────
    # COHERE IMPLEMENTATION (ALTERNATIVE)
    # ─────────────────────────────────────────────────────────────────────

    def _embed_cohere(self, text: str) -> List[float]:
        """
        Embed using Cohere API (alternative to HuggingFace).
        
        Pros:
          - High quality (4096 dimensions)
          - Professional grade
          
        Cons:
          - Limited free tier (~1000 embeddings/month)
          - Requires API key setup
        """

        try:
            import cohere
            
            client = cohere.Client(api_key=self.api_key)
            
            response = client.embed(
                texts=[text],
                model="embed-english-v3.0",
                input_type="search_document",
            )

            return response.embeddings[0]

        except ImportError:
            raise ImportError("Install cohere: pip install cohere")
        except Exception as e:
            raise ValueError(f"Failed to embed with Cohere: {str(e)}")

    def _embed_batch_cohere(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding with Cohere."""

        try:
            import cohere
            
            client = cohere.Client(api_key=self.api_key)
            
            response = client.embed(
                texts=texts,
                model="embed-english-v3.0",
                input_type="search_document",
            )

            return response.embeddings

        except ImportError:
            raise ImportError("Install cohere: pip install cohere")
        except Exception as e:
            raise ValueError(f"Failed to embed batch with Cohere: {str(e)}")

    # ─────────────────────────────────────────────────────────────────────
    # GOOGLE IMPLEMENTATION (ALTERNATIVE)
    # ─────────────────────────────────────────────────────────────────────

    def _embed_google(self, text: str) -> List[float]:
        """
        Embed using Google Generative AI (alternative).
        
        Pros:
          - Free tier available
          - Good quality
          
        Cons:
          - Requires billing account
          - Slightly slower
        """

        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
            )

            return result["embedding"]

        except ImportError:
            raise ImportError("Install google-generativeai: pip install google-generativeai")
        except Exception as e:
            raise ValueError(f"Failed to embed with Google: {str(e)}")

    def _embed_batch_google(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding with Google."""

        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            
            embeddings = []
            for text in texts:
                result = genai.embed_content(
                    model="models/embedding-001",
                    content=text,
                )
                embeddings.append(result["embedding"])

            return embeddings

        except ImportError:
            raise ImportError("Install google-generativeai: pip install google-generativeai")
        except Exception as e:
            raise ValueError(f"Failed to embed batch with Google: {str(e)}")


class PineconeService:
    """
    Stores embeddings in Pinecone (unchanged from Day 4).
    Works with ANY embedding dimension (384, 768, 1536, etc).
    """

    def __init__(self):
        try:
            from pinecone import Pinecone
        except ImportError:
            raise ImportError("Install pinecone: pip install pinecone-client")

        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
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

                vectors_to_upsert.append((vector_id, embedding, metadata))

            upsert_response = self.index.upsert(vectors=vectors_to_upsert)

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

            formatted_results = []
            for match in results.matches:
                formatted_results.append({
                    "id": match.id,
                    "score": match.score,
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
