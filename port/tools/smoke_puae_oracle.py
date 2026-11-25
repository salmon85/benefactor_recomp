#!/usr/bin/env python3
"""Smoke-test the development-only PUAE oracle on normal and world-5 levels.

Requires the locally built benefactor-harness, the user's Kickstart ROM, and
the WHDLoad support tree. Rebuilds oracle disks from the supplied CLS ADFs,
refreezes once, then verifies levels 1 and 49 reach stable gameplay.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
HARNESS = PORT / "build" / "benefactor-harness"
ORACLE_INSTALL = PORT / "oracle-whdload" / "Benefactor"
ANALYSIS = ROOT / "analysis"
LEVEL1_ASSET_RANGES = (
    (0x5AC4EA, 74388),
    (0x073880, 50476),
    (0x5BE77E, 83894),
    (0x5C4874, 61098),
    (0x5D902A, 102400),
    (0x5F202A, 15750),
)


def run_harness(commands: str, log_path: Path, *, refreeze: bool) -> str:
    env = os.environ.copy()
    if refreeze:
        env["BENEFACTOR_REFREEZE"] = "1"
    else:
        env.pop("BENEFACTOR_REFREEZE", None)
    cmd = [
        str(HARNESS),
        "Disk.1",
        "Disk.2",
        "Disk.3",
        "--kick",
        "kickstart",
        "--whdload",
        str(ORACLE_INSTALL),
    ]
    proc = subprocess.run(
        cmd,
        cwd=PORT,
        env=env,
        input=commands,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    log_path.write_text(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"harness exited {proc.returncode}; see {log_path}")
    return proc.stdout


def main() -> int:
    if not HARNESS.is_file():
        raise SystemExit(f"missing {HARNESS}; build the benefactor-harness target first")
    if not (PORT / "kickstart" / "kick40068.A1200").is_file():
        raise SystemExit("missing port/kickstart/kick40068.A1200")
    if not (PORT / "whdload" / "Benefactor").is_dir():
        raise SystemExit("missing port/whdload/Benefactor support tree")

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_oracle_disks.py"),
            "--install",
            str(ORACLE_INSTALL),
        ],
        cwd=ROOT,
        check=True,
    )

    pattern = re.compile(
        r"pugoto (?P<level>\d+): cop1lc=\$003484\s+\$20\.w=(?P<readback>\d+)\s+"
        r"\(gameplay stable=(?P<stable>\d+)\)"
    )
    for level, refreeze in ((1, True), (49, False)):
        log_path = ANALYSIS / f"puae-oracle-smoke-level{level}.log"
        if level == 1:
            commands = (
                "pugoto 1\n"
                "pudump logs/puae_oracle_level1.bin\n"
                "rungame\n"
                "dumpall logs/pc_oracle_level1.bin\n"
                "q\n"
            )
        else:
            commands = f"pugoto {level}\nq\n"
        output = run_harness(commands, log_path, refreeze=refreeze)
        matches = [m for m in pattern.finditer(output) if int(m.group("level")) == level]
        if not matches:
            raise SystemExit(f"level {level} did not reach stable gameplay; see {log_path}")
        match = matches[-1]
        readback = int(match.group("readback"))
        stable = int(match.group("stable"))
        if readback != level or stable < 60:
            raise SystemExit(
                f"level {level} bad state: readback={readback}, stable={stable}; see {log_path}"
            )
        print(f"PASS level {level}: cop1lc=$003484, $20.w={readback}, stable={stable}")

        if level == 1:
            puae = (PORT / "logs" / "puae_oracle_level1.bin").read_bytes()
            pc = (PORT / "logs" / "pc_oracle_level1.bin").read_bytes()
            for start, length in LEVEL1_ASSET_RANGES:
                if puae[start:start + length] != pc[start:start + length]:
                    raise SystemExit(f"level-1 asset mismatch at ${start:06X} ({length} bytes)")
            total = sum(length for _, length in LEVEL1_ASSET_RANGES)
            print(f"PASS level-1 loaded assets: {total} bytes byte-identical")

    print("PUAE oracle smoke: 2/2 levels and loaded-asset parity passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
