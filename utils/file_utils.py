"""File handling utilities"""
import json
import os
import re
from functools import lru_cache
from typing import List, Dict, Any
from config import ALLOWED_EXTENSIONS, PDPL_JSON_PATH


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove invalid characters for Windows/Unix filesystems.
    Handles Windows reserved names and invalid characters.
    """
    # Get the base name (remove any path)
    filename = os.path.basename(filename)
    
    # Replace invalid characters with underscores
    # Invalid chars for Windows: < > : " / \ | ? *
    # Also replace control characters (0x00-0x1f, 0x7f-0x9f)
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f]', '_', filename)
    
    # Remove any non-printable characters
    filename = ''.join(char for char in filename if char.isprintable())
    
    # Remove leading/trailing spaces and dots (Windows doesn't like these)
    filename = filename.strip('. ')
    
    # Check for Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    name_without_ext = os.path.splitext(filename)[0].upper()
    if name_without_ext in reserved_names:
        filename = f"file_{filename}"
    
    # Limit length to 200 characters (leave room for upload folder path)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    
    # If filename becomes empty or just extension, use a default
    if not filename or filename.startswith('.') or not filename.strip():
        filename = 'uploaded_file.pdf'
    
    return filename


def allowed_file(filename: str) -> bool:
    """Check if uploaded file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def load_pdpl_articles() -> List[Dict[str, Any]]:
    """
    Load PDPL articles from the JSON format.

    New format has nested structure: articles -> clauses -> sub-clauses.

    This function now returns **one entry per main article**, where:
    - `text` contains the article heading PLUS all clause and sub-clause text
    - `clauses` contains a flattened list of all clauses/sub-clauses for that article

    Vector indexing and BM25 now work at **article level** instead of per-clause.
    """
    def process_clauses_recursively(clauses, article_number, parent_path="", parent_id=None):
        """Recursively process clauses and sub-clauses"""
        processed = []
        for clause in clauses:
            clause_label = clause.get('label', '')
            clause_text = clause.get('text', '')
            current_path = f"{parent_path}/{clause_label}" if parent_path else str(clause_label)
            
            clause_entry = {
                'id': f"PDPL:{article_number}:{current_path.replace('/', ':')}",
                'article_number': article_number,
                'label': clause_label,
                'text': clause_text,
                'path': f"{article_number}/{current_path}",
                'parent_id': parent_id or f"PDPL:{article_number}",
                'is_main_article': False,
                'full_path': current_path  # For debugging
            }
            
            processed.append(clause_entry)
            
            # Recursively process sub-clauses if they exist
            if clause.get('clauses'):
                sub_clauses = process_clauses_recursively(
                    clause.get('clauses', []),
                    article_number,
                    current_path,
                    clause_entry['id']
                )
                processed.extend(sub_clauses)
        
        return processed
    
    try:
        with open(PDPL_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, dict) or 'articles' not in data:
            # Old format compatibility
            return data if isinstance(data, list) else []
        
        # Build list of main articles only (each with its own clauses)
        articles_list = []
        
        for article in data.get('articles', []):
            article_number = article.get('number')
            article_text = article.get('text', f"Article {article_number}")
            
            # Process all clauses recursively (including nested sub-clauses)
            all_clauses = process_clauses_recursively(
                article.get('clauses', []),
                article_number
            )

            # Combine article heading + all clause text into a single article-level text
            clause_texts = " ".join(
                c.get('text', '') for c in all_clauses if c.get('text')
            )
            if clause_texts:
                combined_text = f"{article_text}. {clause_texts}"
            else:
                combined_text = article_text

            # Main article entry (one per article)
            article_entry = {
                'id': f"PDPL:{article_number}",
                'article_number': article_number,
                'label': '0',  # Main article
                'text': combined_text,
                'path': str(article_number),
                'parent_id': None,
                'is_main_article': True,
                'clauses': all_clauses,
            }

            articles_list.append(article_entry)
        
        print(f"[INFO] Loaded {len(articles_list)} main PDPL articles with nested clauses")
        
        return articles_list
        
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing {PDPL_JSON_PATH}: {e}")
        return []


@lru_cache(maxsize=1)
def get_cached_pdpl_articles() -> List[Dict[str, Any]]:
    """
    Load PDPL articles once and cache the result for performance.
    
    This prevents reloading and re-enriching articles on every request:
    - Avoids reading pdpl.json (962 lines) from disk
    - Avoids recursive processing of 182 articles/clauses
    - Avoids reading pdpl_definitions.json (271 lines)
    - Avoids enriching 127 articles with keywords
    
    Cache is cleared on server restart, so changes to pdpl.json
    will be picked up after restart.
    
    Returns:
        List of enriched PDPL articles (same as load_pdpl_articles)
    """
    return load_pdpl_articles()
