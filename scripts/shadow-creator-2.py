#!/usr/bin/env python3
import sys
import os


def read_lines(path):
    with open(path, 'r', encoding='utf8') as f:
        return f.readlines()


def write_lines(path, lines):
    with open(path, 'w', encoding='utf8') as f:
        f.writelines(line if line.endswith('\n') else line + '\n' for line in lines)


def is_integer_token(tok):
    return tok.isdigit()


def extract_inline_or_comment_name(lines, idx):
    total_lines = len(lines)
    raw = lines[idx].rstrip('\n')
    stripped = raw.strip()

    if not stripped:
        return None, False

    tokens_no_trail = stripped.split(';', 1)[0].strip().split()
    if not tokens_no_trail:
        return None, False

    last_numeric_idx = -1
    for j, tok in enumerate(tokens_no_trail):
        if is_integer_token(tok):
            last_numeric_idx = j

    candidate = None

    if last_numeric_idx != -1 and last_numeric_idx + 1 < len(tokens_no_trail):
        candidate = ' '.join(tokens_no_trail[last_numeric_idx + 1:]).strip()

    consumed = False

    if not candidate and (idx + 1) < total_lines:
        nxt = lines[idx + 1].strip()
        if nxt.startswith(';'):
            nxt_tokens = nxt.split()
            if len(nxt_tokens) >= 3:
                candidate = ' '.join(nxt_tokens[2:]).strip()
                consumed = True

    if candidate:
        if candidate.startswith('\\'):
            candidate = candidate[1:]
        return candidate.strip(), consumed

    return None, consumed


def collect_shadow_sources(lines):
    sources = []
    total = len(lines)
    i = 0

    while i < total:
        raw = lines[i].rstrip('\n')
        stripped = raw.strip()

        if not stripped:
            i += 1
            continue

        line_no_trail = stripped.split(';', 1)[0].strip()
        if not line_no_trail:
            i += 1
            continue

        parts = line_no_trail.split()
        if len(parts) < 2:
            i += 1
            continue

        op = parts[1]

        if op in ("state", "input"):
            src_id = parts[0]

            name, consumed = extract_inline_or_comment_name(lines, i)

            if consumed:
                i += 1

            sources.append({
                'id': src_id,
                'name': name,
                'type': op
            })

        i += 1

    return sources


def find_max_id(lines):
    max_id = 0

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue

        line_no_trail = stripped.split(';', 1)[0].strip()
        if not line_no_trail:
            continue

        parts = line_no_trail.split()

        if parts and parts[0].isdigit():
            v = int(parts[0])
            if v > max_id:
                max_id = v

    return max_id


def extract_base_and_role(name):
    """
    Detect names like:
        gold.core.signal
        gate.core.signal

    Returns (base_name, role) or (None, None)
    """
    if not name:
        return None, None

    parts = name.split('.', 1)

    if len(parts) != 2:
        return None, None

    role, rest = parts

    if role in ("gold", "gate"):
        return rest, role

    return None, None


def sanitize_name_for_btor(name):
    return name.replace('.', '_').replace(' ', '_')


def build_pair_shadows(sources, start_id):
    next_id = start_id
    shadow_lines = []
    mapping_lines = []

    pairs = {}

    for s in sources:
        base, role = extract_base_and_role(s['name'])

        if not base:
            continue

        if base not in pairs:
            pairs[base] = {}

        pairs[base][role] = s

    for base, roles in pairs.items():
        if "gate" in roles and "gold" in roles:

            shadow_id = next_id
            next_id += 1

            shadow_name = f"shadow_{sanitize_name_for_btor(base)}"
            btor_name = "\\" + shadow_name

            shadow_lines.append(f"{shadow_id} state 1 {btor_name}")

            gate_id = roles["gate"]["id"]
            gold_id = roles["gold"]["id"]

            mapping_lines.append(f"{gate_id} {gold_id} {shadow_id}")

    return shadow_lines, mapping_lines


def process_btor2_file_create_shadows(input_path,
                                      output_combined_path,
                                      output_mapping_path):
    if not os.path.exists(input_path):
        print(f"Error: input file '{input_path}' not found.")
        return

    lines = read_lines(input_path)

    sources = collect_shadow_sources(lines)
    max_id = find_max_id(lines)
    next_free = max_id + 1

    shadow_lines, mapping_lines = build_pair_shadows(sources, next_free)

    combined_lines = [ln.rstrip('\n') for ln in lines]
    combined_lines.append('; --- appended shared shadow boolean states ---')
    combined_lines.extend(shadow_lines)

    write_lines(output_combined_path, combined_lines)
    write_lines(output_mapping_path, mapping_lines)

    print(f"Created {len(shadow_lines)} shared shadow states.")
    print(f"Combined file written: {output_combined_path}")
    print(f"Mapping file written: {output_mapping_path}")


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 shadow-creator-2.py <input.btor2> <output_combined.btor2> <mapping.txt>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_combined = sys.argv[2]
    output_mapping = sys.argv[3]

    process_btor2_file_create_shadows(
        input_file,
        output_combined,
        output_mapping
    )


if __name__ == '__main__':
    main()
