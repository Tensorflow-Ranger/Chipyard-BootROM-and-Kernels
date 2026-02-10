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
# BTOR PARSING
# -----------------------------

def parse_shadow_mapping(btor2_path):

    orig_name_to_id = {}
    shadow_name_to_id = {}

    # Match BOTH state and input
    line_re = re.compile(
        r'^\s*(\d+)\s+(state|input)\s+\d+\s+\\?(.+?)\s*$'
    )

    with open(btor2_path) as f:
        for line in f:
            line = line.strip()
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

    mapping = {}

    for shadow_name, shadow_id in shadow_name_to_id.items():
        orig = shadow_name[len("shadow_"):]
        if orig in orig_name_to_id:
            mapping[orig_name_to_id[orig]] = shadow_id

    return mapping

# -----------------------------
# FAST TRACE PROCESSING
# -----------------------------

def process_trace(input_yaml, output_yaml, shadow_map):

    orig_ids = list(shadow_map.keys())

    # Only track needed originals
    prev_vals = {}

    shadow_latched = {sid: 0 for sid in shadow_map.values()}
    active = set(shadow_map.items())

    with open(input_yaml) as fin, open(output_yaml, "w") as fout:

        data = yaml.load(fin, Loader=FastLoader)

        first = True

        for snap in data:

            model = snap._model

            if first:
                for sid in shadow_latched:
                    model[sid] = 0

                for oid in orig_ids:
                    prev_vals[oid] = model.get(oid, 0)

                first = False

            else:
                new_active = set()

                for oid, sid in active:

                    curr = model.get(oid, 0)

                    if curr != prev_vals.get(oid, 0):
                        shadow_latched[sid] = 1
                        model[sid] = 1
                    else:
                        model[sid] = shadow_latched[sid]
                        if shadow_latched[sid] == 0:
                            new_active.add((oid, sid))

                    prev_vals[oid] = curr

                active = new_active

                # write already latched quickly
                for sid, val in shadow_latched.items():
                    if val == 1:
                        model[sid] = 1

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
        print("Usage: python pex_shadow.py pex.yaml shadows.btor2 output.yaml")
        sys.exit(1)

    shadow_map = parse_shadow_mapping(sys.argv[2])

    print("Mappings:", len(shadow_map))

    process_trace(sys.argv[1], sys.argv[3], shadow_map)

    print("Done")


if __name__ == "__main__":
    main()
