#!/usr/bin/env python3
"""Regenerate the translated guest banks from the player's disks (cross-platform).

Same pipeline as tools/regen.sh, but works on Windows too: it only needs a C
compiler for the standalone bank dumper (dump_banks.c) and this Python
interpreter with `capstone` installed.

    regen.py [--cc "zig cc"] [--force] [--python PATH]

The hash gate is identical to regen.sh: if src/engine/generated already matches
the recompiler/loader inputs, nothing is rebuilt unless --force is given.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import sys


def sh(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print("[regen]", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def hash_inputs(root: Path) -> str:
    digest = hashlib.sha256()
    paths: list[Path] = []
    for pattern in ("tools/recomp/*.py", "tools/recomp/*.txt"):
        paths += sorted(root.glob(pattern))
    paths += sorted((root / "tools/recomp/seeds").glob("*"))
    paths += [
        root / "src/engine/overlay_load.c",
        root / "src/engine/overlay_load.h",
        root / "src/engine/disk_boot.c",
        root / "tools/dump_banks.c",
    ]
    for path in paths:
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc", default=os.environ.get("CC", "cc"),
                    help='compiler command for the bank dumper (e.g. "zig cc")')
    ap.add_argument("--cc-arg", action="append", default=[],
                    help="extra argument placed after --cc (repeatable; use for 'cc' of 'zig cc')")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]      # .../port
    gen = root / "src/engine/generated"
    hashfile = gen / ".regen-hash"
    scratch = root / "scratch/regen"
    disks = [Path("Disk.1"), Path("Disk.2"), Path("Disk.3")]

    want = hash_inputs(root)
    if not args.force and (gen / "game.h").is_file() and hashfile.is_file() \
            and hashfile.read_text().strip() == want:
        print("[regen] src/generated up-to-date (hash match) — skipping")
        return 0

    missing = [str(d) for d in disks if not d.is_file()]
    if missing:
        print(f"[regen] ERROR: missing {', '.join(missing)} — the translated code is "
              "generated from your own Benefactor disk images. Put Disk.1/2/3 in "
              "the port directory.", file=sys.stderr)
        return 1

    scratch.mkdir(parents=True, exist_ok=True)
    gen.mkdir(parents=True, exist_ok=True)
    exe = "dumpbanks.exe" if os.name == "nt" else "dumpbanks"
    dumper = scratch / exe

    cc = shlex.split(args.cc, posix=(os.name != "nt")) + list(args.cc_arg)
    print("[regen] building bootstrap dumper")
    sh(cc + ["-O2", "-I", "src",
             "tools/dump_banks.c", "src/engine/overlay_load.c", "src/engine/disk_boot.c",
             "-o", str(dumper)], cwd=root)

    print("[regen] dumping bank inputs from disks")
    sh([str(dumper), str(scratch), *[str(d) for d in disks]], cwd=root)

    recomp = Path(args.python)
    py = [str(recomp), "tools/recomp/recomp.py"]
    gp_seeds = (root / "tools/recomp/gp_seeds.txt").read_text().strip()
    credits_seeds = (root / "tools/recomp/credits_seeds.txt").read_text().strip()

    print("[regen] recompiling 4 banks")
    sh(py + [str(scratch / "chip_ram_dump.bin"), "--chip-dump", "--out-dir", "src/engine/generated"], cwd=root)
    sh(py + [str(scratch / "chip_flow_gp.bin"), "--chip-dump", "--base", "3000",
             "--code-size", "46000", "--seed", gp_seeds, "--bank", "gp",
             "--areg", "5=511E", "--out-dir", "src/engine/generated"], cwd=root)
    sh(py + [str(scratch / "gmem_after_load.bin"), "--chip-dump", "--base", "3000",
             "--code-size", "5A0000", "--areg", "5=57EE12", "--bank", "gpl",
             "--out-dir", "src/engine/generated",
             "--seed-dir", "tools/recomp/seeds"], cwd=root)
    sh(py + [str(scratch / "gmem_after_credits.bin"), "--chip-dump", "--base", "3330",
             "--code-size", "31112", "--areg", "5=355C", "--seed", credits_seeds,
             "--bank", "credits", "--out-dir", "src/engine/generated"], cwd=root)

    hashfile.write_text(want + "\n")
    print("[regen] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
