#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path


def run(cmd):
    print(">>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def vcd_to_pex(config_yaml):
    run([
        "python3", "-m", "learning.examples",
        "vcd-to-pex",
        "--config", str(config_yaml)
    ])


def make_shadow_btor(base_btor):
    out = base_btor.with_name(base_btor.stem + "_with_shadows.btor2")
    run([
        "python3",
        "shadow_creator.py",
        str(base_btor),
        str(out)
    ])
    return out


def shadow_or(pex, btor, out):
    run([
        "python3",
        "pex_shadow.py",
        pex,
        btor,
        out
    ])


def shadow_and(prev, curr, btor, out):
    run([
        "python3",
        "pex_shadow_2.py",
        prev,
        curr,
        btor,
        out
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--clips", type=int, required=True)
    ap.add_argument("--shadow-policy", required=True,
                    help="Comma-separated list: 0=OR, 1=AND")
    ap.add_argument("--btor2", help="Optional base btor2")
    args = ap.parse_args()

    policy = [int(x) for x in args.shadow_policy.split(",")]
    if len(policy) != args.clips:
        raise ValueError("shadow-policy length must equal number of clips")

    prefix = args.prefix
    n = args.clips

    # Determine BTOR file
    if args.btor2:
        base_btor = Path(args.btor2)
        shadow_btor = make_shadow_btor(base_btor)
    else:
        shadow_btor = Path("with_shadows.btor2")

    prev_shadowed = None

    for i in range(1, n + 1):
        clip = f"{prefix}_clip_{i}"
        config = Path(f"examples/rocketchip/vcd_to_pex_{clip}.yaml")

        print(f"\n=== Processing {clip} ===")

        # Stage A: VCD → PEX
        vcd_to_pex(config)

        curr_pex = Path("pex.yaml")
        out_shadow = Path(f"{clip}_shadow.yaml")

        # Stage B: Shadow filling
        if policy[i - 1] == 0:
            shadow_or(str(curr_pex), str(shadow_btor), str(out_shadow))

        else:
            if prev_shadowed is None:
                raise RuntimeError(
                    f"AND-decay used on first clip ({clip})"
                )
            shadow_and(
                str(prev_shadowed),
                str(curr_pex),
                str(shadow_btor),
                str(out_shadow)
            )

        prev_shadowed = out_shadow


if __name__ == "__main__":
    main()
