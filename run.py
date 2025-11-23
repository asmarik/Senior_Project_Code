#!/usr/bin/env python
"""
Simple script to run the FastAPI server with proper configuration.
"""
import os
import sys
import uvicorn

if __name__ == "__main__":
    # Load .env if it exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("[OK] Loaded configuration from .env file")
    except ImportError:
        print("[WARNING] python-dotenv not found, using default settings")
    
    # Get port from environment or use default
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Check if LLM is disabled
    llm_disabled = os.getenv("FORCE_DISABLE_LLM", "false").lower() == "true"
    mode = "Fast Mode (LLM Disabled)" if llm_disabled else "Full Mode (LLM Enabled)"
    
    print("=" * 60)
    print("Starting PDF Compliance Checker API")
    print("=" * 60)
    print(f"Mode: {mode}")
    print(f"URL: http://localhost:{port}")
    print(f"Docs: http://localhost:{port}/docs")
    print("=" * 60)
    print("\nPress CTRL+C to stop the server\n")
    
    # Run the server
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )

