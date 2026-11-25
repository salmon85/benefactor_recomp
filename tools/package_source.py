#!/usr/bin/env python3
"""Create a source-only Benefactor RE archive.

Excludes proprietary game code/assets, disk images, ROMs, generated banks,
build products, oracle states, and third-party vendor trees. The archive is
not playable by itself; recipients must supply their own disks and regenerate.
"""
from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "benefactor-re-source.tar.gz"
INCLUDE_DIRS = {"port", "tools", "tests", "docs", "reports"}
INCLUDE_FILES = {"TODO.md", "README.md", "LICENSE", "AGENTS.md"}
EXCLUDE_PARTS = {
    ".git", ".venv", "build", "dist", "logs", "scratch", "analysis", "reference",
    "vendor", "generated", "decomp", "oracle-disks", "oracle-whdload", "whdload", "kickstart", "__pycache__",
}
EXCLUDE_SUFFIXES = {
    ".adf", ".zip", ".lha", ".rom", ".bin", ".state", ".o", ".a", ".so",
    ".ppm", ".png", ".jpg", ".log", ".jsonl",
}


def allowed(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_PARTS for part in rel.parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if path.name.startswith("Disk."):
        return False
    # INCLUDE_FILES are top-level files only (not vendored copies of the same name).
    if rel.parts[0] in INCLUDE_DIRS:
        return path.is_file()
    if len(rel.parts) == 1 and rel.name in INCLUDE_FILES:
        return path.is_file()
    return False


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*") if allowed(p))
    with tarfile.open(OUT, "w:gz") as tf:
        for path in files:
            tf.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"{OUT}: {len(files)} files, {OUT.stat().st_size} bytes, sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
