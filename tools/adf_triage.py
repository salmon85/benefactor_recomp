#!/usr/bin/env python3
"""Read-only static triage for Amiga ADF images.

Records image identity, standard double-density geometry, sector-zero headers,
known signature hits, and size-bearing container candidates. Container sizes are
candidate interpretations of big-endian header fields, not proof of a decoder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

SECTOR_SIZE = 512
SECTORS_PER_TRACK = 11
HEADS = 2
CYLINDERS = 80
STANDARD_DD_SIZE = SECTOR_SIZE * SECTORS_PER_TRACK * HEADS * CYLINDERS
BOOTBLOCK_SIZE = 1024
MAX_OUTPUT_SIZE = 16 * 1024 * 1024

SIGNATURES = {
    b"DOS\0": "Amiga DOS boot magic",
    b"TSL!": "custom TSL! tag / repeated filler",
    b"BENEFACTOR DISK 2": "custom Disk.2 header",
    b"BENEFACTOR DISK 3": "custom Disk.3 header",
    b"ATN!": "Imploder-family container candidate",
    b"IMP!": "Imploder-family container candidate",
    b"=SB=": "LH5-style stream candidate",
    b"FORM": "IFF FORM container",
    b"CAT ": "IFF CAT container",
    b"ILBM": "IFF bitmap chunk tag",
    b"8SVX": "IFF audio chunk tag",
    b"HUNK": "Amiga hunk header tag",
    b"PP20": "PowerPacker tag",
    b"PACK": "Amiga packer tag",
    b"LZW ": "IFF LZW chunk tag",
}
SIZED_SIGNATURES = {b"ATN!": 12, b"IMP!": 12, b"=SB=": 12, b"FORM": 8, b"CAT ": 8}
CONTAINER_SIGNATURES = tuple(SIZED_SIGNATURES)


def ascii_preview(data: bytes) -> str:
    return "".join(chr(value) if 32 <= value < 127 else "." for value in data)


def find_all(data: bytes, signature: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        offset = data.find(signature, start)
        if offset < 0:
            return offsets
        offsets.append(offset)
        start = offset + 1


def repeated_runs(data: bytes, signature: bytes) -> list[dict]:
    """Return maximal ranges made of adjacent, non-overlapping signature copies."""
    runs: list[dict] = []
    search = 0
    width = len(signature)
    while True:
        start = data.find(signature, search)
        if start < 0:
            return runs
        end = start + width
        while data[end : end + width] == signature:
            end += width
        copies = (end - start) // width
        if copies > 1:
            runs.append(
                {
                    "offset": start,
                    "offset_hex": f"0x{start:x}",
                    "end_exclusive": end,
                    "end_hex": f"0x{end:x}",
                    "size": end - start,
                    "copies": copies,
                }
            )
        search = end


def sector_location(offset: int) -> dict:
    sector = offset // SECTOR_SIZE
    track = sector // SECTORS_PER_TRACK
    return {
        "sector": sector,
        "offset_in_sector": offset % SECTOR_SIZE,
        "cylinder": track // HEADS,
        "head": track % HEADS,
        "sector_in_track": sector % SECTORS_PER_TRACK + 1,
    }


def zero_sector_runs(data: bytes) -> list[dict]:
    states = [any(data[offset : offset + SECTOR_SIZE]) for offset in range(0, len(data), SECTOR_SIZE)]
    runs: list[dict] = []
    start = 0
    for index in range(1, len(states) + 1):
        if index == len(states) or states[index] != states[start]:
            if not states[start]:
                runs.append({"start_sector": start, "end_sector_exclusive": index, "count": index - start})
            start = index
    return runs


def bootblock_info(data: bytes) -> dict | None:
    if len(data) < BOOTBLOCK_SIZE or data[:4] != b"DOS\0":
        return None
    stored = struct.unpack_from(">I", data, 4)[0]
    total = 0
    for offset in range(0, BOOTBLOCK_SIZE, 4):
        previous = total
        total = (total + struct.unpack_from(">I", data, offset)[0]) & 0xFFFFFFFF
        if total < previous:
            total = (total + 1) & 0xFFFFFFFF
    return {
        "size": BOOTBLOCK_SIZE,
        "checksum_offset": 4,
        "checksum_algorithm": "additive end-around carry over all 256 big-endian longwords",
        "checksum_stored_be32": f"0x{stored:08x}",
        "checksum_total_be32": f"0x{total:08x}",
        "checksum_valid": total == 0xFFFFFFFF,
        "entry_offset": 0x0C,
        "entry_bytes_hex": data[0x0C:0x10].hex(" "),
    }


def sized_candidate(data: bytes, offset: int, signature: bytes, next_offsets: list[int]) -> dict:
    header_size = SIZED_SIGNATURES[signature]
    available = len(data) - offset
    candidate = {
        "signature": signature.decode("ascii"),
        "offset": offset,
        "offset_hex": f"0x{offset:x}",
        **sector_location(offset),
        "header_size": header_size,
        "header_hex": data[offset : offset + header_size].hex(" "),
    }
    reasons: list[str] = []
    if available < header_size:
        candidate.update(
            {
                "plausible": False,
                "rejected_reasons": ["truncated header"],
                "fits_image": False,
            }
        )
        return candidate

    if signature in (b"FORM", b"CAT "):
        declared_size = struct.unpack_from(">I", data, offset + 4)[0]
        end = offset + header_size + declared_size
        plausible_size = declared_size > 0
        packed_relation = True
        candidate["declared_payload_size"] = declared_size
        candidate["declared_payload_size_hex"] = f"0x{declared_size:x}"
    elif signature in (b"ATN!", b"IMP!"):
        declared_output, trailer_offset = struct.unpack_from(">II", data, offset + 4)
        trailer = offset + trailer_offset
        end = trailer + 0x32
        plausible_size = 0 < declared_output <= MAX_OUTPUT_SIZE and trailer_offset >= header_size
        packed_relation = trailer_offset >= header_size
        candidate["declared_output_size"] = declared_output
        candidate["declared_output_size_hex"] = f"0x{declared_output:x}"
        candidate["declared_trailer_offset"] = trailer_offset
        candidate["declared_trailer_offset_hex"] = f"0x{trailer_offset:x}"
        candidate["trailer_offset"] = trailer
        candidate["trailer_offset_hex"] = f"0x{trailer:x}"
        candidate["trailer_size"] = 0x32
        candidate["packed_data_size"] = trailer_offset - header_size
        trailer_available = trailer + 0x32 <= len(data)
        candidate["trailer_available"] = trailer_available
        if trailer_available:
            literal_run = struct.unpack_from(">I", data, trailer + 12)[0]
            bit_word = struct.unpack_from(">H", data, trailer + 16)[0]
            token_table = data[trailer + 18 : trailer + 46]
            trailer_valid = literal_run <= declared_output and any(token_table)
            candidate["trailer_literal_run"] = literal_run
            candidate["trailer_bit_word"] = f"0x{bit_word:04x}"
            candidate["trailer_token_table_hex"] = token_table.hex(" ")
            candidate["trailer_structurally_valid"] = trailer_valid
            if literal_run > declared_output:
                reasons.append("trailer literal run exceeds output size")
            if not any(token_table):
                reasons.append("trailer token table is empty")
        else:
            trailer_valid = False
            reasons.append("trailer extends past image end")
        if declared_output == 0:
            reasons.append("zero output size")
        elif declared_output > MAX_OUTPUT_SIZE:
            reasons.append("output size exceeds triage limit")
        if trailer_offset < header_size:
            reasons.append("trailer offset overlaps header")
    else:
        declared_output, declared_packed = struct.unpack_from(">II", data, offset + 4)
        declared_size = declared_packed
        end = offset + header_size + declared_packed
        plausible_size = 0 < declared_output <= MAX_OUTPUT_SIZE and 0 < declared_packed <= declared_output
        packed_relation = 0 < declared_packed <= declared_output
        candidate["declared_output_size"] = declared_output
        candidate["declared_output_size_hex"] = f"0x{declared_output:x}"
        if declared_output == 0:
            reasons.append("zero output size")
        elif declared_output > MAX_OUTPUT_SIZE:
            reasons.append("output size exceeds triage limit")
        if declared_packed == 0:
            reasons.append("zero packed size")
        elif not packed_relation:
            reasons.append("packed size exceeds output size")

    fits = end <= len(data)
    if signature in (b"FORM", b"CAT ", b"=SB=") and declared_size == 0:
        reasons.append("zero container size")
    if not fits:
        reasons.append("container extends past image end")

    next_offset = next((value for value in next_offsets if value > offset), None)
    common = {
        "data_offset": offset + header_size,
        "end_exclusive": end,
        "end_hex": f"0x{end:x}",
        "fits_image": fits,
        "plausible": bool(
            plausible_size
            and packed_relation
            and fits
            and (trailer_valid if signature in (b"ATN!", b"IMP!") else True)
        ),
        "rejected_reasons": reasons,
        "next_container_signature_offset": next_offset,
        "next_container_signature_gap_from_start": None if next_offset is None else next_offset - offset,
        "gap_after_end_to_next_signature": None if next_offset is None or end > next_offset else next_offset - end,
    }
    if signature in (b"FORM", b"CAT "):
        common["declared_payload_size"] = declared_size
        common["declared_payload_size_hex"] = f"0x{declared_size:x}"
    elif signature in (b"ATN!", b"IMP!"):
        common["container_size"] = end - offset
    else:
        common["declared_packed_size"] = declared_size
        common["declared_packed_size_hex"] = f"0x{declared_size:x}"
        common["container_size"] = end - offset
    candidate.update(common)
    return candidate


def triage_image(path: Path) -> dict:
    data = path.read_bytes()
    hits = {signature: find_all(data, signature) for signature in SIGNATURES}

    signature_report: dict[str, dict] = {}
    for signature, offsets in hits.items():
        shown = offsets[:32]
        entry = {
            "description": SIGNATURES[signature],
            "count": len(offsets),
            "first_offset": offsets[0] if offsets else None,
            "first_offset_hex": f"0x{offsets[0]:x}" if offsets else None,
            "last_offset": offsets[-1] if offsets else None,
            "last_offset_hex": f"0x{offsets[-1]:x}" if offsets else None,
            "offsets": shown,
            "offsets_hex": [f"0x{offset:x}" for offset in shown],
            "offsets_truncated": len(offsets) > len(shown),
        }
        if signature == b"TSL!":
            entry["repetitive_runs"] = repeated_runs(data, signature)
        signature_report[signature.decode("ascii", "backslashreplace")] = entry

    all_container_offsets = sorted({offset for signature in CONTAINER_SIGNATURES for offset in hits[signature]})
    candidates = [
        sized_candidate(data, offset, signature, all_container_offsets)
        for signature in CONTAINER_SIGNATURES
        for offset in hits[signature]
    ]
    candidates.sort(key=lambda item: item["offset"])
    plausible = [item for item in candidates if item["plausible"]]
    for candidate in plausible:
        start = candidate["offset"]
        end = candidate["end_exclusive"]
        candidate["overlaps_plausible_offsets"] = [
            other["offset_hex"]
            for other in plausible
            if other is not candidate and start < other["end_exclusive"] and other["offset"] < end
        ]

    sector0 = data[:SECTOR_SIZE]
    standard_match = len(data) == STANDARD_DD_SIZE
    tag = struct.unpack_from(">H", data, 0x3FE)[0] if len(data) >= 0x400 else None
    sector_headers = []
    for sector in range(min(4, len(data) // SECTOR_SIZE)):
        offset = sector * SECTOR_SIZE
        header = data[offset : offset + 32]
        sector_headers.append(
            {
                "sector": sector,
                "offset": offset,
                "offset_hex": f"0x{offset:x}",
                "first_32_hex": header.hex(" "),
                "first_32_ascii": ascii_preview(header),
            }
        )
    return {
        "path": str(path),
        "name": path.name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "geometry": {
            "sector_size": SECTOR_SIZE,
            "total_sectors": len(data) // SECTOR_SIZE,
            "trailing_partial_sector_bytes": len(data) % SECTOR_SIZE,
            "standard_dd_size": STANDARD_DD_SIZE,
            "matches_standard_dd": standard_match,
            "cylinders": CYLINDERS if standard_match else None,
            "heads": HEADS if standard_match else None,
            "sectors_per_track": SECTORS_PER_TRACK if standard_match else None,
        },
        "sector_zero": {
            "sha256": hashlib.sha256(sector0).hexdigest(),
            "first_64_hex": sector0[:64].hex(" "),
            "first_64_ascii": ascii_preview(sector0[:64]),
            "custom_tag_be16_at_0x3fe": None if tag is None else f"0x{tag:04x}",
        },
        "sector_headers": sector_headers,
        "bootblock": bootblock_info(data),
        "signatures": signature_report,
        "container_candidates": candidates,
        "zero_sector_runs": zero_sector_runs(data),
    }


def expand_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".adf"))
        elif path.is_file():
            expanded.append(path)
        else:
            raise FileNotFoundError(path)
    if not expanded:
        raise ValueError("no ADF inputs found")
    return expanded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="ADF files or directories (default: disks/)")
    parser.add_argument("--output", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args()

    try:
        images = expand_paths(args.paths or [Path("disks")])
        report = {
            "schema_version": 1,
            "assumptions": {
                "geometry": "standard Amiga DD: 80 cylinders, 2 heads, 11 sectors/track, 512-byte sectors",
                "sector_order": "linear ADF sector order; cylinder = sector // 22, head = (sector // 11) % 2",
                "header_endian": "big-endian 32-bit size fields",
                "container_size_interpretation": (
                    "ATN!/IMP! use [magic][output size][trailer offset from start]; the observed decoder trailer is "
                    "0x32 bytes (three saved longs, literal count, bit word, 28-byte token table). =SB= uses "
                    "[magic][output size][packed payload size]. FORM/CAT use [magic][payload size]. "
                    "These are structural candidates, not decoder validation."
                ),
                "plausibility": (
                    "nonzero sizes; ATN!/IMP! trailer offset at least 12; =SB= packed <= output; inferred end within image"
                ),
                "coverage": "raw byte scan; embedded magic inside compressed data can create false candidates",
            },
            "signatures_scanned": {
                signature.decode("ascii", "backslashreplace"): description for signature, description in SIGNATURES.items()
            },
            "disks": [triage_image(path) for path in images],
        }
    except (OSError, ValueError) as error:
        parser.error(str(error))

    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
