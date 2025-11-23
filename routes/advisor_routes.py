"""Advisor endpoint - AI compliance advisor with article-by-article analysis"""
import os
import time
import re
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from functools import wraps

from config import UPLOAD_FOLDER, MAX_FILE_SIZE
from utils.file_utils import allowed_file, get_cached_pdpl_articles, sanitize_filename
from utils.scoring_utils import calculate_overall_score
from services.pdf_service import extract_text_simple
from services.matching_service import match_with_pdpl
from services.llm_service import llm_generate_recommendation
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
                'llm_used': True
            }
        return result
    return wrapper


@router.post("/advisor")
@monitor_performance
async def compliance_advisor(
    file: UploadFile = File(...)
):
    """
    LLM-Powered Compliance Advisor with Article-by-Article Analysis.
    
    This endpoint:
    1. Uses Hybrid BM25 → E5 retrieval + LLM clause matching (same as /score_hybrid_llm)
    2. For each article scoring ≥80%: Confirms policy covers this article
    3. For each article scoring <80%: Generates LLM-powered recommendations to improve coverage
    
    Returns detailed article analysis with coverage status and actionable recommendations.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    if not model_manager.llm_enabled:
        raise HTTPException(status_code=503, detail="LLM Compliance Advisor is not available. LLM model failed to load.")
    
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
        
        # Extract text from PDF
        extracted_text = extract_text_simple(filepath)
        full_text = " ".join(page["text"] for page in extracted_text)
        
        # Force enable LLM for this request (same as score_hybrid_llm)
        original_clause_matching = model_manager.llm_clause_matching
        original_reranking = model_manager.llm_reranking
        
        model_manager.llm_clause_matching = True
        model_manager.llm_reranking = True
        
        try:
            # Match with PDPL using HYBRID + LLM (same as score_hybrid_llm)
            pdpl_articles = get_cached_pdpl_articles()
            matches = match_with_pdpl(
                extracted_text,
                pdpl_articles,
                threshold=0.5,
                top_k=15,
                use_text_fallback=False,
                use_llm_rerank=False,  # Use E5 ranking only
            )
            
            # Calculate overall score
            all_article_numbers = sorted(list(set(a.get('article_number') for a in pdpl_articles if a.get('article_number'))))
            overall_score_info = calculate_overall_score(matches, total_articles=len(all_article_numbers), all_article_numbers=all_article_numbers)
            
            # Define target articles (same as score_hybrid_llm)
            TARGET_ARTICLES = {4, 5, 10, 11, 12, 13, 15, 20, 25, 26, 29}
            
            # Analyze each article and generate recommendations for those below 80%
            article_analysis = []
            covered_articles = []
            needs_improvement_articles = []
            
            COVERAGE_THRESHOLD = 75.0  # 75% threshold
            
            for match in matches:
                article_num = match.get('article_number', 0)
                
                # Only analyze target articles
                if article_num not in TARGET_ARTICLES:
                    continue
                
                article_title = match.get('article_title', '')
                coverage_percentage = match.get('coverage_percentage', 0)
                coverage_band = match.get('coverage_band', '')
                missing_clauses = match.get('missing_clauses', [])
                partially_covered_clauses = match.get('partially_covered_clauses', [])
                covered_clauses = match.get('covered_clauses', [])
                
                article_info = {
                    'article_number': article_num,
                    'article_title': article_title,
                    'coverage_percentage': coverage_percentage,
                    'coverage_band': coverage_band,
                    'covered_clauses_count': len(covered_clauses),
                    'partially_covered_clauses_count': len(partially_covered_clauses),
                    'missing_clauses_count': len(missing_clauses)
                }
                
                # Check if coverage is above or below 80%
                if coverage_percentage >= COVERAGE_THRESHOLD:
                    article_info['status'] = 'covered'
                    article_info['message'] = f"✓ Your policy adequately covers Article {article_num}: {article_title}"
                    article_info['recommendation'] = None
                    covered_articles.append(article_num)
                else:
                    article_info['status'] = 'needs_improvement'
                    article_info['message'] = f"Article {article_num} needs improvement"
                    
                    # Generate LLM recommendation
                    print(f"[ADVISOR] Generating recommendation for Article {article_num} ({coverage_percentage:.0f}% coverage)")
                    recommendation = llm_generate_recommendation(
                        article_number=article_num,
                        article_title=article_title,
                        coverage_percentage=coverage_percentage,
                        missing_clauses=missing_clauses,
                        partially_covered_clauses=partially_covered_clauses,
                        pdf_text=full_text  # Pass full text for better context extraction
                    )
                    article_info['recommendation'] = recommendation
                    needs_improvement_articles.append(article_num)
                
                # Add clause details for reference
                article_info['covered_clauses'] = [
                    {'label': c.get('label', ''), 'score': c.get('coverage_score', 0)}
                    for c in covered_clauses[:3]  # Top 3
                ]
                article_info['missing_clauses'] = [
                    {'label': c.get('label', ''), 'text': c.get('text', '')[:150]}
                    for c in missing_clauses[:3]  # Top 3
                ]
                article_info['partially_covered_clauses'] = [
                    {'label': c.get('label', ''), 'text': c.get('text', '')[:150], 'score': c.get('coverage_score', 0)}
                    for c in partially_covered_clauses[:3]  # Top 3
                ]
                
                article_analysis.append(article_info)
            
            # Sort: needs improvement first, then by article number
            article_analysis.sort(key=lambda x: (x['status'] == 'covered', x['article_number']))
            
        finally:
            # Restore original settings
            model_manager.llm_clause_matching = original_clause_matching
            model_manager.llm_reranking = original_reranking
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'filename': original_filename,
            'analysis_method': 'Hybrid BM25 → E5 + LLM Clause Matching',
            'coverage_threshold': COVERAGE_THRESHOLD,
            'summary': {
                'overall_score': round(overall_score_info['overall_score'], 2),
                'compliance_level': overall_score_info['compliance_level'],
                'total_articles_analyzed': len(article_analysis),
                'covered_articles_count': len(covered_articles),
                'needs_improvement_count': len(needs_improvement_articles),
                'covered_articles': sorted(covered_articles),
                'needs_improvement_articles': sorted(needs_improvement_articles),
                'total_articles': overall_score_info.get('total_articles', 0),
                'articles_found': overall_score_info.get('articles_analyzed', 0),
                'articles_missing': overall_score_info.get('missing_count', 0)
            },
            'articles': article_analysis,
            'metadata': {
                'analysis_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'target_articles': sorted(list(TARGET_ARTICLES)),
                'coverage_threshold_percentage': COVERAGE_THRESHOLD
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

