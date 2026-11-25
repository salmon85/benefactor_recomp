#!/usr/bin/env python3
"""Headless smoke test for the native end-game credits bank."""
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
PORT = 8790


def request(path: str) -> bytes:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=1) as response:
        return response.read()


def main() -> int:
    env = os.environ.copy()
    env.update({
        "BENEFACTOR_HTTP": str(PORT),
        "BENEFACTOR_NO_PACE": "1",
        "BENEFACTOR_WIDESCREEN_MODE": "16:9",
        "BENEFACTOR_RENDERER": "benren",
        "BENEFACTOR_PRESENT": "sdl",
    })
    proc = subprocess.Popen(
        [str(BIN), "--headless", "--credits", *map(str, DISKS)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.monotonic() + 8.0
        state = {}
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"process exited early with {proc.returncode}")
            try:
                state = json.loads(request("/state"))
                if state.get("credits_active") == 1:
                    break
            except Exception:
                pass
            time.sleep(0.05)
        if state.get("credits_active") != 1:
            raise RuntimeError(f"credits bank did not activate: {state}")
        time.sleep(0.25)
        ppm = request("/fb.ppm")
        if len(ppm) < 1000:
            raise RuntimeError("credits framebuffer is empty")
        print(json.dumps({"state": state, "framebuffer_bytes": len(ppm)}))
        return 0
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            output, _ = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate(timeout=3)
        errors = [line for line in output.splitlines() if "[rt-miss]" in line or "[watchdog]" in line]
        if errors:
            print("\n".join(errors))


if __name__ == "__main__":
    raise SystemExit(main())
