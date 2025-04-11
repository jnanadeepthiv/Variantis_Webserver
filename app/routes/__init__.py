# app/routes/__init__.py
from app.models import session_manager  # Import session_manager from models
from .auth import auth_bp
from .main import main_bp
from .results import results_bp
from .uploads import uploads_bp



# Export all blueprints for easy access
__all__ = ['auth_bp', 'main_bp', 'results_bp', 'uploads_bp', 'session_manager']