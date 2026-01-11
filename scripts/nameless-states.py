#  Figures out which lines in a BTOR2 file are state lines without symbolic names.
# Also tells you how many of them. 
import sys
import os

def parse_btor2_for_unnamed_states(filepath):
    """
    Parses a BTOR2 file to find and count state lines without a symbolic name.

    Args:
        filepath (str): The path to the .btor2 file.

    Returns:
        A tuple containing:
        - total_states (int): The total number of state lines found.
        - unnamed_states (int): The number of state lines without a name.
        - unnamed_lines_list (list): A list of the actual unnamed state lines.
    """
    # --- Input Validation ---
    if not os.path.exists(filepath):
        print(f"Error: File not found at '{filepath}'")
        return None, None, None
    if not filepath.endswith('.btor2'):
        print(f"Warning: File '{filepath}' does not have a .btor2 extension.")

    # --- Initialization ---
    total_states = 0
    unnamed_states = 0
    unnamed_lines_list = []
    
    print(f"Starting analysis of '{filepath}'...")
    try:
        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                # Split the line into tokens based on whitespace
                tokens = line.strip().split()

                # A valid 'state' line must have at least 3 tokens (e.g., "id state width")
                # and the second token must be the keyword 'state'.
                if len(tokens) >= 3 and tokens[1] == 'state':
                    total_states += 1

                    # The symbolic name, if it exists, is always the last token.
                    # A symbolic name is a string that is not a plain number.
                    last_token = tokens[-1]
                    
                    # If the last token consists only of digits, it must be a node ID,
                    # which means there is no symbolic name present.
                    if last_token.isdigit():
                        unnamed_states += 1
                        # Store the line number and content for optional printing
                        unnamed_lines_list.append(f"Line {line_num}: {line.strip()}")

    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None, None, None

    return total_states, unnamed_states, unnamed_lines_list

def main():
    """
    Main function to run the script from the command line.
    """
    # --- Argument Parsing ---
    args = sys.argv[1:]
    if not args:
        print("Usage: python check_btor2_names_v2.py <path_to_btor2_file> [--print-unnamed]")
        sys.exit(1)

    # Find the filepath and check for the optional flag
    filepath = None
    print_unnamed_flag = False
    
    for arg in args:
        if arg == '--print-unnamed':
            print_unnamed_flag = True
        elif not arg.startswith('--'):
            filepath = arg
        else:
            print(f"Unknown option: {arg}")
            sys.exit(1)
            
    if not filepath:
        print("Error: No btor2 file specified.")
        print("Usage: python check_btor2_names_v2.py <path_to_btor2_file> [--print-unnamed]")
        sys.exit(1)

    # --- Run Analysis ---
    total_states, unnamed_states, unnamed_lines_list = parse_btor2_for_unnamed_states(filepath)

    if total_states is None:
        # An error occurred during parsing, exit gracefully.
        sys.exit(1)
        
    # --- Print Summary ---
    print("\n--- Analysis Complete ---")
    print(f"Total 'state' lines found: {total_states}")
    print(f"State lines MISSING a name: {unnamed_states}")

    if total_states > 0:
        named_states = total_states - unnamed_states
        percentage_unnamed = (unnamed_states / total_states) * 100
        print(f"State lines WITH a name:    {named_states}")
        print(f"Percentage of unnamed states: {percentage_unnamed:.2f}%")
    print("-------------------------")

    # --- Optionally Print Unnamed Lines ---
    if print_unnamed_flag:
        if unnamed_lines_list:
            print("\n--- Unnamed State Lines Found ---")
            for line in unnamed_lines_list:
                print(line)
            print("---------------------------------")
        else:
            print("\nNo unnamed state lines were found to print.")


if __name__ == "__main__":
    main()