
from .sqlite_db import SQLiteSessionManager, SessionError, DatabaseError

# Create a global session manager instance that can be initialized later
session_manager = None

def init_session_manager(app, db_path, session_timeout_minutes=20):
    """
    Initialize the global session manager instance.
    
    Args:
        app: Flask application instance
        db_path: Path to the SQLite database file
        session_timeout_minutes: Session timeout duration in minutes
    
    Returns:
        Initialized SQLiteSessionManager instance
    """
    global session_manager
    session_manager = SQLiteSessionManager(
        app=app,
        db_path=db_path,
        session_timeout_minutes=session_timeout_minutes
    )
    return session_manager

# Export these names for import from other modules
__all__ = [
    'SQLiteSessionManager',
    'SessionError',
    'DatabaseError',
    'session_manager',
    'init_session_manager'
]