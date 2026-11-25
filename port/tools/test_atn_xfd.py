#!/usr/bin/env python3
"""Differential-test the native ATN!/IMP! decoder against xfd-native.

xfd-native runs the original 68000 decruncher slaves under Musashi. It is used
only as a development oracle; neither it nor Musashi is linked into the game.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISKS = sorted((ROOT / "disks").glob("*.adf"))
XFD = ROOT / "reference" / "xfd-native" / "build" / "xfdnative"
HELPER = ROOT / "analysis" / "bootstrap" / "atn_decode"


def build_helper() -> None:
    HELPER.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "cc", "-O2", "-I", str(ROOT / "reference" / "static" / "src"),
        str(ROOT / "tools" / "atn_decode.c"),
        str(ROOT / "reference" / "static" / "src" / "engine" / "disk_boot.c"),
        "-o", str(HELPER),
    ], check=True)


def main() -> int:
    if not XFD.exists():
        raise SystemExit(f"missing xfd-native oracle: {XFD}")
    build_helper()
    rows = []
    with tempfile.TemporaryDirectory(dir=ROOT / "analysis") as td:
        tmp = Path(td)
        for disk in DISKS:
            data = disk.read_bytes()
            for magic in (b"ATN!", b"IMP!"):
                pos = 0
                while True:
                    off = data.find(magic, pos)
                    if off < 0 or off + 12 > len(data):
                        break
                    pos = off + 1
                    out_len, packed_len = struct.unpack_from(">II", data, off + 4)
                    if not (58 <= packed_len <= out_len <= 0x400000):
                        continue
                    read_len = min(packed_len + 0x32, len(data) - off)
                    packed = tmp / "packed.bin"
                    xfd_out = tmp / "xfd.bin"
                    native_out = tmp / "native.bin"
                    packed.write_bytes(data[off : off + read_len])
                    for p in (xfd_out, native_out):
                        p.unlink(missing_ok=True)
                    xfd = subprocess.run(
                        [str(XFD), "-f", str(packed), str(xfd_out)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    native = subprocess.run([
                        str(HELPER), str(disk), hex(off), hex(read_len), str(native_out),
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    xfd_ok = xfd.returncode == 0 and xfd_out.exists()
                    native_ok = native.returncode == 0 and native_out.exists()
                    same = None
                    if xfd_ok and native_ok:
                        same = hashlib.sha256(xfd_out.read_bytes()).digest() == \
                               hashlib.sha256(native_out.read_bytes()).digest()
                    rows.append({
                        "disk": disk.name, "offset": hex(off), "magic": magic.decode(),
                        "output": out_len, "packed": packed_len,
                        "xfd_ok": xfd_ok, "native_ok": native_ok, "same": same,
                    })
    report = ROOT / "reports" / "atn-differential.json"
    report.write_text(json.dumps(rows, indent=2) + "\n")
    both_ok = [r for r in rows if r["xfd_ok"] and r["native_ok"]]
    both_bad = [r for r in rows if not r["xfd_ok"] and not r["native_ok"]]
    mismatches = [r for r in both_ok if not r["same"]]
    status_mismatches = [r for r in rows if r["xfd_ok"] != r["native_ok"]]
    print(f"streams={len(rows)} decoded={len(both_ok)} agreed_corrupt={len(both_bad)} "
          f"byte_mismatches={len(mismatches)} status_mismatches={len(status_mismatches)}")
    for row in mismatches + status_mismatches:
        print(json.dumps(row))
    return 1 if mismatches or status_mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
