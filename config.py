"""
Configuration and constants for the PDF Compliance Checker API.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Server Configuration
UPLOAD_FOLDER = 'uploads'
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'pdf'}

# Qdrant Configuration
QDRANT_PATH = "./qdrant_db"
QDRANT_COLLECTION_NAME = 'pdpl_articles'
EMBEDDING_DIM = 384  # Dimension for E5-small-v2

# Model Configuration
EMBEDDING_MODEL_NAME = 'intfloat/e5-small-v2'

# LLM API Configuration (OpenAI)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # SECURITY FIX: Removed hardcoded API key
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")  # Fast and cheap GPT-4 model

# Legacy Gemini config (kept for backward compatibility)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")

# LLM Configuration from environment variables
LLM_CLAUSE_MATCHING = os.getenv("LLM_CLAUSE_MATCHING", "true").lower() == "true"
LLM_RERANKING = os.getenv("LLM_RERANKING", "true").lower() == "true"
FORCE_DISABLE_LLM = os.getenv("FORCE_DISABLE_LLM", "false").lower() == "true"

# PDPL Configuration
PDPL_JSON_PATH = 'pdpl.json'

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
