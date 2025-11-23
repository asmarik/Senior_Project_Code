"""Upload endpoint - Complete compliance analysis pipeline"""
import os
import time
from fastapi import APIRouter, File, UploadFile, HTTPException
from functools import wraps

from config import UPLOAD_FOLDER, MAX_FILE_SIZE
from utils.file_utils import allowed_file, get_cached_pdpl_articles, sanitize_filename
from services.pdf_service import extract_text_from_pdf
from services.matching_service import match_with_pdpl
from models import model_manager

router = APIRouter()


def monitor_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        elapsed_time = time.time() - start_time
        if isinstance(result, dict):
            result['performance'] = {
                'elapsed_time_seconds': round(elapsed_time, 2),
                'llm_used': model_manager.llm_enabled and (model_manager.llm_clause_matching or model_manager.llm_reranking)
            }
        return result
    return wrapper


@router.post("/upload")
@monitor_performance
async def upload_file(file: UploadFile = File(...)):
    """
    Complete Pipeline - Upload a PDF and get full compliance analysis.
    
    Includes: OCR + RAG (semantic search) + Text matching + Coverage analysis
    
    Returns:
        JSON response with extracted text and matched PDPL articles with full coverage analysis
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    # Sanitize filename to prevent path traversal and invalid characters
    original_filename = file.filename
    filename = sanitize_filename(original_filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Read and save file
        contents = await file.read()
        
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024)}MB"
            )
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text from PDF
        extracted_text = extract_text_from_pdf(filepath)
        
        # Match with PDPL articles (cached for performance)
        pdpl_articles = get_cached_pdpl_articles()
        matches = match_with_pdpl(extracted_text, pdpl_articles, threshold=0.5, top_k=15)
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'filename': original_filename,
            'total_pages': len(extracted_text),
            'extracted_text': extracted_text,
            'matches': matches,
            'total_matches': len(matches),
            'message': 'File processed successfully'
        }
        
    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

