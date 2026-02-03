# Adds _ext module definitions to a Verilog file based on missing instantiations.
import re
import sys
from collections import defaultdict

def parse_verilog_for_context(input_filepath):
    """
    First pass: Parse the entire Verilog file to gather context using a more robust parser.
    """
    # pf:ensures:parse_verilog_for_context.modules_have_declarations all defined modules have corresponding declarations
    print(f"Pass 1: Parsing '{input_filepath}' for all module declarations...")
    
    module_def_regex = re.compile(r"^\s*module\s+([a-zA-Z_][\w]*)")
    # UPDATED REGEX: Handles multiple comma-separated declarations
    declaration_regex = re.compile(
        r"^\s*(input|output|wire|reg)\s*(?:wire|reg)?\s*(\[.*?\])?\s*([^;]+);"
    )
    endmodule_regex = re.compile(r"^\s*endmodule")

    defined_modules = set()
    module_declarations = defaultdict(dict)
    
    current_module = None

    with open(input_filepath, 'r') as f:
        for line in f:
            if current_module:
                if endmodule_regex.match(line):
                    current_module = None
                    continue
                
                decl_match = declaration_regex.match(line)
                if decl_match:
                    decl_type, width, names_str = decl_match.groups()
                    # Split the comma-separated list of names and clean them up
                    names = [name.strip() for name in names_str.split(',')]
                    for name in names:
                        if name: # Ensure not an empty string
                            module_declarations[current_module][name] = {
                                'type': decl_type,
                                'width': width.strip() if width else ""
                            }
            else:
                module_match = module_def_regex.match(line)
                if module_match:
                    module_name = module_match.group(1)
                    defined_modules.add(module_name)
                    current_module = module_name
    
    print(f"Found {len(defined_modules)} existing module definitions and parsed their internal declarations.")
    return defined_modules, module_declarations


def find_and_define_missing_modules(input_filepath, defined_modules, module_declarations):
    """
    Second pass: Finds instantiations of missing _ext modules and generates their definitions.
    """
    # pf:requires:find_and_define_missing_modules.context_populated defined_modules and module_declarations must be populated from parse_verilog_for_context
    # pf:ensures:find_and_define_missing_modules.missing_not_defined returned modules are not in defined_modules
    # This function's logic remains correct given the improved context from Pass 1.
    print("\nPass 2: Finding missing blackbox instantiations...")
    
    module_def_regex = re.compile(r"^\s*module\s+([a-zA-Z_][\w]*)")
    inst_start_regex = re.compile(r"^\s*([a-zA-Z_][\w]*_ext)\s+([a-zA-Z_][\w]*)?\s*\(")
    port_conn_regex = re.compile(r"^\s*\.([a-zA-Z_][\w]+)\s*\(\s*([a-zA-Z_][\w]+)\s*\)")
    endmodule_regex = re.compile(r"^\s*endmodule")

    missing_modules_to_generate = {}
    current_parent_module = None
    parsing_instantiation = False
    current_connections = {}
    current_ext_module_name = None

    with open(input_filepath, 'r') as f:
        for line in f:
            if endmodule_regex.match(line):
                current_parent_module = None
            elif module_def_regex.match(line):
                current_parent_module = module_def_regex.match(line).group(1)

            if current_parent_module and not parsing_instantiation:
                inst_match = inst_start_regex.match(line)
                if inst_match:
                    ext_module_name = inst_match.group(1)
                    if ext_module_name not in defined_modules and ext_module_name not in missing_modules_to_generate:
                        parsing_instantiation = True
                        current_ext_module_name = ext_module_name
                        current_connections = {}

            if parsing_instantiation:
                port_match = port_conn_regex.match(line)
                if port_match:
                    port_name, connected_wire = port_match.groups()
                    current_connections[port_name] = connected_wire
                
                if ");" in line:
                    parent_context = module_declarations.get(current_parent_module)
                    if parent_context:
                        inferred_ports = []
                        for port_name, wire_name in current_connections.items():
                            if wire_name in parent_context:
                                wire_info = parent_context[wire_name]
                                inferred_dir = 'input' if wire_info['type'] != 'output' else 'output'
                                inferred_ports.append({
                                    'name': port_name,
                                    'dir': inferred_dir,
                                    'width': wire_info['width']
                                })
                        missing_modules_to_generate[current_ext_module_name] = inferred_ports
                        print(f"  Found missing module '{current_ext_module_name}' in parent '{current_parent_module}'. Will generate definition.")

                    parsing_instantiation = False
                    current_ext_module_name = None
                    current_connections = {}
    
    return missing_modules_to_generate

def generate_and_append_modules(output_filepath, input_filepath, new_modules_data):
    """
    Generates the Verilog code for new modules and appends it to the original file content.
    """
    # pf:requires:generate_and_append_modules.modules_from_pass2 new_modules_data must be computed by find_and_define_missing_modules
    # pf:ensures:generate_and_append_modules.all_modules_generated generated_code length equals new_modules_data length
    print("\nPass 3: Generating and writing new file...")
    generated_code = []
    for module_name, ports in new_modules_data.items():
        port_list_str = ",\n\t".join(p['name'] for p in ports)
        port_declarations_str = "\n".join(f"\t{p['dir']} {p['width']} {p['name']};" for p in ports)
        module_text = f"""
module {module_name} (
\t{port_list_str}
);
{port_declarations_str}
\t// This module is a black box, logic is not defined.
endmodule
"""
        generated_code.append(module_text)

    with open(output_filepath, 'w') as outfile:
        with open(input_filepath, 'r') as infile:
            outfile.write(infile.read())
        if generated_code:
            outfile.write("\n\n// ----- Auto-generated Blackbox Modules -----\n")
            outfile.write("\n".join(generated_code))
    
    print(f"\nProcessing complete. Appended {len(generated_code)} new module definitions.")
    print(f"New file saved as '{output_filepath}'.")

if __name__ == "__main__":
    # --- CONFIGURATION ---
    input_verilog_file = "combined.v"
    output_verilog_file = "combined_with_ext.v"
    # --- END CONFIGURATION ---

    try:
        defined_modules, module_declarations = parse_verilog_for_context(input_verilog_file)
        new_modules_to_generate = find_and_define_missing_modules(input_verilog_file, defined_modules, module_declarations)
        generate_and_append_modules(output_verilog_file, input_verilog_file, new_modules_to_generate)
    except FileNotFoundError:
        print(f"FATAL ERROR: The input file '{input_verilog_file}' was not found.")
        sys.exit(1)