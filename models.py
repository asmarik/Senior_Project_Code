"""
Model initialization - Singleton pattern for ML models.
"""
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from rank_bm25 import BM25Okapi
from openai import OpenAI

from config import (
    EMBEDDING_MODEL_NAME,
    OPENAI_API_KEY,
    OPENAI_MODEL_NAME,
    FORCE_DISABLE_LLM,
    QDRANT_PATH,
    QDRANT_COLLECTION_NAME,
    EMBEDDING_DIM,
    LLM_CLAUSE_MATCHING,
    LLM_RERANKING
)


class ModelManager:
    """Singleton class to manage all ML models"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        print("\n[MODELS] Initializing models...")
        
        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(path=QDRANT_PATH)
        self._initialize_qdrant_collection()
        
        # Initialize embedding model
        print(f"[MODELS] Loading embedding model: {EMBEDDING_MODEL_NAME}")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        
        # Initialize OpenAI LLM
        self.llm_enabled = False
        self.openai_client = None
        self.llm_clause_matching = LLM_CLAUSE_MATCHING
        self.llm_reranking = LLM_RERANKING
        
        if not FORCE_DISABLE_LLM:
            self._initialize_openai()
        else:
            print("[MODELS] LLM loading skipped (FORCE_DISABLE_LLM=true)")
            self.llm_clause_matching = False
            self.llm_reranking = False
        
        # BM25 index (initialized later with articles)
        self.bm25_index = None
        self.bm25_articles = []
        
        print("[MODELS] Configuration:")
        print(f"  - LLM Clause Matching: {'ENABLED' if self.llm_clause_matching and self.llm_enabled else 'DISABLED'}")
        print(f"  - LLM Re-ranking: {'ENABLED' if self.llm_reranking and self.llm_enabled else 'DISABLED'}")
        
        self._initialized = True
    
    def _initialize_qdrant_collection(self):
        """Initialize Qdrant collection if it doesn't exist"""
        try:
            collections = self.qdrant_client.get_collections()
            collection_exists = any(col.name == QDRANT_COLLECTION_NAME for col in collections.collections)
            
            if not collection_exists:
                self.qdrant_client.create_collection(
                    collection_name=QDRANT_COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=Distance.COSINE
                    )
                )
                print(f"[MODELS] Created Qdrant collection: {QDRANT_COLLECTION_NAME}")
            else:
                print(f"[MODELS] Qdrant collection exists: {QDRANT_COLLECTION_NAME}")
        except Exception as e:
            print(f"[MODELS] Warning: Could not initialize Qdrant collection: {e}")
    
    def _initialize_openai(self):
        """Initialize OpenAI API"""
        print(f"[MODELS] Initializing OpenAI API: {OPENAI_MODEL_NAME}")
        try:
            if not OPENAI_API_KEY or OPENAI_API_KEY == "":
                raise ValueError("OPENAI_API_KEY not set in environment variables")
            
            # Initialize OpenAI client
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            
            # Test the connection with a simple call
            test_response = self.openai_client.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            
            self.llm_enabled = True
            print(f"[MODELS] OpenAI API initialized successfully ({OPENAI_MODEL_NAME})")
        except Exception as e:
            self.llm_enabled = False
            self.openai_client = None
            self.llm_clause_matching = False
            self.llm_reranking = False
            print(f"[MODELS] WARNING: Could not initialize OpenAI API: {e}")
            print("[MODELS] Will use traditional similarity matching instead")
    
    def initialize_bm25(self, articles):
        """Initialize BM25 index with PDPL articles"""
        if not articles:
            return
        
        self.bm25_articles = articles
        tokenized_articles = [article['text'].lower().split() for article in articles]
        self.bm25_index = BM25Okapi(tokenized_articles)
        print(f"[MODELS] BM25 index initialized with {len(articles)} articles")


# Global model manager instance
model_manager = ModelManager()
