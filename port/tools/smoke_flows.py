#!/usr/bin/env python3
"""Headless regression tests for cold boot and poster/menu/gameplay flow."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "benefactor-pc"
DISKS = [ROOT / "Disk.1", ROOT / "Disk.2", ROOT / "Disk.3"]


def request(port: int, path: str) -> bytes:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=1) as response:
        return response.read()


def state(port: int) -> dict:
    try:
        return json.loads(request(port, "/state"))
    except Exception:
        return {}


def run(name: str, port: int, skip_intro: bool) -> dict:
    env = os.environ.copy()
    env.update({
        "BENEFACTOR_HTTP": str(port),
        "BENEFACTOR_NO_PACE": "1",
        "BENEFACTOR_SKIP_INTRO": "1" if skip_intro else "0",
        "BENEFACTOR_WIDESCREEN_MODE": "16:9",
        "BENEFACTOR_RENDERER": "benren",
        "BENEFACTOR_PRESENT": "sdl",
    })
    if skip_intro:
        env.update({
            "BENEFACTOR_PRESS": "40", "BENEFACTOR_RELEASE": "41",
            "BENEFACTOR_PRESS2": "200", "BENEFACTOR_RELEASE2": "210",
            "BENEFACTOR_LIMIT": "500",
        })
    proc = subprocess.Popen(
        [str(BIN), "--headless", *map(str, DISKS)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.monotonic() + 12.0
        current = {}
        saw_menu = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"process exited early with {proc.returncode}")
            current = state(port)
            if current.get("cop1lc") == "008302":
                saw_menu = True
            if current.get("gameplay_active") == 1:
                break
            if not skip_intro and current.get("overlay_active") == 1:
                break
            time.sleep(0.02)

        if skip_intro:
            if not saw_menu:
                raise RuntimeError(f"main menu was not reached: {current}")
            if current.get("gameplay_active") != 1:
                raise RuntimeError(f"menu did not enter gameplay: {current}")
        elif current.get("overlay_active") != 1 and current.get("gameplay_active") != 1:
            raise RuntimeError(f"cold intro did not reach an overlay: {current}")

        ppm = request(port, "/fb.ppm")
        if len(ppm) < 1000:
            raise RuntimeError("framebuffer is empty")
        return {"name": name, "state": current, "saw_menu": saw_menu,
                "framebuffer_bytes": len(ppm)}
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            output, _ = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate(timeout=3)
        errors = [line for line in output.splitlines()
                  if "[rt-miss]" in line or "[watchdog]" in line or "unhandled" in line]
        if errors:
            raise RuntimeError("\n".join(errors))


def main() -> int:
    results = [
        run("cold-intro", 8798, False),
        run("poster-menu-gameplay", 8799, True),
    ]
    for result in results:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
