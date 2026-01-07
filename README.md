# Stale Data Project

## Preprocessing Pipeline

This pipeline prepares a **SmallBoom** design for scalable formal verification by eliminating memories, completing missing module definitions, selectively blackboxing internal logic, and producing a clean BTOR2 model.

### High-level flow

1. **Chisel elaboration**

2. **FIRRTL transforms**

   * `WithMemToRegs` (replace memories with registers)

3. **Verilog emission**

4. **`ext_definition_adder.py`**

   * Generate missing `*_ext` blackbox stubs
   * Manually fix missing ports (`R0_en`, etc.)
   * Add `plusarg_reader` blackbox

5. **`verilog-blackboxing.py`**

   * Perform shallow blackboxing inside `BoomTile`

6. **Yosys → BTOR2**

   * No memories
   * No missing modules

7. **`btor2-cleaner.py`**

   * Normalize and clean BTOR2 signal names

---

## Steps to Build the Pipeline

### 1. Add `MemToRegs` FIRRTL transform

Add the following to `BoomConfig.scala` to eliminate memories *before* Verilog is generated:

```scala
import chisel3._
import firrtl.options.Dependency
import firrtl.passes.ReplaceMems
import firrtl.stage.Forms
import freechips.rocketchip.config.{Config, Field, Parameters}

// FIRRTL transform to replace all memories with registers
class MemToRegs extends firrtl.Transform {
  override def invalidates(a: firrtl.Transform): Boolean = false
  override def dependencies = Seq(Dependency(firrtl.passes.RemoveValidIf))
  override def name = "Replace All Mems with Registers"

  override def execute(state: firrtl.CircuitState): firrtl.CircuitState = {
    val result = (new ReplaceMems).run(state.circuit)
    state.copy(circuit = result)
  }
}

// Config fragment to enable the transform
class WithMemToRegs extends Config((site, here, up) => {
  case firrtl.stage.FirrtlCircuitAnnotation =>
    Seq(firrtl.annotations.Annotation(
      firrtl.CircuitTarget("Top"),
      classOf[MemToRegs],
      ""
    ))
})

// Example SmallBoom config with memory elimination enabled
class SmallBoomV4Config extends Config(
  new WithMemToRegs ++
  new boom.v4.common.WithSmallBooms ++
  new chipyard.config.AbstractConfig
)
```

---

### 2. Build SmallBoom in Chipyard

Build using the config that includes `WithMemToRegs`:

```bash
make <target> CONFIG=SmallBoomV4Config
```

This ensures all FIRRTL memories are converted into registers.

---

### 3. Generate a combined Verilog file

Use **SV2V** to merge the generated Verilog into a single file representing the full SmallBoom design.

---

### 4. Add missing `_ext` module definitions

Run:

```bash
python ext_definition_adder.py
```

This:

* Detects instantiated but undefined `*_ext` modules
* Auto-generates minimal blackbox definitions

These stubs replace behavior that simulators like Verilator normally fill in.

---

### 5. Manually fix missing ports

Some `_ext` modules require manual fixes that cannot be inferred automatically:

* `meta_0_ext`
* `ghist_0_ext`
* `rob_compact_uop_mem_0_ext`

Add missing ports such as:

* `R0_en`

---

### 6. Add `plusarg_reader` blackbox

Append the following blackbox definition to the combined Verilog:

```verilog
module plusarg_reader #(
    parameter DEFAULT = 0,
    parameter FORMAT = "",
    parameter WIDTH = 32
) (
    output [WIDTH-1:0] out
);
// blackbox: no implementation
endmodule
```

This removes simulation-only dependencies from the design.

---

### 7. Perform shallow blackboxing

Run:

```bash
python verilog-blackboxing.py
```

This:

* Treats `BoomTile` as the verification boundary
* Blackboxes most internal modules
* Preserves selected whitebox modules (e.g., `LSU`) and their subtrees

---

### 8. Convert Verilog to BTOR2

Run Yosys with your script:

```bash
yosys script.ys
```

This produces a `.btor2` file with:

* No memories
* No missing modules
* Clean blackbox cutpoints

---

### 9. Clean the BTOR2

Finally, normalize signal names:

```bash
python btor2-cleaner.py input.btor2 output.btor2
```

This:

* Removes junk names
* Resolves inline vs comment names
* Produces a readable, deterministic BTOR2 model

---

## What problem each script solves

### `ext_definition_adder.py`

When building **SmallBoom**, the generated Verilog often contains instantiations of modules that do **not** have corresponding definitions in the file, typically named like:

```verilog
Something_ext
```

This causes downstream tools to fail with errors such as:

```
Module 'X_ext' not found
```

However, the logic of these modules is **not required**—only their interfaces are.

**What this script does:**

* Detects instantiated but undefined `_ext` modules
* Infers their interfaces from how they are connected
* Auto-generates **minimal blackbox module definitions** with:

  * Correct port names
  * Correct directions
  * Correct bit-widths

This makes the Verilog **structurally complete** without adding unnecessary logic.

---

### `verilog-blackboxing.py`

A Verilog design forms a **module dependency graph**:

* Modules instantiate other modules
* This creates a hierarchy (tree/graph)

This script lets you define a **verification boundary**, typically `BoomTile`.

**Goal:**

> Blackbox most logic *inside* `BoomTile`, while keeping a small set of important modules (e.g., `LSU`) fully visible. Everything outside `BoomTile` remains untouched.

**Conceptually:**

* Outside the boundary → **left intact**
* Inside the boundary → **blackboxed by default**
* Explicit exceptions → **kept as whiteboxes (along with their children)**

**What this script does:**

* Builds a dependency graph from the Verilog
* Identifies all modules inside `BoomTile`
* Adds `(* blackbox *)` annotations selectively
* Enables **shallow blackboxing** for scalable formal verification

---

### `btor2-cleaner.py`

BTOR2 files generated by tools often contain messy or inconsistent signal naming:

* Names may appear inline, in comments, or both
* Tool-generated junk names (containing `$`)
* Names split across multiple lines
* Decorative comments (`; begin`, `; end`, filenames)

These issues make debugging and formal analysis harder.

**What this script does:**

* Normalizes BTOR2 signal names
* Ensures **at most one clean, valid name per command**
* Applies deterministic name precedence:

  * Comment name (highest priority)
  * Inline name (fallback)
  * No name if both are invalid
* Removes decorative and junk comments

The result is a **clean, readable, tool-friendly BTOR2 file**.


