# Leaves the modules outside the boundary module intact, while black-boxing those inside BoomTile. Shallow blackboxing on BoomTile.
## Adds '(* blackbox *)' annotations to modules in a Verilog file based on a dependency graph.
import re
import sys
from collections import deque
import argparse
import sys

def build_verilog_dependency_graph(fir_filepath):
    """
    Parses a Verilog file to build a map of module dependencies.
    NOTE: This parser is simple and assumes a standard coding style where
    a module instantiation is on its own line.
    """
    module_def_regex = re.compile(r"^\s*module\s+([a-zA-Z_][\w]*)")
    # Regex to capture "module_name instance_name ("
    inst_regex = re.compile(r"^\s*([a-zA-Z_][\w]+)\s+(?:#\s*\(.*?\))?\s*([a-zA-Z_][\w]+)\s*\(")
    
    dependency_graph = {}
    current_module = None
    print(f"Building dependency graph from {fir_filepath}...")

    with open(fir_filepath, 'r') as f:
        for line in f:
            module_match = module_def_regex.match(line)
            if module_match:
                current_module = module_match.group(1)
                if current_module not in dependency_graph:
                    dependency_graph[current_module] = set()
                continue

            if current_module:
                inst_match = inst_regex.match(line)
                if inst_match:
                    # Avoid matching the module definition itself
                    if inst_match.group(1) != "module":
                        instantiated_module = inst_match.group(1)
                        dependency_graph[current_module].add(instantiated_module)
                        
    print(f"Found {len(dependency_graph)} total modules.")
    return dependency_graph

def find_all_reachable(graph, start_nodes):
    """Finds all modules reachable from a set of start_nodes, including the start_nodes themselves."""
    reachable_set = set(s for s in start_nodes if s in graph)
    queue = deque(reachable_set)
    visited = set(reachable_set)
    while queue:
        module = queue.popleft()
        if module in graph:
            for dependency in graph.get(module, []):
                if dependency not in visited:
                    reachable_set.add(dependency)
                    visited.add(dependency)
                    queue.append(dependency)
    return reachable_set

def annotate_verilog(input_filepath, output_filepath, blacklist_set):
    """Adds a '(* blackbox *)' annotation to modules in the blacklist_set."""
    module_regex = re.compile(r"^\s*module\s+([a-zA-Z_][\w]*)")
    annotated_count = 0
    print(f"\nWriting annotated Verilog to '{output_filepath}'...")

    with open(input_filepath, 'r') as infile, open(output_filepath, 'w') as outfile:
        for line in infile:
            module_match = module_regex.match(line)
            if module_match:
                module_name = module_match.group(1)
                if module_name in blacklist_set:
                    indentation = re.match(r"^\s*", line).group(0)
                    outfile.write(f"{indentation}(* blackbox *)\n")
                    annotated_count += 1
            outfile.write(line)
            
    print(f"Annotation complete. Black-boxed {annotated_count} modules.")

if __name__ == "__main__":
    args = parse_args()
    
    # --- CONFIGURATION ---
    input_verilog_file = args.input_file
    output_verilog_file = args.output
    boundary_module = args.boundary
        
    # 2. Modules INSIDE the boundary to KEEP as whiteboxes (and all their children).
    internal_whitelist_seeds = {
        "LSU",
        "BoomNonBlockingDCache",
    }
    # --- END CONFIGURATION ---

    # Step 1: Build dependency graph from the Verilog file.
    graph = build_verilog_dependency_graph(input_verilog_file)

    if boundary_module not in graph:
        print(f"FATAL ERROR: Boundary module '{boundary_module}' not found in Verilog file.")
        sys.exit(1)

    # Step 2: Find all modules inside the boundary.
    # We use find_all_reachable but then remove the boundary module itself from the set.
    modules_inside_boundary = find_all_reachable(graph, [boundary_module])
    modules_inside_boundary.discard(boundary_module)
    print(f"\nFound {len(modules_inside_boundary)} modules inside '{boundary_module}'.")

    # Step 3: Find the full set of internal modules to keep.
    internal_keep_set = find_all_reachable(graph, internal_whitelist_seeds)
    print(f"Identified {len(internal_keep_set)} total modules to keep in the internal whitelist.")

    # Step 4: Calculate the final blacklist.
    # This is everything inside the boundary, MINUS our exceptions.
    blacklist_set = modules_inside_boundary - internal_keep_set
    print(f"Calculated {len(blacklist_set)} modules to blackbox.")

    # --- Sanity Check ---
    if "BoomCore" in blacklist_set:
        print("  Sanity Check: 'BoomCore' will be black-boxed. (Correct)")
    if "LSU" not in blacklist_set:
        print("  Sanity Check: 'LSU' will be kept as a whitebox. (Correct)")

    # Step 5: Write the new file with the annotations.
    annotate_verilog(input_verilog_file, output_verilog_file, blacklist_set)
