"""Debug routes to test file upload and processing"""
import os
import fitz
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional

from config import UPLOAD_FOLDER, MAX_FILE_SIZE, OPENAI_MODEL_NAME
from utils.file_utils import sanitize_filename
from services.llm_service import llm_clause_match
from models import model_manager

router = APIRouter()


class LLMTestRequest(BaseModel):
    """Request model for testing LLM"""
    clause_text: str
    pdf_text: str
    article_number: Optional[int] = 1
    clause_label: Optional[str] = "1"


@router.post("/debug/test_upload")
async def debug_test_upload(file: UploadFile = File(...)):
    """
    Debug endpoint to test each step of file processing
    """
    results = {
        'steps': [],
        'success': False,
        'error': None
    }
    
    try:
        # Step 1: Check filename
        results['steps'].append({
            'step': 1,
            'name': 'Original filename',
            'value': file.filename,
            'status': 'OK'
        })
        
        # Step 2: Sanitize filename
        sanitized = sanitize_filename(file.filename)
        results['steps'].append({
            'step': 2,
            'name': 'Sanitized filename',
            'value': sanitized,
            'status': 'OK'
        })
        
        # Step 3: Create upload directory
        upload_dir = os.path.abspath(UPLOAD_FOLDER)
        os.makedirs(upload_dir, exist_ok=True)
        results['steps'].append({
            'step': 3,
            'name': 'Upload directory',
            'value': upload_dir,
            'status': 'OK'
        })
        
        # Step 4: Build filepath
        filepath = os.path.join(upload_dir, sanitized)
        results['steps'].append({
            'step': 4,
            'name': 'Full filepath',
            'value': filepath,
            'status': 'OK'
        })
        
        # Step 5: Read file contents
        contents = await file.read()
        results['steps'].append({
            'step': 5,
            'name': 'Read file contents',
            'value': f'{len(contents)} bytes',
            'status': 'OK'
        })
        
        # Step 6: Write to disk
        try:
            with open(filepath, "wb") as f:
                f.write(contents)
            results['steps'].append({
                'step': 6,
                'name': 'Write to disk',
                'value': 'Success',
                'status': 'OK'
            })
        except Exception as e:
            results['steps'].append({
                'step': 6,
                'name': 'Write to disk',
                'value': str(e),
                'status': 'ERROR'
            })
            raise
        
        # Step 7: Verify file exists
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            results['steps'].append({
                'step': 7,
                'name': 'Verify file exists',
                'value': f'Yes, {file_size} bytes',
                'status': 'OK'
            })
        else:
            results['steps'].append({
                'step': 7,
                'name': 'Verify file exists',
                'value': 'No',
                'status': 'ERROR'
            })
        
        # Step 8: Try to open with PyMuPDF (this is likely where the error happens)
        try:
            # Try different path formats
            pdf_doc = fitz.open(filepath)
            page_count = len(pdf_doc)
            pdf_doc.close()
            results['steps'].append({
                'step': 8,
                'name': 'Open with PyMuPDF (fitz)',
                'value': f'Success, {page_count} pages',
                'status': 'OK'
            })
        except Exception as e:
            results['steps'].append({
                'step': 8,
                'name': 'Open with PyMuPDF (fitz)',
                'value': f'{type(e).__name__}: {str(e)}',
                'status': 'ERROR'
            })
            
            # Try with raw string path
            try:
                pdf_doc = fitz.open(filename=filepath)
                page_count = len(pdf_doc)
                pdf_doc.close()
                results['steps'].append({
                    'step': 9,
                    'name': 'Open with PyMuPDF (filename param)',
                    'value': f'Success, {page_count} pages',
                    'status': 'OK'
                })
            except Exception as e2:
                results['steps'].append({
                    'step': 9,
                    'name': 'Open with PyMuPDF (filename param)',
                    'value': f'{type(e2).__name__}: {str(e2)}',
                    'status': 'ERROR'
                })
        
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)
            results['steps'].append({
                'step': 10,
                'name': 'Cleanup',
                'value': 'File deleted',
                'status': 'OK'
            })
        
        results['success'] = True
        return results
        
    except Exception as e:
        import traceback
        results['error'] = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': traceback.format_exc()
        }
        
        # Try to clean up
        try:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass
        
        return results


@router.post("/debug/test_llm")
async def debug_test_llm(request: LLMTestRequest):
    """
    Debug endpoint to test LLM clause matching with custom inputs.
    
    This allows you to test your LLM prompt changes without uploading a full PDF.
    
    Example request body:
    {
        "clause_text": "The Controller shall provide contact details.",
        "pdf_text": "Our company contact: info@example.com, phone: 123-456",
        "article_number": 31,
        "clause_label": "1"
    }
    """
    try:
        # Check if LLM is enabled
        if not model_manager.llm_enabled:
            return {
                'success': False,
                'error': 'LLM is not enabled. Check your API key configuration.',
                'llm_status': {
                    'enabled': model_manager.llm_enabled,
                    'clause_matching': model_manager.llm_clause_matching,
                    'reranking': model_manager.llm_reranking,
                    'model_loaded': model_manager.openai_client is not None
                }
            }
        
        # Force enable clause matching for this test
        original_setting = model_manager.llm_clause_matching
        model_manager.llm_clause_matching = True
        
        try:
            # Call LLM clause match
            result = llm_clause_match(
                clause_text=request.clause_text,
                pdf_text=request.pdf_text,
                article_number=request.article_number,
                clause_label=request.clause_label
            )
            
            if result is None:
                return {
                    'success': False,
                    'error': 'LLM returned None - check server logs for details',
                    'llm_status': {
                        'enabled': model_manager.llm_enabled,
                        'clause_matching': model_manager.llm_clause_matching,
                        'model_loaded': model_manager.openai_client is not None
                    }
                }
            
            return {
                'success': True,
                'result': result,
                'input': {
                    'clause_text': request.clause_text[:100] + '...' if len(request.clause_text) > 100 else request.clause_text,
                    'pdf_text_length': len(request.pdf_text),
                    'article_number': request.article_number,
                    'clause_label': request.clause_label
                },
                'llm_status': {
                    'enabled': model_manager.llm_enabled,
                    'clause_matching': model_manager.llm_clause_matching,
                    'model_loaded': model_manager.openai_client is not None
                }
            }
        finally:
            # Restore original setting
            model_manager.llm_clause_matching = original_setting
            
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'llm_status': {
                'enabled': model_manager.llm_enabled,
                'clause_matching': model_manager.llm_clause_matching if hasattr(model_manager, 'llm_clause_matching') else None,
                'model_loaded': model_manager.openai_client is not None if hasattr(model_manager, 'openai_client') else None
            }
        }


@router.get("/llm_status")
async def debug_llm_status():
    """
    Check LLM configuration and status.
    """
    from config import OPENAI_MODEL_NAME
    return {
        'llm_enabled': model_manager.llm_enabled,
        'clause_matching_enabled': model_manager.llm_clause_matching,
        'reranking_enabled': model_manager.llm_reranking,
        'model_loaded': model_manager.openai_client is not None,
        'model_name': OPENAI_MODEL_NAME if model_manager.openai_client else None,
        'api_provider': 'OpenAI',
        'api_key_configured': bool(os.getenv('OPENAI_API_KEY'))
    }

