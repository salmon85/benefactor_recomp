#!/usr/bin/env python3
"""Extract and verify the art-replacement inventory for one gameplay frame.

The BenRen renderer emits one SceneQuad per sprite/tile per frame. `scenedump`
resolves each quad through its per-scanline palette into a PNG and records a
content-hash id, so an artist can replace a single distinct sprite/tile once and
have every instance pick it up. This tool runs the dump twice (deterministic
headless boot) and checks that the inventory reproduces exactly, plus basic
sanity on the extracted assets.

Usage: scene_dump.py [--level N] [--frame N] [--out DIR]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image

PORT = Path(__file__).resolve().parents[1]
HARNESS = PORT / "build" / "benefactor-harness"


def dump(level: int, frame: int, out: Path) -> str:
    if out.exists():
        shutil.rmtree(out)
    env = os.environ.copy()
    env.update({
        "BENEFACTOR_SKIP_PUAE": "1",
        "BENEFACTOR_WIDESCREEN_MODE": "16:9",
        "BENEFACTOR_RENDERER": "benren",
        "BENEFACTOR_PRESENT": "sdl",
    })
    rel = os.path.relpath(out, PORT)
    proc = subprocess.run(
        [str(HARNESS), "--level", str(level), "Disk.1", "Disk.2", "Disk.3"],
        cwd=PORT, env=env,
        input=f"rungame\npc {frame}\nscenedump {rel}\nq\n",
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=300, check=False,
    )
    if not (out / "scene.txt").is_file():
        raise SystemExit(f"scene dump failed (rc={proc.returncode}):\n{proc.stdout[-2000:]}")
    m = re.search(r"\[scenedump\] (\d+) quads, (\d+) distinct assets", proc.stdout)
    if not m:
        raise SystemExit(f"no scenedump summary line:\n{proc.stdout[-2000:]}")
    return proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--frame", type=int, default=40)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or PORT / "analysis" / "scene-inventory" / f"level{args.level}"

    dump(args.level, args.frame, out)
    lines = (out / "scene.txt").read_text().splitlines()
    nquads = len(lines)
    id_to_file: dict[str, Path] = {}
    world = screen = shadow = 0
    for line in lines:
        f = dict(re.findall(r"(\w+)=(\S+)", line))
        ident = f["id"]
        world += f["space"] == "WORLD"
        screen += f["space"] == "SCREEN"
        shadow += f["shadow"] == "1"
        id_to_file.setdefault(ident, out / f"asset_{ident}_{f['w']}x{f['h']}.png")
    pngs = sorted(out.glob("asset_*.png"))
    if nquads < 300:
        raise SystemExit(f"too few quads: {nquads}")
    if len(id_to_file) < 40:
        raise SystemExit(f"too few distinct assets: {len(id_to_file)}")
    if shadow == 0:
        raise SystemExit("no character (shadow) quads in the dump")
    if len(pngs) != len(id_to_file):
        raise SystemExit(f"asset file count {len(pngs)} != distinct ids {len(id_to_file)}")
    for ident, path in id_to_file.items():
        if not path.is_file():
            raise SystemExit(f"missing asset bitmap for {ident}: {path.name}")
        with Image.open(path) as im:
            im.verify()

    # Determinism: the same frame in a fresh process must reproduce the same list.
    again = out.with_name(out.name + "-recheck")
    dump(args.level, args.frame, again)
    if (again / "scene.txt").read_text() != (out / "scene.txt").read_text():
        raise SystemExit("scene inventory is not reproducible across runs")
    if {p.name for p in again.glob("asset_*.png")} != {p.name for p in pngs}:
        raise SystemExit("asset bitmap set differs across runs")
    shutil.rmtree(again)

    print(f"PASS scene inventory: level {args.level} frame {args.frame}: "
          f"{nquads} quads ({world} WORLD, {screen} SCREEN, {shadow} character) "
          f"-> {len(id_to_file)} distinct assets in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
