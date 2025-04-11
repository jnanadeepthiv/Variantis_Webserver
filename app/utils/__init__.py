from app.utils.file_handlers import (
    cleanup_job, contains_executable_code, is_valid_fasta, process_fasta_file,
    perform_alignment, process_alignments_files, calculate_transitions_transversions,
    count_transitions_transversions, extract_alignment_pair, colour_code_alignment
)
from app.utils.validators import validate_session, validate_csrf_token