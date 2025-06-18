# Copyright (C) 2025 SharmaG-omics
#
# Variantis Production is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.



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