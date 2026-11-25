#!/usr/bin/env python3
"""Verify the optional HD HUD changes only the widescreen side margin."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

from PIL import Image, ImageChops

PORT = Path(__file__).resolve().parents[1]
HARNESS = PORT / "build" / "benefactor-harness"
SHOTS = PORT / "scratch" / "screenshots"


def capture(enabled: bool) -> Image.Image:
    tag = "modern_hud_on" if enabled else "modern_hud_off"
    path = SHOTS / f"{tag}.png"
    path.unlink(missing_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "BENEFACTOR_SKIP_PUAE": "1",
            "BENEFACTOR_WIDESCREEN_MODE": "16:9",
            "BENEFACTOR_RENDERER": "benren",
            "BENEFACTOR_PRESENT": "sdl",
            "BENEFACTOR_MODERN_HUD": "1" if enabled else "0",
        }
    )
    proc = subprocess.run(
        [
            str(HARNESS),
            "--level",
            "1",
            "Disk.1",
            "Disk.2",
            "Disk.3",
        ],
        cwd=PORT,
        env=env,
        input=f"rungame\npc 1\nshot {tag}\nq\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
        check=False,
    )
    if not path.is_file():
        raise RuntimeError(f"capture failed (rc={proc.returncode}):\n{proc.stdout}")
    return Image.open(path).convert("RGB")


def main() -> int:
    off = capture(False)
    on = capture(True)
    if off.size != (500, 282) or on.size != (500, 282):
        raise SystemExit(f"unexpected framebuffer sizes: off={off.size}, on={on.size}")

    diff = ImageChops.difference(off, on)
    bbox = diff.getbbox()
    if bbox is None:
        raise SystemExit("HD HUD produced no framebuffer change")
    raw = diff.tobytes()
    changed = sum(1 for i in range(0, len(raw), 3) if raw[i:i + 3] != b"\0\0\0")
    if changed < 500:
        raise SystemExit(f"HD HUD change is too small: {changed} pixels")
    if bbox[0] < 420:
        raise SystemExit(f"HD HUD intruded into the 352px playfield: bbox={bbox}")
    print(f"PASS HD HUD: {changed} pixels changed, bbox={bbox}, frame={on.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
