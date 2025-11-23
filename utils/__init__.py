"""Utility functions for the PDF Compliance Checker API"""

from .text_utils import (
    similarity_score,
    normalize_text,
    calculate_keyword_overlap
)
from .scoring_utils import calculate_overall_score, calculate_article_coverage
from .file_utils import allowed_file, load_pdpl_articles

__all__ = [
    'similarity_score',
    'normalize_text',
    'calculate_keyword_overlap',
    'calculate_overall_score',
    'calculate_article_coverage',
    'allowed_file',
    'load_pdpl_articles'
]
