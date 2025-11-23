"""Comprehensive Analysis - Combined Score and Missing Items with LLM"""
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


@router.post("/analyze_comprehensive")
@monitor_performance
async def analyze_comprehensive_with_llm(file: UploadFile = File(...)):
    """
    Comprehensive Analysis with OpenAI API - Combines Score + Missing Items Analysis
    
    This endpoint provides a complete compliance analysis using OpenAI API for:
    - Overall compliance score
    - Detailed clause-level matching
    - Missing articles and clauses with AI explanations
    - Partially covered items with recommendations
    
    Uses OpenAI's GPT-4o-mini API (cloud-based) for enhanced accuracy.
    Processing time: 60-120 seconds depending on document size and API response time.
    
    Returns:
        Complete analysis with score, matches, and missing items all in one response
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    if not model_manager.llm_enabled:
        raise HTTPException(
            status_code=503,
            detail="LLM is not available. This endpoint requires LLM to be enabled."
        )
    
    # Sanitize filename to prevent path traversal and invalid characters
    original_filename = file.filename
    filename = sanitize_filename(original_filename)
    
    # Use absolute path to avoid Windows path issues
    upload_dir = os.path.abspath(UPLOAD_FOLDER)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    
    print(f"[DEBUG] Original filename: {original_filename}")
    print(f"[DEBUG] Sanitized filename: {filename}")
    print(f"[DEBUG] Upload directory: {upload_dir}")
    print(f"[DEBUG] Full filepath: {filepath}")
    
    try:
        # Read and save file
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB")
        
        print(f"[DEBUG] File size: {len(contents)} bytes")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        print(f"[DEBUG] File saved successfully")
        
        # Extract text from PDF
        extracted_text = extract_text_simple(filepath)
        
        # Force enable LLM for this comprehensive analysis
        original_clause_matching = model_manager.llm_clause_matching
        original_reranking = model_manager.llm_reranking
        
        model_manager.llm_clause_matching = True
        model_manager.llm_reranking = True
        
        try:
            # Match with PDPL using LLM (single pass for efficiency)
            pdpl_articles = get_cached_pdpl_articles()
            matches = match_with_pdpl(extracted_text, pdpl_articles, threshold=0.5, top_k=15)
            
            # Calculate overall score
            all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
            overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
        finally:
            # Restore original settings
            model_manager.llm_clause_matching = original_clause_matching
            model_manager.llm_reranking = original_reranking
        
        # Collect detailed matches (for score display)
        detailed_matches = []
        for match in matches:
            # Get article info from nested 'article' key
            article = match.get('article', {})
            article_num = article.get('article_number', 0)
            article_title = article.get('article_title', '')
            
            matched_clauses = []
            missing_clauses = []
            partial_clauses = []
            
            # Note: key is 'covered_clauses' not 'matched_clauses'
            for clause in match.get('covered_clauses', []):
                matched_clauses.append({
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 1.0),
                    'band': 'Full',
                    'text': clause.get('text', ''),
                    'llm_explanation': clause.get('llm_explanation', '')
                })
            
            for clause in match.get('missing_clauses', []):
                missing_clauses.append({
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 0),
                    'missing_reason': clause.get('missing_reason', ''),
                    'llm_explanation': clause.get('llm_explanation', ''),
                    'text': clause.get('text', '')
                })
            
            for clause in match.get('partially_covered_clauses', []):
                partial_clauses.append({
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 0),
                    'band': 'Partial',
                    'partial_reason': clause.get('partial_reason', ''),
                    'llm_explanation': clause.get('llm_explanation', ''),
                    'text': clause.get('text', '')
                })
            
            detailed_matches.append({
                'article_number': article_num,
                'article_title': article_title,
                'overall_coverage': match.get('coverage_percentage', 0),  # Fixed: was 'overall_coverage'
                'band': match.get('band', 'None'),
                'matched_clauses': matched_clauses,
                'missing_clauses': missing_clauses,
                'partially_covered_clauses': partial_clauses
            })
        
        # Collect all missing clauses (for missing items view)
        all_missing_clauses = []
        all_partially_covered_clauses = []
        
        for match in matches:
            # Get article number from nested 'article' key
            article = match.get('article', {})
            article_num = article.get('article_number', 0)
            
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
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Return comprehensive analysis combining both score and missing items
        return {
            'success': True,
            'filename': original_filename,
            'llm_used': True,
            'analysis_type': 'comprehensive',
            
            # Overall Score Information (from score_llm)
            'overall_score': overall_score_info['overall_score'],
            'compliance_level': overall_score_info['compliance_level'],
            
            # Missing Articles (from both)
            'missing_articles': {
                'count': overall_score_info['missing_count'],
                'article_numbers': overall_score_info['missing_articles']
            },
            
            # Detailed Matches (from score_llm)
            'matches': detailed_matches,
            
            # Missing Items Analysis (from missing_llm)
            'missing_clauses': {
                'count': len(all_missing_clauses),
                'clauses': all_missing_clauses
            },
            'partially_covered_clauses': {
                'count': len(all_partially_covered_clauses),
                'clauses': all_partially_covered_clauses
            },
            
            # Summary Statistics
            'summary': {
                'total_articles': len(all_article_numbers),
                'covered_articles': len(all_article_numbers) - overall_score_info['missing_count'],
                'missing_articles': overall_score_info['missing_count'],
                'total_items_missing': overall_score_info['missing_count'] + len(all_missing_clauses),
                'articles_not_found': overall_score_info['missing_count'],
                'clauses_not_found': len(all_missing_clauses),
                'clauses_partially_covered': len(all_partially_covered_clauses)
            }
        }
        
    except HTTPException:
        print(f"[ERROR] HTTPException in comprehensive analysis")
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        raise
    except Exception as e:
        # Better error logging with full details
        import traceback
        error_traceback = traceback.format_exc()
        
        print("=" * 80)
        print("[ERROR] Comprehensive analysis failed!")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"Error Args: {e.args}")
        if hasattr(e, 'errno'):
            print(f"Error Number: {e.errno}")
        if hasattr(e, 'strerror'):
            print(f"Error String: {e.strerror}")
        if hasattr(e, 'filename'):
            print(f"Error Filename: {e.filename}")
        print("\nFull Traceback:")
        print(error_traceback)
        print("=" * 80)
        
        # Cleanup
        try:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
                print(f"[CLEANUP] Removed file: {filepath}")
        except Exception as cleanup_error:
            print(f"[CLEANUP ERROR] Failed to remove file: {cleanup_error}")
        
        # Return detailed error to user
        raise HTTPException(
            status_code=500, 
            detail=f"Error: {str(e)} | Type: {type(e).__name__} | Check server logs for details"
        )

