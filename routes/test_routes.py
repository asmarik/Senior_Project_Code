"""Test endpoints - OCR, RAG, and Hybrid retrieval testing"""
import os
from fastapi import APIRouter, File, UploadFile, HTTPException

from config import UPLOAD_FOLDER, MAX_FILE_SIZE
from utils.file_utils import allowed_file
from utils.text_utils import normalize_text, calculate_keyword_overlap
from services.pdf_service import extract_text_from_pdf, extract_text_simple
from services.retrieval_service import hybrid_retrieval_bm25_e5, semantic_search_pdpl

router = APIRouter()


@router.post("/ocr")
async def test_ocr(file: UploadFile = File(...)):
    """
    Test OCR/Text extraction only - Extract text from PDF without matching.
    
    Returns:
        JSON response with extracted text only (no PDPL matching)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    filename = file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Read and save file
        contents = await file.read()
        
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds maximum {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text
        extracted_text = extract_text_from_pdf(filepath)
        
        # Calculate statistics
        total_chars = sum(p['character_count'] for p in extracted_text)
        total_words = sum(p['word_count'] for p in extracted_text)
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'filename': filename,
            'total_pages': len(extracted_text),
            'total_characters': total_chars,
            'total_words': total_words,
            'pages': extracted_text,
            'message': 'Text extraction completed successfully'
        }
        
    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@router.post("/hybrid")
async def test_hybrid(file: UploadFile = File(...)):
    """
    Test Hybrid BM25 → E5 Retrieval - Show the two-stage retrieval process.
    
    Step 1: BM25 retrieves top-200 candidates (keyword-based)
    Step 2: E5-small re-ranks those 200 to top-20 (semantic)
    
    Returns:
        JSON response with hybrid retrieval results
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    filename = file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Read and save file
        contents = await file.read()
        
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds maximum {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text
        extracted_text = extract_text_simple(filepath)
        
        # Combine all text for hybrid retrieval
        full_text = ' '.join([page['text'] for page in extracted_text])
        full_text_normalized = normalize_text(full_text)
        
        # Perform HYBRID BM25 → E5 retrieval
        hybrid_matches = hybrid_retrieval_bm25_e5(
            full_text,
            top_k_bm25=200,
            top_k_final=20,
        )

        # --- Score calibration for debugging endpoint ---
        # E5 cosine scores are typically "compressed" in the 0.80–0.85 range,
        # which makes irrelevant PDFs *look* highly similar.
        # For this /test/hybrid endpoint we:
        #   1) Use a stricter absolute floor (0.80) in line with main matching.
        #   2) If even the *best* score is below 0.80, treat the whole PDF as "no strong match".
        #   3) Keep only articles above the floor and expose summary statistics.
        filtered_matches = []
        rejected_matches = []

        # Quick sanity check: does the policy even look PDPL / Saudi-specific?
        # If none of these markers appear, we treat the policy as "non-PDPL" for this
        # *testing* endpoint and suppress all matches, even if the raw scores are high.
        pdpl_markers = [
            "pdpl",
            "saudi",
            "kingdom",
            "ksa",
            "personal data protection law",
            "personal data protection regulation",
            "privacy policy",
            "policy", 
            "notice",
            "third party",
            "breach",
            "data",
            "data controller",
            "personal",
            "information",
            "data processing",
            "international data transfer",
            "data disclosure",
            "transfer",
        ]
        # Count unique marker hits (avoid counting duplicates)
        pdpl_marker_hits = sum(1 for m in set(pdpl_markers) if m in full_text_normalized)

        if hybrid_matches:
            similarities = [m.get('similarity', 0.0) for m in hybrid_matches]
            max_similarity = max(similarities)
            min_similarity = min(similarities)
            avg_similarity = sum(similarities) / len(similarities)

            # Thresholds for this *testing* endpoint
            ABS_MIN_SIMILARITY = 0.80  # Align with core pipeline threshold
            MIN_KEYWORD_OVERLAP = 0.15  # Require at least some lexical overlap

            # If the policy appears non-PDPL (less than 5 markers), force all matches to rejected
            # COMMENTED OUT FOR TESTING - allows documents with few PDPL markers to be scored
            # if pdpl_marker_hits <= 5:
            #     for match, sim in zip(hybrid_matches, similarities):
            #         rejected_matches.append({
            #             'article_number': match['article'].get('article_number', '?'),
            #             'similarity': sim,
            #             'keyword_overlap': None,
            #             'reason': (
            #                 'Policy text contains no PDPL/Saudi markers; '
            #                 'treating hybrid scores as noise for this test endpoint.'
            #             )
            #         })
            #     filtered_matches = []
            # Else, apply score-based filters
            if max_similarity < ABS_MIN_SIMILARITY:
                for match, sim in zip(hybrid_matches, similarities):
                    rejected_matches.append({
                        'article_number': match['article'].get('article_number', '?'),
                        'similarity': sim,
                        'keyword_overlap': None,
                        'reason': (
                            f'All scores below absolute minimum '
                            f'({max_similarity:.3f} < {ABS_MIN_SIMILARITY}) – '
                            'policy likely not PDPL-specific.'
                        )
                    })
                filtered_matches = []
            else:
                # Normal case: apply BOTH similarity floor AND keyword-overlap floor
                for match in hybrid_matches:
                    article = match['article']
                    similarity = match.get('similarity', 0.0)
                    article_text = article.get('text', '') or ''
                    article_text_normalized = normalize_text(article_text)

                    # Keyword overlap between policy and the PDPL article
                    keyword_overlap = calculate_keyword_overlap(
                        article_text_normalized,
                        full_text_normalized,
                    )

                    if similarity >= ABS_MIN_SIMILARITY and keyword_overlap >= MIN_KEYWORD_OVERLAP:
                        enriched_match = dict(match)
                        enriched_match['keyword_overlap'] = keyword_overlap
                        filtered_matches.append(enriched_match)
                    else:
                        rejected_matches.append({
                            'article_number': article.get('article_number', '?'),
                            'similarity': similarity,
                            'keyword_overlap': keyword_overlap,
                            'reason': (
                                f'Rejected by hybrid filter: '
                                f'sim={similarity:.3f} (min {ABS_MIN_SIMILARITY}), '
                                f'overlap={keyword_overlap:.3f} (min {MIN_KEYWORD_OVERLAP})'
                            )
                        })
        else:
            max_similarity = None
            min_similarity = None
            avg_similarity = None
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'filename': filename,
            'total_pages': len(extracted_text),
            'extracted_text_preview': full_text[:500] + '...' if len(full_text) > 500 else full_text,
            'total_characters': len(full_text),
            'hybrid_matches': filtered_matches,
            'total_hybrid_matches': len(filtered_matches),
            'filtered_out_count': len(rejected_matches),
            'filtered_out_articles': rejected_matches[:10],  # Show first 10 rejected
            'max_similarity': max_similarity,
            'min_similarity': min_similarity,
            'avg_similarity': avg_similarity,
            'absolute_minimum_similarity_threshold': 0.80,
            'minimum_keyword_overlap_threshold': 0.15,
            'retrieval_method': 'BM25 → top-200, then E5-small re-rank → top-20, filtered at 0.80',
            'message': (
                f'Hybrid retrieval completed: {len(filtered_matches)} passed strict filter, '
                f'{len(rejected_matches)} rejected. '
                'If max_similarity < 0.80, the PDF is treated as having no strong PDPL matches. '
                'Matches must also show a minimum level of keyword overlap with the PDPL article.'
            ),
            'note': (
                'E5 scores are numerically high for most texts (often 0.80–0.85). '
                'This endpoint applies a stricter 0.80 floor AND a keyword-overlap filter to avoid '
                'showing irrelevant PDFs as strongly matched; the main scoring pipeline uses '
                'additional LLM-based checks.'
            )
        }
        
    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@router.post("/rag")
async def test_rag(file: UploadFile = File(...)):
    """
    Test RAG/Semantic Search only (E5-small) - Extract text and show semantic matches.
    
    Returns:
        JSON response with semantic search results only
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    filename = file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Read and save file
        contents = await file.read()
        
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds maximum {MAX_FILE_SIZE / (1024*1024)}MB")
        
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Extract text
        extracted_text = extract_text_simple(filepath)
        
        # Combine all text for semantic search
        full_text = ' '.join([page['text'] for page in extracted_text])
        
        # Perform semantic search
        semantic_matches = semantic_search_pdpl(full_text, top_k=20)
        
        # Filter by minimum similarity (0.70) - E5 scores are compressed (0.80-0.85 for everything)
        MINIMUM_SIMILARITY = 0.70  # Lowered from 0.88 - even relevant PDFs score 0.82-0.83
        filtered_matches = []
        rejected_matches = []
        
        for match in semantic_matches:
            similarity = match.get('similarity', match.get('vector_score', 0))
            if similarity >= MINIMUM_SIMILARITY:
                filtered_matches.append(match)
            else:
                rejected_matches.append({
                    'article_number': match['article'].get('article_number', '?'),
                    'similarity': similarity,
                    'reason': f'Below threshold ({similarity:.3f} < {MINIMUM_SIMILARITY})'
                })
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return {
            'success': True,
            'filename': filename,
            'total_pages': len(extracted_text),
            'extracted_text_preview': full_text[:500] + '...' if len(full_text) > 500 else full_text,
            'semantic_matches': filtered_matches,
            'total_semantic_matches': len(filtered_matches),
            'filtered_out_count': len(rejected_matches),
            'filtered_out_articles': rejected_matches[:10],  # Show first 10 rejected
            'minimum_similarity_threshold': MINIMUM_SIMILARITY,
            'message': f'Semantic search completed: {len(filtered_matches)} passed filter, {len(rejected_matches)} rejected',
            'note': 'Uses E5-small-v2 embeddings. Only articles with ≥70% similarity shown. LLM does final filtering.'
        }
        
    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

