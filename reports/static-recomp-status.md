# Benefactor static recompilation status

## Bottom line

A native, no-interpreter PC build exists at:

`/home/salmon/benefactor-re/port/build/benefactor-pc`

It is produced by statically translating the recovered Motorola 68000 banks to C and compiling that C with the native Benefactor runtime. The runtime contains native disk/decompression, OCS/CIA service, audio, input, scene/rendering, and widescreen owners. No 68000 interpreter or Amiga emulator is linked into the gameplay executable.

All 60 direct levels now pass the headless gameplay smoke test. Cold intro, the poster/menu/gameplay route, and the end-game credits bank also pass targeted smoke tests. The existing BenRen/Vulkan renderer produces 500x282 widescreen frames. An optional original vector HD HUD can use the right-side widescreen margin without entering the 352px playfield.

## Input identity

The source ZIPs are under `/home/salmon/benefactor/`. Extracted ADFs are under `disks/`.

| Disk | Bytes | SHA-256 |
|---|---:|---|
| Disk.1 | 901120 | `0b7bc60dacc4ab66bb582c51d8fd12181693749f05ac49b7d7acbc31eeee9b71` |
| Disk.2 | 901120 | `2acbe50c90ad2302d97eaa0d18fa9eb6f8c15548817142676eb3960cb4ecd2be` |
| Disk.3 | 901120 | `afa4b06727dbf7c0d75649d4737bc832dbbb4ff95cf8c0bdd20a37260cb25b2a` |

These are standard 80-cylinder, two-head, 11-sector ADFs. `unadf` cannot mount them because the CLS distribution uses a custom boot/data layout rather than a normal AmigaDOS filesystem.

## REA/OpenCode result

OpenCode was run with `opencode-go/hungerg-free`. REA 6.5.0 is connected and reports Ghidra/Hopper providers, but its advertised `open_binary` raw architectures do not include Motorola 68000 and it has no Amiga HUNK loader. Static 68000 work therefore uses Capstone 5.0.9 and custom ADF/ATN tooling.[11]

OpenCode produced `tools/adf_triage.py`, `tests/test_adf_triage.py`, and `reports/disk-triage.json`. Its long bootblock disassembly run was stopped after it began retrying an overloaded inference service; the useful triage artifacts remain.

## Disk mapping recovered

The CLS ADFs insert a 0x400-byte stub before the game data area. Runtime offsets are the original logical offsets; physical payload offsets are:

- Disk.1: `logical + 0x400` for game payloads at/after `0x1880`.
- Disk.2 and Disk.3: `logical + 0x400` for all streamed game payloads, including logical offset zero.

The first `ATN!` at Disk.1 `0x1880` is not the usable main payload for the native Imploder decoder. The valid main payload is at physical `0x1c80`.

Recovered compressed payloads include:

| Guest image | Disk | Logical offset | Physical offset | Decompressed bytes |
|---|---|---:|---:|---:|
| main/intro | 1 | `0x1880` | `0x1c80` | `0x6d13c` |
| title/menu | 1 | `0x26270` | `0x26670` | `0x4575c` |
| gameplay relocation table | 1 | `0x548a0` | `0x54ca0` | `0x2818` |
| gameplay low image | 1 | `0x565ba` | `0x569ba` | `0x280b4` |
| gameplay engine | 1 | `0x689be` | `0x68dbe` | `0x2a9e8` |
| credits/end-game | 3 | `0xc7100` | `0x31128` | `0x31112` |

The title's raw high-score sector is absent at the original offset. A local 100-byte fallback table derived from the supplied distribution is used, with the rest of the `0x1880` area zeroed.

### CLS redistribution aliases

The CLS redistribution moved four shared world-5 streams to Disk.3 while leaving the gameplay table pointed at their old Disk.2 offsets. It also moved the credits stream. `port/src/engine/disk_boot.c` uses exact `(disk, logical offset, length)` aliases:

| Original request | Actual source |
|---|---|
| Disk.2 `0x0de203`, len `0x50a6` | Disk.3 physical `0x558cc` |
| Disk.2 `0x0e3387`, len `0x64b8` | Disk.3 physical `0x5aa50` |
| Disk.2 `0x0d22eb`, len `0x9388` | Disk.3 physical `0x499b4` |
| Disk.2 `0x0e983f`, len `0x51dc` | Disk.3 physical `0x60f08` |
| Disk.3 `0x0c7100`, len `0x1888c` | Disk.3 physical `0x31128` |

The native ATN decoder is bounds-checked and has a cross-disk recovery fallback for corrupt streams. The deterministic aliases above are the primary fix; recovery is not used for the known world-5 path.

## Static translation

Reference tree: the pre-removal static Benefactor port at upstream commit `eb47e74` (the parent of the static-product removal commit). It already contains substantial reverse engineering, a 68000-to-C recompiler, native loaders, a hardware service layer, native widescreen compositing, and BenRen SDL/Vulkan renderers.[8] The WHDLoad install and slave source provide independent loader/decruncher entry-point evidence.[9]

Local working port: `/home/salmon/benefactor-re/port/`

Generated function counts:

| Bank | Functions |
|---|---:|
| main/intro | 64 |
| title/menu | 64 |
| gameplay | 1073 |
| credits/end-game | 26 |
| **Total** | **1227** |

The gameplay completeness gate reports all 384 literal dispatch targets registered. Generated C is local and gitignored because it is derived from copyrighted game code.

## Verified execution

Build command:

```sh
cmake --build /home/salmon/benefactor-re/port/build --target benefactor-pc -j2
```

Representative direct-level command:

```sh
BENEFACTOR_NO_PACE=1 \
BENEFACTOR_WIDESCREEN_MODE=16:9 \
BENEFACTOR_RENDERER=benren \
BENEFACTOR_PRESENT=sdl \
/home/salmon/benefactor-re/port/build/benefactor-pc \
  --headless --level 1 Disk.1 Disk.2 Disk.3
```

All-level smoke command:

```sh
/home/salmon/benefactor-re/.venv/bin/python \
  /home/salmon/benefactor-re/port/tools/smoke_levels.py $(seq 1 60)
```

Result: **60/60 pass**. Every level reaches `cop1lc=003484`, `saveable=1`, and produces a 500x282 frame. World 5 is now named `THE TECHNO TREAT` by the preloader and levels 49-58 load through the Disk.3 aliases.

Additional flow tests:

```sh
/home/salmon/benefactor-re/.venv/bin/python \
  /home/salmon/benefactor-re/port/tools/smoke_flows.py
/home/salmon/benefactor-re/.venv/bin/python \
  /home/salmon/benefactor-re/port/tools/smoke_credits.py
/home/salmon/benefactor-re/.venv/bin/python \
  /home/salmon/benefactor-re/port/tools/smoke_modern_hud.py
/home/salmon/benefactor-re/.venv/bin/python \
  /home/salmon/benefactor-re/port/tools/smoke_puae_oracle.py
```

Results:

- Cold intro reaches the title overlay without a `$646E` dispatch miss.
- Poster reaches the menu, and menu fire enters gameplay.
- Credits activate `credits_active=1`, render a non-empty framebuffer, and produce no dispatch miss/watchdog. The ending story progresses into a stone-tablet credits roll; a captured frame lists Thomas Andersson, Patrik Bergdahl, Olof Gustafsson, and Fredrik Lillegren.
- The credits bank can also be entered directly with `--credits` for testing.
- The optional HD side HUD is enabled by `BENEFACTOR_MODERN_HUD=1` or OPTIONS → GRAPHICS → HD SIDE HUD. Its deterministic off/on capture changes 7,540 pixels at 500x282, bounded to `(434,64)-(490,200)`, entirely right of the 352px playfield.

The HTTP framebuffer reports `P6 / 500 282 / 255`, confirming true 16:9 content rather than a stretched 352-pixel frame. Visual inspection shows coherent cavern geometry, sprites, HUD, and distinct left/right world content.

## Differential verification

A development-only differential test compares the native ATN!/IMP! decoder with `xfd-native`, which runs the original 68000 decruncher slaves under Musashi:

```sh
/home/salmon/benefactor-re/.venv/bin/python \
  /home/salmon/benefactor-re/port/tools/test_atn_xfd.py
```

Result: **34 streams examined; 32 decoded byte-identically; 2 agreed corrupt; 0 byte mismatches; 0 status mismatches.** The two agreed-corrupt streams are the decoy Disk.1 header and the original Disk.2 world-5 copy that the CLS alias replaces.

The development oracle is now deterministic and reaches stable gameplay on levels 1 and 49. `port/tools/smoke_puae_oracle.py` verifies `cop1lc=$003484`, correct `$20.w`, and 60 stable frames; all six loaded level-1 asset regions remain byte-identical (388,006 bytes).

Sustained shared-entry lockstep is implemented in `port/tools/smoke_puae_lockstep.py`. It seeds the same `$577000` entry, advances both cores through the card and 480 gameplay frames, and compares palette/timing/non-pointer Copper state, low memory, player state, and the visible framebuffer. PUAE's comparison crop is `x=96,w=704`; the final 40 output columns are out-of-frame border fill and are excluded, leaving a strict 312x282 region.

Current results:

- Level 1: `fb diff=5/87984` valid pixels.
- Level 49: `fb diff=574/87984` valid pixels. Its first raw Copper delta is a BPL page pointer (`$02B3EE` vs `$03862A`), so pointer values are normalized while the rendered page contents remain checked.
- Level-1 bounded whole-mix PCM: `port/tools/smoke_puae_audio.py --level 1` passes aligned content/gain parity (`corr_median=0.9023`, 10/12 windows good, `gain_median=0.8904`, RMS ratio `1.0007`).
- World-5 bounded per-channel PCM: all four channels pass. Level 49 medians — ch0 `corr=0.9665 gain=0.9509`, ch1 `0.9971/0.9976`, ch2 `0.9582/0.9262`, ch3 `0.9948/0.9806`; worst channel counts 36/36, 58/60, 60/60, 53/54 good windows. The native CIA schedule matches the three measured phases at scanlines 0, 8.5, and 30.5.

This is bounded content/gain parity with local latency alignment, not sample-identical global callback timing. The world-5 PCM gate synchronizes the mutable positional sound/work buffers at frame boundaries; replayer state remains independently executed. PUAE remains a development oracle only.

Report: `reports/atn-differential.json`.

## Replacement-art inventory

The BenRen renderer already emits one `SceneQuad` per sprite/tile per frame (index bitmap + per-scanline palette). `scenedump <dir>` in the harness now resolves that draw list to PNGs, and `port/tools/scene_dump.py` verifies the inventory reproduces across fresh runs. Each distinct sprite/tile gets a stable FNV-1a id computed from its index bitmap only, so palette cycling and screen position do not change the id.

- Level 1, frame 40: 437 quads → **105 distinct assets** (6 character sprites).
- Level 49 (world 5), frame 40: 1,275 quads → **262 distinct assets** (12 character sprites).

These ids are the handles for an art override table at the scene-emit seam; the extracted PNGs are the current reference art. No replacement artwork is produced or shipped.

## Unit/regression tests

```sh
/home/salmon/benefactor-re/.venv/bin/python -m unittest discover -s tests -v
cd /home/salmon/benefactor-re/port
/home/salmon/benefactor-re/.venv/bin/python -m unittest discover -s tools -p 'test_*.py' -v
```

Results: 7 ADF/oracle-disk tests pass; 21 recompiler tests pass, including generated-bank dispatch/table invariants. Worst-case gates: 60/60 direct levels, cold intro, poster → menu → gameplay, credits roll, HD HUD framebuffer regression, two-level PUAE oracle with six byte-identical level-1 asset ranges, sustained level-1/level-49 video lockstep, level-1 whole-mix PCM parity, level-49 per-channel PCM parity, and the scene-inventory reproducibility gate all pass.

## Decisions and remaining work

- **Static recompiler vs readable native rewrite:** keep the static recompiler for the guest/gameplay banks. It preserves behavior and has passing dispatch/completeness gates. Platform-facing owners (disk, hardware service, audio, input, rendering, widescreen, loaders) remain readable native C and can be modernized independently.
- **Modern art:** existing renderers support native scene composition, widescreen, SDL/Vulkan, ambient darkness, and drop shadows. An original optional vector HD side HUD is now included and verified. Replacement sprite/tile art or a full graphical remake still requires an art direction/assets pass.
- **Full PUAE gameplay differential:** sustained level-1 and world-5 video lockstep pass. Level-1 whole-mix and level-49 per-channel bounded PCM content/gain parity pass; global callback latency is intentionally not bit-identical.
- **Packaging:** a source-only archive is produced by `tools/package_source.py`. It excludes disks, ROMs, generated guest code, memory banks, build products, oracle states, and vendor trees. It is not playable by itself. Verified by extracting it into a clean scratch directory, regenerating all four banks from supplied disks, building without the PUAE vendor tree, and passing level-49 and credits smoke tests.

Source archive:

`/home/salmon/benefactor-re/dist/benefactor-re-source.tar.gz`

## Legal/distribution boundary

All disk images, extracted data, memory banks, disassembly, and generated C remain local. The static recompiler's output is derived from copyrighted game code and must not be published or bundled without permission. The upstream project's MIT license covers its own port/runtime code, not the game or generated guest code.

## Sources

[8] https://github.com/SomeoneIsWorking/benefactor/tree/eb47e741bd43c9472abdc274f3583455a23ca9c6
[9] https://www.whdload.de/games/Benefactor.html
[11] https://www.capstone-engine.org/documentation.html
