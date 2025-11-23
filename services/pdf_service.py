"""PDF text extraction service"""
import fitz  # PyMuPDF
from typing import List, Dict, Any


def extract_text_from_pdf(filepath: str) -> List[Dict[str, Any]]:
    """
    Extract text from PDF file using PyMuPDF.
    
    Args:
        filepath: Path to the PDF file
    
    Returns:
        List of dictionaries with page number, text, character count, and word count
    
    Raises:
        Exception: If PDF reading fails
    """
    extracted_text = []
    
    pdf_document = fitz.open(filepath)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        page_text = page.get_text()
        
        # If no text found (scanned PDF), mark as empty
        if not page_text.strip():
            page_text = "[No text found - may be a scanned image]"
        
        extracted_text.append({
            'page': page_num + 1,
            'text': page_text.strip(),
            'character_count': len(page_text.strip()),
            'word_count': len(page_text.strip().split())
        })
    
    pdf_document.close()
    
    return extracted_text


def extract_text_simple(filepath: str) -> List[Dict[str, str]]:
    """
    Simple text extraction without character/word counts.
    
    Args:
        filepath: Path to the PDF file
    
    Returns:
        List of dictionaries with page number and text
    """
    extracted_text = []
    
    pdf_document = fitz.open(filepath)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        page_text = page.get_text()
        
        extracted_text.append({
            'page': page_num + 1,
            'text': page_text.strip() if page_text.strip() else ""
        })
    
    pdf_document.close()
    
    return extracted_text
