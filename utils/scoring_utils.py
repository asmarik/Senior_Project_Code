"""Scoring and coverage calculation utilities"""
from typing import List, Dict, Any
from .text_utils import normalize_text

# Global flag for LLM-only mode (set by routes)
_llm_only_mode = False

# Articles to exclude from overall-score calculations (legacy behaviour).
# Kept for backward compatibility but NOT used when INCLUDED_ARTICLES_FOR_OVERALL is set.
GOV_ONLY_ARTICLES = set()

# Explicit list of articles to use for overall score (testing mode).
# When non-empty, ONLY these articles are counted in the overall score,
# band statistics, and missing-articles list.
INCLUDED_ARTICLES_FOR_OVERALL = {4, 5, 10, 11, 12, 13, 15, 20, 25, 26, 29}


def get_applicable_article_numbers(pdpl_articles: List[Dict[str, Any]]) -> List[int]:
    """
    Get list of article numbers that apply to private entities.
    (All articles are now included; no exclusions.)
    """
    all_numbers = sorted(list(set(
        a.get('article_number')
        for a in pdpl_articles
        if a.get('article_number')
    )))
    return all_numbers


def calculate_article_coverage(article: Dict[str, Any], extracted_text: List[Dict[str, str]], 
                               pdpl_articles: List[Dict[str, Any]], llm_clause_match_func=None,
                               bm25_score: float = 0.0, e5_score: float = 0.0) -> Dict[str, Any]:
    """
    Calculate how much of a PDPL article is covered based on its CLAUSES.
    Returns coverage classification, percentage, and missing clauses.
    
    Coverage Classification:
    - Fully Covered: 70-100%
    - Partially Covered: 40-70%
    - Missing: 0-40%
    
    Args:
        article: The PDPL article to analyze (with clauses)
        extracted_text: List of pages with extracted text
        pdpl_articles: All PDPL articles (to check clauses)
        llm_clause_match_func: Optional LLM clause matching function
    
    Returns:
        dict with coverage_type, coverage_percentage, missing_clauses details
    """
    full_text = ' '.join([page['text'] for page in extracted_text])
    full_text_normalized = normalize_text(full_text)
    
    article_number = article.get('article_number', 0)
    article_id = article.get('id', '')
    is_main_article = article.get('is_main_article', False)
    
    # Get all clauses for this article
    if is_main_article:
        clauses = article.get('clauses', [])
    else:
        clauses = [article]

    # ------------------------------------------------------------------
    # NEW: Article-level LLM path (ONE LLM CALL PER ARTICLE)
    # ------------------------------------------------------------------
    # If an LLM clause-matching function is provided and this is a main
    # PDPL article, we now evaluate the ENTIRE article in a single LLM
    # call and return one 0–100 score for the whole article.
    #
    # This replaces the previous "per-clause LLM call + aggregation"
    # behaviour for main articles.
    # ------------------------------------------------------------------
    if llm_clause_match_func and is_main_article:
        return _calculate_article_coverage_llm_article_level(
            article=article,
            full_text=full_text,
            full_text_normalized=full_text_normalized,
            article_number=article_number,
            article_id=article_id,
            clauses=clauses,
            llm_clause_match_func=llm_clause_match_func,
            bm25_score=bm25_score,
            e5_score=e5_score,
        )
    
    if not clauses:
        # No clauses, treat as single item - use BM25 + E5 scores
        bm25_normalized = min(1.0, bm25_score / 10.0) if bm25_score > 0 else 0.0
        coverage = (0.4 * bm25_normalized) + (0.6 * e5_score)
        
        # No boost or floor - trust BM25 + E5 scores directly
        coverage_percentage = round(coverage * 100, 2)
        
        # LLM-BASED THRESHOLDS for article classification
        if coverage_percentage >= 75:
            coverage_type = "covered"
        elif coverage_percentage >= 40:
            coverage_type = "partially_covered"
        else:
            coverage_type = "missing"
        
        return {
            'coverage_type': coverage_type,
            'coverage_percentage': coverage_percentage,
            'covered_clauses': [] if coverage_percentage < 40 else [article],
            'missing_clauses': [article] if coverage_percentage < 40 else [],
            'total_clauses': 1,
            'covered_clauses_count': 1 if coverage_percentage >= 40 else 0,
            'missing_clauses_count': 0 if coverage_percentage >= 40 else 1,
            'article_id': article_id,
            'article_number': article_number
        }
    
    # Calculate coverage for each clause
    covered_clauses = []
    partially_covered_clauses = []
    missing_clauses = []
    clause_coverage_scores = []
    
    # Declare global variable at the start of the loop scope
    global _llm_only_mode
    
    for clause in clauses:
        clause_text = normalize_text(clause.get('text', ''))
        if not clause_text or clause_text in ['article', f'article {article_number}']:
            continue
        
        # Initialize debug variables
        llm_score_raw = None
        traditional_score_raw = None
        traditional_score_before_boost = None
        
        # Try LLM matching if function provided
        if llm_clause_match_func:
            # If in LLM-only mode, LLM function MUST be provided
            pass
        elif _llm_only_mode:
            # LLM-only mode but no LLM function provided - ERROR
            raise RuntimeError(
                f"LLM-only mode: LLM function not provided for Article {article_number}. "
                f"Cannot score in LLM-only mode without LLM."
            )
        
        if llm_clause_match_func:
            llm_result = llm_clause_match_func(
                clause_text=clause.get('text', ''),
                pdf_text=full_text,
                article_number=article_number,
                clause_label=clause.get('label', '')
            )
            
            if llm_result:
                llm_score = llm_result['score']
                llm_score_raw = llm_score  # Store for debug
                llm_explanation = llm_result.get('explanation', '')
                llm_confidence = llm_result.get('confidence', 'medium')
                
                # Use BM25 + E5 scores from retrieval as traditional score
                bm25_normalized = min(1.0, bm25_score / 10.0) if bm25_score > 0 else 0.0
                traditional_score = (0.4 * bm25_normalized) + (0.6 * e5_score)
                traditional_score_before_boost = traditional_score  # Store for debug
                
                # No boost - trust BM25 + E5 scores directly from retrieval
                traditional_score_raw = traditional_score  # Store for debug
                
                # LLM-ONLY SCORING: Use 100% LLM score
                # BM25 and E5 are used for retrieval/filtering only, not for scoring
                clause_coverage = llm_score
                matching_method = 'llm_only_scoring'
                
                print(f"[LLM-SCORING] Article {article_number}, Clause {clause.get('label', '')}: "
                      f"LLM={llm_score:.2f}, Final={clause_coverage:.2f} (100% LLM)")
            else:
                # LLM returned None
                if _llm_only_mode:
                    # In LLM-only mode, NO FALLBACK - raise error
                    raise RuntimeError(
                        f"LLM-only mode: LLM failed for Article {article_number}, Clause {clause.get('label', '')}. "
                        f"No fallback allowed in LLM-only mode."
                    )
                else:
                    # In hybrid mode, fallback to traditional
                    print(f"[LLM] Article {article_number}, Clause {clause.get('label', '')}: "
                          f"LLM returned None, falling back to traditional")
                    clause_coverage, llm_explanation, llm_confidence, matching_method = _traditional_clause_match(
                        clause_text, full_text_normalized, bm25_score, e5_score
                    )
        else:
            # LLM function not provided
            if _llm_only_mode:
                # Already handled above, but just in case
                raise RuntimeError(
                    f"LLM-only mode: Cannot use traditional scoring for Article {article_number}."
                )
            else:
                # Traditional matching only (normal mode)
                clause_coverage, llm_explanation, llm_confidence, matching_method = _traditional_clause_match(
                    clause_text, full_text_normalized, bm25_score, e5_score
                )
        
        clause_coverage_scores.append(clause_coverage)
        coverage_score = round(clause_coverage * 100, 2)
        
        clause_info = {
            'id': clause.get('id', ''),
            'article_number': article_number,
            'label': clause.get('label', ''),
            'path': clause.get('path', ''),
            'text': clause.get('text', '')[:200] + '...' if len(clause.get('text', '')) > 200 else clause.get('text', ''),
            'coverage_score': coverage_score,
            'matching_method': matching_method
        }
        
        # Add detailed scoring breakdown for debugging
        if llm_score_raw is not None and traditional_score_raw is not None:
            # Check mode for formula display (already declared global above)
            if _llm_only_mode:
                formula = f'100% LLM = {coverage_score}'
            else:
                formula = f'(0.7×{round(llm_score_raw*100,1)}) + (0.3×{round(traditional_score_raw*100,1)}) = {coverage_score}'
            
            clause_info['debug_scores'] = {
                'llm_score': round(llm_score_raw * 100, 2),
                'traditional_score': round(traditional_score_raw * 100, 2),
                'traditional_before_boost': round(traditional_score_before_boost * 100, 2) if traditional_score_before_boost is not None else None,
                'final_score': coverage_score,
                'formula': formula,
                'mode': 'llm_only' if _llm_only_mode else 'hybrid',
                'boost_applied': (traditional_score_before_boost is not None and traditional_score_raw > traditional_score_before_boost)
            }
        
        if llm_explanation:
            clause_info['llm_explanation'] = llm_explanation
        if llm_confidence:
            clause_info['llm_confidence'] = llm_confidence
        
        # Categorize clause based on LLM score thresholds
        if coverage_score >= 75:
            covered_clauses.append(clause_info)
        elif coverage_score >= 40:
            clause_info['band'] = 'Partial'
            if llm_explanation and 'llm' in matching_method:
                clause_info['partial_reason'] = llm_explanation
            else:
                clause_info['partial_reason'] = f"Partial coverage: some elements of Article {article_number}, Label {clause.get('label', '')} are present but incomplete"
            partially_covered_clauses.append(clause_info)
        else:
            if llm_explanation and 'llm' in matching_method:
                clause_info['missing_reason'] = llm_explanation
            else:
                clause_info['missing_reason'] = f"Article {article_number}, Label {clause.get('label', '')} is missing - no matching content found"
            missing_clauses.append(clause_info)
    
    # Calculate article-level score (average of all clause scores)
    total_clauses = len(clause_coverage_scores)
    if total_clauses > 0:
        average_coverage = sum(clause_coverage_scores) / total_clauses
        coverage_percentage = round(average_coverage * 100, 2)
    else:
        coverage_percentage = 0.0
    
    # Determine coverage band for article (LOWERED THRESHOLDS)
    # LLM-BASED THRESHOLDS: 75-100 = Full, 40-74 = Partial, 0-39 = Missing
    if coverage_percentage >= 75:
        band = "Full"
    elif coverage_percentage >= 40:
        band = "Partial"
    else:
        band = "Missing"
    
    return {
        'band': band,
        'coverage_percentage': coverage_percentage,
        'covered_clauses': covered_clauses,
        'partially_covered_clauses': partially_covered_clauses,
        'missing_clauses': missing_clauses,
        'total_clauses': total_clauses,
        'covered_clauses_count': len(covered_clauses),
        'partially_covered_clauses_count': len(partially_covered_clauses),
        'missing_clauses_count': len(missing_clauses),
        'article_id': article_id,
        'article_number': article_number
    }


def _calculate_article_coverage_llm_article_level(
    article: Dict[str, Any],
    full_text: str,
    full_text_normalized: str,
    article_number: int,
    article_id: str,
    clauses: List[Dict[str, Any]],
    llm_clause_match_func,
    bm25_score: float = 0.0,
    e5_score: float = 0.0,
) -> Dict[str, Any]:
    """
    Single LLM call per article:
    - Build an article-level requirement text (entire article content)
    - Call the provided LLM function ONCE
    - Optionally blend with traditional score (same hybrid rules)
    - Return a single coverage score (0–100) for the whole article
    """
    global _llm_only_mode

    # Build article-level requirement text:
    # Prefer the article's own 'text' field; if missing, join clause texts.
    raw_article_text = article.get('text', '') or ' '.join(
        c.get('text', '') for c in clauses
    )
    raw_article_text = raw_article_text.strip()

    if not raw_article_text:
        # Fallback: no textual definition for the article, treat as missing
        return {
            'band': 'Missing',
            'coverage_percentage': 0.0,
            'covered_clauses': [],
            'partially_covered_clauses': [],
            'missing_clauses': [],
            'total_clauses': 0,
            'covered_clauses_count': 0,
            'partially_covered_clauses_count': 0,
            'missing_clauses_count': 0,
            'article_id': article_id,
            'article_number': article_number,
        }

    article_text_normalized = normalize_text(raw_article_text)

    # Initialise debug variables
    llm_score_raw = None
    traditional_score_raw = None
    traditional_score_before_boost = None

    # Run a SINGLE LLM call for the whole article
    llm_result = None
    if llm_clause_match_func:
        llm_result = llm_clause_match_func(
            clause_text=raw_article_text,
            pdf_text=full_text,
            article_number=article_number,
            clause_label="Article-level",
        )

    if llm_result:
        llm_score = llm_result.get('score', 0.0)
        llm_score_raw = llm_score
        llm_explanation = llm_result.get('explanation', '')
        llm_confidence = llm_result.get('confidence', 'medium')

        # Use BM25 + E5 scores from retrieval as traditional score
        # Normalize BM25 score (typically 0-10 range) to 0-1
        bm25_normalized = min(1.0, bm25_score / 10.0) if bm25_score > 0 else 0.0
        
        # E5 score is already 0-1 (cosine similarity)
        # Combine: 40% BM25 (keyword), 60% E5 (semantic)
        traditional_score = (0.4 * bm25_normalized) + (0.6 * e5_score)
        traditional_score_before_boost = traditional_score

        # No boost - trust BM25 + E5 scores directly from retrieval
        traditional_score_raw = traditional_score

        # LLM-ONLY SCORING: Use 100% LLM score
        # BM25 and E5 are used for retrieval/filtering only, not for scoring
        article_coverage = llm_score
        matching_method = 'llm_only_scoring_article'

        print(
            f"[LLM-SCORING-ARTICLE] Article {article_number}: "
            f"LLM={llm_score:.2f}, Final={article_coverage:.2f} (100% LLM)"
        )
    else:
        # LLM failed or not available
        if _llm_only_mode:
            raise RuntimeError(
                f"LLM-only mode: LLM failed for Article {article_number} (article-level). "
                f"No fallback allowed in LLM-only mode."
            )

        print(
            f"[LLM-ARTICLE] Article {article_number}: "
            f"LLM returned None, falling back to traditional article-level scoring"
        )
        traditional_score, _, _, matching_method = _traditional_clause_match(
            article_text_normalized, full_text_normalized, bm25_score, e5_score
        )
        article_coverage = traditional_score
        llm_explanation = None
        llm_confidence = None

    # Convert article coverage (0–1) to percentage
    coverage_percentage = round(article_coverage * 100, 2)

    # Map to article-level band with the same thresholds
    # LLM-BASED THRESHOLDS: 75-100 = Full, 40-74 = Partial, 0-39 = Missing
    if coverage_percentage >= 75:
        band = "Full"
    elif coverage_percentage >= 40:
        band = "Partial"
    else:
        band = "Missing"

    # Build a single pseudo-clause representing the whole article
    clause_label = article.get('title', '') or f"Article {article_number}"
    clause_info = {
        'id': article_id,
        'article_number': article_number,
        'label': clause_label,
        'path': article.get('path', ''),
        'text': raw_article_text[:200] + '...' if len(raw_article_text) > 200 else raw_article_text,
        'coverage_score': coverage_percentage,
        'matching_method': matching_method,
    }

    if llm_score_raw is not None and traditional_score_raw is not None:
        if _llm_only_mode:
            formula = f'100% LLM = {coverage_percentage}'
        else:
            formula = (
                f'(0.7×{round(llm_score_raw * 100, 1)}) + '
                f'(0.3×{round(traditional_score_raw * 100, 1)}) = {coverage_percentage}'
            )

        clause_info['debug_scores'] = {
            'llm_score': round(llm_score_raw * 100, 2),
            'traditional_score': round(traditional_score_raw * 100, 2),
            'traditional_before_boost': round(traditional_score_before_boost * 100, 2)
            if traditional_score_before_boost is not None
            else None,
            'final_score': coverage_percentage,
            'formula': formula,
            'mode': 'llm_only' if _llm_only_mode else 'hybrid',
            'boost_applied': (
                traditional_score_before_boost is not None
                and traditional_score_raw > traditional_score_before_boost
            ),
        }

    if llm_explanation:
        clause_info['llm_explanation'] = llm_explanation
    if llm_confidence:
        clause_info['llm_confidence'] = llm_confidence

    covered_clauses: List[Dict[str, Any]] = []
    partially_covered_clauses: List[Dict[str, Any]] = []
    missing_clauses: List[Dict[str, Any]] = []

    # LLM-BASED THRESHOLDS: 75-100 = Full, 40-74 = Partial, 0-39 = Missing
    if coverage_percentage >= 75:
        covered_clauses.append(clause_info)
    elif coverage_percentage >= 40:
        clause_info['band'] = 'Partial'
        clause_info['partial_reason'] = (
            llm_explanation
            or f"Article {article_number} has partial coverage based on article-level analysis."
        )
        partially_covered_clauses.append(clause_info)
    else:
        clause_info['missing_reason'] = (
            llm_explanation
            or f"Article {article_number} appears missing or very weak based on article-level analysis."
        )
        missing_clauses.append(clause_info)

    return {
        'band': band,
        'coverage_percentage': coverage_percentage,
        'covered_clauses': covered_clauses,
        'partially_covered_clauses': partially_covered_clauses,
        'missing_clauses': missing_clauses,
        'total_clauses': 1,
        'covered_clauses_count': len(covered_clauses),
        'partially_covered_clauses_count': len(partially_covered_clauses),
        'missing_clauses_count': len(missing_clauses),
        'article_id': article_id,
        'article_number': article_number,
    }

def _traditional_clause_match(clause_text: str, full_text_normalized: str, bm25_score: float = 0.0, e5_score: float = 0.0) -> tuple:
    """
    Traditional similarity matching fallback using BM25 + E5 scores.
    
    Formula: TraditionalScore = 0.4 × BM25 + 0.6 × E5
    No boost or floor - trust retrieval scores as-is.
    
    Returns:
        tuple: (coverage_score, llm_explanation, llm_confidence, matching_method)
    """
    # Use BM25 + E5 from retrieval
    bm25_normalized = min(1.0, bm25_score / 10.0) if bm25_score > 0 else 0.0
    traditional_score = (0.4 * bm25_normalized) + (0.6 * e5_score)
    
    return traditional_score, None, None, 'traditional_bm25_e5'


def calculate_overall_score(matches: List[Dict[str, Any]], total_articles: int = 38, 
                           all_article_numbers: List[int] = None) -> Dict[str, Any]:
    """
    Calculate overall compliance score out of 100 based on all PDPL articles.
    
    Formula: TotalComplianceScore = (Sum of ArticleScores / NumberOfArticles) × 100
    
    Note: ArticleScores are already percentages (0-100), so we just average them.
    If INCLUDED_ARTICLES_FOR_OVERALL is non-empty, only those article numbers are used.
    Otherwise, articles listed in GOV_ONLY_ARTICLES are excluded.
    
    Args:
        matches: List of matched articles with coverage info
        total_articles: Total number of articles in PDPL (default 38, excluding gov articles)
        all_article_numbers: List of all article numbers (to identify missing ones)
    
    Returns:
        dict with overall_score, compliance_level, missing_articles, and statistics
    """
    if all_article_numbers is None:
        # Default PDPL main article range (2–45)
        all_article_numbers = list(range(2, 46))
    else:
        all_article_numbers = list(all_article_numbers)

    # If we have an explicit include-list for overall score, restrict to it.
    if INCLUDED_ARTICLES_FOR_OVERALL:
        all_article_numbers = [
            num for num in all_article_numbers if num in INCLUDED_ARTICLES_FOR_OVERALL
        ]
    else:
        # Otherwise, drop any excluded (legacy behaviour)
        all_article_numbers = [
            num for num in all_article_numbers if num not in GOV_ONLY_ARTICLES
        ]

    # Always derive total_articles from the filtered list so the denominator matches.
    total_articles = len(all_article_numbers)
    
    if not matches:
        return {
            'overall_score': 0.0,
            'compliance_level': 'Critical',
            'total_articles': total_articles,
            'articles_analyzed': 0,
            'covered_count': 0,
            'partially_covered_count': 0,
            'low_coverage_count': 0,
            'missing_count': total_articles,
            'missing_articles': all_article_numbers,
            'average_article_coverage': 0.0
        }
    
    # Group by article number to avoid counting duplicates
    article_scores: Dict[int, float] = {}
    article_bands: Dict[int, str] = {}
    # Optional debug info per article (LLM vs traditional components)
    article_debug_components: Dict[int, Dict[str, Any]] = {}
    
    for match in matches:
        article_num = match.get('article_number', 0)
        # If an explicit include-list is set, ignore any other articles.
        if INCLUDED_ARTICLES_FOR_OVERALL and article_num not in INCLUDED_ARTICLES_FOR_OVERALL:
            continue
        # Skip legacy excluded articles as a safety net.
        if article_num in GOV_ONLY_ARTICLES:
            continue
        if article_num not in article_scores:
            article_scores[article_num] = match.get('coverage_percentage', 0)
            article_bands[article_num] = match.get('band', 'Missing')

            # Try to pull debug_scores (llm_score/traditional_score) from any clause
            debug_scores = None
            for clause_key in ('covered_clauses', 'partially_covered_clauses', 'missing_clauses'):
                for clause in match.get(clause_key, []) or []:
                    if clause.get('debug_scores'):
                        debug_scores = clause['debug_scores']
                        break
                if debug_scores:
                    break

            if debug_scores:
                article_debug_components[article_num] = debug_scores
    
    # Calculate overall score (average of all article percentages)
    total_coverage = sum(article_scores.values())
    overall_score = round(total_coverage / total_articles, 2)

    # DEBUG: show how the overall score was derived
    print("\n=== Compliance Score Debug (100% LLM Scoring) ===")
    for num, score in sorted(article_scores.items()):
        debug = article_debug_components.get(num)
        if debug:
            llm_pct = debug.get('llm_score')
            print(f"  Article {num}: {score:.2f}% | LLM: {llm_pct:.2f}%")
        else:
            print(f"  Article {num}: {score:.2f}%")
    print(f"[DEBUG] Sum of coverage: {total_coverage:.2f}")
    print(f"[DEBUG] total_articles (denominator): {total_articles}")
    print(f"[DEBUG] overall_score: {overall_score}")
    if article_scores:
        print(
            f"[DEBUG] average_article_coverage: "
            f"{sum(article_scores.values()) / len(article_scores):.2f}"
        )
    
    # Count coverage bands
    unique_articles_by_band = {}
    for match in matches:
        article_num = match.get('article_number', 0)
        # Apply same include/exclude rules for band statistics
        if INCLUDED_ARTICLES_FOR_OVERALL and article_num not in INCLUDED_ARTICLES_FOR_OVERALL:
            continue
        if article_num in GOV_ONLY_ARTICLES:
            continue
        band = match.get('band', 'Missing')
        if article_num not in unique_articles_by_band:
            unique_articles_by_band[article_num] = band
    
    # Categorize articles by band and create lists
    covered_articles = sorted([num for num, b in unique_articles_by_band.items() if b == 'Full'])
    partially_covered_articles = sorted([num for num, b in unique_articles_by_band.items() if b == 'Partial'])
    low_coverage_articles = sorted([num for num, b in unique_articles_by_band.items() if b == 'Missing'])
    
    covered = len(covered_articles)
    partially_covered = len(partially_covered_articles)
    low_coverage = len(low_coverage_articles)
    
    # Find missing articles (respecting include/exclude rules)
    found_article_numbers = set(article_scores.keys())
    missing_article_numbers = sorted(
        [num for num in all_article_numbers if num not in found_article_numbers]
    )
    missing_count = len(missing_article_numbers)
    
    if INCLUDED_ARTICLES_FOR_OVERALL:
        print(f"[INFO] Overall score uses ONLY articles {sorted(INCLUDED_ARTICLES_FOR_OVERALL)}")
    else:
        print(f"[INFO] Scoring excludes articles {GOV_ONLY_ARTICLES} from overall calculations")
    print(f"[DEBUG] missing articles: {missing_article_numbers}")
    
    # Map overall score to compliance level (user-defined bands):
    # 0–39   = not compliant
    # 40–74  = partially compliant
    # 75–100 = compliant
    if overall_score >= 75:
        compliance_level = "compliant"
    elif overall_score >= 40:
        compliance_level = "partially_compliant"
    else:
        compliance_level = "not_compliant"
    
    return {
        'overall_score': overall_score,
        'compliance_level': compliance_level,
        'total_articles': total_articles,
        'articles_analyzed': len(article_scores),
        'covered_count': covered,
        'covered_articles': covered_articles,
        'partially_covered_count': partially_covered,
        'partially_covered_articles': partially_covered_articles,
        'low_coverage_count': low_coverage,
        'low_coverage_articles': low_coverage_articles,
        'missing_count': missing_count,
        'missing_articles': missing_article_numbers,
        'average_article_coverage': round(sum(article_scores.values()) / len(article_scores), 2) if article_scores else 0.0
    }
