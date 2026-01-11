# Stale Data Project 

This repository contains the preprocessing pipeline designed to prepare the **SmallBoom** RISC-V design for scalable formal verification. The pipeline transforms a raw Chisel/Verilog design into a clean, optimized **BTOR2** model by eliminating memories, handling missing definitions, and applying selective blackboxing.

## How to Run the Flow

### Prerequisites
*   **Chipyard** (with `verilator` and `yosys` installed in the environment)
*   **Python 3.6+**
*   **Yosys** (Version 0.60+ recommended for `cutpoint -blackbox` support)

### Phase 1: Chisel Generation 
Before running the scripts, you must generate the Verilog.
Note: You do not need to eliminate memories at this stage. Yosys will do that for us. 

1.  **Build Chipyard**:
    ```bash
    make <target> CONFIG=SmallBoomV4Config
    ```
3.  **Convert to Single File**: Use `sv2v` or similar tools to merge the generated Verilog into a single file named `combined_converted.v`.

### Phase 2: Automated Preprocessing
We provide a single orchestrator script, `run_formal_flow.py`, to handle the entire chain from Verilog to BTOR2.

**Run the full pipeline:**
```bash
python3 run_formal_flow.py
```

**Run up to a specific step:**
If you want to debug the intermediate Verilog (e.g., after blackboxing but before Yosys):
```bash
# Runs steps 1 through 4 (Blackboxing)
python3 run_formal_flow.py 4
```

**List available steps:**
```bash
python3 run_formal_flow.py --list-steps
```

---

## Pipeline Architecture

The flow consists of 8 distinct stages. Below is a detailed explanation of what happens at each stage and why.

### 1. External Definition Injection (`ext_definition_adder.py`)
**Problem:** The generated Verilog often contains instantiations of modules (e.g., `Something_ext`) that have no definition, causing Yosys to crash.
**Action:**
*   Scans the Verilog for undefined modules.
*   Infers port widths and directions based on instantiation connections.
*   Auto-generates minimal blackbox stubs.
*   Injects the `plusarg_reader` blackbox to handle simulation artifacts.

### 2. Syntax Patching (`fix.py`)
**Problem:** Automated definition generation or Verilog conversion can sometimes leave syntax errors (e.g., missing ports on specific `_ext` modules like `meta_0_ext` or `R0_en`).
**Action:** Applies regex-based patches to fix known syntax issues, missing ports, or malformed Verilog constructs.

### 3. Selective Blackboxing (`verilog-blackboxing.py`)
**Problem:** The full CPU is too large for formal verification. We need to focus on specific units (like the LSU) while ignoring the complexity of the Decoder, FPU, or Branch Predictor.
**Action:**
*   Builds a module dependency graph.
*   Treats `BoomTile` as the verification boundary.
*   **Blackboxes** modules inside the tile by default.
*   **Whiteboxes** specific targets (e.g., the Load/Store Unit) and recursively preserves their children.
*   Adds `(* blackbox *)` attributes to the Verilog.

### 4. Yosys Synthesis
**Action:** Converts the processed Verilog into the BTOR2 format.
*   **`proc`, `flatten`**: Standard netlist preparation.
*   **`memory -nomap`**: Ensures any remaining arrays (like the Register File) are preserved as abstract arrays rather than bit-blasted logic.
*   **`cutpoint -blackbox`**: Converts the outputs of blackboxed modules into unconstrained primary inputs (formal cutpoints).
*   **`miter`**: Creates an identity miter structure required for certain formal workflows.

### 5. BTOR2 Cleaning (`btor2-cleaner.py`)
**Problem:** Tools often generate BTOR2 with inconsistent naming, junk characters (like `$`), or names split across comments.
**Action:**
*   Normalizes signal names.
*   Prioritizes comment-based names over inline names.
*   Removes decorative comments and metadata.
*   Ensures deterministic output for reproducible proofs.

### 6. State Replacement (`replace_states_with_inputs.py`)
**Action:** Iterates through the BTOR2 file and converts specific state elements into inputs if they are determined to be driven by external constraints or blackboxes, further reducing state space.

### 7. Final Sanity Check (`nameless-states.py`)
**Action:** Scans the final BTOR2 file to ensure all state elements have valid symbolic names. If states are missing names, it flags them, as this usually indicates an issue with the synthesis or cleaning process that makes debugging traces impossible.

