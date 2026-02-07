#!/usr/bin/env python3
import sys
import os
import re

def read_lines(path):
    with open(path, 'r', encoding='utf8') as f:
        return f.readlines()

def write_lines(path, lines):
    with open(path, 'w', encoding='utf8') as f:
        f.writelines(line if line.endswith('\n') else line + '\n' for line in lines)

def is_integer_token(tok):
    return tok.isdigit()

def extract_inline_or_comment_name(lines, idx):
    """
    Given file lines and an index idx for a line, attempt to get a name associated
    with that line either inline (tokens after last numeric token) or from the
    immediate next-line comment format '; <id> <name...>'.
    Returns (name_or_None, consumed_comment_bool)
    """
    total_lines = len(lines)
    raw = lines[idx].rstrip('\n')
    stripped = raw.strip()
    if not stripped:
        return None, False
    # remove trailing comment for token parsing
    tokens_no_trail = stripped.split(';', 1)[0].strip().split()
    if not tokens_no_trail:
        return None, False
    # find last numeric token index
    last_numeric_idx = -1
    for j, tok in enumerate(tokens_no_trail):
        if is_integer_token(tok):
            last_numeric_idx = j
    candidate = None
    if last_numeric_idx != -1 and last_numeric_idx + 1 < len(tokens_no_trail):
        candidate = ' '.join(tokens_no_trail[last_numeric_idx + 1:]).strip()
    # attempt next-line comment if no inline
    consumed = False
    if not candidate and (idx + 1) < total_lines:
        nxt = lines[idx + 1].strip()
        if nxt.startswith(';'):
            nxt_tokens = nxt.split()
            # Expect format: '; <id> <name...>'
            if len(nxt_tokens) >= 3:
                candidate = ' '.join(nxt_tokens[2:]).strip()
                consumed = True
    if candidate:
        # remove leading backslash if present (we'll re-escape when creating shadow)
        if candidate.startswith('\\'):
            candidate = candidate[1:]
        return candidate, consumed
    return None, consumed

def sanitize_name_for_btor(name):
    # sanitize whitespace -> underscore, remove unwanted $ signs
    s = name.replace(' ', '_')
    s = s.replace('$', '')
    # ensure no leading/trailing whitespace
    s = s.strip()
    return s

def collect_states(lines):
    """
    Returns a list of dicts: { 'id': <str id token>, 'width': <int width or None>, 'name': <str or None>, 'line_idx': <int> }
    """
    states = []
    total = len(lines)
    i = 0
    while i < total:
        raw = lines[i].rstrip('\n')
        stripped = raw.strip()
        if not stripped:
            i += 1
            continue
        # remove trailing comment for parsing
        line_no_trail = stripped.split(';', 1)[0].strip()
        if not line_no_trail:
            i += 1
            continue
        parts = line_no_trail.split()
        if len(parts) < 2:
            i += 1
            continue
        op = parts[1]
        if op == 'state':
            # format: <id> state <width> [name]
            src_id = parts[0]
            width = None
            if len(parts) >= 3 and parts[2].isdigit():
                width = int(parts[2])
            # try to extract inline or next-line comment name
            name, consumed = extract_inline_or_comment_name(lines, i)
            if consumed:
                i += 1  # consume the comment line so we don't re-process it
            states.append({'id': src_id, 'width': width, 'name': name, 'line_idx': i})
        i += 1
    return states

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
        # first token usually an id if numeric
        if parts and parts[0].isdigit():
            try:
                v = int(parts[0])
                if v > max_id:
                    max_id = v
            except ValueError:
                pass
    return max_id

def build_shadow_lines(states, start_id):
    """
    For every entry in states, produce:
      - a shadow boolean state (width=1)
      - a next line that forces it to 0
    Returns list of lines and next_free_id.
    """
    next_id = start_id
    shadow_lines = []

    for s in states:
        orig_id = s['id']

        # choose base name
        if s['name']:
            base_name = sanitize_name_for_btor(s['name'])
        else:
            base_name = f"state_{orig_id}"

        shadow_name = f"shadow_{base_name}"
        btor_name = '\\' + shadow_name

        # state line
        state_id = next_id
        shadow_lines.append(f"{state_id} state 1 {btor_name}")
        next_id += 1

        # next line: next <state> 0 0
        next_line_id = next_id
        shadow_lines.append(f"{next_line_id} next {state_id} 0 0")
        next_id += 1

    return shadow_lines, next_id

def process_btor2_file_create_shadows(input_path, output_combined_path, output_shadows_path=None):
    if not os.path.exists(input_path):
        print(f"Error: input file '{input_path}' not found.")
        return

    lines = read_lines(input_path)
    # collect states and max id
    states = collect_states(lines)
    max_id = find_max_id(lines)
    # next free id is max_id + 1
    next_free = max_id + 1

    if not states:
        print("No 'state' declarations found in input. No shadows created.")
        # still write a copy of the input to output_combined_path
        write_lines(output_combined_path, lines)
        if output_shadows_path:
            write_lines(output_shadows_path, [])
        return

    shadow_lines, _ = build_shadow_lines(states, next_free)

    # Append shadows to original content (preserve original trailing newline behavior)
    combined_lines = [ln.rstrip('\n') for ln in lines]
    # ensure there's a separating comment for readability
    combined_lines.append('; --- appended shadow boolean states ---')
    combined_lines.extend(shadow_lines)

    # If shadows-only path missing, derive default
    if output_shadows_path is None:
        output_shadows_path = output_combined_path + '.shadows.btor2'

    # Write combined and shadows-only
    write_lines(output_combined_path, combined_lines)
    # include the same header comment in the shadows-only file

    print(f"Created {len(shadow_lines)} shadow states.")
    print(f"Combined file written: {output_combined_path}")

def main():
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python3 btor2-shadow-creator.py <input.btor2> <output_combined.btor2> [<shadows_only.btor2>]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_combined = sys.argv[2]
    output_shadows = sys.argv[3] if len(sys.argv) == 4 else None

    process_btor2_file_create_shadows(input_file, output_combined, output_shadows)

if __name__ == '__main__':
    main()

