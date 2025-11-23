"""
PDF Compliance Checker API - Main Application
Clean, modular FastAPI application with organized routes and services.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from services.retrieval_service import initialize_qdrant_with_pdpl
from routes import (
    main_router,
    test_router,
    score_router,
    missing_router,
    advisor_router,
    upload_router,
    comprehensive_router,
    debug_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize RAG system on startup"""
    print("\n[STARTUP] Initializing RAG system with Qdrant...")
    initialize_qdrant_with_pdpl()
    print("[STARTUP] RAG system ready!\n")
    yield
    print("\n[SHUTDOWN] Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="PDF Compliance Checker API",
    version="5.0.0",
    description="PDPL compliance checker with RAG, semantic search, and optional LLM enhancement",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include all routers
app.include_router(main_router, tags=["main"])
app.include_router(test_router, prefix="/test", tags=["testing"])
app.include_router(score_router, tags=["scoring"])
app.include_router(missing_router, tags=["missing"])
app.include_router(comprehensive_router, tags=["comprehensive"])
app.include_router(advisor_router, tags=["advisor"])
app.include_router(upload_router, tags=["upload"])
app.include_router(debug_router, prefix="/debug", tags=["debug"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

