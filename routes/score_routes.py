"""Score endpoints - Compliance scoring with and without LLM"""
import os
import time
from typing import List, Dict
from fastapi import APIRouter, File, UploadFile, HTTPException
from functools import wraps

from config import UPLOAD_FOLDER, MAX_FILE_SIZE
from utils.file_utils import allowed_file, get_cached_pdpl_articles, sanitize_filename
from utils.scoring_utils import calculate_overall_score
from utils.text_utils import normalize_text
from services.pdf_service import extract_text_simple
from services.matching_service import match_with_pdpl, match_with_pdpl_llm_only
from models import model_manager

router = APIRouter()


# PDPL marker list for relevance checking
PDPL_MARKERS = [
    "pdpl", "saudi", "kingdom", "ksa",
    "personal data protection law", "personal data protection regulation",
    "privacy policy", "third party", "data breach", "data subject",
    "data controller", "personal information", "data processing",
    "international data transfer", "data disclosure",
]
MINIMUM_MARKERS_REQUIRED = 5


def check_pdpl_relevance(extracted_text: List[Dict[str, str]]) -> int:
    """Check how many PDPL/privacy markers are present in the text"""
    full_text = " ".join(page["text"] for page in extracted_text)
    full_text_normalized = normalize_text(full_text)
    return sum(1 for m in set(PDPL_MARKERS) if m in full_text_normalized)


# Performance monitoring decorator
def monitor_performance(func):
    """Decorator to monitor endpoint performance"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        elapsed_time = time.time() - start_time
        
        # Add performance info to result if it's a dict
        if isinstance(result, dict):
            result['performance'] = {
                'elapsed_time_seconds': round(elapsed_time, 2),
                'llm_used': model_manager.llm_enabled and (model_manager.llm_clause_matching or model_manager.llm_reranking)
            }
        return result
    return wrapper


@router.post("/score")
@monitor_performance
async def get_score_only(file: UploadFile = File(...)):
    """
    Score Only - Returns overall compliance score without detailed matches.
    
    Quick endpoint to get compliance score (0-100) and level.
    
    Returns:
        JSON with overall_score, compliance_level, and summary statistics
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
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text
        extracted_text = extract_text_simple(filepath)
        
        # PDPL relevance gate - check for minimum markers
        # COMMENTED OUT FOR TESTING - allows documents with few PDPL markers to be scored
        # pdpl_marker_hits_count = check_pdpl_relevance(extracted_text)
        
        # if pdpl_marker_hits_count < MINIMUM_MARKERS_REQUIRED:
        #     pdpl_articles = get_cached_pdpl_articles()
        #     all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
            
        #     if os.path.exists(filepath):
        #         os.remove(filepath)
            
        #     return {
        #         'success': True,
        #         'missing_articles': {'count': len(all_article_numbers), 'article_numbers': all_article_numbers},
        #         'missing_clauses': {'count': 0, 'clauses': []},
        #         'partially_covered_clauses': {'count': 0, 'clauses': []},
        #         'summary': {
        #             'filename': original_filename,
        #             'overall_score': 0.0,
        #             'compliance_level': 'not_compliant',
        #             'total_articles': len(all_article_numbers),
        #             'articles_found': 0,
        #             'articles_found_list': [],
        #             'articles_missing': len(all_article_numbers),
        #             'articles_missing_list': all_article_numbers,
        #             'covered': 0,
        #             'covered_list': [],
        #             'partially_covered': 0,
        #             'partially_covered_list': [],
        #             'low_coverage': 0,
        #             'low_coverage_list': [],
        #             'average_coverage': 0.0
        #         },
        #         'rejection_reason': f'Policy has only {pdpl_marker_hits_count} privacy markers (need 5+)'
        #     }
        
        # Match with PDPL (cached for performance)
        pdpl_articles = get_cached_pdpl_articles()
        matches = match_with_pdpl(extracted_text, pdpl_articles, threshold=0.5, top_k=15)
        
        # Calculate score
        all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
        overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
        
        # Collect missing clauses and partially covered clauses
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
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
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
                'filename': original_filename,
                'overall_score': overall_score_info['overall_score'],
                'compliance_level': overall_score_info['compliance_level'],
                'total_articles': overall_score_info['total_articles'],
                'articles_found': overall_score_info['articles_analyzed'],
                'articles_found_list': sorted([m.get('article_number') for m in matches if m.get('article_number')]),
                'articles_missing': overall_score_info['missing_count'],
                'articles_missing_list': overall_score_info['missing_articles'],
                'covered': overall_score_info['covered_count'],
                'covered_list': overall_score_info['covered_articles'],
                'partially_covered': overall_score_info['partially_covered_count'],
                'partially_covered_list': overall_score_info['partially_covered_articles'],
                'low_coverage': overall_score_info['low_coverage_count'],
                'low_coverage_list': overall_score_info['low_coverage_articles'],
                'average_coverage': overall_score_info['average_article_coverage']
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


@router.post("/score_hybrid_llm")
@monitor_performance
async def get_score_hybrid_llm(file: UploadFile = File(...)):
    """
    Score with Hybrid + LLM - The most advanced endpoint combining:
    1. Hybrid BM25 → E5 retrieval (best article matching)
    2. LLM-powered clause analysis (most accurate coverage scoring)
    
    This is the PREMIUM endpoint - slowest but most accurate.
    Use this when you need the highest quality compliance analysis.
    
    Returns:
        JSON with overall_score, compliance_level, detailed matches, and LLM explanations
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    if not model_manager.llm_enabled:
        raise HTTPException(
            status_code=503,
            detail="LLM is not available. Use /score endpoint instead."
        )
    
    # Sanitize filename to prevent path traversal and invalid characters
    original_filename = file.filename
    filename = sanitize_filename(original_filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Read and save file
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text
        extracted_text = extract_text_simple(filepath)

        # --------------------------------------------------
        # PDPL relevance gate (align with /test/hybrid logic)
        # --------------------------------------------------
        full_text = " ".join(page["text"] for page in extracted_text)
        full_text_normalized = normalize_text(full_text)

        pdpl_markers = [
            "pdpl",
            "saudi",
            "kingdom",
            "ksa",
            "personal data protection law",
            "personal data protection regulation",
            "privacy policy",
            "third party",
            "data breach",
            "data subject",
            "data controller",
            "personal information",
            "data processing",
            "international data transfer",
            "data disclosure",
        ]
        # Count unique marker hits (avoid counting duplicates)
        pdpl_marker_hits_count = sum(1 for m in set(pdpl_markers) if m in full_text_normalized)
        pdpl_marker_hits = [m for m in pdpl_markers if m in full_text_normalized]

        # If the policy has less than 5 PDPL/privacy markers, short‑circuit:
        # treat as non‑PDPL and skip expensive hybrid + LLM scoring.
        # COMMENTED OUT FOR TESTING - allows documents with few PDPL markers to be scored
        # if pdpl_marker_hits_count < 5:
        #     pdpl_articles = get_cached_pdpl_articles()
        #     all_article_numbers = sorted(
        #         list(
        #             set(
        #                 a.get("article_number")
        #                 for a in pdpl_articles
        #                 if a.get("article_number")
        #             )
        #         )
        #     )
        #     total_articles = len(all_article_numbers)

        #     # Clean up file before returning
        #     if os.path.exists(filepath):
        #         os.remove(filepath)

        #     return {
        #         "success": True,
        #         "filename": original_filename,
        #         "overall_score": 0.0,
        #         "compliance_level": "not_compliant",
        #         "retrieval_method": "Hybrid BM25 → E5-small (skipped: policy has no PDPL/Saudi markers)",
        #         "llm_used": False,
        #         "analysis_method": "Skipped hybrid + LLM scoring for non-PDPL-looking policy",
        #         "pdpl_marker_hits": [],
        #         "missing_articles": {
        #             "count": total_articles,
        #             "article_numbers": all_article_numbers,
        #         },
        #         "missing_clauses": {"count": 0, "clauses": []},
        #         "partially_covered_clauses": {"count": 0, "clauses": []},
        #         "detailed_matches": [],
        #         "summary": {
        #             "total_articles": total_articles,
        #             "articles_found": 0,
        #             "articles_missing": total_articles,
        #             "covered": 0,
        #             "partially_covered": 0,
        #             "low_coverage": 0,
        #             "average_coverage": 0.0,
        #         },
        #     }

        # Force enable LLM for this request
        original_clause_matching = model_manager.llm_clause_matching
        original_reranking = model_manager.llm_reranking
        
        model_manager.llm_clause_matching = True
        model_manager.llm_reranking = True
        
        try:
            # Match with PDPL using HYBRID + LLM
            pdpl_articles = get_cached_pdpl_articles()
            # Hybrid retrieval: BM25 + E5 (no LLM re-ranking for faster processing)
            matches = match_with_pdpl(
                extracted_text,
                pdpl_articles,
                threshold=0.5,
                top_k=15,
                use_text_fallback=False,
                use_llm_rerank=False,  # ❌ Disabled - use E5 ranking only
            )
            
            # Calculate score
            all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
            overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
        finally:
            # Restore original settings
            model_manager.llm_clause_matching = original_clause_matching
            model_manager.llm_reranking = original_reranking
        
        # Filter results to only target articles for output
        TARGET_ARTICLES = {4, 5, 10, 11, 12, 13, 15, 20, 25, 26, 29}
        
        # Collect detailed match information
        detailed_matches = []
        all_missing_clauses = []
        all_partially_covered_clauses = []
        
        for match in matches:
            article_num = match.get('article_number', 0)
            
            # Only include target articles in output
            if article_num not in TARGET_ARTICLES:
                continue
            
            # Add detailed match info
            detailed_matches.append({
                'article_number': article_num,
                'article_title': match.get('article_title', ''),
                'similarity_score': match.get('similarity', 0),
                'coverage_percentage': match.get('coverage_percentage', 0),
                'coverage_band': match.get('coverage_band', ''),
                'retrieval_method': 'Hybrid BM25 → E5-small + LLM',
                'covered_clauses': match.get('covered_clauses', []),
                'partially_covered_clauses': match.get('partially_covered_clauses', []),
                'missing_clauses': match.get('missing_clauses', [])
            })
            
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
        
        return {
            'success': True,
            'retrieval_method': 'Hybrid BM25 → E5-small (two-stage)',
            'llm_used': True,
            'analysis_method': 'LLM-powered clause matching',
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
            'detailed_matches': detailed_matches,
            'summary': {
                'filename': original_filename,
                'overall_score': overall_score_info['overall_score'],
                'compliance_level': overall_score_info['compliance_level'],
                'total_articles': overall_score_info['total_articles'],
                'articles_found': overall_score_info['articles_analyzed'],
                'articles_found_list': sorted([m.get('article_number') for m in detailed_matches if m.get('article_number')]),
                'articles_missing': overall_score_info['missing_count'],
                'articles_missing_list': overall_score_info['missing_articles'],
                'covered': overall_score_info['covered_count'],
                'covered_list': overall_score_info['covered_articles'],
                'partially_covered': overall_score_info['partially_covered_count'],
                'partially_covered_list': overall_score_info['partially_covered_articles'],
                'low_coverage': overall_score_info['low_coverage_count'],
                'low_coverage_list': overall_score_info['low_coverage_articles'],
                'average_coverage': overall_score_info['average_article_coverage']
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


@router.post("/score_llm_only")
@monitor_performance
async def get_score_llm_only(file: UploadFile = File(...)):
    """
    Score with LLM ONLY - 100% LLM scoring, NO traditional/semantic.
    
    This endpoint uses PURE LLM scoring:
    - 100% weight on LLM analysis
    - 0% weight on keyword/similarity
    - No boost factor applied
    - Raw LLM scores only
    
    Use this to see what LLM thinks without any traditional scoring influence.
    Compare with /score_no_llm to see the difference.
    
    Returns:
        JSON with overall_score, compliance_level, and summary statistics
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    if not model_manager.llm_enabled:
        raise HTTPException(
            status_code=503,
            detail="LLM is not available. Use /score_no_llm endpoint instead."
        )
    
    # Sanitize filename to prevent path traversal and invalid characters
    original_filename = file.filename
    filename = sanitize_filename(original_filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Read and save file
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text
        extracted_text = extract_text_simple(filepath)
        
        # TEMPORARILY modify scoring to use 100% LLM
        # We'll do this by setting a special flag
        import utils.scoring_utils as scoring_utils
        original_llm_weight = getattr(scoring_utils, '_llm_only_mode', False)
        scoring_utils._llm_only_mode = True
        
        # Force enable LLM for this request
        original_clause_matching = model_manager.llm_clause_matching
        original_reranking = model_manager.llm_reranking
        
        model_manager.llm_clause_matching = True
        model_manager.llm_reranking = True
        
        try:
            # Match with PDPL using LLM ONLY (no BM25, no E5, no text retrieval)
            pdpl_articles = get_cached_pdpl_articles()
            matches = match_with_pdpl_llm_only(extracted_text, pdpl_articles)
            
            # Calculate score
            all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
            overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
        finally:
            # Restore original settings
            model_manager.llm_clause_matching = original_clause_matching
            model_manager.llm_reranking = original_reranking
            scoring_utils._llm_only_mode = original_llm_weight
        
        # Collect missing clauses and partially covered clauses
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
                    'text': clause.get('text', ''),
                    'debug_scores': clause.get('debug_scores', None)
                })
            
            for clause in match.get('partially_covered_clauses', []):
                all_partially_covered_clauses.append({
                    'article_number': article_num,
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 0),
                    'band': 'Partial',
                    'partial_reason': clause.get('partial_reason', ''),
                    'llm_explanation': clause.get('llm_explanation', ''),
                    'text': clause.get('text', ''),
                    'debug_scores': clause.get('debug_scores', None)
                })
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'llm_used': True,
            'llm_weight': '100%',
            'traditional_weight': '0%',
            'analysis_method': 'Pure LLM scoring (100% LLM, no traditional)',
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
                'filename': original_filename,
                'overall_score': overall_score_info['overall_score'],
                'compliance_level': overall_score_info['compliance_level'],
                'total_articles': overall_score_info['total_articles'],
                'articles_found': overall_score_info['articles_analyzed'],
                'articles_found_list': sorted([m.get('article_number') for m in matches if m.get('article_number')]),
                'articles_missing': overall_score_info['missing_count'],
                'articles_missing_list': overall_score_info['missing_articles'],
                'covered': overall_score_info['covered_count'],
                'covered_list': overall_score_info['covered_articles'],
                'partially_covered': overall_score_info['partially_covered_count'],
                'partially_covered_list': overall_score_info['partially_covered_articles'],
                'low_coverage': overall_score_info['low_coverage_count'],
                'low_coverage_list': overall_score_info['low_coverage_articles'],
                'average_coverage': overall_score_info['average_article_coverage']
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


@router.post("/score_no_llm")
@monitor_performance
async def get_score_no_llm(file: UploadFile = File(...)):
    """
    Score WITHOUT LLM - Pure semantic/traditional scoring only.
    
    This endpoint DISABLES LLM completely and uses only:
    - Keyword overlap
    - Sequence similarity
    - 1.5x boost factor
    - 40% minimum floor
    
    Use this to compare against LLM-powered scoring and see if LLM is helping or hurting.
    
    Returns:
        JSON with overall_score, compliance_level, and summary statistics
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
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text
        extracted_text = extract_text_simple(filepath)
        
        # FORCE DISABLE LLM for this request
        original_clause_matching = model_manager.llm_clause_matching
        original_reranking = model_manager.llm_reranking
        
        model_manager.llm_clause_matching = False
        model_manager.llm_reranking = False
        
        try:
            # Match with PDPL using SEMANTIC ONLY (no LLM)
            pdpl_articles = get_cached_pdpl_articles()
            matches = match_with_pdpl(extracted_text, pdpl_articles, threshold=0.5, top_k=15)
            
            # Calculate score
            all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
            overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
        finally:
            # Restore original settings
            model_manager.llm_clause_matching = original_clause_matching
            model_manager.llm_reranking = original_reranking
        
        # Collect missing clauses and partially covered clauses
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
                    'text': clause.get('text', ''),
                    'debug_scores': clause.get('debug_scores', None)
                })
            
            for clause in match.get('partially_covered_clauses', []):
                all_partially_covered_clauses.append({
                    'article_number': article_num,
                    'label': clause.get('label', ''),
                    'coverage_score': clause.get('coverage_score', 0),
                    'band': 'Partial',
                    'partial_reason': clause.get('partial_reason', ''),
                    'text': clause.get('text', ''),
                    'debug_scores': clause.get('debug_scores', None)
                })
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'llm_used': False,
            'analysis_method': 'Pure semantic (keyword + similarity) with 1.5x boost',
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
                'filename': original_filename,
                'overall_score': overall_score_info['overall_score'],
                'compliance_level': overall_score_info['compliance_level'],
                'total_articles': overall_score_info['total_articles'],
                'articles_found': overall_score_info['articles_analyzed'],
                'articles_found_list': sorted([m.get('article_number') for m in matches if m.get('article_number')]),
                'articles_missing': overall_score_info['missing_count'],
                'articles_missing_list': overall_score_info['missing_articles'],
                'covered': overall_score_info['covered_count'],
                'covered_list': overall_score_info['covered_articles'],
                'partially_covered': overall_score_info['partially_covered_count'],
                'partially_covered_list': overall_score_info['partially_covered_articles'],
                'low_coverage': overall_score_info['low_coverage_count'],
                'low_coverage_list': overall_score_info['low_coverage_articles'],
                'average_coverage': overall_score_info['average_article_coverage']
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


@router.post("/score_llm")
@monitor_performance
async def get_score_with_llm(file: UploadFile = File(...)):
    """
    Score with LLM - Returns compliance score WITH LLM-powered clause matching.
    
    This endpoint uses the LLM for detailed clause-level analysis (SLOW on CPU, 60-120s).
    Compare with /score endpoint (fast, 5-10s) to see the difference.
    
    Returns:
        JSON with overall_score, compliance_level, and summary statistics
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    if not model_manager.llm_enabled:
        raise HTTPException(
            status_code=503,
            detail="LLM is not available. Use /score endpoint instead."
        )
    
    # Sanitize filename to prevent path traversal and invalid characters
    original_filename = file.filename
    filename = sanitize_filename(original_filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Read and save file
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text
        extracted_text = extract_text_simple(filepath)
        
        # Force enable LLM for this request
        original_clause_matching = model_manager.llm_clause_matching
        original_reranking = model_manager.llm_reranking
        
        model_manager.llm_clause_matching = True
        model_manager.llm_reranking = True
        
        try:
            # Match with PDPL using LLM
            pdpl_articles = get_cached_pdpl_articles()
            matches = match_with_pdpl(extracted_text, pdpl_articles, threshold=0.5, top_k=15)
            
            # Calculate score
            all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
            overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
        finally:
            # Restore original settings
            model_manager.llm_clause_matching = original_clause_matching
            model_manager.llm_reranking = original_reranking
        
        # Collect missing clauses and partially covered clauses
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
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'llm_used': True,
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
                'filename': original_filename,
                'overall_score': overall_score_info['overall_score'],
                'compliance_level': overall_score_info['compliance_level'],
                'total_articles': overall_score_info['total_articles'],
                'articles_found': overall_score_info['articles_analyzed'],
                'articles_found_list': sorted([m.get('article_number') for m in matches if m.get('article_number')]),
                'articles_missing': overall_score_info['missing_count'],
                'articles_missing_list': overall_score_info['missing_articles'],
                'covered': overall_score_info['covered_count'],
                'covered_list': overall_score_info['covered_articles'],
                'partially_covered': overall_score_info['partially_covered_count'],
                'partially_covered_list': overall_score_info['partially_covered_articles'],
                'low_coverage': overall_score_info['low_coverage_count'],
                'low_coverage_list': overall_score_info['low_coverage_articles'],
                'average_coverage': overall_score_info['average_article_coverage']
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

