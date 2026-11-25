# Benefactor Harness — Established Facts (DO NOT RE-EXAMINE)

## PUAE determinism — was non-deterministic, now FIXED (2026-05-24)
A LIVE PUAE boot is non-deterministic: the disk-load wait completes ~1 emulated
frame sooner/later run-to-run (host I/O timing). Identical through frame 23
(Kickstart), then 1 frame apart at game-load (`cop1lc`=$001000 @ frame 171 vs 172),
locked 1 frame apart after. Chip RAM at sync is identical (md5), but PUAE's
non-chip state (CPU/CIA/beam) is 1 frame off and leaks into the forward run.
(NOT the CIA TOD hack — tod_hack=0 — and NOT timehack_helper.)

**FIX:** `harness_puae.c` freezes a full machine save-state (`retro_serialize`) at
the sync point once → `logs/puae_sync.state`, and restores it (`retro_unserialize`)
every subsequent run instead of re-booting. `BENEFACTOR_REFREEZE=1` forces a fresh
boot+freeze (after disk/core changes; delete the .state file likewise). PUAE is now
bit-exact run-to-run (warm-vs-warm = 0 bytes, was ~46). The PC port is also
deterministic, so the whole comparison is reproducible. Lockstep/audio smoke
gates restore the frozen state with `BENEFACTOR_REFREEZE=0`; only the oracle-disk
bootstrap refreezes.

### Validation methodology (now simple — both sides deterministic)
1. `FBDUMP_FRAME=N bash run_harness.sh --frames N+5` → `logs/chip_{pc,puae}.bin`
   + `logs/fb_{pc,puae}.bin` (320x256; bytes are B,G,R,A → swap to RGBA in PIL).
2. `cmp -l logs/chip_pc.bin logs/chip_puae.bin` → the TRUE divergence directly
   (no noise mask needed; the old multi-run noise-mask approach is obsolete).
3. A fix helps iff that byte count drops.

Current match: displayed regions (BPL data + copper) PERFECT through 41+ frames.
Residual frame-35 divergence = stable 21 bytes, all off-screen: `$069FB-$06AB5`
(title object table) + `$0718BA` (1B, A-shift carry) + `$078DC2/$078DEA` (glyph
buf-B) + `$07FF9D+` (stack).

## Memory Layout (FIXED)
- Game binary loaded at `g_mem[0]` (chip RAM base = 0). `load_addr = 0`, `RT_MEM_SIZE = 8 MB`.
- Chip RAM = 512 KB (`$00000`–`$7FFFF`). PUAE dump = `logs/harness_puae_chipram.bin` (524288 bytes).
- `A5 = $00531C`, `A6 = $00DFF002` (DFF base offset by 2).
- Stack top = `$080000`.

## Copper Lists (FIXED — stop re-examining)
- `$7BC8` = 0-plane/loading-screen copper list (cop1lc when flag at `A5-$117A` == 0).
- `$86CC` = 3-plane/gameplay copper list (cop1lc when flag != 0).
- `gfn_0041A4` toggles the flag via `not.w -$117A(a5)`.
- Copper list word indexing: `coplist[i]` = 16-bit word at `g_mem[$86CC + i*2]`.
  - Instruction N has reg-word at `$86CC + N*4`, val-word at `$86CC + N*4 + 2`.
  - Word index `i` = instruction N, half H: `i = N*2 + H`.

## Key Copper List Addresses in $86CC List (FIXED)
| Instr | Addr   | Reg    | Val (PUAE) | Meaning         |
|-------|--------|--------|------------|-----------------|
| 21    | $8720  | $0100  | $0200      | BPLCON0=$0200   |
| 22    | $8724  | $0102  | $0000      | BPLCON1=$0000   |
| 23    | $8728  | $0104  | $0040      | BPLCON2=$0040   |
| 47    | $8788  | $01E0  | $0002      | BPL1PTH=$0002   |
| 47val | $878A  | —      | $5334      | BPL1PTL (value) |

- The WATCH16 at `$878A` fires when `gfn_00405C` writes BPL1PTH.
- `$8726–$872C` is clobbered by blitter fill (`bltcon0=$19F0, lf=$9F`) → writes `$FFFF`.
- The blitter D-destination base is `$8720`, source `$8748`. This is the game clearing copper slots for rebuild.

## Blitter Fill Details (ESTABLISHED)
- `bltcon0=$19F0`, `lf=$9F`: output is always `$FFFF` regardless of A source (all minterm bits set for c=0 case).
- Fires once before frame 0 snap, from within `gfn_0041A4`.
- After fill: `g_mem[$872A]=$FFFF` (BPLCON2 slot destroyed).
- PC port fix: `native_0041A4` now rebuilds static copper entries immediately after `gfn_sprite_blitter_setup`.

## Confirmed Root Cause Fixed (2026-05-02)
### Fix 1: w32 copper clobber fix
- `pc.c` used `w32` at copper value-word addresses (`$7C86/$7CDE/$878A/$87E2` paths), which overwrote adjacent copper reg-words.
- Copper instructions are 16-bit reg + 16-bit value pairs. Writing 32-bit across these addresses corrupts the list.
- Fix: use `w16` high/low writes to the correct value-word slots only.

### Fix 2: Static copper entries + $7BC8 BPLPTR overwrite (2026-05-02)
- Blitter fill in `gfn_0041A4` clobbered BPLCON0/1/2/BPL1/2MOD at `$8720–$8732` in the $86CC list.
- `gfn_text_sprite_render` writes screen-derived BPL pointers to both copper lists; $7BC8 list gets wrong screen-num values.
- Fix in `pc.c`: `native_0041A4` restores `$8720–$8732` + both lists' BPLPTRs after blitter. `native_00405C` re-overwrites $7BC8 list BPLPTRs with screen-0 values after `gfn_text_sprite_render`.
- Verified by harness: `PERFECT MATCH across 3 frames` for `--frames 3 --boot-frames 600`.

## Snap / Frame Hook Timing (ESTABLISHED)
- `hw_get_snap()` is called from `hw_present_frame()` → triggers `g_harness_frame_hook()`.
- Snap order within a 3-frame run: SNAP(F0,cop=$86CC), SNAP2(F1,cop=$7BC8), SNAP(F2,cop=$86CC).
- `coplist[47]=$0040` at all snaps = BPLCON2 ($0104, value $0040) correctly restored.
- `g_mem[$872A]=$0040` at SNAP confirms BPLCON2 copper entry is no longer $FFFF.

## frames_differ() Logic (FIXED)
- Compares `cop1lc` equality then full `coplist[]` word-by-word.
- Does NOT compare `bplcon0`/`bpl1mod` register shadows (those differ due to beam timing).
- Does NOT compare `bplpt[]` or `palette[]` (timing artifacts: PUAE frame-start vs PC frame-end).
- Does NOT compare `audio[n].vol`: PUAE reads Paula internal DMA state (`cdp->data.audvol`, updated only on DMA reload); PC reads register shadow (updated immediately on write). Fundamentally incomparable.
- Display lines like `bplpt[0] PUAE=... PC=... DIFF` are cosmetic/informational in the report; they do NOT trigger frames_differ().

## pc.c Per-Frame Call Sequence (S_TITLE)
```
call_fn(0x0031A0)                   ← native_blitter_wait_clear (delegates to recompiled)
hw_write32(DFF080, cop1lc)          ← sets cop1lc from flag
call_fn(0x0041A4)                   ← native_sprite_blitter_setup (blits + copper static rebuild)
call_fn(0x00405C)                   ← native_text_sprite_render (delegates; render hook boundary)
call_fn(0x0055A0)                   ← native_timer_interrupt (delegates to recompiled)
hw_present_frame()                  ← snap captured HERE
```
`S_GAME` path uses `native_game_frame` (0x003488, delegates to recompiled `gfn_game_frame`).

## Native Override Names (pc.c)
| Address  | Function Name               | Purpose |
|----------|-----------------------------|---------|
| $0030C2  | `native_hw_wait`            | Hardware-wait eliminator (no-op) |
| $0031A0  | `native_blitter_wait_clear` | Delegates to recompiled clear/wait routine |
| $003818  | `native_sprite_table_init`  | Broken recompiled (no-op) |
| $0074AA  | `native_boot_anim_iterator` | Boot animation with guard limits |
| $00405C  | `native_text_sprite_render` | Render wrapper boundary |
| $0040B6  | `native_dispatch_table`     | Render dispatch wrapper |
| $0040B8  | `native_item_dispatch_1`    | Render item wrapper |
| $0040BA  | `native_item_dispatch_2`    | Render item wrapper |
| $0040BC  | `native_item_dispatch_3`    | Render item wrapper |
| $0040BE  | `native_item_decrement`     | Render item wrapper |
| $0040CC  | `native_item_scroll`        | Render item wrapper |
| $004102  | `native_item_position`      | Render item wrapper |
| $00412E  | `native_item_blitter`       | Render item wrapper |
| $0041A4  | `native_sprite_blitter_setup` | Blits + copper static rebuild |
| $004236  | `native_blit_row_callback`  | Blit callback wrapper |
| $0052A4  | `native_post_blit_handler`  | Post-blit wrapper |
| $0055A0  | `native_timer_interrupt`    | Timer interrupt (delegates) |
| $003488  | `native_game_frame`         | Game frame + copper static rebuild |

## Frame 2 D0 Corruption Status
- Previous `gfn_00405C` D0-corruption symptom is worked around: `native_00405C` overwrites $7BC8 list BPLPTRs with screen-0 values after `gfn_text_sprite_render`.
- The $86CC list BPLPTRs are left as-is (correct from gfn_text_sprite_render).
- Do not reopen this as a recompiler bug unless harness regression reproduces with current `pc.c`.

## Interactive Render Baseline (UPDATED 2026-05-02)
- Copper list divergence for frame 1 ($7BC8) is now FIXED — coplist words match PUAE across all 3 capture frames.
- Confirmed cause/fix: title modulation lane `$7D40-$7DC6` could be clobbered with `FFFF/3333` garbage on PC; `native_rebuild_copper_static` now restores the exact lane words each frame.
- Remaining render mismatch (if any) is purely renderer decode quality (palette conversion, border alignment, etc.).

## Interactive Render Coordinate + Color Facts (ESTABLISHED 2026-05-02)
- PUAE framebuffer in harness is scaled from full emulator output; active gameplay content starts after visible borders.
- With current renderer, adding `top_border=17` aligns first non-black row with PUAE (`y=17`).
- Applying DIW/DDF horizontal origin correction plus empirical border term (`x_origin += 56`) aligns first non-black x with PUAE (`x=120`).
- Matching palette conversion to PUAE's 16-bit path (RGB12 -> RGB565 -> RGB888) reduced frame-1 diff from `5886` to `5499` pixels.
- **DO NOT RE-EXAMINE** pure copper-list corruption as cause of frame-1 render mismatch while coplist words match; remaining errors are renderer decode/alignment quality.

## CLS oracle disk reconstruction (2026-11-25)
- Do not shift Disk.1 wholesale. Its crack loader reads the main bank from
  physical `$1C80`; preserve bytes through `$26270`, then shift the title-and-
  later region from physical `$26670` to logical `$26270`.
- Disks 2/3 contain streamed payloads only, so remove their `$400` stub and pad
  the logical images to WHDLoad's `$F5000` raw-image size.
- Copy the four relocated world-5 streams and credits stream from their
  physical Disk.3 offsets to the logical offsets requested by the game. The
  third world-5 source is `$499B4` (not `$49B4`).
- Rebuild with `tools/build_oracle_disks.py --install port/oracle-whdload/Benefactor`,
  refreeze with `BENEFACTOR_REFREEZE=1`, and run `port/tools/smoke_puae_oracle.py`.
  Levels 1 and 49 must both report `cop1lc=$003484` and `gameplay stable=60`.
  The level-1 run also dumps both CPU maps and asserts all six loaded asset
  ranges (388,006 bytes) are byte-identical.
- Oracle disks/install trees are development artifacts and must stay out of
  source packages.

## Static native lockstep and audio capture (2026-11-25)

- The shipped executable remains the static native port. PUAE is linked only into
  `benefactor-harness` as a development oracle.
- `port/tools/smoke_puae_lockstep.py --level N` shares the `$577000` entry, seeds
  the level word, advances both cores through card -> gameplay, then runs 480
  synchronized gameplay frames. Use levels 1 and 49 as the sustained gates.
- PUAE comparison crop defaults to `crop_x=96, crop_w=704`. The last 40 output
  columns are border fill beyond PUAE's 720-pixel source frame; `cmp` excludes
  them and reports the valid 312x282 region. Do not compare the filled border as
  game pixels.
- `frames_differ()` ignores BPLxPT/SPRxPT pointer VALUES because native and PUAE
  allocate pages at different chip-RAM addresses. Palette, Copper timing, all
  non-pointer Copper writes, low memory, player state, and framebuffer output
  remain strict.
- Current sustained results: level 1 `fb diff=5/87984`; level 49
  `fb diff=498/87984`. Level 49's first Copper delta is a BPL page pointer
  (`$02B3EE` vs `$03862A`), not a timing/palette delta.
- `acap on|off` captures bounded PC/PUAE PCM to `logs/audio_pc.raw` and
  `logs/audio_puae.raw`. Both are stereo s16 at 44100 Hz.
- `syncmusic` copies the replayer/SFX ranges `$57FE40-$57FEB0`,
  `$59B800-$59B81F`, `$59CF1C-$59D25F`, the ping-pong buffers
  `$580B8-$5822F`, and the streamed sample/work area `$5A0000-$5AC4E9`.
  It also seeds Paula's internal DMA phase (`pt/wlen/state`) from the oracle.
  It is a harness checkpoint tool, not a shipped-game shortcut.
- `pumute <mask>` isolates PUAE Paula channels; `AUDCH_ONLY=<n>` isolates the PC
  channel. `AUDIO_NATIVE_SFX=0` bypasses the native whole-sample SFX override for
  diagnosis.
- `irqcount reset` enables the instruction hook and counts entries at
  `$59BF3E/$59BFA6`; `irqpos` prints their scanline positions plus transitions
  into the wider music range. The output leaves occur on scanlines 0 and ~8.5;
  the third autovector phase is the `$578272` sequencer near scanline 30.5.
  Native audio therefore delivers three phases at sample offsets 0, 24, and 86
  of each 882-sample frame. Equal-thirds and naive two-delivery schedules both
  regressed parity.
- `port/tools/smoke_puae_audio.py --level 1` passes the established whole-mix
  bounded gate. Level 49 uses per-channel isolation and 20 ms local alignment;
  all four channels pass content/gain parity. `BENEFACTOR_AUDIO_SYNC_WORK=1`
  refreshes only the mutable positional sound/work buffers at frame boundaries
  for that gate; replayer state remains independently executed. This is not a
  claim of sample-identical global callback latency.

## Scene inventory for art replacement (2026-11-25)

- `scenedump <dir>` writes the CURRENT BenRen scene as one PNG per distinct
  sprite/tile plus `scene.txt`. Every quad is palette-resolved through
  `pal_rows[y]` (so copper/row colour effects are already applied) and
  transparent texels are magenta `#FF00FF`.
- Asset identity is a FNV-1a hash of the quad's index bitmap ONLY (no palette,
  no position), so an animated palette, a copper fade, or the same tile drawn at
  a different x/y keeps one id. `scene.txt` lines are
  `id=<16 hex> space=WORLD|SCREEN shadow=0|1 x= y= w= h=`, with repeats marked
  `(duplicate of earlier id)`.
- Requires a fresh scene: run `rungame` then `pc N` with
  `BENEFACTOR_RENDERER=benren BENEFACTOR_WIDESCREEN_MODE=16:9
  BENEFACTOR_PRESENT=sdl BENEFACTOR_SKIP_PUAE=1`. `scenesdl`/`scenewin` need the
  same setup; without the BenRen renderer selected the draw list is never built
  and the command prints `no fresh scene`.
- `port/tools/scene_dump.py [--level N] [--frame N]` runs the dump twice in
  fresh processes, rejects non-reproducible inventories, and sanity-checks quad
  count, distinct ids, character (`shadow=1`) quads, and PNG decode. Current
  inventories: level 1 frame 40 `437 quads -> 105 assets` (6 character); level 49
  frame 40 `1275 quads -> 262 assets` (12 character).
- This is the replacement-art boundary: ids are stable handles for an override
  table at the scene-emit seam. No replacement art is shipped.

## Dynarec migration use

These observations are historical evidence, not commands to run the retired
static product. Adapt the PUAE side to the shipping dynarec only after the
separately built first-block discriminator passes. Native overrides are
registered by image generation plus guest address, and original calls execute
through the dynarec as specified in `docs/migration.md`.

## Harness Architecture Note
- **PUAE/libretro-uae is compiled INTO the harness binary** (all sources in `vendor/libretro-uae/` are built as one TU). You can freely add tracing, watchpoints, or printf inside PUAE code — just rebuild the harness target. It is not a prebuilt library you cannot touch.
- Vendor-side diagnostic adaptation must route through the harness logging
  boundary; do not add direct stderr or `write(2)` output.

## Recompiler Fixes Applied (DO NOT RE-FIX)
- `addq/subq` to An: no CCR update (An-dest no-flags).
- `game.c` regenerated with fixed recompiler (17/17 tests pass).
- `cop1lc` polarity in `pc.c`: `f ? $86CC : $7BC8`.
- `HARNESS_BUILD` link: `custom.c` includes `puae_snap_impl.c`.
- `frames_differ()`: uses coplist content, not register shadows.
- Chip RAM snap ordering: PUAE snap before `retro_unload_game()`.
