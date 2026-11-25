# Benefactor — native PC port

Native, non-emulated port of *Benefactor* (1994, Digital Illusions/Psygnosis).
The game's 68000 code is statically translated to C ahead of time; the Amiga
services it needs (chip RAM, Copper, blitter, CIA timers, Paula audio, disk
loader) are readable native C. `benefactor-pc` contains no interpreter, no
dynarec and no emulator. PUAE exists only in the separate `benefactor-harness`
development oracle.

## Player-supplied disks

**The CLS-cracked ADF images from TOSEC are required to play.** They are
copyrighted and are not distributed here.

```text
Benefactor (1994)(Psygnosis)(Disk 1 of 3)[cr CLS].adf  901120 bytes
Benefactor (1994)(Psygnosis)(Disk 2 of 3)[cr CLS].adf  901120 bytes
Benefactor (1994)(Psygnosis)(Disk 3 of 3)[cr CLS].adf  901120 bytes

Disk.1  0b7bc60dacc4ab66bb582c51d8fd12181693749f05ac49b7d7acbc31eeee9b71
Disk.2  2acbe50c90ad2302d97eaa0d18fa9eb6f8c15548817142676eb3960cb4ecd2be
Disk.3  afa4b06727dbf7c0d75649d4737bc832dbbb4ff95cf8c0bdd20a37260cb25b2a
```

The CLS crack shifts payloads by `0x400` and relocates two streams to other
disks; `src/engine/disk_boot.c` implements that layout with exact
`(disk, offset, length)` aliases. No Kickstart, WHDLoad or PUAE file is needed
by the product.

## Build

```sh
cd port
PYTHON=/path/to/venv/bin/python tools/regen.sh   # regenerate translated guest code from your disks
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
```

`tools/regen.sh` needs `pycapstone`; it dumps the four runtime image generations
(main, title, gameplay, credits) from the ADFs and translates them. Generated C
stays local (`.gitignore`d) because it is derived from the game.

Dependencies: C11 compiler, CMake ≥ 3.20, Ninja, SDL2. Vulkan is optional
(HARDWARE renderer only).

## Run

```sh
cd port
./build/benefactor-pc Disk.1 Disk.2 Disk.3             # cold boot
./build/benefactor-pc Disk.1 Disk.2 Disk.3 --level 12  # direct level (1..60)
./build/benefactor-pc Disk.1 Disk.2 Disk.3 --credits   # credits roll
./build/benefactor-pc Disk.1 Disk.2 Disk.3 --headless --level 1
```

Settings live in `benefactor.json` (`benefactor.example.json` documents every
key), progress in `profile.json`. The pause menu (ESC → OPTIONS) edits both:
renderer (VANILLA / SOFTWARE / HARDWARE), aspect (STOCK / 16:9 / 21:9 / AUTO),
HD side HUD, controls, speed, unlocks.

## Verified state

- 60/60 levels reach playable state; cold intro, poster → menu → gameplay and
  the credits roll all work.
- Sustained lockstep vs a frozen PUAE oracle: level 1 differs by 5 of 87,984
  rendered pixels, world 5 by 574 of 87,984; six loaded level-1 asset regions
  are byte-identical (388,006 bytes).
- Level-1 mixed and world-5 per-channel audio pass bounded PCM content/gain
  parity, with the native CIA schedule matching the three measured per-frame
  delivery phases (scanlines 0, 8.5, 30.5).
- ATN/Imploder decoder matches `xfd-native` on 34 streams (32 byte-exact, 2
  agreed corrupt).

Full gate results: `../reports/static-recomp-status.md` and
`../analysis/pre-art-gate.md`.

## Development harness (optional)

`benefactor-harness` builds only when `vendor/libretro-uae` is present; it is a
development comparison tool and is not part of the product. It provides PUAE
lockstep, memory/PCM capture, and `scenedump` for the art-replacement handoff
(`tools/scene_dump.py`). Neither the vendored oracle nor its outputs are
distributed.

## Credits

*Benefactor* © Digital Illusions / Psygnosis. This unofficial project ships
only original port/runtime source; SDL retains its license, and
libretro-uae/PUAE (development oracle only) retains its own.
