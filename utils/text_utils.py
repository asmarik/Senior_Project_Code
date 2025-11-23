"""Text processing utilities"""
import re
from difflib import SequenceMatcher


def similarity_score(text1: str, text2: str) -> float:
    """Calculate similarity between two texts using SequenceMatcher"""
    text1_clean = re.sub(r'\s+', ' ', text1.lower().strip())
    text2_clean = re.sub(r'\s+', ' ', text2.lower().strip())
    return SequenceMatcher(None, text1_clean, text2_clean).ratio()


def normalize_text(text: str) -> str:
    """Normalize text by removing extra spaces, converting to lowercase, and removing special characters"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.lower().strip())
    # Remove common punctuation that might differ
    text = re.sub(r'[^\w\s]', '', text)
    return text


def calculate_keyword_overlap(text1: str, text2: str) -> float:
    """Calculate keyword overlap percentage between two texts"""
    keywords1 = set(text1.split())
    keywords2 = set(text2.split())
    if not keywords1:
        return 0
    return len(keywords1 & keywords2) / len(keywords1)
