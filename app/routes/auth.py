#app/routes/auth.py
from flask import Blueprint, request, jsonify, current_app, make_response
import logging
from logging.handlers import RotatingFileHandler
from app.models import session_manager  # For using the global instance
import uuid 
from app.utils.validators import validate_csrf_token



auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)  

@auth_bp.route('/start-session', methods=['POST'])
@validate_csrf_token
def start_session():
    logger.info("start_session route called")  # Add this
    # Generate a new session ID
    session_id = str(uuid.uuid4())
    ip_address = request.remote_addr
    # print(session_id, ip_address) #DEBUG
    # session_manager is initialized by the app.py
    # Start the session
    # Access the session_manager from the application context
    session_manager = current_app.session_manager

    if session_manager is None:
        raise RuntimeError("session_manager is not initialized!")



    session_status = session_manager.start_session(session_id, ip_address)
    

    if session_status["status"] == "active":
        # Session is active, set the cookie
        response = make_response(jsonify({
            "status": "active",
            "message": "Session started successfully",
            "session_id": session_id
        }))
        # Set session cookie (valid for 20 min)
        response.set_cookie(
            'session_id', 
            session_id, 
            httponly= True, 
            secure=current_app.config.get("SESSION_COOKIE_SECURE", False), 
            samesite="Strict", 
            max_age=1800
        )
    else:
        # Server is busy, inform the client
        response = jsonify({
            "status": "busy",
            "message": "Server is busy. Please try again later."
        })

    return response


@auth_bp.route('/end-session', methods=['POST'])
def end_session():
    logger.info("end_session route called")  # Log that the route was called

    
    # Get the session_id from the request data
    data = request.json
    if not data:
        logger.error("No form data provided")  # Log missing form data
        return jsonify({"status": "error", "message": "No csrf token"}), 400
    
    csrf_token = data.get("csrf_token")
    if not csrf_token:
        logger.info("No csrf_token provided.")
        return jsonify({"status": "error", "message": "No session to end"}),  400


    session_id = data.get('session_id')
    if not session_id or session_id == 'none':
        logger.info("No session ID provided. This might be a new user.")
        return jsonify({"status": "success", "message": "No session to end"}), 200

    logger.info(f"Received session_id: {session_id}")  # Log the received session_id

    # Access the session_manager from the application context
    session_manager = current_app.session_manager

    if session_manager is None:
        logger.error("session_manager is not initialized!")  # Log uninitialized session_manager
        raise RuntimeError("session_manager is not initialized!")

    # Call the session manager to end the session
    try:
        session_manager.end_session(session_id)
        logger.info(f"Session ended successfully for session_id: {session_id}")  # Log successful session end
        return jsonify({'message': 'Session ended', 'session_id': session_id})
    except Exception as e:
        logger.error(f"Error ending session: {e}")  # Log any errors during session end
        return jsonify({"status": "error", "message": "Failed to end session"}), 500