#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse

# ==============================================================================
# CONFIGURATION
# ==============================================================================
INPUT_VERILOG = "combined_converted.v"
TOP_MODULE    = "RocketTile"  # Change this if your top module is different

# Intermediate filenames
FILE_EXT_DEFS   = "combined_with_ext.v"
FILE_FIXED      = "combined_syntax_fixed.v"
FILE_BLACKBOXED = "combined_blackboxed.v"
FILE_YOSYS_BTOR = "yosys_raw.btor2"
FILE_CLEANED    = "cleaned.btor2"
FILE_FINAL      = "final_output.btor2"
FILE_YOSYS_SCRIPT = "script.ys"

# ==============================================================================
# STEP IMPLEMENTATIONS
# ==============================================================================

def run_command(cmd_list, step_name):
    """Helper to run subprocess commands with error checking."""
    print(f"[{step_name}] Running: {' '.join(cmd_list)}")
    try:
        result = subprocess.run(cmd_list, check=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: Step '{step_name}' failed.")
        sys.exit(1)

def step_ext_defs():
    """Step 2: Add External Definitions"""
    run_command(
        ["python3", "ext_definition_adder.py", INPUT_VERILOG, "-o", FILE_EXT_DEFS],
        "Add Ext Defs"
    )

def step_fix_syntax():
    """Step 3: Fix Syntax (fix.py)"""
    run_command(
        ["python3", "fix.py", FILE_EXT_DEFS, "-o", FILE_FIXED],
        "Fix Syntax"
    )

def step_blackbox():
    """Step 4: Verilog Blackboxing"""
    run_command(
        ["python3", "verilog-blackboxing.py", FILE_FIXED, "-o", FILE_BLACKBOXED, "--boundary", TOP_MODULE],
        "Blackboxing"
    )

def step_yosys():
    """Step 5: Run Yosys"""
    # Generate the Yosys script dynamically to ensure it reads the correct file
    yosys_content = f"""
    read_verilog -formal {FILE_BLACKBOXED}
    hierarchy -check -top {TOP_MODULE}
    
    # Standard cleanup
    proc
    flatten
    memory_map
    
    # Handle blackboxes
    cutpoint -blackbox
    opt_clean
    
    # Create Miter (Identity check to verify structure)
    copy {TOP_MODULE} gold
    copy {TOP_MODULE} gate
    miter -equiv -make_outputs -make_outcmp gold gate miter_result
    
    # Prepare for export
    hierarchy -top miter_result
    flatten
    dffunmap
    memory_nordff
    opt_clean
    
    write_btor -x {FILE_YOSYS_BTOR}
    """
    
    with open(FILE_YOSYS_SCRIPT, "w") as f:
        f.write(yosys_content)
    
    run_command(["yosys", FILE_YOSYS_SCRIPT], "Yosys Synthesis")

def step_btor2_cleaner():
    """Step 6: Clean BTOR2"""
    run_command(
        ["python3", "btor2-cleaner.py", FILE_YOSYS_BTOR, FILE_CLEANED],
        "BTOR2 Cleaner"
    )

def step_replace_states():
    """Step 7: Replace States with Inputs"""
    run_command(
        ["python3", "replace_states_with_inputs.py", FILE_CLEANED, FILE_FINAL],
        "Replace States"
    )

def step_check_names():
    """Step 8: Check for Missing Names"""
    # Assuming nameless-states.py prints result to stdout and takes filename as arg
    # We add -v if the script supports it, otherwise just the file
    cmd = ["python3", "nameless-states.py", FILE_FINAL, "-v"]
    run_command(cmd, "Check Missing Names")

# ==============================================================================
# STEP REGISTRY
# ==============================================================================

# List of steps. 'id' corresponds to the user's workflow number.
FLOW = [
    {"id": 1, "desc": "Setup/Verify Input (Implicit)", "func": lambda: print(f"Input file: {INPUT_VERILOG}")},
    {"id": 2, "desc": "Generate Ext Definitions",      "func": step_ext_defs},
    {"id": 3, "desc": "Run Fix (Syntax Patcher)",      "func": step_fix_syntax},
    {"id": 4, "desc": "Apply Blackboxing",             "func": step_blackbox},
    {"id": 5, "desc": "Run Yosys (Generate BTOR2)",    "func": step_yosys},
    {"id": 6, "desc": "Run BTOR2 Cleaner",             "func": step_btor2_cleaner},
    {"id": 7, "desc": "Replace States with Inputs",    "func": step_replace_states},
    {"id": 8, "desc": "Check Missing Names",           "func": step_check_names},
]

# ==============================================================================
# MAIN LOGIC
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Rocket/BOOM Formal Verification Flow Automator")
    
    parser.add_argument('step_limit', nargs='?', type=int, 
                        help="Perform flow ONLY until this step number (inclusive). If omitted, runs all steps.")
    
    parser.add_argument('-l', '--list-steps', action='store_true', 
                        help="List all available steps and exit.")
    
    args = parser.parse_args()

    # Handle List Steps
    if args.list_steps:
        print("\n--- Available Flow Steps ---")
        for step in FLOW:
            print(f"Step {step['id']}: {step['desc']}")
        print("----------------------------")
        return

    # Check Input File
    if not os.path.exists(INPUT_VERILOG):
        print(f"Error: Input file '{INPUT_VERILOG}' not found in current directory.")
        sys.exit(1)

    # Determine limit
    limit = args.step_limit if args.step_limit is not None else 999

    print(f"Starting Flow (Target Step: {limit})...\n")

    for step in FLOW:
        if step['id'] > limit:
            print(f"\n--- Reached target step {limit}. Stopping. ---")
            break
            
        print(f"\n--- [Step {step['id']}] {step['desc']} ---")
        step['func']()

    print("\n--- Flow Complete ---")

if __name__ == "__main__":
    main()
