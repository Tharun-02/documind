# app/core/ingestion/parser.py
#
# WHY THIS FILE EXISTS:
# Takes a PDF file and extracts clean, readable text from it.
# This is the FIRST step in the ingestion pipeline.
#
# PIPELINE FLOW:
#   PDF file → parser.extract_text() → plain text
#             ↓
#           chunker.split_text() → chunks with metadata
#             ↓
#           store in database

from pathlib import Path
from typing import Optional, Dict, Any
import PyPDF2


class PDFParser:
    """
    Extracts text from PDF files.
    
    Why a class? Encapsulation + testability.
    You can create a PDFParser, call methods on it, verify the results.
    
    Why not just use PyPDF2.PdfReader directly?
    Because we might switch to a different library later (pypdf, pdfplumber, etc.)
    The class abstracts away the implementation detail.
    """

    @staticmethod
    def extract_text(file_path: str) -> Dict[str, Any]:
        """
        Extract text and metadata from a PDF file.
        
        Args:
            file_path: path to the PDF file, e.g. "/uploads/contract.pdf"
        
        Returns:
            {
                "text": "full extracted text...",
                "page_count": 10,
                "title": "Contract" (from metadata if available),
                "success": True,
            }
        
        Raises:
            FileNotFoundError: if file doesn't exist
            ValueError: if file isn't a valid PDF
        
        Example:
            result = PDFParser.extract_text("/uploads/contract.pdf")
            if result["success"]:
                print(f"Extracted {result['page_count']} pages")
                print(result["text"][:500])  # first 500 chars
        """

        # Validate file exists
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        if not pdf_path.suffix.lower() == ".pdf":
            raise ValueError(f"File is not a PDF: {file_path}")

        try:
            # Open the PDF and create a reader object
            # PyPDF2.PdfReader is the main class for reading PDFs
            with open(pdf_path, "rb") as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)

                # Extract text from each page
                # reader.pages is a list of page objects
                full_text = ""
                for page_num, page in enumerate(reader.pages):
                    # page.extract_text() returns a string for that page
                    # We keep track of page numbers for metadata
                    page_text = page.extract_text()
                    if page_text:
                        # Add a page marker so we know where pages end
                        # Later, when chunking, we'll use this to attribute chunks to pages
                        full_text += f"\n[PAGE {page_num + 1}]\n{page_text}\n"

                # Try to extract document title from metadata (if it exists)
                title = None
                if reader.metadata:
                    title = reader.metadata.get("/Title")

                # Return structured result
                return {
                    "text": full_text.strip(),  # remove leading/trailing whitespace
                    "page_count": len(reader.pages),
                    "title": title,
                    "success": True,
                }

        except PyPDF2.errors.PdfReadError as e:
            # PyPDF2 throws this if the PDF is corrupted or invalid format
            raise ValueError(f"Invalid or corrupted PDF: {e}")
        except Exception as e:
            # Catch-all for other errors (file permissions, etc.)
            raise ValueError(f"Failed to extract PDF: {e}")


# Convenience function so you can use:
#   from app.core.ingestion.parser import extract_pdf_text
# Instead of:
#   from app.core.ingestion.parser import PDFParser
#   PDFParser.extract_text(...)

def extract_pdf_text(file_path: str) -> Dict[str, Any]:
    """Wrapper for PDFParser.extract_text() for convenience."""
    return PDFParser.extract_text(file_path)
