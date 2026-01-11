import sys
import os

def transform_btor2_states(input_path, output_path):
    """
    Reads a BTOR2-like file and transforms nameless 'state' lines into 'input' lines.

    - If a 'state' line has no symbolic name, it becomes 'id input sort'.
    - If a 'state' line has a symbolic name, it is left unchanged.
    - All other lines are passed through untouched.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at '{input_path}'")
        return

    print(f"Reading from: '{input_path}'")
    
    transformed_lines = []
    
    with open(input_path, 'r') as f_in:
        for line in f_in:
            stripped_line = line.strip()

            # Skip empty lines
            if not stripped_line:
                transformed_lines.append("")
                continue

            tokens = stripped_line.split()

            # Check if the line is a 'state' declaration
            # A valid state line must have at least an ID, the keyword 'state', and a sort ID.
            if len(tokens) >= 3 and tokens[1] == 'state':
                # Determine if the state has a symbolic name.
                # Our rule: If the last token is a number, it has no name.
                last_token = tokens[-1]
                
                if last_token.isdigit():
                    # This is a NAMELESS state. Transform it.
                    state_id = tokens[0]
                    state_sort = tokens[2]
                    new_line = f"{state_id} input {state_sort}"
                    transformed_lines.append(new_line)
                else:
                    # This is a NAMED state. Leave it as is.
                    transformed_lines.append(stripped_line)
            
            else:
                # This is not a state line. Pass it through unchanged.
                transformed_lines.append(stripped_line)

    # Write the processed content to the output file
    try:
        with open(output_path, 'w') as f_out:
            for line in transformed_lines:
                f_out.write(line + '\n')
        print(f"Success! Transformed BTOR2 file written to: '{output_path}'")
    except IOError as e:
        print(f"Error: Could not write to output file '{output_path}'. Reason: {e}")

def main():
    """
    Main function to run the script from the command line.
    """
    if len(sys.argv) != 3:
        print("Usage: python replace_nameless_states.py <input_file.btor2> <output_file.btor2>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    transform_btor2_states(input_file, output_file)

if __name__ == "__main__":
    main()