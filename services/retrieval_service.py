"""Retrieval services - Semantic search, BM25, and hybrid retrieval"""
import numpy as np
from typing import List, Dict, Any
from qdrant_client.models import PointStruct, VectorParams, Distance

from models import model_manager
from config import QDRANT_COLLECTION_NAME
from utils.file_utils import load_pdpl_articles
from .llm_service import llm_rerank_articles


def initialize_qdrant_with_pdpl():
    """
    Initialize Qdrant + BM25 with *article-level* PDPL entries.

    - One vector per main article (heading + all clause texts).
    - Old clause-level points are wiped every startup.
    """
    if not model_manager.qdrant_client:
        print("Qdrant not available, skipping vector initialization")
        return

    client = model_manager.qdrant_client

    # 1) Load the main articles (with nested clauses)
    pdpl_articles = load_pdpl_articles()
    num_articles = len(pdpl_articles)
    print(f"[RAG INIT] Loaded {num_articles} main PDPL articles with nested clauses")

    # 2) Recreate the collection so we drop any old points
    try:
        # Get embedding dimension dynamically from the E5 model
        test_vec = model_manager.embedding_model.encode("test")
        dim = int(len(test_vec))

        client.recreate_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(
                size=dim,
                distance=Distance.COSINE,
            ),
        )
        print(
            f"[RAG INIT] Recreated Qdrant collection '{QDRANT_COLLECTION_NAME}' "
            f"with dim={dim} – all old points removed."
        )
    except Exception as e:
        print(f"[RAG INIT] WARNING: could not recreate collection: {e}")

    # 3) Build article-level embeddings and upsert
    points: List[PointStruct] = []
    for idx, article in enumerate(pdpl_articles):
        # Text used for embedding: article text + all clauses (combined in load_pdpl_articles)
        text_to_embed = article.get("search_text") or article.get("text") or ""
        if not text_to_embed:
            continue

        prefixed_text = f"passage: {text_to_embed}"
        embedding = model_manager.embedding_model.encode(prefixed_text).tolist()

        point = PointStruct(
            id=idx,  # deterministic ID per article
            vector=embedding,
            payload={
                "article": article,
                "article_id": article.get("id", ""),
                "text": article.get("text", ""),
                "article_number": article.get(
                    "article_number", article.get("number", 0)
                ),
                "path": article.get("path", ""),
            },
        )
        points.append(point)

    if points:
        client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=points,
        )
        # Avoid non-ASCII symbols in logs (Windows console limitation)
        print(
            f"[RAG INIT] Indexed {len(points)} PDPL articles in Qdrant (article-level)"
        )

    # 4) BM25 index on the same articles
    model_manager.initialize_bm25(pdpl_articles)
    print(f"[RAG INIT] ✅ BM25 index initialized with {len(pdpl_articles)} articles")


def semantic_search_pdpl(query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Perform semantic search on PDPL articles using vector similarity.
    Returns list of matched articles with similarity scores.
    """
    if not model_manager.qdrant_client:
        return []
    
    try:
        # E5 models require "query: " prefix for queries
        query_with_prefix = f"query: {query_text}"
        query_embedding = model_manager.embedding_model.encode(query_with_prefix).tolist()
        
        # Search in Qdrant
        search_results = model_manager.qdrant_client.search(
            collection_name=QDRANT_COLLECTION_NAME,
            query_vector=query_embedding,
            limit=top_k
        )
        
        # Convert results to match format
        matches = []
        for result in search_results:
            matches.append({
                'article': result.payload.get('article', {}),
                'similarity': float(result.score),
                'match_type': 'semantic',
                'vector_score': float(result.score)
            })
        
        return matches
    except Exception as e:
        print(f"Error in semantic search: {e}")
        return []


def hybrid_retrieval_bm25_e5(query_text: str, top_k_bm25: int = 200, top_k_final: int = 20, use_llm_rerank: bool = True) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: BM25 → top-200; then E5-small re-rank; then optional LLM re-rank → top-20.
    
    Step 1: BM25 retrieves top-200 candidates (keyword-based)
    Step 2: E5-small re-ranks those 200 (semantic similarity)
    Step 3 (OPTIONAL): LLM re-ranks for legal relevance → final top-20
    
    Args:
        query_text: Query text from PDF
        top_k_bm25: Number of candidates from BM25 (default 200)
        top_k_final: Final number after re-ranking (default 20)
        use_llm_rerank: Whether to use LLM re-ranking (default True)
    
    Returns:
        List of top-20 articles with scores
    """
    if not model_manager.bm25_index or not model_manager.bm25_articles:
        print("BM25 index not initialized, falling back to semantic search")
        return semantic_search_pdpl(query_text, top_k_final)
    
    try:
        # Step 1: BM25 retrieval (keyword-based) → top-200
        tokenized_query = query_text.lower().split()
        bm25_scores = model_manager.bm25_index.get_scores(tokenized_query)
        
        # Get top-200 indices
        top_indices = np.argsort(bm25_scores)[::-1][:top_k_bm25]
        
        # Get candidates
        candidates = []
        for idx in top_indices:
            if idx < len(model_manager.bm25_articles):
                candidates.append({
                    'article': model_manager.bm25_articles[idx],
                    'bm25_score': float(bm25_scores[idx]),
                    'index': int(idx)
                })
        
        if not candidates:
            print("No BM25 candidates found, falling back to semantic search")
            return semantic_search_pdpl(query_text, top_k_final)
        
        # Step 2: E5-small re-ranking (semantic) → top-20
        query_with_prefix = f"query: {query_text}"
        query_embedding = model_manager.embedding_model.encode(query_with_prefix)
        
        # Compute E5 similarity for each candidate
        for candidate in candidates:
            article_text = candidate['article'].get('text', '')
            passage_with_prefix = f"passage: {article_text}"
            article_embedding = model_manager.embedding_model.encode(passage_with_prefix)
            
            # Cosine similarity
            similarity = np.dot(query_embedding, article_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(article_embedding)
            )
            candidate['e5_similarity'] = float(similarity)
            candidate['similarity'] = float(similarity)
        
        # Sort by E5 similarity
        candidates.sort(key=lambda x: x['e5_similarity'], reverse=True)
        
        # Step 3 (OPTIONAL): LLM re-ranking for legal relevance → final top-20
        if use_llm_rerank and model_manager.llm_enabled and model_manager.llm_reranking:
            print(f"[INFO] Applying LLM re-ranking to top candidates...")
            top_candidates = llm_rerank_articles(query_text, candidates, top_k_final)
        else:
            top_candidates = candidates[:top_k_final]
        
        # Convert to standard format
        matches = []
        for candidate in top_candidates:
            match_dict = {
                'article': candidate['article'],
                'similarity': candidate.get('final_score', candidate['e5_similarity']),
                'match_type': 'hybrid_bm25_e5_llm' if use_llm_rerank and model_manager.llm_enabled else 'hybrid_bm25_e5',
                'bm25_score': candidate['bm25_score'],
                'e5_score': candidate['e5_similarity']
            }
            if 'llm_relevance_score' in candidate:
                match_dict['llm_relevance_score'] = candidate['llm_relevance_score']
            matches.append(match_dict)
        
        return matches
        
    except Exception as e:
        print(f"Error in hybrid retrieval: {e}")
        return semantic_search_pdpl(query_text, top_k_final)

