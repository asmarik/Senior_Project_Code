"""API Routes for PDF Compliance Checker"""

from .main_routes import router as main_router
from .test_routes import router as test_router
from .score_routes import router as score_router
from .missing_routes import router as missing_router
from .comprehensive_routes import router as comprehensive_router
from .advisor_routes import router as advisor_router
from .upload_routes import router as upload_router
from .debug_routes import router as debug_router

__all__ = [
    'main_router',
    'test_router',
    'score_router',
    'missing_router',
    'comprehensive_router',
    'advisor_router',
    'upload_router',
    'debug_router'
]

