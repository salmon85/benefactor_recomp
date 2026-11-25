#!/usr/bin/env python3
"""Lockstep smoke test for PC vs PUAE from the shared $577000 entry."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
HARNESS = PORT / "build" / "benefactor-harness"


def main(level: int = 1) -> int:
    if not (PORT / "logs" / "puae_sync.state").is_file():
        raise SystemExit("missing frozen PUAE state; run tools/smoke_puae_oracle.py first")
    env = os.environ.copy()
    env["BENEFACTOR_REFREEZE"] = "0"
    log_path = ROOT / "analysis" / f"puae-lockstep-level{level}.log"
    commands = "\n".join(
        [
            "pumenu",
            "fire 1",
            "pu 6",
            "fire 0",
            "purunto 577000 2000",
            f"mwp 20 {level:02X} w",
            "mpu 20 1 w",
            "pufrompc 0 100",
            "syncbeam",
            "both 600",
            "state",
            "fire 1",
            "both 8",
            "fire 0",
            "both 300",
            "both 180",
            "state",
            "diffstate",
            "cmp",
            "q",
            "",
        ]
    )
    proc = subprocess.run(
        [
            str(HARNESS),
            "--level",
            str(level),
            "Disk.1",
            "Disk.2",
            "Disk.3",
            "--kick",
            "kickstart",
            "--whdload",
            str(PORT / "oracle-whdload" / "Benefactor"),
        ],
        cwd=PORT,
        env=env,
        input=commands,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    LOG = log_path
    LOG.write_text(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit(f"harness exited {proc.returncode}; see {LOG}")

    def last(pattern: str) -> re.Match | None:
        matches = list(re.finditer(pattern, proc.stdout))
        return matches[-1] if matches else None

    entry = last(r"purunto \$577000: (hit|NOT reached)")
    card = last(r"both \+600 -> PC=\$003914 PU=\$003914")
    play = last(r"both \+300 -> PC=\$003484 PU=\$003484")
    parity = last(r"frames_differ=(\d+)")
    mem = last(r"\[diffstate\] mem20 PU=([0-9A-F]+) PC=([0-9A-F]+)")
    player = last(r"\[diffstate\] player PU=([0-9A-F]+) PC=([0-9A-F]+)")
    fb = last(r"\[crepl\] fb diff=(\d+)/(\d+)")
    if not entry or entry.group(1) != "hit":
        raise SystemExit("PUAE did not reach the shared gameplay entry")
    if not card or not play:
        raise SystemExit("both cores did not traverse card -> gameplay together")
    if not parity or parity.group(1) != "0":
        raise SystemExit("copper/palette frame state differs")
    if not mem:
        raise SystemExit("missing low-state comparison")
    if mem.group(1) != mem.group(2):
        raise SystemExit(f"low state differs: PUAE={mem.group(1)} PC={mem.group(2)}")
    if not player:
        raise SystemExit("missing player-state comparison")
    if player.group(1) != player.group(2):
        raise SystemExit(f"player state differs: PUAE={player.group(1)} PC={player.group(2)}")
    fb_limit = 10 if level == 1 else 600
    if not fb or int(fb.group(1)) >= fb_limit:
        value = fb.group(1) if fb else "missing"
        raise SystemExit(f"sustained valid-region framebuffer parity failed: diff={value}")
    print(
        "PASS shared-entry lockstep: card/gameplay, frame state, low state, "
        f"player state, fb diff={fb.group(1)} (level {level})"
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.level <= 60:
        raise SystemExit("level must be 1..60")
    raise SystemExit(main(args.level))
