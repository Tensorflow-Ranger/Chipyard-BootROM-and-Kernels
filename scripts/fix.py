#!/usr/bin/env python3
"""
BOOM Verilog Patcher
--------------------
This script performs multiple passes on a Verilog file to fix synthesis and syntax issues:
1. Replaces specific broken modules with corrected versions.
2. Fixes operator precedence in ternary operations (e.g., `a == b ?`).
3. Fixes dangling 'if' statements where the body was stripped (unexpected TOK_END).

Usage:
    python3 patch_boom_verilog.py input_file.v -o output_file.v
"""

import re
import argparse
import sys
import os

# ==============================================================================
# CONFIGURATION: CORRECTED MODULE DEFINITIONS
# ==============================================================================

REPLACEMENT_MODULES = {
    "UARTTx": r"""
module UARTTx (
	clock,
	reset,
	io_en,
	io_in_ready,
	io_in_valid,
	io_in_bits,
	io_out,
	io_div,
	io_nstop
);
	input clock;
	input reset;
	input io_en;
	output wire io_in_ready;
	input io_in_valid;
	input [7:0] io_in_bits;
	output wire io_out;
	input [15:0] io_div;
	input io_nstop;

	// Internal Wires
	wire [31:0] _plusarg_reader_1_out;
	wire [31:0] _plusarg_reader_out;
	wire io_in_ready_0;
	wire _GEN;
	wire pulse;
	wire _GEN_0;
	wire _GEN_1;
	wire [31:0] _RANDOM [0:0];

	// Internal Registers
	reg [15:0] prescaler;
	reg [3:0] counter;
	reg [8:0] shifter;
	reg out;

	// Continuous Assignments
	assign io_in_ready_0 = io_en & ~|counter;
	assign _GEN = io_in_ready_0 & io_in_valid;
	assign pulse = prescaler == 16'h0000;
	assign _GEN_0 = _GEN & |_plusarg_reader_out;
	assign _GEN_1 = pulse & |counter;
	assign io_in_ready = io_in_ready_0;
	assign io_out = out;

	// Procedural Logic
	always @(posedge clock) begin
		if (reset) begin
			prescaler <= 16'h0000;
			counter <= 4'h0;
			out <= 1'h1;
		end
		else begin
			if (|counter)
				prescaler <= (pulse ? io_div : prescaler - 16'h0001);
			if (_GEN_1) begin
				counter <= counter - 4'h1;
				out <= shifter[0];
			end
			else if (_GEN_0)
				counter <= (io_nstop ? 4'hb : 4'h0) | (io_nstop ? 4'h0 : 4'ha);
		end
		if (_GEN_1)
			shifter <= {1'h1, shifter[8:1]};
		else if (_GEN_0)
			shifter <= {io_in_bits, 1'h0};
	end

	// Module Instantiations
	plusarg_reader #(
		.DEFAULT(1),
		.FORMAT("uart_tx=%d"),
		.WIDTH(32)
	) plusarg_reader(.out(_plusarg_reader_out));

	plusarg_reader #(
		.DEFAULT(0),
		.FORMAT("uart_tx_printf=%d"),
		.WIDTH(32)
	) plusarg_reader_1(.out(_plusarg_reader_1_out));

endmodule
""",

    "UARTTx_TestHarness_UNIQUIFIED": r"""
module UARTTx_TestHarness_UNIQUIFIED (
	clock,
	reset,
	io_en,
	io_in_ready,
	io_in_valid,
	io_in_bits,
	io_out,
	io_div,
	io_nstop
);
	input clock;
	input reset;
	input io_en;
	output wire io_in_ready;
	input io_in_valid;
	input [7:0] io_in_bits;
	output wire io_out;
	input [15:0] io_div;
	input io_nstop;

	// Internal Wires
	wire [31:0] _plusarg_reader_1_out;
	wire [31:0] _plusarg_reader_out;
	wire io_in_ready_0;
	wire _GEN;
	wire pulse;
	wire _GEN_0;
	wire _GEN_1;
	wire [31:0] _RANDOM [0:0];

	// Internal Registers
	reg [15:0] prescaler;
	reg [3:0] counter;
	reg [8:0] shifter;
	reg out;

	// Continuous Assignments
	assign io_in_ready_0 = io_en & ~|counter;
	assign _GEN = io_in_ready_0 & io_in_valid;
	assign pulse = prescaler == 16'h0000;
	assign _GEN_0 = _GEN & |_plusarg_reader_out;
	assign _GEN_1 = pulse & |counter;
	assign io_in_ready = io_in_ready_0;
	assign io_out = out;

	// Procedural Logic
	always @(posedge clock) begin
		if (reset) begin
			prescaler <= 16'h0000;
			counter <= 4'h0;
			out <= 1'h1;
		end
		else begin
			if (|counter)
				prescaler <= (pulse ? io_div : prescaler - 16'h0001);
			if (_GEN_1) begin
				counter <= counter - 4'h1;
				out <= shifter[0];
			end
			else if (_GEN_0)
				counter <= (io_nstop ? 4'hb : 4'h0) | (io_nstop ? 4'h0 : 4'ha);
		end
		if (_GEN_1)
			shifter <= {1'h1, shifter[8:1]};
		else if (_GEN_0)
			shifter <= {io_in_bits, 1'h0};
	end

	// Module Instantiations
	plusarg_reader #(
		.DEFAULT(1),
		.FORMAT("uart_tx=%d"),
		.WIDTH(32)
	) plusarg_reader(.out(_plusarg_reader_out));

	plusarg_reader #(
		.DEFAULT(0),
		.FORMAT("uart_tx_printf=%d"),
		.WIDTH(32)
	) plusarg_reader_1(.out(_plusarg_reader_1_out));

endmodule
"""
}

# ==============================================================================
# PASS 1: MODULE REPLACEMENT
# ==============================================================================

def pass_replace_modules(content):
    """
    Pass 1: Replaces entire modules defined in the REPLACEMENT_MODULES dict.
    """
    replaced_names = []
    
    # Matches "module Name ... endmodule" (non-greedy)
    # re.DOTALL makes '.' match newlines
    pattern = re.compile(r"\bmodule\s+(\w+).*?endmodule", re.DOTALL)

    def replacement_handler(match):
        module_name = match.group(1)
        if module_name in REPLACEMENT_MODULES:
            replaced_names.append(module_name)
            return REPLACEMENT_MODULES[module_name].strip()
        return match.group(0)

    new_content = pattern.sub(replacement_handler, content)
    
    print(f"[Pass 1] Modules Replaced: {len(replaced_names)}")
    for name in replaced_names:
        print(f"    - {name}")
        
    return new_content

# ==============================================================================
# PASS 2: TERNARY OPERATOR PRECEDENCE
# ==============================================================================

def pass_fix_ternary(content):
    """
    Pass 2: Fixes precedence issues like: 
    enq_ptr_value == 4'hb ? 
    to 
    (enq_ptr_value == 4'hb) ?
    """
    # Pattern: Variable == 4'hb ?
    # Group 1: Variable Name
    # Group 2: Constant (4'hb or similar hex)
    pattern = re.compile(r"([a-zA-Z0-9_]+)\s*==\s*(4'h[0-9a-fA-F]+)\s*\?")
    replacement = r"(\1 == \2) ?"
    
    new_content, count = pattern.subn(replacement, content)
    
    print(f"[Pass 2] Ternary Fixes Applied: {count}")
    return new_content

# ==============================================================================
# PASS 3: DANGLING IFS (EMPTY BODIES)
# ==============================================================================

def pass_fix_dangling_ifs(content):
    """
    Pass 3: Fixes 'if' statements that have no body (often due to stripped $fwrite).
    Example: if (...) end  ->  if (...) begin end end
    """
    # Pattern: 
    # 1. if ((...))  -> captures the condition
    # 2. end         -> captures the immediate end
    # Using specific trace signal pattern for safety, but can be generalized.
    pattern = re.compile(r"(\s*if\s*\(\(1\s*&\s*_csr_io_trace_0_valid\)\s*&\s*~reset\))(\s*end)")
    replacement = r"\1 begin end\2"
    
    new_content, count = pattern.subn(replacement, content)
    
    print(f"[Pass 3] Dangling IFs Patched: {count}")
    return new_content

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Comprehensive Verilog Patcher')
    parser.add_argument('input_file', help='Path to the input .v file')
    parser.add_argument('-o', '--output', help='Path to the output .v file (default: overwrite input)')
    
    args = parser.parse_args()
    
    input_path = args.input_file
    output_path = args.output if args.output else args.input_file

    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        sys.exit(1)

    print(f"Reading {input_path}...")
    try:
        with open(input_path, 'r') as f:
            content = f.read()

        # Chain the passes
        content = pass_replace_modules(content)
        content = pass_fix_ternary(content)
        content = pass_fix_dangling_ifs(content)

        print(f"Writing result to {output_path}...")
        with open(output_path, 'w') as f:
            f.write(content)
            
        print("Done.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
