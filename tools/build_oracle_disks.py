#!/usr/bin/env python3
"""Rebuild disk images for the PUAE/WHDLoad development oracle.

The supplied CLS ADFs insert a 0x400-byte crack stub before streamed game
payloads. Disk.1 is special: its initial crack loader reads the main bank from
physical $1C80, so the boot/main area must remain byte-for-byte intact. Later
WHDLoad-patched loads use logical offsets, so the title bank and everything
after it are shifted left by $400. Disks 2 and 3 contain streamed payloads only
and are shifted wholesale.

The CLS redistribution also moved four world-5 streams and the credits stream
without updating the game's table. This script copies those exact payloads to
the logical offsets the original game requests. The result is development-only
and must never be shipped.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "disks"
OUT = ROOT / "port" / "oracle-disks"
WHDLOAD_DISK_SIZE = 1003520  # $F5000, the raw image size expected by WHDLoad.

D1_TITLE_LOGICAL = 0x26270
D1_TITLE_PHYSICAL = 0x26670
CLS_SHIFT = 0x400

# (request disk, logical offset, length, source disk, physical source offset)
ALIASES = (
    (2, 0x0DE203, 0x0050A6, 3, 0x0558CC),
    (2, 0x0E3387, 0x0064B8, 3, 0x05AA50),
    (2, 0x0D22EB, 0x009388, 3, 0x499B4),
    (2, 0x0E983F, 0x0051DC, 3, 0x060F08),
    (3, 0x0C7100, 0x001888C, 3, 0x031128),
)


def _pad_to_whdload(data: bytearray) -> bytearray:
    if len(data) > WHDLOAD_DISK_SIZE:
        raise ValueError(f"reconstructed image is {len(data)} bytes, limit is {WHDLOAD_DISK_SIZE}")
    if len(data) < WHDLOAD_DISK_SIZE:
        data.extend(b"\0" * (WHDLOAD_DISK_SIZE - len(data)))
    return data


def _place(data: bytearray, off: int, payload: bytes) -> None:
    end = off + len(payload)
    if off < 0 or end > len(data):
        raise ValueError(f"write ${off:X}..${end:X} exceeds ${len(data):X}-byte image")
    data[off:end] = payload


def reconstruct_oracle_disks(d1: bytes, d2: bytes, d3: bytes) -> tuple[bytes, bytes, bytes]:
    """Return logical Disk.1/2/3 images for the WHDLoad oracle."""
    originals = (d1, d2, d3)
    if any(len(data) > WHDLOAD_DISK_SIZE for data in originals):
        raise ValueError("input image exceeds the WHDLoad raw-image size")
    if len(d1) < D1_TITLE_PHYSICAL:
        raise ValueError("Disk.1 is too short to contain the title bank")

    # Preserve Disk.1's boot block, decoy header, and valid main payload at
    # physical $1C80. Only the title-and-later region uses logical offsets.
    logical1 = bytearray(d1[:D1_TITLE_LOGICAL] + d1[D1_TITLE_PHYSICAL:])
    logical2 = bytearray(d2[CLS_SHIFT:])
    logical3 = bytearray(d3[CLS_SHIFT:])
    images = [
        _pad_to_whdload(logical1),
        _pad_to_whdload(logical2),
        _pad_to_whdload(logical3),
    ]

    for disk_no, logical_off, length, source_disk, physical_off in ALIASES:
        source = originals[source_disk - 1]
        end = physical_off + length
        if end > len(source):
            raise ValueError(
                f"Disk.{source_disk} source ${physical_off:X}..${end:X} "
                f"exceeds ${len(source):X} bytes"
            )
        _place(images[disk_no - 1], logical_off, source[physical_off:end])

    return bytes(images[0]), bytes(images[1]), bytes(images[2])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install",
        type=Path,
        help="also copy the WHDLoad support tree here and replace its Disk.1/2/3",
    )
    args = parser.parse_args()

    files = sorted(SRC.glob("*.adf"))
    if len(files) != 3:
        raise SystemExit("expected three ADFs")
    disks = reconstruct_oracle_disks(*(path.read_bytes() for path in files))

    OUT.mkdir(parents=True, exist_ok=True)
    for index, data in enumerate(disks, 1):
        path = OUT / f"Disk.{index}"
        path.write_bytes(data)
        print(f"{path}: {len(data)} bytes sha256={hashlib.sha256(data).hexdigest()}")

    if args.install:
        source_install = ROOT / "port" / "whdload" / "Benefactor"
        if not source_install.is_dir():
            raise SystemExit(f"WHDLoad support tree not found: {source_install}")
        shutil.copytree(source_install, args.install, dirs_exist_ok=True)
        for index, data in enumerate(disks, 1):
            (args.install / f"Disk.{index}").write_bytes(data)
        print(f"oracle install: {args.install}")


if __name__ == "__main__":
    main()
