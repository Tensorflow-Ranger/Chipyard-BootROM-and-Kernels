#!/usr/bin/env python3

import yaml
import re
import sys


# -----------------------------
# FAST YAML LOADER
# -----------------------------

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


# -----------------------------
# PARSE COMMON SHADOW MAPPING
# -----------------------------

def parse_common_shadow_mapping(mapping_file):
    """
    Mapping file format:
        gate_id gold_id shadow_id
    """

    pairs = []  # (gate_id, shadow_id)

    with open(mapping_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) != 3:
                continue

            gate_id = int(parts[0])
            # gold_id = int(parts[1])  # not needed
            shadow_id = int(parts[2])

            pairs.append((gate_id, shadow_id))

    return pairs


# -----------------------------
# TRACE PROCESSING
# -----------------------------

def process_trace(input_yaml, output_yaml, shadow_pairs):

    monitored_ids = [gate for gate, _ in shadow_pairs]

    prev_vals = {}
    shadow_latched = {sid: 0 for _, sid in shadow_pairs}

    active = set(shadow_pairs)

    with open(input_yaml) as fin, open(output_yaml, "w") as fout:

        data = yaml.load(fin, Loader=FastLoader)

        first = True

        for snap in data:

            model = snap._model

            if first:
                # initialize shadows to 0
                for sid in shadow_latched:
                    model[sid] = 0

                # record initial values
                for gate_id in monitored_ids:
                    prev_vals[gate_id] = model.get(gate_id, 0)

                first = False

            else:
                new_active = set()

                for gate_id, shadow_id in active:

                    curr = model.get(gate_id, 0)

                    if curr != prev_vals.get(gate_id, 0):
                        shadow_latched[shadow_id] = 1
                        model[shadow_id] = 1
                    else:
                        model[shadow_id] = shadow_latched[shadow_id]
                        if shadow_latched[shadow_id] == 0:
                            new_active.add((gate_id, shadow_id))

                    prev_vals[gate_id] = curr

                active = new_active

                # enforce latched shadows
                for sid, val in shadow_latched.items():
                    if val == 1:
                        model[sid] = 1

        # clean output
        clean_data = []
        for snap in data:
            clean_data.append({
                "_model": snap._model,
                "is_start": getattr(snap, "is_start", False)
            })

        yaml.safe_dump(clean_data, fout)


# -----------------------------
# MAIN
# -----------------------------

def main():

    if len(sys.argv) != 4:
        print("Usage: python pex_shadow.py pex.yaml mapping.txt output.yaml")
        sys.exit(1)

    shadow_pairs = parse_common_shadow_mapping(sys.argv[2])

    print("Pairs loaded:", len(shadow_pairs))

    process_trace(sys.argv[1], sys.argv[3], shadow_pairs)

    print("Done")


if __name__ == "__main__":
    main()
