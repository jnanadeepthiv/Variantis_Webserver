import os
from Bio import SeqIO
from io import StringIO
import pandas as pd
import numpy as np
import psa
import re
import itertools
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, send_file, jsonify, json, make_response,session,current_app
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)



def cleanup_job(app):
    """Cleanup expired sessions automatically every 15 minutes."""
    with app.app_context():  # Create application context for the job
        try:
            session_manager = current_app.session_manager

            if session_manager is None:
                raise RuntimeError("session_manager is not initialized!")

            session_manager.cleanup_inactive_sessions(expiration_minutes=15)
        except Exception as e:
            app.logger.error(f"Cleanup job failed: {e}")

def contains_executable_code(file_path):
    """
    Check if the file contains dangerous keywords or binary data.
    """
    dangerous_keywords = [
        "#!/", "exec", "import os", "import sys", "subprocess", "rm -rf", 
        "<script>", "eval(", "system(", "popen(", "fork(", "execve("
    ]
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                # Check for dangerous keywords
                if any(keyword.lower() in line.lower() for keyword in dangerous_keywords):
                    return True
    except UnicodeDecodeError:  # File contains non-text (binary data)
        return True
    return False

def is_valid_fasta(file_path):
    """
    Validate if the file is a valid FASTA file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            # Check if the first line starts with '>'
            if not first_line.startswith(">"):
                return False
    except UnicodeDecodeError:  # File contains non-text (binary data)
        return False
    return True


def process_fasta_file(file_path, output_alignment, user_output_alignment, psa_program, gap_open, gap_extend):
    """
    Process the input FASTA file, perform alignments, and write results.
    """
    try:
        
        # Use a context manager to open the file safely
        with open(file_path, 'r') as fasta_file:
            records = list(SeqIO.parse(fasta_file, 'fasta'))  # Parse the file
            
        # Check if any records were parsed
        if not records:
            raise ValueError("The uploaded file is not a valid FASTA file.")
        
        # Check if at least two sequences are present
        if len(records) < 2:
            raise ValueError("At least two sequences must be present in the uploaded FASTA file.")

        
        sequences = {f"query{i+1:03d}": record for i, record in enumerate(records)}
        logger.info(f"Processed {len(sequences)} sequences.")

        with open(user_output_alignment, 'w') as user_file, open(output_alignment, 'w') as calc_file:
            user_file.write("Query-to-ID Mapping:\n")
            for qid, record in sequences.items():
                user_file.write(f"{qid}: {record.description}\n")
            user_file.write("\n" + "=" * 70 + "\n\n")

            for qid, sid in itertools.combinations(sequences.keys(), 2):
                qseq = str(sequences[qid].seq)
                sseq = str(sequences[sid].seq)
                qdescription = sequences[qid].description
                sdescription = sequences[sid].description

                alignment = perform_alignment(qid, sid, qseq, sseq, psa_program, gap_open, gap_extend)
                user_file.write(f"Alignment of \n [{qid}]:{qdescription}  and \n [{sid}]:{sdescription} :\n")
                user_file.write(alignment.fasta())
                user_file.write("\n" + "=" * 70 + "\n")

                calc_file.write(alignment.fasta())
                calc_file.write("\n" + "=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Error processing FASTA file: {e}", exc_info=True)
        raise ValueError(f"Error processing FASTA file: {e}")

def perform_alignment(qi_d, si_d, qseq, sseq, psa_program, gap_open, gap_extend):
    """
    Performing pairwise alignment using user updated parameters.
    """
    if psa_program == 'stretcher':
        alignment_result = psa.stretcher(moltype='nucl', qid=qi_d, sid=si_d, qseq=qseq, sseq=sseq, matrix="EDNAFULL", gapopen=gap_open, gapextend=gap_extend)
    else:
        alignment_result = psa.needle(moltype='nucl', qid=qi_d, sid=si_d, qseq=qseq, sseq=sseq, matrix="EDNAFULL", gapopen=gap_open, gapextend=gap_extend)

    return alignment_result


def process_alignments_files(output_alignment, output_single_line_fasta):
    """
    Convert multi-line FASTA alignments to single-line format.
    """
    try:
        delimiter = "=" * 70
        with open(output_alignment, "r") as infile, open(output_single_line_fasta, "w") as outfile:
            file_content = infile.read()
            blocks = file_content.split(delimiter)

            for block in blocks:
                if not block.strip():
                    continue
                block_as_file = StringIO("\n".join(block.strip().splitlines()))
                
                # Attempt to parse the block as a FASTA file
                records = list(SeqIO.parse(block_as_file, "fasta"))
                
                # Check if any records were parsed
                if not records:
                    raise ValueError("Invalid FASTA block in alignment file.")

                for record in records:
                    outfile.write(f">{record.description}\n")
                    outfile.write(f"{str(record.seq).replace('\n', '')}\n")
                outfile.write(delimiter + "\n")

    except Exception as e:
        logger.error(f"Error processing alignment file: {e}", exc_info=True)
        raise ValueError(f"Error processing alignment file: {e}")

def calculate_transitions_transversions(output_single_line_fasta, nucleotide_excel, user_nucleotide_excel, transratio_excel,summary_features_excel,summary_alignment_excel):
    """
    Calculate transitions, transversions, and generate output files.
    """
    try:
        delimiter = "=" * 70
        transition_transversion_matrix = pd.DataFrame()
        summary_features_matrix = pd.DataFrame(columns=[
            'Sequence_Pair',
            'Transition_Count',
            'Transition_Percentage',
            'Transversion_Count',
            'Transversion_Percentage',
            'Gap_Count',
            'Gap_Percentage',
            'Identical_Count',
            'Identical_Percentage'
        ])
        summary_alignment_matrix = pd.DataFrame(columns=[
            'Sequence_Pair',
            'Query_1_Length',
            'Query_2_Length',
            'Aligned_Length'
        ])
        nucleotide_matrices = {}

        with open(output_single_line_fasta, "r") as trans_infile:
            trans_file_content = trans_infile.read()
            blocks = trans_file_content.split(delimiter)

            for block in blocks:
                if not block.strip():
                    continue
                block_as_file = StringIO("\n".join(block.strip().splitlines()))
                
                # Attempt to parse the block as a FASTA file
                records = list(SeqIO.parse(block_as_file, "fasta"))
                
                # Check if any records were parsed
                if not records:
                    raise ValueError("Invalid FASTA block in transitions/transversions file.")

                if len(records) != 2:
                    logger.warning(f"Skipping block with {len(records)} sequences (expected 2):\n{block}")
                    continue
                
                # Extract "query1" from ">query1 1-35"
                seq1_header= records[0].description
                seq2_header = records[1].description
                seq1_header= seq1_header.strip().lower().split()[0][0:] 
                seq2_header= seq2_header.strip().lower().split()[0][0:] 
                
                pair_name = f"{seq1_header}_vs_{seq2_header}" 

                seq1 =  str(records[0].seq).replace('\n', '')
                seq2 =  str(records[1].seq).replace('\n', '')
                
                # Get pre-aligned lengths from original sequences
                seq1_prealigned = len(str(records[0].seq).replace('-', ''))
                seq2_prealigned = len(str(records[1].seq).replace('-', ''))
                aligned_length = len(seq1)  # Length after alignment
                
                # Count transitions and transversions
                stats, matrix = count_transitions_transversions(seq1, seq2)

                # Update transition/transversion ratio matrix
                transition_transversion_matrix.loc[seq1_header, seq2_header] = stats['ratio']
                transition_transversion_matrix.loc[seq2_header, seq1_header] = stats['ratio']
                
                # Store nucleotide matrix
                nucleotide_matrices[pair_name] = matrix
                
                # Update summary features matrix
                summary_features_matrix.loc[len(summary_features_matrix)] = {
                    'Sequence_Pair': pair_name,
                    'Transition_Count': stats['transitions'],
                    'Transition_Percentage': stats['transition_percent'],
                    'Transversion_Count': stats['transversions'],
                    'Transversion_Percentage': stats['transversion_percent'],
                    'Gap_Count': stats['gap_count'],
                    'Gap_Percentage': stats['gap_percent'],
                    'Identical_Count': stats['identical'],
                    'Identical_Percentage': stats['identical_percent']
                }
                
                # Update summary alignment matrix
                summary_alignment_matrix.loc[len(summary_alignment_matrix)] = {
                    'Sequence_Pair': pair_name,
                    'Query_1_Length': seq1_prealigned,
                    'Query_2_Length': seq2_prealigned,
                    'Aligned_Length': aligned_length
                }
                


        # Sort the index and columns of the transition_transversion_matrix
        transition_transversion_matrix = transition_transversion_matrix.sort_index(axis=0).sort_index(axis=1)
        
        transition_transversion_matrix = transition_transversion_matrix.fillna("-")
        
        

        #downloadable_nucleotide_excel
        with pd.ExcelWriter(nucleotide_excel) as writer:
            for pair, matrix in nucleotide_matrices.items():
                # Convert the substitution matrix into a DataFrame
                matrix_df = pd.DataFrame.from_dict(matrix, orient="index", columns=matrix.keys())
                matrix_df.index.name = "Base"  # Set index name explicitly
                #print(f"\nSubstitution Matrix for {pair}:")
                #print(matrix_df)
                # Write the DataFrame to a new sheet
                matrix_df.to_excel(writer, sheet_name=pair, index_label="Base")
                
        # User_nucleotide_Excel_display_on_web
        with pd.ExcelWriter(user_nucleotide_excel) as writer:
            # Create a DataFrame for the nucleotide matrices
            nuc_df = pd.DataFrame(columns=["Sequence Pair", "A", "T", "G", "C"])

            for pair, matrix in nucleotide_matrices.items():
                # Convert the substitution matrix into a row for the DataFrame
                row = {
                    "Sequence Pair": pair,
                    "A": matrix['A'],
                    "T": matrix['T'],
                    "G": matrix['G'],
                    "C": matrix['C']
                }
                # Append the row to the DataFrame using pd.concat()
                nuc_df = pd.concat([nuc_df, pd.DataFrame([row])], ignore_index=True)


            # Write the DataFrame to Excel
            nuc_df.to_excel(writer, sheet_name="User_Nucleotide Matrices", index=False)
        transition_transversion_matrix.to_excel(transratio_excel)
        summary_features_matrix.to_excel(summary_features_excel, index=False)
        summary_alignment_matrix.to_excel(summary_alignment_excel, index=False)


    except Exception as e:
        logger.error(f"Error calculating transitions/transversions: {e}", exc_info=True)
        raise ValueError(f"Error calculating transitions/transversions: {e}")

def count_transitions_transversions(seq1, seq2):
    """
    Counting the transitions and Transversionss and their Ratio.
    """
    purines = {'A', 'G'}
    pyrimidines = {'C', 'T'}
    # Define a set of ambiguous nucleotide symbols
    ambiguous_symbols = {'-', 'N', 'R', 'Y', 'K', 'M', 'S', 'W', 'B', 'D', 'H', 'V', 'U'}
    transitions, transversions, identical, gap_count = 0, 0 , 0, 0
    total_length = len(seq1)

    # Initialize nucleotide substitution matrix
    nucleotide_set = 'ACGT'
    matrix = {base1: {base2: 0 for base2 in nucleotide_set} for base1 in nucleotide_set}

    for b1, b2 in zip(seq1, seq2):
        if b1 == '-' or b2 == '-':  # Count all gaps
            gap_count += 1
            continue
        if b1 in ambiguous_symbols or b2 in ambiguous_symbols:
            continue
        if b1 not in nucleotide_set or b2 not in nucleotide_set:
            raise ValueError(f"Invalid base pair: b1={b1}, b2={b2}")
        if b1 not in nucleotide_set or b2 not in nucleotide_set:
            #print(f"Skipping invalid bases: b1={b1}, b2={b2}")
            continue
        if b1 == b2:
            identical += 1
            continue # i wnat to calucute the no of identical nucleotides also.

        matrix[b1][b2] += 1

        # Determine transition or transversion
        if (b1 in purines and b2 in purines) or (b1 in pyrimidines and b2 in pyrimidines):
            transitions += 1
        else:
            transversions += 1
    
    # Print the substitution matrix for debugging
    #print("\nNucleotide Substitution Matrix:")
    #for base1, row in matrix.items():
        #print(f"{base1}: {row}")
    #print(transitions,transversions)
    
    # Calculate percentages
    transition_percent = (transitions / total_length) * 100 if total_length > 0 else 0
    transversion_percent = (transversions / total_length) * 100 if total_length > 0 else 0
    identical_percent = (identical / total_length) * 100 if total_length > 0 else 0
    gap_percent = (gap_count / total_length) * 100 if total_length > 0 else 0
    
    
    ratio = f"{transitions / transversions:.3f}" if transversions != 0 else "Undefined"
    return {
        'transitions': transitions,
        'transversions': transversions,
        'identical': identical,
        'gap_count': gap_count,
        'transition_percent': round(transition_percent, 2),
        'transversion_percent': round(transversion_percent, 2),
        'identical_percent': round(identical_percent, 2),
        'gap_percent': round(gap_percent, 2),
        'total_length': total_length,
        'ratio': ratio
    }, matrix


def extract_alignment_pair(processed_content, query, subject):
    """
    Extract the alignment pair for the given query and subject.
    Normalize the input and match only the relevant part of the header.
    """
    # Normalize the input
    query = query.lower().replace(" ", "")
    subject = subject.lower().replace(" ", "")

    blocks = processed_content.split("=" * 70)
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().splitlines()
        header1 = lines[0].strip().lower().split()[0][1:]  # Extract "query1" from ">query1 1-35"
        seq1 = lines[1].strip()
        header2 = lines[2].strip().lower().split()[0][1:]  # Extract "query2" from ">query2 1-35"
        seq2 = lines[3].strip()

        if query == header1 and subject == header2:
            return (seq1, seq2)
        elif query == header2 and subject == header1:
            return (seq2, seq1)
    return None

def colour_code_alignment(alignment_pair,query, subject):
    """
    Compare the sequences and apply colour coding.
    Calculate percentages for the pie chart.
    """
    # Define color mapping
    color_map = {
        "identical": "green",
        "transition": "orange",
        "transversion": "red",
        "gap": "black",
        "unknown": "grey"  # Add a color for N (unknown)
        
    }

    seq1, seq2 = alignment_pair
    stats = {
        "identical": 0,
        "transitions": 0,
        "transversions": 0,
        "gaps": 0,
        "unknown": 0,  # Add a counter for N
        "total_length": len(seq1)
    }

    purines = {'A', 'G'}
    pyrimidines = {'C', 'T'}
    ambiguous_symbols = {'N', 'R', 'Y', 'K', 'M', 'S', 'W', 'B', 'D', 'H', 'V','U'}  # Excludes '-'

    # Function to wrap sequences into lines of 50 characters
    def wrap_sequence(sequence, length=50):
        return [sequence[i:i+length] for i in range(0, len(sequence), length)]

    # Wrap the sequences before applying HTML tags
    wrapped_seq1 = wrap_sequence(seq1)
    wrapped_seq2 = wrap_sequence(seq2)

    colour_coded_alignment = []

    for line1, line2 in zip(wrapped_seq1, wrapped_seq2):
        colour_coded_line1 = []
        colour_coded_line2 = []

        for char1, char2 in zip(line1, line2):
            if char1 == char2:
                color = color_map["identical"]
                stats["identical"] += 1
            elif char1 == '-' or char2 == '-':
                color = color_map["gap"]
                stats["gaps"] += 1
            elif char1 in ambiguous_symbols or char2 in ambiguous_symbols:  
                color = color_map["unknown"]
                stats["unknown"] += 1
            elif (char1 in purines and char2 in purines) or (char1 in pyrimidines and char2 in pyrimidines):
                color = color_map["transition"]
                stats["transitions"] += 1
            else:
                color = color_map["transversion"]
                stats["transversions"] += 1

            # Apply color to both sequences
            colour_coded_line1.append(f'<span style="color: {color}">{char1}</span>')
            colour_coded_line2.append(f'<span style="color: {color}">{char2}</span>')

        # Combine the lines with line breaks
        colour_coded_alignment.append(f"{query}: {''.join(colour_coded_line1)}<br>{subject}: {''.join(colour_coded_line2)}<br><br>")

    # Calculate percentages
    total_length = stats["total_length"]
    stats["identical_percent"] = (stats["identical"] / total_length) * 100
    stats["transitions_percent"] = (stats["transitions"] / total_length) * 100
    stats["transversions_percent"] = (stats["transversions"] / total_length) * 100
    stats["gaps_percent"] = (stats["gaps"] / total_length) * 100
    stats["unknown_percent"] = (stats["unknown"] / total_length) * 100


    # Combine the wrapped and color-coded alignment into a single string
    wrapped_alignment = "".join(colour_coded_alignment)

    return wrapped_alignment, stats
