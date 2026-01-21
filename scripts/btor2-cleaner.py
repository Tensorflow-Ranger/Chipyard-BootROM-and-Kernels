import sys
import os

def process_btor2_file(input_path, output_path):
    """
    Reads BTOR2, collects names from uext lines (inline or comment next-line),
    and propagates those names back onto input lines if missing.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at '{input_path}'")
        return

    with open(input_path, 'r', encoding='utf8') as f:
        lines = f.readlines()

    total_lines = len(lines)

    # ---------------------------
    # PRE-PASS: collect names from uext and output lines
    # ---------------------------
    input_name_map = {}  # maps source_id (str) -> name (str)

    i = 0
    while i < total_lines:
        raw = lines[i].rstrip('\n')
        stripped = raw.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Remove trailing comments for token parsing
        line_no_trail = stripped.split(';', 1)[0].strip()
        if not line_no_trail:
            i += 1
            continue

        parts = line_no_trail.split()
        if len(parts) < 2:
            i += 1
            continue

        op = parts[1]

        # Handle identity-like ops that can carry names
        if op in ('uext', 'output'):
            command_id = parts[0]

            # Extract source ID depending on op
            if op == 'uext':
                # <id> uext <width> <src> <ext> [name]
                if len(parts) < 5:
                    i += 1
                    continue
                src_id = parts[3]
            else:  # output
                # <id> output <src> [name]
                if len(parts) < 3:
                    i += 1
                    continue
                src_id = parts[2]

            # --- Attempt 1: inline name after last numeric token ---
            last_numeric_idx = -1
            for j, tok in enumerate(parts):
                if tok.isdigit():
                    last_numeric_idx = j

            candidate = None
            if last_numeric_idx != -1 and last_numeric_idx + 1 < len(parts):
                candidate = ' '.join(parts[last_numeric_idx + 1:]).strip()

            # --- Attempt 2: next-line comment ; <id> <name> ---
            if not candidate and (i + 1) < total_lines:
                nxt = lines[i + 1].strip()
                if nxt.startswith(';'):
                    nxt_tokens = nxt.split()
                    if len(nxt_tokens) >= 3 and nxt_tokens[1] == command_id:
                        candidate = ' '.join(nxt_tokens[2:]).strip()
                        i += 1  # consume the comment line

            # --- Validate and record ---
            if candidate:
                if candidate.startswith('\\'):
                    candidate = candidate[1:]
                if '$' not in candidate:
                    if src_id not in input_name_map:
                        input_name_map[src_id] = candidate

        i += 1

    # ---------------------------
    # MAIN PASS: original logic, but attach names to input lines using input_name_map
    # ---------------------------
    processed_lines = []
    i = 0

    while i < total_lines:
        current_line_raw = lines[i].strip()

        # Skip empty lines or purely decorative comments like '; begin' or '; end'
        if not current_line_raw or current_line_raw.startswith(('; begin', '; end')):
            i += 1
            continue

        # Remove any trailing decorative comment (e.g., '; combined_blackboxed.v...')
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
                if good_inline_name.startswith('\\'):
                    good_inline_name = good_inline_name[1:]

        # --- STAGE 2: Hunt for a higher-priority name on the next line ---
        comment_name = ""  # Default to no name from comments

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

        # Highest priority: name from following comment
        if comment_name:
            final_line += f" {comment_name}"
        # Next: inline name already on this line
        elif good_inline_name:
            final_line += f" {good_inline_name}"
        # NEW: if this is an input, try to inherit name from uext usage
        elif len(tokens) > 1 and tokens[1] == 'input' and command_id in input_name_map:
            final_line += f" {input_name_map[command_id]}"

        processed_lines.append(final_line)
        i += 1

    # --- Write the processed content to the output file ---
    try:
        with open(output_path, 'w', encoding='utf8') as f:
            for line in processed_lines:
                f.write(line + '\n')
        print(f"Success! Cleaned BTOR2 file written to: {output_path}")
    except IOError as e:
        print(f"Error: Could not write to output file '{output_path}'. Reason: {e}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 btor2-cleaner.py <input.btor2> <output.btor2>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    process_btor2_file(input_file, output_file)

if __name__ == "__main__":
    main()
