# Benefactor reverse-engineering workspace

## Purpose
Determine a practical path from the user-supplied Amiga Benefactor disk images to a native PC game with modern rendering and true widescreen, without shipping an Amiga emulator.

## Inputs and safety
- The three original ZIP files under `/home/salmon/benefactor/` are authoritative user inputs. Never modify them.
- Extracted ADFs under `disks/` are analysis inputs. Treat them as read-only.
- Keep extracted proprietary data and disassembly local. Do not publish game assets, generated game code, ROMs, or copyrighted source excerpts.
- Emulation may be used only as a development oracle/debugger. The target product must not require an emulator.
- Separate observed facts, derived conclusions, and hypotheses in every report.

## Tooling
- Use `/home/salmon/benefactor-re/.venv/bin/python` for Python analysis; Capstone and Pillow are installed there.
- OpenCode is available with model `opencode-go/hungerg-free`.
- REA MCP is connected, but its advertised `open_binary` raw-binary architectures do not include Motorola 68000 and it has no Amiga HUNK loader. Do not assume REA can disassemble 68000 directly.
- Prefer Capstone, custom Amiga hunk/ADF parsers, and Ghidra/IRA when a real 68000 loader is needed.

## Deliverables
- Preserve evidence: hashes, offsets, disk geometry, parser assumptions, and command provenance.
- Put durable findings under `reports/` and reusable tools under `tools/`.
- Do not claim a function or format is understood until supported by bytes, control flow, execution evidence, or an authoritative reference.
