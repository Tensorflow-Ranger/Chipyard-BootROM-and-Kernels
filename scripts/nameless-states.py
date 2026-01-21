import sys
import os

def parse_btor2_for_unnamed_states_and_inputs(filepath):
    """
    Parses a BTOR2 file to find and count state and input lines without symbolic names.

    Args:
        filepath (str): The path to the .btor2 file.

    Returns:
        A tuple containing:
        - total_states (int)
        - unnamed_states (int)
        - unnamed_state_lines (list)
        - total_inputs (int)
        - unnamed_inputs (int)
        - unnamed_input_lines (list)
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found at '{filepath}'")
        return (None,) * 6

    total_states = 0
    unnamed_states = 0
    unnamed_state_lines = []

    total_inputs = 0
    unnamed_inputs = 0
    unnamed_input_lines = []

    print(f"Starting analysis of '{filepath}'...")

    try:
        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                tokens = line.strip().split()
                if len(tokens) < 3:
                    continue

                kind = tokens[1]
                last_token = tokens[-1]

                has_name = not last_token.isdigit()

                if kind == 'state':
                    total_states += 1
                    if not has_name:
                        unnamed_states += 1
                        unnamed_state_lines.append(
                            f"Line {line_num}: {line.strip()}"
                        )

                elif kind == 'input':
                    total_inputs += 1
                    if not has_name:
                        unnamed_inputs += 1
                        unnamed_input_lines.append(
                            f"Line {line_num}: {line.strip()}"
                        )

    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return (None,) * 6

    return (
        total_states,
        unnamed_states,
        unnamed_state_lines,
        total_inputs,
        unnamed_inputs,
        unnamed_input_lines,
    )


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python check_btor2_names_v3.py <path_to_btor2_file> [--print-unnamed]")
        sys.exit(1)

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
        sys.exit(1)

    (
        total_states,
        unnamed_states,
        unnamed_state_lines,
        total_inputs,
        unnamed_inputs,
        unnamed_input_lines,
    ) = parse_btor2_for_unnamed_states_and_inputs(filepath)

    if total_states is None:
        sys.exit(1)

    print("\n--- Analysis Complete ---")

    # --- State summary ---
    print(f"Total 'state' lines found: {total_states}")
    print(f"State lines MISSING a name: {unnamed_states}")
    if total_states > 0:
        print(f"Percentage unnamed states: {(unnamed_states / total_states) * 100:.2f}%")

    print()

    # --- Input summary ---
    print(f"Total 'input' lines found: {total_inputs}")
    print(f"Input lines MISSING a name: {unnamed_inputs}")
    if total_inputs > 0:
        print(f"Percentage unnamed inputs: {(unnamed_inputs / total_inputs) * 100:.2f}%")

    print("-------------------------")

    if print_unnamed_flag:
        if unnamed_state_lines:
            print("\n--- Unnamed State Lines ---")
            for l in unnamed_state_lines:
                print(l)

        if unnamed_input_lines:
            print("\n--- Unnamed Input Lines ---")
            for l in unnamed_input_lines:
                print(l)

        if not unnamed_state_lines and not unnamed_input_lines:
            print("\nNo unnamed state or input lines found.")


if __name__ == "__main__":
    main()