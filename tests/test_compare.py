# tests/test_compare.py
#
# Unit tests for CompareService (Day 8 - Clause Comparison)
#

from unittest.mock import MagicMock, patch
import pytest

from app.services.compare_service import CompareService
from app.models.document import Document, DocumentChunk


class TestCompareService:
    """Tests for CompareService.compare_documents method."""

    def test_compare_documents_returns_empty_when_no_chunks(self):
        """When either document has no chunks, return empty similar_clauses."""
        db = MagicMock()

        doc_1 = Document(id=1, filename="doc1.pdf", user_id=1)
        doc_2 = Document(id=2, filename="doc2.pdf", user_id=1)

        db.query(Document).filter.return_value.first.side_effect = [doc_1, doc_2]
        db.query(DocumentChunk).filter.return_value.all.side_effect = [[], [MagicMock()]]

        service = CompareService(db)
        result = service.compare_documents(1, 2, user_id=1)

        assert result["total_comparisons"] == 0
        assert result["similar_clauses"] == []
        assert result["document_1_id"] == 1
        assert result["document_2_id"] == 2

    def test_compare_documents_verifies_ownership(self):
        """Verify documents belong to the requesting user."""
        db = MagicMock()

        # First document belongs to user, second doesn't
        doc_1 = Document(id=1, filename="doc1.pdf", user_id=1)
        doc_2 = Document(id=2, filename="doc2.pdf", user_id=999)  # Different user

        db.query(Document).filter.return_value.first.side_effect = [doc_1, None]

        service = CompareService(db)

        with pytest.raises(ValueError, match="Document 2 not found or access denied"):
            service.compare_documents(1, 2, user_id=1)

    def test_compare_documents_computes_cosine_similarity(self):
        """Verify cosine similarity calculation works correctly."""
        db = MagicMock()

        doc_1 = Document(id=1, filename="doc1.pdf", user_id=1)
        doc_2 = Document(id=2, filename="doc2.pdf", user_id=1)

        db.query(Document).filter.return_value.first.side_effect = [doc_1, doc_2]

        # Create chunks with known embeddings
        chunk_1 = DocumentChunk(id=1, document_id=1, content="same text", page_number=1)
        chunk_2 = DocumentChunk(id=2, document_id=2, content="same text", page_number=1)

        db.query(DocumentChunk).filter.return_value.all.side_effect = [[chunk_1], [chunk_2]]

        service = CompareService(db)

        # Mock embedding service to return identical vectors (similarity = 1.0)
        with patch.object(service.embedding_service, 'embed_text') as mock_embed:
            mock_embed.return_value = [1.0, 0.0, 0.0]

            result = service.compare_documents(1, 2, user_id=1, threshold=0.5)

        assert len(result["similar_clauses"]) == 1
        assert result["similar_clauses"][0]["similarity_score"] == 1.0
        assert result["total_comparisons"] == 1

    def test_compare_documents_filters_by_threshold(self):
        """Only return clauses above similarity threshold."""
        db = MagicMock()

        doc_1 = Document(id=1, filename="doc1.pdf", user_id=1)
        doc_2 = Document(id=2, filename="doc2.pdf", user_id=1)

        db.query(Document).filter.return_value.first.side_effect = [doc_1, doc_2]

        chunk_1 = DocumentChunk(id=1, document_id=1, content="text one", page_number=1)
        chunk_2 = DocumentChunk(id=2, document_id=2, content="text two", page_number=1)

        db.query(DocumentChunk).filter.return_value.all.side_effect = [[chunk_1], [chunk_2]]

        service = CompareService(db)

        # Mock embeddings: first call returns [1,0,0], second returns [0,1,0]
        # Cosine similarity = 0 (orthogonal vectors)
        with patch.object(service.embedding_service, 'embed_text') as mock_embed:
            mock_embed.side_effect = [
                [1.0, 0.0, 0.0],  # chunk_1 embedding
                [0.0, 1.0, 0.0],  # chunk_2 embedding
            ]

            result = service.compare_documents(1, 2, user_id=1, threshold=0.5)

        assert len(result["similar_clauses"]) == 0  # 0 < 0.5 threshold

    def test_compare_documents_handles_multiple_chunks(self):
        """Compare all chunk pairs between two documents."""
        db = MagicMock()

        doc_1 = Document(id=1, filename="doc1.pdf", user_id=1)
        doc_2 = Document(id=2, filename="doc2.pdf", user_id=1)

        db.query(Document).filter.return_value.first.side_effect = [doc_1, doc_2]

        # 2 chunks in doc1, 2 chunks in doc2 = 4 total comparisons
        chunks_1 = [
            DocumentChunk(id=1, document_id=1, content="clause A", page_number=1),
            DocumentChunk(id=2, document_id=1, content="clause B", page_number=2),
        ]
        chunks_2 = [
            DocumentChunk(id=3, document_id=2, content="clause A", page_number=1),
            DocumentChunk(id=4, document_id=2, content="clause C", page_number=1),
        ]

        db.query(DocumentChunk).filter.return_value.all.side_effect = [chunks_1, chunks_2]

        service = CompareService(db)

        # First pair identical (sim=1.0), rest different
        embeddings = [
            [1.0, 0.0, 0.0],  # chunk_1
            [0.0, 1.0, 0.0],  # chunk_2
            [1.0, 0.0, 0.0],  # chunk_3 (same as chunk_1)
            [0.0, 0.0, 1.0],  # chunk_4
        ]

        with patch.object(service.embedding_service, 'embed_text') as mock_embed:
            mock_embed.side_effect = embeddings

            result = service.compare_documents(1, 2, user_id=1, threshold=0.7)

        assert result["total_comparisons"] == 4
        # Only chunk_1 vs chunk_3 should match (both [1,0,0])
        assert len(result["similar_clauses"]) == 1
        assert result["similar_clauses"][0]["document_1_chunk_id"] == 1
        assert result["similar_clauses"][0]["document_2_chunk_id"] == 3

    def test_cosine_similarity_identical_vectors(self):
        """Cosine similarity of identical vectors is 1.0."""
        service = CompareService(MagicMock())
        vec = [1.0, 2.0, 3.0]
        assert service._cosine_similarity(vec, vec) == 1.0

    def test_cosine_similarity_orthogonal_vectors(self):
        """Cosine similarity of orthogonal vectors is 0.0."""
        service = CompareService(MagicMock())
        assert service._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_cosine_similarity_zero_vector(self):
        """Cosine similarity with zero vector returns 0.0."""
        service = CompareService(MagicMock())
        assert service._cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
        assert service._cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0

    def test_cosine_similarity_negative_correlation(self):
        """Cosine similarity handles negative correlation (-1.0)."""
        service = CompareService(MagicMock())
        assert service._cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0

    def test_get_verified_document_raises_on_missing(self):
        """_get_verified_document raises ValueError when document not found."""
        db = MagicMock()
        db.query(Document).filter.return_value.first.return_value = None

        service = CompareService(db)

        with pytest.raises(ValueError, match="Document 99 not found or access denied"):
            service._get_verified_document(99, user_id=1)


