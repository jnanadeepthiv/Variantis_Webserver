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




# app/route/results.py
import logging
from logging.handlers import RotatingFileHandler
from flask import Blueprint, request, jsonify, render_template,current_app
import pandas as pd
import itertools
import psa
from Bio import SeqIO
import os
import numpy as np
from flask import Flask, render_template, redirect, url_for, request, send_file, jsonify, json, make_response,session
from io import StringIO
from flask_wtf.csrf import CSRFProtect,validate_csrf
from app.routes import session_manager  # For using the global instance
from app.utils.file_handlers import process_fasta_file, perform_alignment, process_alignments_files, calculate_transitions_transversions, count_transitions_transversions, extract_alignment_pair, colour_code_alignment
from app.utils.validators import validate_session

results_bp = Blueprint('results', __name__)


logger = logging.getLogger(__name__) 

@results_bp.route('/results') 
@validate_session  # Ensures session is valid before running the route
def align_fasta():
    try:
        session_id = request.cookies.get('session_id')  #  Retrieve from cookie
        
        session_manager = current_app.session_manager

        if session_manager is None:
            raise RuntimeError("session_manager is not initialized!")

        
        # Get the details of that particular session stored in the session_data table earlier
        session_data = session_manager.get_session_individual_details(session_id)
        if not session_data:
            return jsonify({"status": "error", "message": "Session data not found"}), 404

        

        # Process the FASTA file and generate results
        process_fasta_file(session_data['upload_file_path'], session_data['alignment_file_path'],
                        session_data['user_alignment_file_path'], session_data['psa_program'],
                        session_data['gap_open'], session_data['gap_extend'])
        process_alignments_files(session_data['alignment_file_path'], session_data['processed_file_path'])
        calculate_transitions_transversions(session_data['processed_file_path'],
                                            session_data['nucleotide_matrix_path'],
                                            session_data['user_nucleotide_matrix_path'],
                                            session_data['transratio_matrix_path'],
                                            session_data['summary_features_path'],
                                            session_data['summary_alignment_path'])
                                            

        
        # Render and return the results.html template
        return render_template('results.html')

    
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500  # Return JSON error
    

@results_bp.route('/all_results')
@validate_session  # Ensures session is valid before running the route
def all_results_section():
    try:
        # Get the session_id from the form data
        session_id = request.cookies.get('session_id')  #  Read from cookie
        
        session_manager = current_app.session_manager

        if session_manager is None:
            raise RuntimeError("session_manager is not initialized!")

        
        session_data = session_manager.get_session_individual_details(session_id)

        if not session_data:
            return jsonify({"status": "error", "message": "Session data not found"}), 404

        # Read the transition/transversion ratio matrix
        trans_matrix_path = session_data['transratio_matrix_path']
        trans_matrix = pd.read_excel(trans_matrix_path, index_col=0)

        # Read matrices from session-specific Excel file
        nuc_matrix_path = session_data['user_nucleotide_matrix_path']
        
        # Convert Excel sheets back to original dictionary format
        nuc_matrix = {}
        with pd.ExcelFile(nuc_matrix_path) as excel:
            df = excel.parse("User_Nucleotide Matrices")  # Read the sheet
            for _, row in df.iterrows():
                pair = row["Sequence Pair"]
                nuc_matrix[pair] = {
                    "A": row["A"],
                    "T": row["T"],
                    "G": row["G"],
                    "C": row["C"]
                }
        
        # Extract Query-to-ID Mapping from user_alignment_file_path
        query_header_map = []
        user_alignment_file_path = session_data['user_alignment_file_path']
        with open(user_alignment_file_path, 'r') as file:
            lines = file.readlines()
            capture = False
            for line in lines:
                if line.strip() == "Query-to-ID Mapping:":
                    capture = True
                    continue
                if capture and line.strip().startswith("=" * 70):
                    break
                if capture and line.strip():
                    query_header_map.append(line.strip())

        
        # Pass the matrices to the template
        return render_template('partials/all_results.html', trans_matrix=trans_matrix, nuc_matrix=nuc_matrix, query_header_map=query_header_map)

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@results_bp.route('/alignment', methods=['GET', 'POST'])
@validate_session  # Ensures session is valid before running the route
def alignment_section():
    if request.method == "GET":

        # Get the session_id from the form data
        session_id = request.cookies.get('session_id')  #  Read from cookie
        
        session_manager = current_app.session_manager

        if session_manager is None:
            raise RuntimeError("session_manager is not initialized!")

        
        # Retrieve session data
        session_data = session_manager.get_session_individual_details(session_id)
        if not session_data:
            return jsonify({"status": "error", "message": "Session data not found"}), 404

        # Pass num_sequences to the template
        no_seq = session_data['num_sequences']
        return render_template('partials/alignment.html', no_seq=no_seq, session_id=session_id)

    elif request.method == "POST":
        try:
            #print("POST request received")  # Debug statement
            
            csrf_token = request.headers.get('X-CSRF-TOKEN')
    

            # Validate CSRF token
            if not csrf_token:
                return jsonify({"status": "error", "message": {e}}), 400

            validate_csrf(csrf_token)  # Properly validate CSRF token
            
            data = request.get_json()
            #print("Received data:", data)  # Debug statement
            
            if not data:
                #print("No JSON data provided")  # Debug statement
                return jsonify({"error": "JSON data not provided"}), 400

            customquery = data.get("queryrequest")
            customsubject = data.get("subjectrequest")
            
            #print("Query:", customquery)  # Debug statement
            #print("Subject:", customsubject)  # Debug statement
            
            if not customquery or not customsubject:
                #print("Query or subject missing")  # Debug statement
                return jsonify({"error": "Both query and subject should be provided"}), 400
            if customquery == customsubject:
                #print("Query and subject are the same")  # Debug statement
                return jsonify({"error": "Query and subject should not be the same"}), 400

            # Retrieve session data
            session_id = data.get("session_id")
            #print("Session ID:", session_id)  # Debug statement
            
            session_manager = current_app.session_manager

            if session_manager is None:
                raise RuntimeError("session_manager is not initialized!")
            
            session_data = session_manager.get_session_individual_details(session_id)
            #print("Session data retrieved:", session_data)  # Debug statement
            
            if not session_data:
                #print("Session data not found")  # Debug statement
                return jsonify({"status": "error", "message": "Session data not found"}), 404

            # Read the processed file
            processed_file_path = session_data['processed_file_path']
            #print("Processed file path:", processed_file_path)  # Debug statement
            
            with open(processed_file_path, 'r') as f:
                processed_content = f.read()
            #print("Processed file content read successfully")  # Debug statement

            # Extract the alignment pair
            alignment_pair = extract_alignment_pair(processed_content, customquery, customsubject)
            #print("Alignment pair extracted:", alignment_pair)  # Debug statement
            
            if not alignment_pair:
                #print("Alignment pair not found")  # Debug statement
                return jsonify({"error": "Alignment pair not found"}), 404

            # Perform colour coding and generate statistics
            colour_coded_alignment, stats = colour_code_alignment(alignment_pair,customquery,customsubject)
            #print("Colour-coded alignment generated")  # Debug statement
            #print("Stats generated:", stats)  # Debug statement

            # Prepare the response
            response = {
                "message": "Data received in the backend",
                "query": customquery,
                "subject": customsubject,
                "colour_coded_alignment": colour_coded_alignment,
                "stats": stats
            }
            #print("Response prepared:", response)  # Debug statement
            return jsonify(response), 200

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

@results_bp.route('/summary_dashboard')
@validate_session # Ensures session is valid beofre running the route
def summary_dashboard_section():
    try:
        # Get the session_id from the form data
        session_id = request.cookies.get('session_id')  #  Read from cookie
        
        session_manager = current_app.session_manager

        if session_manager is None:
            raise RuntimeError("session_manager is not initialized!")

        
        session_data = session_manager.get_session_individual_details(session_id)

        if not session_data:
            return jsonify({"status": "error", "message": "Session data not found"}), 404

        # read the summary_features_excel
        summary_features_path = session_data['summary_features_path']
        summary_features_matrix = pd.read_excel(summary_features_path)
        
        #read the summary_alignment_excel
        summary_alignment_path = session_data['summary_alignment_path']
        summary_alignment_matrix = pd.read_excel(summary_alignment_path)
    
    # Pass the matrices to the template
        return render_template('partials/summary_dashboard.html', features_matrix=summary_features_matrix, alignment_matrix=summary_alignment_matrix)

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
    





@results_bp.route('/run_details')
@validate_session  # Ensures session is valid before running the route
def run_details_section():
    try:
        # Get the session_id from the form data
        session_id = request.cookies.get('session_id')  #  Read from cookie
        
        session_manager = current_app.session_manager

        if session_manager is None:
            raise RuntimeError("session_manager is not initialized!")

        
        # Retrieve session data
        session_data = session_manager.get_session_individual_details(session_id)
        if not session_data:
            return jsonify({"status": "error", "message": "Session data not found"}), 404

        # Prepare alignment parameters
        alignment_params = {
            "psa_program": session_data['psa_program'],
            "gap_open": session_data['gap_open'],
            "gap_extend": session_data['gap_extend'],
            "matrix": "EDNAFULL",  # Hardcoded 
            "sequence_type": "DNA",  # Hardcoded 
            "output_format": "FASTA"  # Hardcoded 
        }
        

        
        # Prepare file URLs for download
        files = {
            'nucleotide_matrix': url_for('results.download_file',  filename='nucleotide.xlsx'),
            'transratio_matrix': url_for('results.download_file',  filename='transratio.xlsx'),
            'user_alignment': url_for('results.download_file',  filename='user_alignment.fasta'),
            'summary_features':  url_for('results.download_file',  filename='summary_features.xlsx'),
            'summary_alignment':  url_for('results.download_file',  filename='summary_alignment.xlsx')
        }

        return render_template('partials/run_details.html', files=files, alignment_params=alignment_params)

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500



@results_bp.route('/download/<filename>')
@validate_session  # Ensures session is valid before running the route
def download_file(filename):
    session_id = request.cookies.get('session_id')  # Retrieve session ID from cookie
    
    session_manager = current_app.session_manager

    if session_manager is None:
        raise RuntimeError("session_manager is not initialized!")

    
    session_data = session_manager.get_session_individual_details(session_id)
    if not session_data:
        return jsonify({"status": "error", "message": "Session data not found"}), 404


    # Retrieve the correct file path from session_data
    file_path_map = {
        "nucleotide.xlsx": session_data['nucleotide_matrix_path'],
        "transratio.xlsx": session_data['transratio_matrix_path'],
        "user_alignment.fasta": session_data['user_alignment_file_path'],
        "summary_features.xlsx" : session_data['summary_features_path'],
        "summary_alignment.xlsx" : session_data['summary_alignment_path']
    }

    file_path = file_path_map.get(filename)
    if not file_path or not os.path.exists(file_path):
        return jsonify({"status": "error", "message": "File not found"}), 404

    # Send the file for download
    return send_file(file_path, as_attachment=True)
