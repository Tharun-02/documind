# app/core/generation/llm_service.py
# Day 5: LLM Integration with Groq (FREE)

from typing import Generator
import requests
from app.config import settings


class LLMService:
    """
    Call LLM to generate answers from retrieved chunks.
    Uses Groq API (fastest free LLM available).
    
    Why Groq?
    - Completely FREE (no credit card)
    - Super fast (50+ tokens/sec)
    - High quality (Mixtral model)
    - No limits (seriously)
    """

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = "llama-3.3-70b-versatile"  # Best free model w/ reliable tool-calling (Day 6)
        self.base_url = "https://api.groq.com/openai/v1"

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: list,
        stream: bool = False,
    ) -> str:
        """
        Generate answer using LLM.
        
        Args:
            question: user's question
            retrieved_chunks: list of {"content": "...", "similarity_score": 0.9, ...}
            stream: if True, yield tokens as they arrive
            
        Returns:
            Generated answer string
        """

        # Build prompt
        context = self._format_context(retrieved_chunks)
        prompt = self._build_prompt(question, context)
        
        # Call Groq API
        response = self._call_groq(
            prompt=prompt,
            stream=stream,
        )
        
        if stream:
            return response  # Generator
        else:
            return response  # String

    def _format_context(self, chunks: list) -> str:
        """Format retrieved chunks into context string."""
        formatted = "RETRIEVED DOCUMENTS:\n\n"
        
        for i, chunk in enumerate(chunks, 1):
            score = chunk.get('similarity_score', 0)
            content = chunk.get('content', '')
            filename = chunk.get('filename', 'Unknown')
            
            formatted += f"Document {i} ({filename}, relevance: {score:.2f}):\n"
            formatted += f"{content}\n\n"
        
        return formatted

    def _build_prompt(self, question: str, context: str) -> str:
        """Build the complete prompt for LLM."""
        return f"""You are a helpful assistant that answers questions about documents.

{context}

Question: {question}

Answer the question based only on the provided documents. If the answer is not in the documents, say "I don't know" instead of guessing. Be specific and cite which document you're referencing when possible."""

    def _call_groq(self, prompt: str, stream: bool = False):
        """Call Groq API."""
        try:
            # Using requests (no additional dependency)
            # Groq is OpenAI-compatible API
            
            import json
            
            url = f"{self.base_url}/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1024,
                "stream": stream,
            }
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                stream=stream,
                timeout=60,
            )
            
            if response.status_code != 200:
                raise ValueError(f"Groq API error: {response.text}")
            
            if stream:
                # Return generator for streaming
                return self._stream_response(response)
            else:
                # Return complete response
                data = response.json()
                return data['choices'][0]['message']['content']
        
        except Exception as e:
            raise ValueError(f"Failed to call Groq: {str(e)}")

    def _stream_response(self, response) -> Generator[str, None, None]:
        """Stream tokens as they arrive."""
        try:
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str != '[DONE]':
                            try:
                                data = json.loads(data_str)
                                if 'choices' in data:
                                    delta = data['choices'][0]['delta']
                                    if 'content' in delta:
                                        yield delta['content']
                            except:
                                pass
        except Exception as e:
            raise ValueError(f"Streaming error: {str(e)}")


# Alternative: Ollama (if using local)
class OllamaService:
    """Local LLM via Ollama (if you have GPU)."""
    
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.model = "mistral"  # or llama2, neural-chat
    
    def generate_answer(self, question: str, retrieved_chunks: list) -> str:
        """Generate answer using local Ollama."""
        context = self._format_context(retrieved_chunks)
        prompt = self._build_prompt(question, context)
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=60,
            )
            
            data = response.json()
            return data['response']
        except Exception as e:
            raise ValueError(f"Ollama error: {str(e)}")
    
    def _format_context(self, chunks: list) -> str:
        formatted = "DOCUMENTS:\n\n"
        for i, chunk in enumerate(chunks, 1):
            score = chunk.get('similarity_score', 0)
            content = chunk.get('content', '')
            formatted += f"Doc {i} (relevance {score:.2f}):\n{content}\n\n"
        return formatted
    
    def _build_prompt(self, question: str, context: str) -> str:
        return f"""{context}

Question: {question}

Answer based on documents. Say "I don't know" if not found."""
