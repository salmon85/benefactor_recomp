# One-step launchers

These scripts ask for the three CLS-cracked ADFs, download the port's source,
build it locally with a self-contained toolchain kit, and start the game. Nothing
is installed on the system: cmake, ninja, zig (C compiler), Python + capstone and
SDL2 all live inside the kit the launcher downloads.

| Platform | Launcher | Kit |
|---|---|---|
| Linux x86_64 | `benefactor-launch.sh` | `benefactor-buildkit-linux-x86_64.tar.xz` |
| Windows x86_64 | `benefactor-launch.ps1` | `benefactor-buildkit-windows-x86_64.zip` |

Both download the source archive and kit from the same GitHub release
(`v0.2.0`), so run them from a machine with internet access the first time.

## You still need the game

The launcher verifies and copies your disks; it does not download them. Use the
TOSEC release:

```
Benefactor (1994)(Psygnosis)(Disk 1 of 3)[cr CLS].adf
Benefactor (1994)(Psygnosis)(Disk 2 of 3)[cr CLS].adf
Benefactor (1994)(Psygnosis)(Disk 3 of 3)[cr CLS].adf
```

SHA-256 `0b7bc60d…`, `2acbe50c…`, `afa4b067…` (full values are in the top-level
README and are checked by the launcher). Any other disk version is refused
unless you pass `--any-disks` / `-AnyDisks`, and the loader will probably fail.

## Linux

```sh
chmod +x benefactor-launch.sh
./benefactor-launch.sh                     # file dialogs (zenity/kdialog, else terminal prompt)
./benefactor-launch.sh Disk1.adf Disk2.adf Disk3.adf
./benefactor-launch.sh --level 12           # start directly at a level
./benefactor-launch.sh --rebuild            # rebuild from scratch
```

Data goes to `~/.local/share/benefactor-launcher/` (`src/`, `kit/`, `disks/`,
`launcher.log`). Override with `BENEFACTOR_LAUNCHER_HOME`.

System requirements: a desktop Linux with bash, curl, tar and xz (present on any
normal install). The built game needs the runtime X11/XWayland libraries your
desktop already has; SDL2 itself is shipped in the kit.

## Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\benefactor-launch.ps1
powershell -ExecutionPolicy Bypass -File .\benefactor-launch.ps1 -Disks d1.adf,d2.adf,d3.adf
powershell -ExecutionPolicy Bypass -File .\benefactor-launch.ps1 -Level 12
```

Data goes to `%LOCALAPPDATA%\BenefactorLauncher`. Requires Windows 10 1803+ (for
`tar.exe`) and PowerShell 5.1, both built in. `SDL2.dll` is copied next to the
executable by the launcher.

## What the launcher does, in order

1. Verifies each ADF (size 901,120 + SHA-256) and copies it to the data dir.
2. Downloads `benefactor-re-source.tar.gz` from the release and extracts it.
3. Downloads the platform build kit and unpacks it.
4. Runs `tools/regen.py` with the kit's Python + capstone and the kit's compiler,
   translating the four runtime banks from your disks (the generated code is
   derived from the game and is never distributed).
5. Configures and builds `benefactor-pc` with the kit's cmake/ninja/zig against
   the kit's SDL2.
6. Launches the game.

Every step is idempotent: later runs skip the download/build unless `--rebuild`
is passed or the binary is missing. Build logs: `launcher.log` in the data dir.

## Notes

- First build takes a few minutes (bank translation + ~1,200 translated
  functions). Later launches are instant.
- The kit is x86_64 only. ARM Linux (Raspberry Pi, Apple Silicon under Linux
  VMs) is not covered by the prebuilt SDL2; build with your own compiler and
  `cmake -DSDL2_DIR=...` instead.
- Windows builds drop the opt-in POSIX HTTP debug server; everything gameplay
  facing is compiled in.
