#!/usr/bin/env python3

import yaml
import re
import sys


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


# ---------------- BTOR PARSE ----------------

def parse_shadow_mapping(btor2_path):

    orig_name_to_id = {}
    shadow_name_to_id = {}

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


# ---------------- LOAD LAST SNAPSHOT ----------------

def load_last_snapshot(prev_yaml, shadow_map):

    with open(prev_yaml) as f:
        data = yaml.load(f, Loader=FastLoader)

    last_snap = data[-1]

    if isinstance(last_snap, dict):
        last_model = last_snap.get("_model", {})
    else:
        last_model = last_snap._model

    prev_orig_vals = {}
    prev_shadow_vals = {}

    for oid, sid in shadow_map.items():
        prev_orig_vals[oid] = last_model.get(oid, 0)
        prev_shadow_vals[sid] = last_model.get(sid, 1)

    return prev_orig_vals, prev_shadow_vals



# ---------------- TRACE PROCESSING ----------------

def process_trace(prev_yaml, new_yaml, output_yaml, shadow_map):

    prev_vals, shadow_latched = load_last_snapshot(prev_yaml, shadow_map)

    active = set(shadow_map.items())

    with open(new_yaml) as fin, open(output_yaml, "w") as fout:

        data = yaml.load(fin, Loader=FastLoader)

        for snap in data:

            model = snap._model
            new_active = set()

            for oid, sid in active:
                curr = model.get(oid, 0)

                if curr != prev_vals[oid]:
                    shadow_latched[sid] = 0

                if shadow_latched[sid] == 1:
                    new_active.add((oid, sid))

                prev_vals[oid] = curr

            active = new_active

            # 🔴 THIS IS THE KEY FIX
            for sid, val in shadow_latched.items():
                model[sid] = val


        clean = []
        for snap in data:
            clean.append({
                "_model": snap._model,
                "is_start": getattr(snap, "is_start", False)
            })

        yaml.safe_dump(clean, fout)


# ---------------- MAIN ----------------

def main():

    if len(sys.argv) != 5:
        print("Usage:")
        print("python pex_shadow_decay.py prev.yaml new.yaml shadows.btor2 output.yaml")
        sys.exit(1)

    prev_yaml = sys.argv[1]
    new_yaml = sys.argv[2]
    btor = sys.argv[3]
    out = sys.argv[4]

    mapping = parse_shadow_mapping(btor)

    print("Mappings:", len(mapping))

    process_trace(prev_yaml, new_yaml, out, mapping)

    print("Done")


if __name__ == "__main__":
    main()
