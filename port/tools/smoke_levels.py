#!/usr/bin/env python3
"""Headless smoke test for statically recompiled Benefactor levels."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "benefactor-pc"
DISKS = [ROOT / "Disk.1", ROOT / "Disk.2", ROOT / "Disk.3"]


def request(port: int, path: str) -> bytes:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=1) as response:
        return response.read()


def wait_ready(port: int, proc: subprocess.Popen, timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"process exited early with {proc.returncode}")
        try:
            return json.loads(request(port, "/state"))
        except Exception as exc:  # noqa: BLE001 - diagnostic retry loop
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"HTTP debug server not ready: {last_error}")


def run_level(level: int, port: int) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "BENEFACTOR_HTTP": str(port),
            "BENEFACTOR_NO_PACE": "1",
            "BENEFACTOR_WIDESCREEN_MODE": "16:9",
            "BENEFACTOR_RENDERER": "benren",
            "BENEFACTOR_PRESENT": "sdl",
        }
    )
    proc = subprocess.Popen(
        [str(BIN), "--headless", "--level", str(level), *map(str, DISKS)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_ready(port, proc)
        request(port, "/input?fire=1")
        time.sleep(0.15)
        request(port, "/input?fire=0&r=1")
        deadline = time.monotonic() + 6.0
        state = {}
        while time.monotonic() < deadline:
            state = json.loads(request(port, "/state"))
            if state.get("saveable") == 1 and state.get("cop1lc") == "003484":
                break
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        ppm = request(port, "/fb.ppm")
        header = ppm.split(b"\n", 3)[:3]
        return {
            "level": level,
            "state": state,
            "framebuffer_header": [line.decode("ascii") for line in header],
            "framebuffer_bytes": len(ppm),
            "process_exited": proc.poll(),
        }
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
            print("\n".join(errors), file=sys.stderr)


def main() -> int:
    levels = [int(value) for value in sys.argv[1:]] or [1, 9, 22, 35, 60]
    results = []
    for index, level in enumerate(levels):
        try:
            result = run_level(level, 8800 + index)
        except Exception as exc:  # noqa: BLE001 - report per-level failure
            result = {"level": level, "error": str(exc)}
        results.append(result)
        print(json.dumps(result), flush=True)
    return 0 if all("error" not in item and item.get("state", {}).get("saveable") == 1 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
