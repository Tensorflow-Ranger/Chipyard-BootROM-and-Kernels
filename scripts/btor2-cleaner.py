import sys
import os

def process_btor2_file(input_path, output_path):
    """
    Reads and cleans a non-standard BTOR2 file using a robust, multi-stage
    process that validates all potential signal names and handles all comment types.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at '{input_path}'")
        return

    print(f"Reading from: {input_path}")

    with open(input_path, 'r') as f:
        lines = f.readlines()

    processed_lines = []
    i = 0
    total_lines = len(lines)

    while i < total_lines:
        current_line_raw = lines[i].strip()

        # Skip empty lines or purely decorative comments like '; begin' or '; end'
        if not current_line_raw or current_line_raw.startswith(('; begin', '; end')):
            i += 1
            continue

        # --- STAGE 1: Clean the current line and identify its parts ---

        # First, remove any trailing decorative comment (e.g., '; combined_blackboxed.v...')
        line_no_trailing_comment = current_line_raw.split(';', 1)[0].strip()

        if not line_no_trailing_comment:
            i += 1
            continue

        tokens = line_no_trailing_comment.split()
        command_id = tokens[0]

        # Find the index of the LAST token that is a number.
        last_numeric_idx = -1
        for j, token in enumerate(tokens):
            if token.isdigit():
                last_numeric_idx = j
        
        # The base command is everything up to and including that last number.
        base_command_tokens = tokens[:last_numeric_idx + 1]
        base_command = ' '.join(base_command_tokens)
        
        # The inline symbol is everything after the last number.
        inline_symbol_tokens = tokens[last_numeric_idx + 1:]
        good_inline_name = ""
        if inline_symbol_tokens:
            potential_inline_name = ' '.join(inline_symbol_tokens)
            # A good inline name is one that does NOT contain '$'
            if '$' not in potential_inline_name:
                good_inline_name = potential_inline_name


        # --- STAGE 2: Hunt for a higher-priority name on the next line ---
        comment_name = "" # Default to no name from comments

        if (i + 1) < total_lines:
            next_line_stripped = lines[i + 1].strip()
            
            if next_line_stripped.startswith(';'):
                next_tokens = next_line_stripped.split()
                if len(next_tokens) >= 3 and next_tokens[1] == command_id:
                    # This is the name comment. Extract the potential name.
                    potential_name_from_comment = ' '.join(next_tokens[2:])
                    
                    # VALIDATION: Only accept the name if it is NOT junk.
                    if '$' not in potential_name_from_comment:
                        name = potential_name_from_comment
                        if name.startswith('\\'):
                            name = name[1:]
                        comment_name = name
                    
                    i += 1  # Consume the comment line (whether its name was good or junk)

        # --- STAGE 3: Reconstruct the final line with correct name precedence ---
        final_line = base_command
        
        # The name from the comment on the next line has the HIGHEST priority.
        if comment_name:
            final_line += f" {comment_name}"
        # If there was no valid comment name, fall back to the valid INLINE name.
        elif good_inline_name:
            final_line += f" {good_inline_name}"
            
        processed_lines.append(final_line)
        
        i += 1

    # --- Write the processed content to the output file ---
    try:
        with open(output_path, 'w') as f:
            for line in processed_lines:
                f.write(line + '\n')
        print(f"Success! Cleaned BTOR2 file written to: {output_path}")
    except IOError as e:
        print(f"Error: Could not write to output file '{output_path}'. Reason: {e}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python clean_btor2_final.py <input_file.btor2> <output_file.btor2>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    process_btor2_file(input_file, output_file)

if __name__ == "__main__":
    main()