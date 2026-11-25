# Benefactor — native recompilation

A native, **non-emulated** PC port of *Benefactor* (1994, Digital Illusions /
Psygnosis), produced by statically translating the game's 68000 code to C ahead
of time and re-implementing the Amiga services it uses (chip RAM, Copper,
blitter, CIA timers, Paula audio, disk/loader) in readable native code.

There is no CPU interpreter, no dynarec and no UAE at runtime: the shipped
`benefactor-pc` binary executes translated native code only. PUAE is linked
solely into the separate `benefactor-harness` development oracle.

## You must supply the game disks

**To play this, you need the CLS-cracked ADF disk images of Benefactor from
TOSEC.** They are copyrighted and are *not* included here or in any release —
this repository ships port/runtime source only.

Use exactly these three images (standard 901,120-byte ADFs):

```text
Benefactor (1994)(Psygnosis)(Disk 1 of 3)[cr CLS].adf
  0b7bc60dacc4ab66bb582c51d8fd12181693749f05ac49b7d7acbc31eeee9b71
Benefactor (1994)(Psygnosis)(Disk 2 of 3)[cr CLS].adf
  2acbe50c90ad2302d97eaa0d18fa9eb6f8c15548817142676eb3960cb4ecd2be
Benefactor (1994)(Psygnosis)(Disk 3 of 3)[cr CLS].adf
  afa4b06727dbf7c0d75649d4737bc832dbbb4ff95cf8c0bdd20a37260cb25b2a
```

The CLS crack relocates payloads by `0x400` bytes and moves two streams to
different disks; the native loader handles that layout explicitly. Other
versions of the disks (including WHDLoad images) are not supported by the
current loader.

## Quick start: one-step launchers

Download the launcher for your platform from the
[latest release](https://github.com/salmon85/benefactor_recomp/releases/latest).
It asks for the three ADFs, downloads the source and a self-contained build kit
(cmake, ninja, Zig compiler, Python + capstone, SDL2), builds the game and runs
it. Nothing is installed system-wide.

```sh
# Linux x86_64 — single file, works offline (source + toolchain inside)
chmod +x Benefactor-x86_64.AppImage
./Benefactor-x86_64.AppImage
```

```sh
# Linux x86_64 — small script that downloads the kit on first run
chmod +x benefactor-launch.sh
./benefactor-launch.sh
```

```powershell
# Windows x86_64 (PowerShell 5.1, Windows 10 1803+)
powershell -ExecutionPolicy Bypass -File .\benefactor-launch.ps1
```

Both accept explicit disk paths and pass game options through
(`--level 12`, `--credits`, `--headless` / `-Level 12`). Details:
`port/tools/launcher/README.md`.

## Build

Requires CMake ≥ 3.20, Ninja or Make, a C/C++ compiler, and SDL2
(`libsdl2-dev` / `SDL2` via Homebrew). Vulkan is optional and used only by the
HARDWARE renderer.

```sh
cmake -S port -B port/build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build port/build -j"$(nproc)"
```

The translated guest code is **not** in the repository (it is derived from the
game). Regenerate it from your own disks before the first build:

```sh
cd port
PYTHON=/path/to/venv/bin/python tools/regen.sh   # needs pycapstone
```

## Run

```sh
cd port
./build/benefactor-pc Disk.1 Disk.2 Disk.3            # intro -> poster -> menu -> game
./build/benefactor-pc Disk.1 Disk.2 Disk.3 --level 12 # start directly at level 12
./build/benefactor-pc Disk.1 Disk.2 Disk.3 --credits  # ending credits
./build/benefactor-pc Disk.1 Disk.2 Disk.3 --headless --level 1  # no window
```

`Disk.1`–`Disk.3` must be the ADFs above (copy or symlink them into `port/`, or
pass full paths). Settings persist in `benefactor.json` and progress in
`profile.json`, both created next to the working directory.

In game: arrows move, `Z`/`Ctrl`/`Space`/`Return` fire, `Up` jumps, `X`/`LShift`
interacts, `Tab` fast-forwards, `C` toggles free camera (needs widescreen),
`ESC` opens the pause/options menu (renderer, aspect ratio, HD side HUD).

## Status

Verified against a frozen PUAE oracle: all **60/60** levels reach playable
state, cold intro, poster → menu → gameplay and the credits roll all work, and
sustained lockstep gameplay differs from the oracle by 5 pixels of 87,984
(level 1) and 574 of 87,984 (world 5). Level-1 mixed and world-5 per-channel
audio pass bounded PCM content/gain parity.

Rendering supports 4:3, 16:9 and 21:9, three renderers (VANILLA copper/blitter,
SOFTWARE BenRen per-sprite CPU composite, HARDWARE BenRen Vulkan per-sprite),
plus an optional original vector HD side HUD.

Details and every gate result: `reports/static-recomp-status.md` and
`analysis/pre-art-gate.md`.

### Where this stops: replacement artwork

The next stage is new sprite/tile art. The renderer already emits one quad per
sprite/tile with an index bitmap, so art can be replaced by asset id:

```sh
cd port
BENEFACTOR_SKIP_PUAE=1 BENEFACTOR_RENDERER=benren BENEFACTOR_WIDESCREEN_MODE=16:9 \
  ../.venv/bin/python tools/scene_dump.py --level 1
```

`scenedump` (harness REPL) writes one PNG per distinct sprite plus `scene.txt`
with stable ids hashed from the bitmap only — palette fades and screen position
do not change an id. Level 1 yields 105 distinct assets, world 5 yields 262. No
replacement artwork has been produced.

## What is not in this repository

- Game disk images, Kickstart ROMs, WHDLoad slaves.
- Generated/translated guest C, memory-bank dumps, oracle states.
- Extracted game artwork, screenshots, and the vendored PUAE/libretro source.

## Legal

Unofficial, non-commercial fan project; not affiliated with or endorsed by
Digital Illusions, Psygnosis or Sony. Port and runtime source here is original
work (MIT). *Benefactor* and its assets remain the property of their owners;
supplying your own disks is your responsibility.
