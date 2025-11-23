"""Missing endpoints - Identify missing PDPL articles and clauses"""
import os
import time
from fastapi import APIRouter, File, UploadFile, HTTPException
from functools import wraps

from config import UPLOAD_FOLDER, MAX_FILE_SIZE
from utils.file_utils import allowed_file, get_cached_pdpl_articles, sanitize_filename
from utils.scoring_utils import calculate_overall_score
from services.pdf_service import extract_text_simple
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


@router.post("/missing")
@monitor_performance
async def get_missing_only(file: UploadFile = File(...)):
    """
    Missing Items Only - Returns what's missing from the PDF.
    
    Shows missing articles, missing clauses, and partially covered clauses.
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
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        extracted_text = extract_text_simple(filepath)
        
        pdpl_articles = get_cached_pdpl_articles()
        matches = match_with_pdpl(extracted_text, pdpl_articles, threshold=0.5, top_k=15)
        
        all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
        overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
        
        all_missing_clauses = []
        all_partially_covered_clauses = []
        
        for match in matches:
            article_num = match.get('article_number', 0)
            
            for clause in match.get('missing_clauses', []):
                all_missing_clauses.append({
                    'article_number': article_num,
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 0),
                    'missing_reason': clause.get('missing_reason', ''),
                    'text': clause.get('text', '')
                })
            
            for clause in match.get('partially_covered_clauses', []):
                all_partially_covered_clauses.append({
                    'article_number': article_num,
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 0),
                    'band': 'Partial',
                    'text': clause.get('text', '')
                })
        
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'filename': original_filename,
            'overall_score': overall_score_info['overall_score'],
            'compliance_level': overall_score_info['compliance_level'],
            'missing_articles': {
                'count': overall_score_info['missing_count'],
                'article_numbers': overall_score_info['missing_articles']
            },
            'missing_clauses': {
                'count': len(all_missing_clauses),
                'clauses': all_missing_clauses
            },
            'partially_covered_clauses': {
                'count': len(all_partially_covered_clauses),
                'clauses': all_partially_covered_clauses
            },
            'summary': {
                'total_items_missing': overall_score_info['missing_count'] + len(all_missing_clauses),
                'articles_not_found': overall_score_info['missing_count'],
                'clauses_not_found': len(all_missing_clauses),
                'clauses_partially_covered': len(all_partially_covered_clauses)
            }
        }
        
    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/missing_llm")
@monitor_performance
async def get_missing_with_llm(file: UploadFile = File(...)):
    """
    Missing with LLM - Returns missing items WITH LLM-generated explanations.
    
    Uses LLM for detailed explanations of what's missing (SLOW on CPU, 60-120s).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    if not model_manager.llm_enabled:
        raise HTTPException(status_code=503, detail="LLM is not available. Use /missing endpoint instead.")
    
    # Sanitize filename to prevent path traversal and invalid characters
    original_filename = file.filename
    filename = sanitize_filename(original_filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        extracted_text = extract_text_simple(filepath)
        
        # Force enable LLM
        original_clause_matching = model_manager.llm_clause_matching
        original_reranking = model_manager.llm_reranking
        
        model_manager.llm_clause_matching = True
        model_manager.llm_reranking = True
        
        try:
            pdpl_articles = get_cached_pdpl_articles()
            matches = match_with_pdpl(extracted_text, pdpl_articles, threshold=0.5, top_k=15)
            
            all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
            overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
        finally:
            model_manager.llm_clause_matching = original_clause_matching
            model_manager.llm_reranking = original_reranking
        
        all_missing_clauses = []
        all_partially_covered_clauses = []
        
        for match in matches:
            article_num = match.get('article_number', 0)
            
            for clause in match.get('missing_clauses', []):
                all_missing_clauses.append({
                    'article_number': article_num,
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 0),
                    'missing_reason': clause.get('missing_reason', ''),
                    'llm_explanation': clause.get('llm_explanation', ''),
                    'text': clause.get('text', '')
                })
            
            for clause in match.get('partially_covered_clauses', []):
                all_partially_covered_clauses.append({
                    'article_number': article_num,
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 0),
                    'band': 'Partial',
                    'partial_reason': clause.get('partial_reason', ''),
                    'llm_explanation': clause.get('llm_explanation', ''),
                    'text': clause.get('text', '')
                })
        
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'filename': original_filename,
            'llm_used': True,
            'overall_score': overall_score_info['overall_score'],
            'compliance_level': overall_score_info['compliance_level'],
            'missing_articles': {
                'count': overall_score_info['missing_count'],
                'article_numbers': overall_score_info['missing_articles']
            },
            'missing_clauses': {
                'count': len(all_missing_clauses),
                'clauses': all_missing_clauses
            },
            'partially_covered_clauses': {
                'count': len(all_partially_covered_clauses),
                'clauses': all_partially_covered_clauses
            },
            'summary': {
                'total_items_missing': overall_score_info['missing_count'] + len(all_missing_clauses),
                'articles_not_found': overall_score_info['missing_count'],
                'clauses_not_found': len(all_missing_clauses),
                'clauses_partially_covered': len(all_partially_covered_clauses)
            }
        }
        
    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

