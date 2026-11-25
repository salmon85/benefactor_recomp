# TODO

## Completed
- [x] Inventory and hash the three user-supplied CLS ADFs.
- [x] Confirm REA is connected but does not advertise a 68000/Amiga HUNK loader.
- [x] Use Capstone for Motorola 68000 disassembly.
- [x] Identify the CLS 0x400-byte data shift and map runtime disk reads.
- [x] Decrunch main, title, relocation, gameplay-low, and gameplay-engine ATN! payloads.
- [x] Assemble main/title/gameplay memory banks and apply gameplay relocations.
- [x] Statically translate 1,227 functions to C and build a native PC executable.
- [x] Verify direct-level gameplay and 500x282 widescreen rendering without an interpreter.
- [x] Smoke-test all 60 direct levels: 60/60 pass.
- [x] Boot the poster/title overlay with `BENEFACTOR_SKIP_INTRO=1`.
- [x] Resolve world-5 loading via exact CLS Disk.2 -> Disk.3 stream aliases.
- [x] Verify cold intro without the `$00646E` dispatch miss.
- [x] Map, decrunch, and translate the 26-function Disk.3 credits bank.
- [x] Verify poster -> menu -> gameplay flow with a deterministic headless smoke test.
- [x] Differential-test the native ATN decoder against xfd-native: 32 byte-exact decodes, 2 agreed-corrupt streams, 0 mismatches.
- [x] Repair the development-only PUAE/WHDLoad disk oracle and verify stable gameplay on levels 1 and 49.
- [x] Add an optional original vector HD HUD in the widescreen side margin, with a framebuffer regression test.
- [x] Keep the static gameplay banks; modernize platform-facing owners as readable native C.
- [x] Produce a source-only archive that excludes proprietary code/assets, disks, ROMs, generated banks, and build products.
- [x] Add deterministic shared-entry PUAE/PC lockstep gates for sustained level-1 and world-5 gameplay (480 frames).
- [x] Correct native audio output to 44.1 kHz and PUAE master gain; pass bounded level-1 aligned PCM parity.
- [x] Match the three measured CIA audio phases and pass bounded per-channel world-5 PCM content/gain parity.
- [x] Extract a stable per-asset scene inventory (`scenedump` + `port/tools/scene_dump.py`) as the handoff into the replacement-art stage.

## Open
- [ ] Replace sprites/tiles with new art keyed by scene-inventory ids, plus shader work beyond the existing BenRen/Vulkan renderer and optional HD side HUD.
- [ ] Publish/package a playable build only after proprietary generated code/assets are excluded and distribution permission is resolved.
