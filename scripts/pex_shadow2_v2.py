#!/usr/bin/env python3

import yaml
import re
import sys
from typing import Dict, Tuple


# ---------------- YAML LOADER ----------------

class ConcreteExampleWrapper:
    def __init__(self, data):
        self.__dict__.update(data)


class FastLoader(yaml.CLoader):
    pass


def python_object_constructor(loader, tag_suffix, node):
    data = loader.construct_mapping(node, deep=False)
    return ConcreteExampleWrapper(data)


FastLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/object:",
    python_object_constructor
)


# ---------------- SHADOW MAPPING PARSING ----------------

def parse_shadow_mapping(path: str) -> Dict[int, int]:
    """
    Accepts either:
      - a mapping file with lines: "<gate_id> <gold_id> <shadow_id>"
      - OR a BTOR2 file containing state/input lines where shadow names are like:
            shadow_<orig_name>
        and original names exist as other state/input lines.
    Returns mapping: { original_id_or_gate_id: shadow_id }
    Behavior:
      - If the file contains ANY valid triple lines, those are used (gate -> shadow).
      - Otherwise falls back to scanning a BTOR2 file for names (legacy behavior).
    """

    mapping = {}

    # Try to parse as mapping triples first
    try:
        with open(path) as f:
            triple_lines = []
            for raw in f:
                line = raw.strip()
                if not line or line.startswith(';'):
                    continue
                parts = line.split()
                # Accept exactly 3 integer tokens
                if len(parts) == 3 and all(p.lstrip('-').isdigit() for p in parts):
                    gate_id = int(parts[0])
                    # gold_id = int(parts[1])  # unused here
                    shadow_id = int(parts[2])
                    triple_lines.append((gate_id, shadow_id))

            if triple_lines:
                for gate_id, shadow_id in triple_lines:
                    mapping[gate_id] = shadow_id
                return mapping
    except FileNotFoundError:
        pass  # we'll try fallback and report later

    # Fallback: treat the file as a BTOR2 and extract names (legacy)
    orig_name_to_id = {}
    shadow_name_to_id = {}

    line_re = re.compile(r'^\s*(\d+)\s+(state|input)\s+\d+\s+\\?(.+?)\s*$')

    try:
        with open(path) as f:
            for raw in f:
                line = raw.strip()
                if not line or line[0] == ';':
                    continue
                m = line_re.match(line)
                if not m:
                    continue
                node_id = int(m.group(1))
                name = m.group(3)
                if name.startswith("shadow_"):
                    shadow_name_to_id[name] = node_id
                else:
                    orig_name_to_id[name] = node_id
    except FileNotFoundError:
        print(f"Error: mapping/btor file '{path}' not found.")
        return {}

    # Build mapping orig_id -> shadow_id where names match 'shadow_<orig>'
    for shadow_name, shadow_id in shadow_name_to_id.items():
        orig = shadow_name[len("shadow_"):]
        if orig in orig_name_to_id:
            mapping[orig_name_to_id[orig]] = shadow_id

    return mapping


# ---------------- LOAD LAST SNAPSHOT ----------------

def load_last_snapshot(prev_yaml: str, shadow_map: Dict[int, int]) -> Tuple[Dict[int, int], Dict[int, int]]:
    """
    Loads the final snapshot from prev_yaml and returns:
      prev_orig_vals: { orig_id (gate): value }
      prev_shadow_vals: { shadow_id: value }
    Default for missing original IDs: 0
    Default for missing shadow IDs: 1  (because this script uses '0-latching' semantics)
    """
    try:
        with open(prev_yaml) as f:
            data = yaml.load(f, Loader=FastLoader)
    except FileNotFoundError:
        # No previous snapshot — treat everything as defaulted
        prev_orig_vals = {oid: 0 for oid in shadow_map.keys()}
        prev_shadow_vals = {sid: 1 for sid in shadow_map.values()}
        return prev_orig_vals, prev_shadow_vals

    if not data:
        prev_orig_vals = {oid: 0 for oid in shadow_map.keys()}
        prev_shadow_vals = {sid: 1 for sid in shadow_map.values()}
        return prev_orig_vals, prev_shadow_vals

    last_snap = data[-1]
    if isinstance(last_snap, dict):
        last_model = last_snap.get("_model", {})
    else:
        last_model = last_snap._model

    prev_orig_vals = {}
    prev_shadow_vals = {}

    for oid, sid in shadow_map.items():
        prev_orig_vals[oid] = last_model.get(oid, 0)
        # Default shadow value is 1 under '0-latching' semantics
        prev_shadow_vals[sid] = last_model.get(sid, 1)

    return prev_orig_vals, prev_shadow_vals


# ---------------- TRACE PROCESSING ----------------

def process_trace(prev_yaml: str, new_yaml: str, output_yaml: str, shadow_map: Dict[int, int]):
    """
    Processes new_yaml trace and writes an output_yaml with shadow values updated.
    Shadow semantics in this script:
      - Shadows are initially (from prev) assumed 1.
      - If the monitored original (gate_id) changes compared to previous value,
        the corresponding shadow is set to 0 (and remains 0).
      - We monitor the "original" IDs listed as keys in shadow_map.
    """

    prev_vals, shadow_latched = load_last_snapshot(prev_yaml, shadow_map)

    # active is set of (orig_id, shadow_id) pairs still eligible to become 0
    active = set(shadow_map.items())

    with open(new_yaml) as fin:
        data = yaml.load(fin, Loader=FastLoader)

    # If data is empty, produce empty output gracefully
    if not data:
        yaml.safe_dump([], open(output_yaml, "w"))
        return

    for snap in data:
        model = snap._model
        new_active = set()

        for oid, sid in active:
            curr = model.get(oid, 0)

            # If the monitored gate changed from prev value, set shadow to 0
            if curr != prev_vals.get(oid, 0):
                shadow_latched[sid] = 0

            # If shadow is still 1, it remains active for future changes
            if shadow_latched.get(sid, 1) == 1:
                new_active.add((oid, sid))

            prev_vals[oid] = curr

        active = new_active

        # Enforce shadow values in the current snapshot model
        for sid, val in shadow_latched.items():
            model[sid] = val

    # Clean and write out the modified trace
    clean = []
    for snap in data:
        clean.append({
            "_model": snap._model,
            "is_start": getattr(snap, "is_start", False)
        })

    with open(output_yaml, "w") as fout:
        yaml.safe_dump(clean, fout)


# ---------------- MAIN ----------------

def main():
    if len(sys.argv) != 5:
        print("Usage:")
        print("  python pex_shadow_decay.py prev.yaml new.yaml mapping_or_btor_file output.yaml")
        print("")
        print("mapping_or_btor_file may be either:")
        print("  - a mapping text file with lines: '<gate_id> <gold_id> <shadow_id>'")
        print("  - or a BTOR2 file that contains 'shadow_<orig>' names (legacy)")
        sys.exit(1)

    prev_yaml = sys.argv[1]
    new_yaml = sys.argv[2]
    mapping_path = sys.argv[3]
    out = sys.argv[4]

    mapping = parse_shadow_mapping(mapping_path)

    if not mapping:
        print("Warning: no mappings found. Nothing will be updated.")
    else:
        print("Mappings loaded:", len(mapping))

    process_trace(prev_yaml, new_yaml, out, mapping)

    print("Done")


if __name__ == "__main__":
    main()
