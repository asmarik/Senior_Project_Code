"""PDPL matching services"""
from typing import List, Dict, Any
from utils.text_utils import normalize_text, similarity_score, calculate_keyword_overlap
from utils.scoring_utils import calculate_article_coverage
from .retrieval_service import hybrid_retrieval_bm25_e5
from .llm_service import llm_clause_match

# Articles that were previously treated as regulator-only.
# User now wants ALL articles (including 35, 36, 40, 42) to be eligible,
# so this set is kept for reference but left empty.
GOV_ONLY_ARTICLES = set()


def match_with_pdpl_text(
    extracted_text: List[Dict[str, str]],
    pdpl_articles: List[Dict[str, Any]],
    threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Match extracted text with PDPL articles using text similarity.
    Returns list of matched articles with similarity scores.
    """
    matches: List[Dict[str, Any]] = []

    # Combine all extracted text from all pages
    full_text = " ".join([page["text"] for page in extracted_text])
    full_text_normalized = normalize_text(full_text)

    for article in pdpl_articles:
        if not article.get("text"):
            continue

        article_text = article["text"]
        article_text_normalized = normalize_text(article_text)

        # Calculate similarity
        sim = similarity_score(full_text_normalized, article_text_normalized)

        # Check for partial matches
        partial_match = (
            article_text_normalized in full_text_normalized
            or full_text_normalized in article_text_normalized
        )

        # Check for keyword overlap
        keyword_overlap = calculate_keyword_overlap(
            article_text_normalized, full_text_normalized
        )

        # Final score combines similarity and keyword overlap
        if sim >= 0.95 and keyword_overlap >= 0.95:
            final_score = 1.0
        elif keyword_overlap >= 0.99:
            final_score = max(sim, 0.95)
        else:
            final_score = max(sim, keyword_overlap * 0.9)

        if final_score >= threshold or partial_match:
            matches.append(
                {
                    "article": article,
                    "similarity": final_score,
                    "match_type": "text" if sim >= threshold else "partial",
                    "keyword_overlap": keyword_overlap,
                }
            )

    # Sort by similarity score (highest first)
    matches.sort(key=lambda x: x["similarity"], reverse=True)

    return matches


def match_with_pdpl(
    extracted_text: List[Dict[str, str]],
    pdpl_articles: List[Dict[str, Any]],
    threshold: float = 0.4,
    top_k: int = 10,
    *,
    use_text_fallback: bool = True,
    use_llm_rerank: bool = True,
) -> List[Dict[str, Any]]:
    """
    Match extracted text with PDPL articles using both semantic search (RAG) and text matching.
    Combines results for better accuracy.

    Major changes:
    - Higher MINIMUM_SIMILARITY for hybrid retrieval (0.87).
    - Skip government-only / regulator-only articles.
    - Deduplicate matches by (article_id, article_number).

    Only matches MAIN ARTICLES (not individual clauses as separate entries).
    Clauses are analyzed within each article for percentage calculation.
    """
    # Combine all extracted text from all pages
    full_text = " ".join([page["text"] for page in extracted_text])

    # Filter to only main articles (not individual clause entries)
    main_articles = [a for a in pdpl_articles if a.get("is_main_article", False)]

    # Use hybrid retrieval (BM25 + E5 + optional LLM)
    print(
        f"[INFO] Using hybrid retrieval (BM25 + E5"
        f"{' + LLM' if use_llm_rerank else ''}) for {len(main_articles)} articles..."
    )
    semantic_matches = hybrid_retrieval_bm25_e5(
        query_text=full_text,
        top_k_bm25=200,
        top_k_final=top_k * 3,  # Get more candidates for better coverage
        use_llm_rerank=use_llm_rerank,
    )

    # Also use text-based matching as a fallback (optional)
    if use_text_fallback:
        text_matches = match_with_pdpl_text(
            extracted_text, main_articles, threshold=threshold
        )
    else:
        text_matches = []

    # Combine results (prioritize semantic matches, but include high-scoring text matches)
    seen_keys = set()
    combined_matches: List[Dict[str, Any]] = []

    # Threshold for semantic matches (E5 cosine similarity)
    # 0.70 ~= 70% similarity - allows more articles to be scored by LLM
    MINIMUM_SIMILARITY = 0.70

    # Handle semantic / hybrid matches
    for match in semantic_matches:
        article = match["article"]
        article_num = article.get("article_number")

        similarity = match.get("similarity", 0.0)
        if similarity < MINIMUM_SIMILARITY:
            print(
                f"[FILTER] Rejecting article {article_num}: "
                f"similarity {similarity:.3f} < {MINIMUM_SIMILARITY}"
            )
            continue

        # Use composite key to avoid duplicates
        article_id = article.get("id") or article.get("article_id")
        key = (article_id, article_num)

        if key not in seen_keys:
            seen_keys.add(key)
            combined_matches.append(match)
            print(
                f"[ACCEPT] Article {article_num}: similarity {similarity:.3f} >= {MINIMUM_SIMILARITY}"
            )

    # Add high-scoring text matches that weren't in semantic results (if enabled)
    if use_text_fallback:
        for match in text_matches:
            article = match["article"]
            article_num = article.get("article_number")

            article_id = article.get("id") or article.get("article_id")
            key = (article_id, article_num)

            if key not in seen_keys and match["similarity"] >= threshold:
                seen_keys.add(key)
                combined_matches.append(match)

    # Calculate coverage for each matched article
    print(f"[INFO] Calculating clause-level coverage for {len(combined_matches)} matched articles...")
    for match in combined_matches:
        # Extract BM25 and E5 scores from retrieval
        bm25_score = match.get("bm25_score", 0.0)
        e5_score = match.get("e5_score", match.get("e5_similarity", 0.0))
        
        coverage_info = calculate_article_coverage(
            article=match["article"],
            extracted_text=extracted_text,
            pdpl_articles=pdpl_articles,
            llm_clause_match_func=llm_clause_match,
            bm25_score=bm25_score,
            e5_score=e5_score,
        )

        # Add coverage info to match
        match.update(coverage_info)

    # Sort by coverage percentage (highest first)
    combined_matches.sort(key=lambda x: x.get("coverage_percentage", 0), reverse=True)

    return combined_matches


def match_with_pdpl_llm_only(
    extracted_text: List[Dict[str, str]],
    pdpl_articles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    LLM-only PDPL matching:
    - NO BM25
    - NO E5 vectors
    - NO text similarity / keyword thresholds
    - For every main PDPL article, compute clause coverage using the LLM only.

    This is the most expensive but also the purest LLM-based evaluation path.
    """
    # Combine all extracted text from all pages (used inside coverage calculation)
    full_text = " ".join([page["text"] for page in extracted_text])
    print(f"[LLM ONLY] Starting pure LLM coverage calculation, policy length={len(full_text)} chars")

    # Filter to only main articles (not individual clause entries)
    main_articles = [a for a in pdpl_articles if a.get("is_main_article", False)]
    print(f"[LLM ONLY] Evaluating ALL {len(main_articles)} main PDPL articles via LLM (no retrieval)")

    matches: List[Dict[str, Any]] = []

    for article in main_articles:
        coverage_info = calculate_article_coverage(
            article=article,
            extracted_text=extracted_text,
            pdpl_articles=pdpl_articles,
            llm_clause_match_func=llm_clause_match,
            bm25_score=0.0,  # No retrieval in LLM-only mode
            e5_score=0.0,
        )

        match = {
            "article": article,
            "article_number": article.get("article_number"),
            "article_title": article.get("title", ""),
        }
        match.update(coverage_info)
        matches.append(match)

    # Sort by coverage percentage (highest first)
    matches.sort(key=lambda x: x.get("coverage_percentage", 0), reverse=True)

    return matches
