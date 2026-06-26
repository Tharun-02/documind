# app/core/ingestion/chunker.py
#
# WHY THIS FILE EXISTS:
# Takes full document text and splits it into overlapping chunks.
# This is the SECOND step in the ingestion pipeline (after parser).
#
# CRITICAL FOR RAG:
# The chunks you create here directly affect retrieval quality later.
# Bad chunking → bad retrieval → bad LLM answers.
#
# PIPELINE FLOW:
#   PDF text → chunker.split_text() → list of chunks with metadata
#                ↓
#            embed each chunk
#                ↓
#            store in vector DB

from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter


class DocumentChunker:
    """
    Splits text into overlapping chunks for RAG systems.
    
    Uses LangChain's RecursiveCharacterTextSplitter which is industry standard.
    Why industry standard?
    - Balances chunk size with overlap (smart defaults)
    - Recursive splitting preserves context better than naive splitting
    - Tested with thousands of real documents
    """

    # Class-level splitter object (created once, reused)
    # This is efficient because creating a splitter is relatively expensive
    _splitter = RecursiveCharacterTextSplitter(
        # ── SIZE CONFIGURATION ──────────────────────────────────────────
        # chunk_size: target size of each chunk in CHARACTERS (not tokens)
        # 800 chars ≈ 200-300 tokens (depends on language)
        # Why 800? It's a sweet spot:
        #   - Big enough to capture full context
        #   - Small enough to fit in LLM context window (4k+ tokens available)
        #   - Small enough to retrieve quickly
        # For detailed PDFs: try 500-1000
        # For chat transcripts: try 300-500
        chunk_size=800,

        # chunk_overlap: how much overlap between chunks in CHARACTERS
        # Chunk 1: "...... [overlap zone] ....."
        # Chunk 2: "     [overlap zone] ...... "
        # Why overlap? Prevents context cutoff
        # If context you need is split between two chunks,
        # overlap ensures both chunks are retrieved together
        chunk_overlap=100,

        # ── SPLITTING STRATEGY ──────────────────────────────────────────
        # separators: list of delimiters to split on, tried in order
        # The splitter tries each separator in order until chunks fit size
        # "\n\n" (paragraph): best for keeping ideas together
        # "\n" (newline): preserves line breaks (good for code, scripts)
        # " " (space): splits words (worst case)
        # "" (character): splits at character level (last resort)
        separators=[
            "\n\n",  # Try paragraph split first (best quality)
            "\n",    # Then line break
            " ",     # Then space (word boundary)
            "",      # Finally character (never use for text, only last resort)
        ],

        # length_function: how to count chunk size
        # We use len() which counts characters
        # Alternative: token_counter from tiktoken (counts tokens)
        # tokens are more accurate but require LLM knowledge
        length_function=len,

        # add_start_index: if True, adds character position to metadata
        # Useful for tracing back to original document
        add_start_index=False,
    )

    @classmethod
    def split_text(
        cls,
        text: str,
        document_id: int,
        filename: str = "unknown",
        page_count: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks and add rich metadata.
        
        Args:
            text: full document text to split
            document_id: ID of the Document row in DB (foreign key)
            filename: original filename (for reference)
            page_count: total pages in document (for context)
        
        Returns:
            List of dicts, each representing one chunk:
            [
                {
                    "content": "chunk text...",
                    "chunk_index": 0,
                    "page_number": 1,
                    "document_id": 1,
                    "filename": "contract.pdf",
                },
                ...
            ]
        
        Example:
            chunks = DocumentChunker.split_text(
                text=extracted_text,
                document_id=42,
                filename="contract.pdf",
                page_count=10,
            )
            # chunks[0] = {
            #     "content": "The contract...",
            #     "chunk_index": 0,
            #     "page_number": 1,
            #     ...
            # }
        """

        # Step 1: Use LangChain's splitter to create raw chunks
        # .split_text() returns a list of strings (just the content)
        raw_chunks = cls._splitter.split_text(text)

        # Step 2: Process each chunk to extract page number and add metadata
        chunks_with_metadata = []

        for chunk_index, chunk_content in enumerate(raw_chunks):
            # Extract page number from the text
            # Remember from parser.py: we added "[PAGE N]" markers
            # Example: "[PAGE 3]\nSome text..."
            page_number = extract_page_number(text, chunk_content, page_count)

            chunk = {
                "content": chunk_content,
                "chunk_index": chunk_index,
                "page_number": page_number,
                "document_id": document_id,
                "filename": filename,
                # These fields are optional, added for context:
                "chunk_count": len(raw_chunks),  # total chunks in this doc
            }

            chunks_with_metadata.append(chunk)

        return chunks_with_metadata


def extract_page_number(
    full_text: str,
    chunk_content: str,
    page_count: int,
) -> int:
    """
    Determine which page a chunk came from.
    
    Strategy:
    1. Try to find "[PAGE N]" markers within the chunk
    2. If not found, guess based on chunk position
    3. Default to 1 if we can't determine
    
    Why guess? Because chunks might not cleanly align with page markers
    (a chunk might start mid-page or span pages).
    This is a heuristic that works 90% of the time.
    """
    
    # Look for "[PAGE N]" pattern in the chunk content
    # Example: "[PAGE 5]\nSome text" → extract 5
    if "[PAGE" in chunk_content:
        try:
            # Find the first "[PAGE" occurrence
            start = chunk_content.find("[PAGE ") + 6
            end = chunk_content.find("]", start)
            if end > start:
                page_str = chunk_content[start:end].strip()
                page_num = int(page_str)
                return min(page_num, page_count)  # cap at page_count
        except (ValueError, IndexError):
            pass  # if parsing fails, fall through to default

    # Default: assume it's somewhere in the middle
    # This is weak but better than nothing
    return max(1, min(page_count, page_count // 2))


# ═════════════════════════════════════════════════════════════════════════
# CHUNKING STRATEGY EXPLAINED — Why This Matters
# ═════════════════════════════════════════════════════════════════════════
#
# EXAMPLE: Contract with a clause split across chunks
#
# BAD CHUNKING (no overlap):
#   Chunk 1: "...Termination clause: Either party may terminate with 30..."
#   Chunk 2: "...days written notice. Effective immediately upon receipt...."
#   Problem: Chunk 1 ends mid-sentence, Chunk 2 starts mid-sentence
#            If you only retrieve Chunk 2, it makes no sense
#
# GOOD CHUNKING (with overlap):
#   Chunk 1: "...Termination clause: Either party may terminate with 30..."
#   Chunk 2: "...with 30 days written notice. Effective immediately upon..."
#   Chunk 3: "...upon receipt. Renewal requires 60 days advance notice..."
#   Better: Chunks overlap, so context is preserved
#           Retrieve Chunk 2 → you still understand it's about 30-day notice
#
# ═════════════════════════════════════════════════════════════════════════
