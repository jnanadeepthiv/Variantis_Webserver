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


#utils/validators.py
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, send_file, jsonify, json, make_response, current_app
from flask_wtf.csrf import CSRFProtect,validate_csrf
from app.models import session_manager
import logging
from logging.handlers import RotatingFileHandler


logger = logging.getLogger(__name__) 

def validate_session(f):
    """ 
    To validate the session id of the user
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.cookies.get('session_id')
        if not session_id:
            return jsonify({"status": "error", "message": "Session ID missing"}), 400
        # Access the session_manager from the application context
        session_manager = current_app.session_manager

        if session_manager is None:
            raise RuntimeError("session_manager is not initialized!")

        # check if the session id in the cookie is matching with the session_manager stored id
        
        session = session_manager.get_all_session_details(session_id)
        if not session:
            return jsonify({"status": "error", "message": "Invalid or expired session"}), 401
        
        return f(*args, **kwargs)  # Proceed with the original route function
    return decorated_function

def validate_csrf_token(f):
    """
    Decorator to validate the CSRF token in the request headers.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        csrf_token = request.headers.get('X-CSRF-TOKEN')

        if not csrf_token:
            return jsonify({"status": "error", "message": "Missing CSRF token"}), 400

        try:
            validate_csrf(csrf_token)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Invalid CSRF token: {str(e)}"}), 400

        return f(*args, **kwargs)  # Call the original function

    return decorated_function