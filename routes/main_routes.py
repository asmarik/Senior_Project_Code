"""Main API routes - root, health, info endpoints"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from models import model_manager
from config import QDRANT_COLLECTION_NAME, OPENAI_MODEL_NAME
from utils.file_utils import get_cached_pdpl_articles

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def root():
    """Serve the landing page"""
    try:
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return {
            "message": "PDF Compliance Checker API",
            "version": "1.0.0",
            "endpoints": {
                "health": "/health",
                "upload": "/upload",
                "pdpl_info": "/pdpl/info",
                "web_interface": "/"
            }
        }


@router.get("/app", response_class=HTMLResponse)
async def app_page():
    """Serve the compliance matcher application"""
    try:
        with open('templates/app.html', 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>App page not found</h1>", status_code=404)


@router.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "message": "PDF Compliance Checker API",
        "version": "5.0.0",
        "llm_status": "enabled" if model_manager.llm_enabled else "disabled",
        "llm_model": OPENAI_MODEL_NAME if model_manager.llm_enabled else "none",
        "llm_configuration": {
            "clause_matching": model_manager.llm_clause_matching,
            "reranking": model_manager.llm_reranking
        },
        "main_endpoints": {
            "fast_without_llm": {
                "score": {
                    "path": "/score",
                    "method": "POST",
                    "description": "Gap and Match Analysis (5-10s)",
                    "llm_used": False,
                    "matching_method": "E5 embeddings + BM25 + Text similarity"
                },
                "missing": {
                    "path": "/missing",
                    "method": "POST",
                    "description": "Show missing articles/clauses (5-10s)",
                    "llm_used": False
                }
            },
            "slow_with_llm": {
                "score_llm": {
                    "path": "/score_llm",
                    "method": "POST",
                    "description": "Compliance score WITH LLM (API-based, 5-15s)",
                    "llm_used": True,
                    "matching_method": f"{OPENAI_MODEL_NAME} + E5 + BM25"
                },
                "missing_llm": {
                    "path": "/missing_llm",
                    "method": "POST",
                    "description": "Missing items WITH LLM explanations (30-60s)",
                    "llm_used": True
                },
                "advisor": {
                    "path": "/advisor",
                    "method": "POST",
                    "description": "AI Compliance Advisor - Interactive Q&A (20-40s)",
                    "llm_used": True
                }
            }
        },
        "testing_endpoints": {
            "test_ocr": {
                "path": "/test/ocr",
                "method": "POST",
                "description": "Extract text from PDF only (2-3s)"
            },
            "test_rag": {
                "path": "/test/rag",
                "method": "POST",
                "description": "Semantic search using E5-small (3-5s)"
            },
            "test_hybrid": {
                "path": "/test/hybrid",
                "method": "POST",
                "description": "Hybrid BM25→E5 retrieval (3-5s)"
            }
        },
        "retrieval_info": {
            "embedding_model": "intfloat/e5-small-v2",
            "llm_model": OPENAI_MODEL_NAME if model_manager.llm_enabled else "none",
            "method": "Hybrid BM25 + E5 + LLM re-ranking"
        },
        "features": [
            "AI Compliance Advisor (Interactive Q&A)",
            "LLM re-ranking for article retrieval",
            "Enhanced missing clause explanations",
            "LLM-powered clause matching",
            "3-stage hybrid retrieval (BM25 → E5 → LLM)",
            "Clause-level coverage analysis",
            "Overall compliance scoring (0-100)"
        ]
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}


@router.get("/pdpl/info")
async def pdpl_info():
    """Get information about loaded PDPL articles (cached for performance)"""
    articles = get_cached_pdpl_articles()
    
    # Get Qdrant collection info
    qdrant_info = {}
    if model_manager.qdrant_client:
        try:
            collection_info = model_manager.qdrant_client.get_collection(QDRANT_COLLECTION_NAME)
            qdrant_info = {
                "collection_name": QDRANT_COLLECTION_NAME,
                "points_count": collection_info.points_count,
                "vectors_config": {
                    "size": collection_info.config.params.vectors.size,
                    "distance": str(collection_info.config.params.vectors.distance)
                }
            }
        except:
            qdrant_info = {"status": "unavailable"}
    
    main_articles = [a for a in articles if a.get('is_main_article', False)]
    total_clauses = sum(len(a.get('clauses', [])) for a in main_articles)

    return {
        "total_articles": len(articles),
        "main_articles": len(main_articles),
        "total_clauses": total_clauses,
        "qdrant_info": qdrant_info,
        "bm25_initialized": model_manager.bm25_index is not None,
        "embedding_model": "intfloat/e5-small-v2",
        "llm_model": OPENAI_MODEL_NAME if model_manager.llm_enabled else "none"
    }

