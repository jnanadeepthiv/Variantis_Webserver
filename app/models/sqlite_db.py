import sqlite3
from flask import current_app
from datetime import datetime, timedelta
import os
from contextlib import contextmanager # for connection pooling
import shutil


class SessionError(Exception):
    pass

class DatabaseError(Exception):
    pass

class SQLiteSessionManager:

    """
    A class to manage user sessions using an SQLite database.

    Features:
    - Start, end, and clean up sessions.
    - Track user interactions and session metadata.
    - Query session details for monitoring purposes.
    """
    
    MAX_ACTIVE_SESSIONS = 15  # Limit to 15 active sessions

    #SQL query constants
    CREATE_TABLE_QUERY = '''
        CREATE TABLE IF NOT EXISTS user_sessions(
              session_id TEXT PRIMARY KEY,
              ip_address TEXT,          
              start_time DATETIME,
              last_activity DATETIME, -- New column to track session activity
              end_time DATETIME
              
        )
    '''
    CREATE_SESSION_DATA_ENTRY_TABLE =  '''
        CREATE TABLE IF NOT EXISTS session_data(
          session_id TEXT PRIMARY KEY, 
          upload_file_path TEXT,
          psa_program TEXT,
          gap_open INTEGER,  -- Added column definition
          gap_extend INTEGER,  -- Added column definition
          num_sequences INTEGER,
          alignment_file_path TEXT,
          user_alignment_file_path TEXT,
          processed_file_path TEXT,
          nucleotide_matrix_path TEXT,
          user_nucleotide_matrix_path TEXT,
          transratio_matrix_path TEXT,
          summary_features_path TEXT,
          summary_alignment_path TEXT,
          FOREIGN KEY(session_id) REFERENCES user_sessions(session_id) ON DELETE CASCADE
        )
    '''
    
    INSERT_SESSION_QUERY = '''
        INSERT INTO user_sessions(session_id,ip_address,start_time,last_activity, end_time)
        VALUES(?,?,?,?,?)
    '''
    INSERT_SESSION_DATA_QUERY ='''
      INSERT INTO session_data(session_id, upload_file_path, psa_program, gap_open, gap_extend,
            num_sequences, alignment_file_path, user_alignment_file_path,
            processed_file_path, nucleotide_matrix_path, user_nucleotide_matrix_path, transratio_matrix_path,summary_features_path,
          summary_alignment_path)
      VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      
    '''
    # Add indexes for faster queries
    CREATE_INDEX_QUERY = '''
        CREATE INDEX IF NOT EXISTS idx_last_activity ON user_sessions(last_activity);
    '''
    
    END_SESSION_QUERY = '''
        UPDATE user_sessions
        SET end_time=?
        WHERE session_id=?
    '''
    DELETE_OLD_SESSION_QUERY ='''
        DELETE FROM user_sessions
        WHERE (end_time IS NOT NULL) OR end_time < ?
    '''
    GET_SESSION_QUERY = '''
      SELECT * FROM user_sessions
      WHERE session_id = ?
    '''
    GET_SESSION_DATA_QUERY = '''
      SELECT * FROM session_data
      WHERE session_id = ?
    '''
    COUNT_ACTIVE_SESSION_QUERY = '''
      SELECT COUNT(*) FROM user_sessions
      WHERE end_time is NULL
    '''
    
    @contextmanager
    def managed_connection(self):
        """Provides a reusable database connection for queries."""
        conn = None  # Initialize conn to None to ensure it's always defined
        try:
            conn = self.get_db_connection()  # Get a reusable connection
            yield conn  # Give the connection to the function that called it
        except sqlite3.Error as e:
            self.app.logger.error(f"Database connection error: {e}") 
            raise DatabaseError(f"Database connection failed: {e}")
        except Exception as e:
            self.app.logger.error(f"Unexpected error in managed_connection: {e}")
            raise DatabaseError(f"Unexpected error: {e}")
        finally:
            if conn:
                try:
                    conn.close()  # Always close the connection after use
                except Exception as e:
                    self.app.logger.error(f"Error closing database connection: {e}")
                    raise DatabaseError(f"Error closing connection: {e}")
    
    def __init__(self,app=None,db_path=None,session_timeout_minutes=20):
        """
            Initialize the SQLiteSessionManager.

            Parameters:
            - db_path: Path to the SQLite database file.
            """
        
        self.db_path = db_path
        self.session_timeout_minutes = session_timeout_minutes
        
        self.app = app
        
        if self.app is not None:
            self.initialize_database()
        

    def get_db_connection(self):
        """Create and return a thread-safe connection to the SQLite database."""
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")  # Enable foreign key support
        conn.execute("PRAGMA journal_mode=WAL;")  # Enable WAL mode for better concurrency
        conn.execute("PRAGMA synchronous=NORMAL;")  # Balance between safety and performance
        return conn

    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Execute a query and return results if specified, with error handling."""
        try:
            with self.managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION;")  # Start a transaction
                current_app.logger.debug(f"Executing query: {query}")
                if params:
                    current_app.logger.debug(f"With params: {params}")
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if fetch_one:
                    result = cursor.fetchone()
                elif fetch_all:
                    result = cursor.fetchall()
                else:
                    result = None
                
                conn.commit()  # Commit the transaction
                return result
        except sqlite3.OperationalError as e:
            current_app.logger.error(f"Database operational error: {e}")
            conn.rollback()  # Rollback on error
            return None
        except sqlite3.IntegrityError as e:
            current_app.logger.error(f"Database integrity error: {e}")
            conn.rollback()  # Rollback on error
            return None
        except sqlite3.Error as e:
            current_app.logger.error(f"General database error: {e}")
            conn.rollback()  # Rollback on error
            return None


    def initialize_database(self):
        """ Create the user sessions table if it doesn't exists."""
        with self.app.app_context():
          self.execute_query(SQLiteSessionManager.CREATE_TABLE_QUERY)
          self.execute_query(SQLiteSessionManager.CREATE_SESSION_DATA_ENTRY_TABLE)
          self.execute_query(self.CREATE_INDEX_QUERY)  # Ensure index for optimization
          current_app.logger.info(f"Initialized database at: {self.db_path}")

    def start_session(self, session_id, ip_address):
        """Start a session immediately."""
        # Validate inputs
        if not session_id or not ip_address:
            raise SessionError("Session ID and IP address are required")

        # Check the number of active sessions
        active_sessions = self.count_active_sessions()
        if active_sessions < self.MAX_ACTIVE_SESSIONS:
            try:
                # Insert the session into the database
                current_time = datetime.now()
                self.execute_query(
                    SQLiteSessionManager.INSERT_SESSION_QUERY,
                    (session_id, ip_address, current_time, current_time, None)
                )
                current_app.logger.info(f"Session started: {session_id} from {ip_address}")
                return {"status": "active", "session_id": session_id}
            except Exception as e:
                # Log and propagate the error
                current_app.logger.error(f"Error starting session {session_id}: {e}")
                raise DatabaseError(f"Failed to start session: {e}")
        else:
            current_app.logger.info(f"Session rejected due to server capacity: {session_id}")
            return {"status": "busy", "message": "Server is busy. Please try again later."}
    
    def count_active_sessions(self):
        """ Count the number fo active sessions."""
        
        result = self.execute_query(self.COUNT_ACTIVE_SESSION_QUERY,fetch_one=True)
        return result[0] if result else 0
    
    def insert_session_data(self, session_id, upload_file_path, psa_program,
                        gap_open, gap_extend, num_sequences, alignment_file_path,
                        user_alignment_file_path, processed_fasta_file_path, 
                        nucleotide_matrix_path, user_nucleotide_matrix_path, transratio_matrix_path, summary_features_path,  summary_alignment_path):
        """ Insert session-specific data into the database."""
        params = (session_id, upload_file_path, psa_program, gap_open, gap_extend, num_sequences, 
                  alignment_file_path, user_alignment_file_path, processed_fasta_file_path, 
                  nucleotide_matrix_path, user_nucleotide_matrix_path, transratio_matrix_path, summary_features_path,  summary_alignment_path)
        self.execute_query(self.INSERT_SESSION_DATA_QUERY, params)  # Pass params as a tuple
        current_app.logger.info(f"Session data inserted for session: {session_id}")
    
        
    def update_activity(self, session_id):
        """Update session last activity timestamp."""
        try:
            now = datetime.now()
            
            # Use managed connection for the entire operation
            with self.managed_connection() as conn:
                cursor = conn.cursor()
                
                # First update the last_activity timestamp
                cursor.execute(
                    "UPDATE user_sessions SET last_activity = ? WHERE session_id = ?",
                    (now, session_id)
                )
                
                # Then check if session should be expired
                cursor.execute(
                    "SELECT start_time FROM user_sessions WHERE session_id = ?",
                    (session_id,)
                )
                session = cursor.fetchone()
                
                if session:
                    session_start_time = datetime.strptime(session["start_time"], "%Y-%m-%d %H:%M:%S.%f")
                    
                    # If session is older than 30 minutes, mark it as expired
                    if (now - session_start_time).total_seconds() > 1800:  # 30 min
                        current_app.logger.info(f"Session {session_id} expired, ending now.")
                        cursor.execute(
                            "UPDATE user_sessions SET end_time = ? WHERE session_id = ?",
                            (now, session_id)
                        )
                        conn.commit()
                        return False  # Indicate session expired
                    
                    conn.commit()
                    return True  # Indicate session is still active
                
                return False  # Session not found
                
        except Exception as e:
            current_app.logger.error(f"Error updating activity for session {session_id}: {e}")
            return False

    def _add_session_to_db(self, session_id, ip_address):
        """Helper function to insert session into database."""
        current_time = datetime.now()
        with self.managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO user_sessions (session_id, ip_address, start_time, last_activity, end_time) VALUES (?, ?, ?, ?, ?)",
                (session_id, ip_address, current_time, current_time, None)
            )
            conn.commit() 
        current_app.logger.info(f"Session added to database: {session_id}")

    def cleanup_inactive_sessions(self, expiration_minutes=15):
        """
        Remove expired/inactive sessions and delete their associated files.
        Also, clear WAL files for database performance.
        """
        
        try:

            cutoff_time = datetime.now() - timedelta(minutes=expiration_minutes)
            
            # Find inactive sessions
            inactive_sessions = self.execute_query(
                "SELECT session_id FROM user_sessions WHERE last_activity < ? AND end_time IS NULL",
                (cutoff_time,), fetch_all=True
            )
            
            if inactive_sessions:
                    self.app.logger.info(f"Found {len(inactive_sessions)} inactive sessions to clean up")
                    

            for session in inactive_sessions:
                    try:
                        self.end_session(session['session_id'])
                    except Exception as e:
                        self.app.logger.error(f"Error ending session {session['session_id']}: {e}")
            
            self.cleanup_orphaned_files()    
            

            # Clear WAL files for better database performance
            with self.get_db_connection() as conn:
                # Check if there are active transactions using `pragma_wal_checkpoint`
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                self.app.logger.info("WAL checkpoint executed.")
                
                # Optionally, run VACUUM to optimize the database
                conn.execute("VACUUM;")
                self.app.logger.info("Database vacuumed.")
            
            self.app.logger.info(f"Cleaned up inactive sessions older than {expiration_minutes} minutes.")
            
        except Exception as e:
            self.app.logger.error(f"Error in cleanup_inactive_sessions: {e}")
            raise
    
    

            
    def end_session(self, session_id):
        """End session and delete associated files."""
        try:
            now = datetime.now()
            
            with self.managed_connection() as conn:
                cursor = conn.cursor()
                
                # Fetch session data before deletion
                cursor.execute(self.GET_SESSION_DATA_QUERY, (session_id,))
                session_data = cursor.fetchone()
                
                # Define paths for upload and results directories
                upload_dir = os.path.join(self.app.config.get("UPLOADS_FOLDER", ""), session_id)
                results_dir = os.path.join(self.app.config.get("RESULTS_FOLDER", ""), session_id)

                
                if session_data:
                    # Update session end time in user_sessions
                    cursor.execute(
                        "UPDATE user_sessions SET end_time = ? WHERE session_id = ?",
                        (now, session_id)
                    )
                    
                    # Commit both updates at once
                    conn.commit()

                    # Delete associated files and directories
                    self._delete_session_files(session_data)
                    
                    # Delete session record (CASCADE will remove session_data too)
                    cursor.execute(
                        "DELETE FROM user_sessions WHERE session_id = ?",
                        (session_id,)
                    )
                    
                    # Commit the deletion
                    conn.commit()

                    
                    self.app.logger.info(f"Successfully ended session: {session_id}")
                else:
                    self.app.logger.warning(f"No session data found for session: {session_id}")
                    # Check if empty directories exist and delete them
                    deleted_any = False
                    for directory in [upload_dir, results_dir]:
                        if os.path.exists(directory):
                            if not os.listdir(directory):  # Check if empty
                                self.app.logger.info(f"Deleting empty directory: {directory}")
                                try:
                                    shutil.rmtree(directory)
                                    self.app.logger.info(f"Deleted empty directory: {directory}")
                                    deleted_any = True
                                except Exception as e:
                                    self.app.logger.error(f"Error deleting empty directory {directory}: {e}")
                            
                            else:
                                self.app.logger.warning(f"Directory {directory} is not empty. Skipping deletion.")
                            
                    # If no empty directories were found, log a message
                    if not deleted_any:
                        self.app.logger.info(f"No session data or empty directories found for session: {session_id}")
                        
                        
                    # **NEW STEP**: Check if session exists in `user_sessions`
                    cursor.execute("SELECT 1 FROM user_sessions WHERE session_id = ?", (session_id,))
                    session_exists = cursor.fetchone()

                    if session_exists:
                        # **Update end_time and delete session**
                        cursor.execute(
                            "UPDATE user_sessions SET end_time = ? WHERE session_id = ?",
                            (now, session_id)
                        )
                        conn.commit()

                        cursor.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
                        conn.commit()
                        
                        self.app.logger.info(f"Ended session {session_id} that had no associated data.")


        except Exception as e:
            self.app.logger.error(f"Error ending session {session_id}: {e}")
            raise

        return {"status": "ended", "session_id": session_id}

    def cleanup_orphaned_files(self):
        """Delete orphaned session directories in the uploads and results folders."""
        try:
            uploads_folder = self.app.config.get("UPLOADS_FOLDER", "")
            results_folder = self.app.config.get("RESULTS_FOLDER", "")

            # Get a list of session directories in the uploads and results folders
            upload_session_dirs = [d for d in os.listdir(uploads_folder) if os.path.isdir(os.path.join(uploads_folder, d))]
            result_session_dirs = [d for d in os.listdir(results_folder) if os.path.isdir(os.path.join(results_folder, d))]

            with self.managed_connection() as conn:
                cursor = conn.cursor()

                for session_id in set(upload_session_dirs + result_session_dirs):
                    # Check if the session_id exists in the user_sessions table
                    cursor.execute("SELECT 1 FROM user_sessions WHERE session_id = ?", (session_id,))
                    session_exists = cursor.fetchone()

                    if not session_exists:
                        # If the session does not exist in the database, delete the directory
                        upload_dir = os.path.join(uploads_folder, session_id)
                        results_dir = os.path.join(results_folder, session_id)

                        for directory in [upload_dir, results_dir]:
                            if os.path.exists(directory):
                                self.app.logger.info(f"Attempting to delete orphaned directory: {directory}")
                                try:
                                    shutil.rmtree(directory)
                                    self.app.logger.info(f"Deleted orphaned directory: {directory}")
                                except Exception as e:
                                    self.app.logger.error(f"Error deleting orphaned directory {directory}: {e}")

        except Exception as e:
            self.app.logger.error(f"Error deleting orphaned session directories: {e}")
            raise
        
    
    
    
    
    
    
    def _delete_session_files(self, session_data):
        """Delete uploaded files and directories safely."""
        file_paths = [
            "upload_file_path", "alignment_file_path", "user_alignment_file_path",
            "processed_file_path", "nucleotide_matrix_path", "user_nucleotide_matrix_path", "transratio_matrix_path", "summary_features_path", "summary_alignment_path"
        ]

        # Delete individual files
        for file_field in file_paths:
            try:
                # Access the column value directly using square brackets
                file_path = session_data[file_field]
                if file_path and os.path.exists(file_path):
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        self.app.logger.info(f"Deleted file: {file_path}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        self.app.logger.info(f"Deleted directory: {file_path}")
            except KeyError:
                # Handle the case where the column does not exist
                self.app.logger.warning(f"Column '{file_field}' not found in session_data for session: {session_data['session_id']}")
            except Exception as e:
                self.app.logger.error(f"Error deleting {file_path}: {e}")
                raise  # Optionally raise the exception if critical

        # Delete session-specific upload and results directories
        upload_dir = os.path.join(self.app.config.get("UPLOADS_FOLDER", ""), session_data["session_id"])
        results_dir = os.path.join(self.app.config.get("RESULTS_FOLDER", ""), session_data["session_id"])

    
        #clearing the uploading and resulting dir
        for directory in [upload_dir, results_dir]:
            if os.path.exists(directory):
                self.app.logger.info(f"Attempting to delete: {directory}")
                try:
                    shutil.rmtree(directory)
                    self.app.logger.info(f"Deleted session directory: {directory} in {'uploads' if directory == upload_dir else 'results'}") # and then when it deletes in the results_dir it should delete the folder in results_dir too.
                except Exception as e:
                    self.app.logger.error(f"Error deleting directory {directory}: {e}")
                    raise  # Optionally raise the exception if critical
                
                
    def get_all_session_details(self,session_id):
        """Retrieve details of all session."""
        session = self.execute_query(SQLiteSessionManager.GET_SESSION_QUERY,(session_id,),fetch_one=True)
        current_app.logger.info(f"Got session details: {session_id}")
        if session:
            current_app.logger.info(f"Got session details: {session_id}")
            session = dict(session)
            now = datetime.now()

            session_start_time = datetime.strptime(session["start_time"], "%Y-%m-%d %H:%M:%S.%f")

            if (now - session_start_time).total_seconds() > 1800:  # 30 min
                current_app.logger.info(f"Session {session_id} expired, ending now.")
                self.end_session(session_id)  # End session and delete files
                return None  # Return None since session is expired
            
            return session

        return None
    
    def get_session_individual_details(self,session_id):
        """Retrieve session details from session_data and start_time from user_sessions."""
    
        # Fetch session_data details (all required for align_fasta)
        session_data = self.execute_query(SQLiteSessionManager.GET_SESSION_DATA_QUERY, (session_id,), fetch_one=True)

        # Fetch start_time from user_sessions
        session_timing = self.execute_query("SELECT start_time FROM user_sessions WHERE session_id = ?", (session_id,), fetch_one=True)

        if not session_data:
            current_app.logger.warning(f"Session data not found for session_id: {session_id}")
            return None  # No session_data, return None

        if not session_timing:
            current_app.logger.warning(f"Session timing info not found for session_id: {session_id}")
            return None  # No start_time, return None

        # Get the start_time for session expiration check
        session_start_time = datetime.strptime(session_timing["start_time"], "%Y-%m-%d %H:%M:%S.%f")
    
        # Check if session expired (>30 min)
        if (datetime.now() - session_start_time).total_seconds() > 1800:  # 30 min
            current_app.logger.info(f"Session {session_id} expired, ending now.")
            self.end_session(session_id)  # End session and delete files
            return None  # Return None since session is expired
        
        # Convert session_data to a dictionary before returning
        return dict(session_data) if isinstance(session_data, sqlite3.Row) else session_data

        
        

    
    
    
    

    
        
        

