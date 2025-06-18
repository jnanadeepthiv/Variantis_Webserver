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





# app/routes/upload.py
import os
from flask import Flask, render_template, redirect, url_for, request, send_file, jsonify, json, make_response,session, current_app
from werkzeug.utils import secure_filename
from Bio import SeqIO
import os
import itertools
import pandas as pd
import psa
import numpy as np
import re
from flask import current_app
from io import StringIO
import logging
from logging.handlers import RotatingFileHandler
import mimetypes # for MIME check of uploaded FASTA file
from flask_wtf.csrf import CSRFProtect,validate_csrf
from flask import Blueprint
from app.routes import session_manager  # Import from routes, NOT models
from app.utils.file_handlers import  contains_executable_code, is_valid_fasta
from app.utils.validators import validate_session

uploads_bp = Blueprint('uploads', __name__)


logger = logging.getLogger(__name__) 

@uploads_bp.route('/uploads', methods=['POST']) 
@validate_session
def upload_file():
    try:
        session_id = request.cookies.get('session_id')
        session_manager = current_app.session_manager

        if session_manager is None:
            raise RuntimeError("session_manager is not initialized!")

        # Create session-specific directories
        upload_dir = os.path.join(current_app.config['UPLOADS_FOLDER'], session_id)
        results_dir = os.path.join(current_app.config['RESULTS_FOLDER'], session_id)
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(results_dir, exist_ok=True)

        # Check if either file or text input is provided
        has_file = 'file' in request.files and request.files['file'].filename != ''
        has_text = 'fasta_text' in request.form and request.form['fasta_text'].strip() != ''
        
        if not has_file and not has_text:
            return jsonify({"status": "error", "message": "Please provide either a file or paste sequences"}), 400
        if has_file and has_text:
            return jsonify({"status": "error", "message": "Please choose only one input method (file upload OR text paste)"}), 400

        cleanup_needed = True
        file_path = None
        
        try:
            # Handle file upload case
            if has_file:
                file = request.files['file']
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_dir, filename)
                
                # Save the file first
                file.save(file_path)
                
                # Read portion for MIME checking
                with open(file_path, 'rb') as f:
                    file_bytes = f.read(2048)
                    f.seek(0)
                
                # Validate the file
                validate_uploaded_file(file_path, filename, file_bytes)
            
            # Handle text input case
            elif has_text:
                fasta_text = request.form['fasta_text']
                filename = "pasted_sequences.fasta"
                file_path = os.path.join(upload_dir, filename)
                
                # Save text to file
                with open(file_path, 'w') as f:
                    f.write(fasta_text)
                
                # Read portion for MIME checking
                with open(file_path, 'rb') as f:
                    file_bytes = f.read(2048)
                    f.seek(0)
                
                # Validate the created file
                validate_uploaded_file(file_path, filename, file_bytes)

            # Process the FASTA file
            with open(file_path, 'r') as fasta_file:
                records = list(SeqIO.parse(fasta_file, 'fasta'))
                
                if not records:
                    raise ValueError("Input is empty or not a valid nucleotide FASTA format.")
                
                # Check for at least two sequences
                if len(records) < 2:
                    raise ValueError("At least two sequences are required for comparison.")
                
                
                # Validate sequences
                allowed_bases = "ATCGNRYKMSWBDHVU"
                for record in records:
                    sequence = str(record.seq).upper()
                    if re.search(f"[^{allowed_bases}]", sequence):
                        raise ValueError("Invalid characters in FASTA sequence")

            num_sequences = len(records)
            max_sequence_length = max(len(record.seq) for record in records)
            
            # Get custom parameters with defaults
            psa_program = request.form.get('psaprogram', 'needle')
            gap_open = float(request.form.get('gapOpen', 10))
            gap_extend = float(request.form.get('gapExtend', 0.5))
            
            if gap_open < 1 or gap_extend < 0:
                raise ValueError("Gap Open must be >= 1, Gap Extend must be >= 0")

            # Program selection logic
            needle_length_limit = 3000
            stretcher_length_limit = 10000
            
            if psa_program == 'needle' and max_sequence_length > needle_length_limit:
                psa_program = 'stretcher'
                if gap_open < 1 or gap_extend < 1:
                    gap_open = float(16)
                    gap_extend = float(4)
                if gap_open % 1 != 0 or gap_extend % 1 != 0:
                    raise ValueError("Gap Open and Gap extend must be whole numbers")

            if psa_program == 'stretcher':
                if gap_open < 1 or gap_extend < 1:
                    raise ValueError("Gap Open and Gap extend must be >= 1")
                if gap_open % 1 != 0 or gap_extend % 1 != 0:
                    raise ValueError("Gap Open and Gap extend must be whole numbers")

            if max_sequence_length > stretcher_length_limit:
                raise ValueError(
                    f"The longest sequence ({max_sequence_length} bases) exceeds the maximum allowed limit of {stretcher_length_limit} bases. "
                    "Please upload a file with shorter sequences.")

            # Define output paths
            alignment_file_path = os.path.join(results_dir, 'alignment.fasta')
            user_alignment_file_path = os.path.join(results_dir, 'user_alignment.fasta')
            processed_file_path = os.path.join(results_dir, 'alignment_processed.fasta')
            nucleotide_matrix_path = os.path.join(results_dir, 'nucleotide.xlsx')
            user_nucleotide_matrix_path = os.path.join(results_dir, 'user_nucleotide.xlsx')
            transratio_matrix_path = os.path.join(results_dir, 'transratio.xlsx')
            summary_features_path = os.path.join(results_dir, 'summary_features.xlsx')
            summary_alignment_path = os.path.join(results_dir, 'summary_alignment.xlsx')

            cleanup_needed = False
            
            # Insert session data
            session_manager.insert_session_data(
                session_id, file_path, psa_program, gap_open, gap_extend, num_sequences,
                alignment_file_path, user_alignment_file_path, processed_file_path,
                nucleotide_matrix_path, user_nucleotide_matrix_path, transratio_matrix_path, 
                summary_features_path, summary_alignment_path
            )

            return jsonify({
                "status": "success",
                "message": "Input processed successfully",
                "file_name": filename,
                "redirect_url": url_for('results.align_fasta')
            }), 200

        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            if cleanup_needed and file_path and os.path.exists(file_path):
                session_manager.end_session(session_id)
                logger.info(f"Cleaned up session: {session_id}")

    except Exception as e:
        logger.error(f"Pre-file handling error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error occurred"}), 500

def validate_uploaded_file(file_path, filename, file_bytes=None):
    """Common validation for both uploaded files and text-generated files"""
    # Check file size
    file_size = os.path.getsize(file_path)
    if file_size > 10 * 1024 * 1024:  # 10MB limit
        raise ValueError("File size exceeds 10MB limit")

    # Check MIME type if file_bytes is provided
    if file_bytes:
        mime_type = mimetypes.guess_type(filename)[0]
        if mime_type not in ["text/plain", None]:
            raise ValueError("Invalid file type")

    # Check for dangerous content
    if contains_executable_code(file_path):
        raise ValueError("Executable code detected. File rejected.")

    # Validate FASTA format
    if not is_valid_fasta(file_path):
        raise ValueError("Invalid FASTA file format")
