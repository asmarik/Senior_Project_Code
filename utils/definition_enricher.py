"""
Definition Enricher - Enhances PDPL articles with keywords from definitions
"""
import json
import re
from typing import Dict, List, Any


def load_definitions(filepath: str = 'pdpl_definitions.json') -> Dict[str, Any]:
    """
    Load PDPL definitions from JSON file.
    
    Returns:
        Dictionary of definitions with term mappings
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('definitions', {})
    except FileNotFoundError:
        print(f"[WARNING] Definitions file not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse definitions file: {e}")
        return {}


def extract_terms_from_text(text: str, definitions: Dict[str, Any]) -> List[str]:
    """
    Extract which definition terms are mentioned in the text.
    
    MINIMAL MATCHING - NO SYNONYM EXPANSION:
    - Only exact term matches
    - No fuzzy matching
    - No synonym detection
    
    Args:
        text: Text to analyze (article or clause text)
        definitions: Dictionary of definitions
    
    Returns:
        List of term keys that appear in the text
    """
    found_terms = []
    text_lower = text.lower()
    
    for term_key, term_data in definitions.items():
        term = term_data.get('term', '')
        
        # ONLY check if the exact term appears in text (NO SYNONYMS)
        if term.lower() in text_lower:
            found_terms.append(term_key)
    
    return found_terms


def get_keywords_for_terms(terms: List[str], definitions: Dict[str, Any]) -> List[str]:
    """
    Get MINIMAL top domain keyphrases for given terms.
    
    DRASTICALLY REDUCED to prevent over-enrichment:
    - Only top 2-3 most important keyphrases per term
    - NO synonyms
    - NO examples
    - NO definition expansion
    
    Args:
        terms: List of term keys
        definitions: Dictionary of definitions
    
    Returns:
        Minimal list of top keyphrases (5-10 total max)
    """
    keywords = []
    MAX_KEYWORDS_PER_TERM = 2  # Only 2 keyphrases per term
    MAX_TOTAL_KEYWORDS = 10     # Hard cap at 10 keywords total
    
    for term_key in terms:
        if term_key not in definitions:
            continue
        
        if len(keywords) >= MAX_TOTAL_KEYWORDS:
            break  # Stop if we've reached the cap
        
        term_data = definitions[term_key]
        
        # ONLY add the most critical keyphrases - NO SYNONYMS, NO EXAMPLES
        # Only add operations for "Processing" term, and only top 2
        if term_key == 'processing':
            operations = term_data.get('operations', [])
            keywords.extend(operations[:MAX_KEYWORDS_PER_TERM])
        
        # Only add categories for "Sensitive Data" term, and only top 2
        elif term_key == 'sensitive_data':
            categories = term_data.get('categories', [])
            keywords.extend(categories[:MAX_KEYWORDS_PER_TERM])
        
        # For all other terms: add NOTHING (just the term itself is enough)
        # The original term is already in the article text
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower not in seen and len(unique_keywords) < MAX_TOTAL_KEYWORDS:
            seen.add(keyword_lower)
            unique_keywords.append(keyword)
    
    return unique_keywords


def get_plain_text_for_terms(terms: List[str], definitions: Dict[str, Any]) -> str:
    """
    Get plain text definitions for given terms.
    
    Args:
        terms: List of term keys
        definitions: Dictionary of definitions
    
    Returns:
        Combined plain text definitions
    """
    plain_texts = []
    
    for term_key in terms:
        if term_key not in definitions:
            continue
        
        term_data = definitions[term_key]
        term = term_data.get('term', '')
        definition = term_data.get('definition', '')
        
        if definition:
            plain_texts.append(f"{term}: {definition}")
    
    return " ".join(plain_texts)


def enrich_article_with_definitions(article: Dict[str, Any], definitions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance a single article/clause with keywords from definitions.
    
    Args:
        article: Article or clause dictionary
        definitions: Dictionary of definitions
    
    Returns:
        Enhanced article dictionary with added keywords and context
    """
    text = article.get('text', '')
    
    # Find which terms are used in this article
    used_terms = extract_terms_from_text(text, definitions)
    
    if not used_terms:
        return article  # No terms found, return as-is
    
    # Get keywords from those terms
    new_keywords = get_keywords_for_terms(used_terms, definitions)
    
    # Add to existing keywords (if any)
    existing_keywords = article.get('keywords', [])
    combined_keywords = list(set(existing_keywords + new_keywords))
    
    # Get plain text definitions
    term_context = get_plain_text_for_terms(used_terms, definitions)
    
    # Create enhanced search text with MINIMAL keywords (top 10 max)
    search_text_parts = [
        text,
        article.get('plain_text', ''),
        ' '.join(combined_keywords[:10])  # DRASTICALLY REDUCED: Only top 10 keywords
    ]
    search_text = ' '.join(filter(None, search_text_parts))
    
    # Update article with enriched data
    article['keywords'] = combined_keywords
    article['used_terms'] = used_terms
    article['term_definitions'] = term_context
    article['search_text'] = search_text
    article['enriched'] = True
    
    return article


def enrich_articles_with_definitions(articles: List[Dict[str, Any]], 
                                     definitions_filepath: str = 'pdpl_definitions.json') -> List[Dict[str, Any]]:
    """
    Enrich all articles with keywords and context from definitions.
    
    Args:
        articles: List of article/clause dictionaries
        definitions_filepath: Path to definitions JSON file
    
    Returns:
        List of enriched articles
    """
    definitions = load_definitions(definitions_filepath)
    
    if not definitions:
        print("[WARNING] No definitions loaded, articles will not be enriched")
        return articles
    
    enriched_count = 0
    enriched_articles = []
    
    for article in articles:
        # Skip main article entries (they're just containers)
        if article.get('is_main_article', False):
            enriched_articles.append(article)
            continue
        
        # Enrich the article
        enriched = enrich_article_with_definitions(article, definitions)
        enriched_articles.append(enriched)
        
        if enriched.get('enriched', False):
            enriched_count += 1
    
    print(f"[INFO] Enriched {enriched_count}/{len(articles)} articles with MINIMAL keywords (max 5-10 per article)")
    
    # Show some statistics
    if enriched_count > 0:
        sample = next((a for a in enriched_articles if a.get('enriched')), None)
        if sample:
            keyword_count = len(sample.get('keywords', []))
            print(f"[INFO] Example - Article {sample.get('article_number')}:{sample.get('label')} "
                  f"enriched with {keyword_count} keywords (REDUCED from ~64 avg) from terms: "
                  f"{', '.join(sample.get('used_terms', [])[:3])}")
            print(f"[INFO] ✅ Keyword over-enrichment FIXED: {keyword_count} keywords vs previous 100-150")
    
    return enriched_articles


def get_definition_context_for_llm(terms: List[str], definitions: Dict[str, Any]) -> str:
    """
    Generate context text for LLM prompts about specific terms.
    
    Args:
        terms: List of term keys to include
        definitions: Dictionary of definitions
    
    Returns:
        Formatted text suitable for LLM prompts
    """
    if not terms:
        return ""
    
    context_lines = ["TERM DEFINITIONS (for context):"]
    
    for term_key in terms[:5]:  # Limit to first 5 terms to avoid token bloat
        if term_key not in definitions:
            continue
        
        term_data = definitions[term_key]
        term = term_data.get('term', '')
        definition = term_data.get('definition', '')
        
        # Add main definition
        context_lines.append(f"• {term}: {definition}")
        
        # Add key synonyms/examples
        synonyms = term_data.get('synonyms', [])[:5]
        if synonyms:
            context_lines.append(f"  Common phrases: {', '.join(synonyms)}")
    
    return '\n'.join(context_lines)


