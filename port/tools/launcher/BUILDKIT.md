# How the launcher build kits are made

The launchers download a prebuilt "kit" so users need no compilers. The kit is
built once by a maintainer, not by the user. This file records exactly what is
inside so it can be reproduced.

## Contents (both platforms)

| Component | Version | Source |
|---|---|---|
| CMake | 3.30.5 | Kitware release tarball/zip (static Linux build, Windows x86_64 zip) |
| Ninja | 1.12.1 | ninja-build/ninja release (linux zip / win zip) |
| Zig (C compiler) | 0.13.0 | ziglang.org download |
| CPython | 3.12.4 | astral-sh/python-build-standalone `install_only` |
| capstone | 5.0.9 wheel | PyPI, installed into the kit's site-packages |
| SDL2 | 2.32.10 | SDL2 source built here (Linux) / official mingw devel package (Windows) |

Layout expected by the launchers:

```
kit/
  cmake/bin/cmake            # + share/cmake-3.30/
  bin/ninja
  bin/zigcc                  # Linux wrapper: zig cc -target x86_64-linux-gnu
  zig/                       # zig binary + lib/
  python/                    # python3 (or python.exe) + Lib/site-packages/capstone
  sdl2/                      # Linux: include/, lib/cmake/SDL2, libSDL2-2.0.so.0
                             # Windows: x86_64-w64-mingw32/{include,lib,bin}
```

## Linux SDL2 build

Built with the kit's own zig against the host's X11/Wayland headers, with the
drivers dlopen'ing at runtime so the .so has no link-time dependency beyond
libc/libm/libpthread/libdl:

```sh
zig cc -target x86_64-linux-gnu.2.28 ...
cmake -DSDL_SHARED=ON -DSDL_STATIC=OFF -DSDL_TEST=OFF \
      -DSDL_X11=ON -DSDL_X11_SHARED=ON \
      -DSDL_WAYLAND=ON -DSDL_WAYLAND_SHARED=ON \
      -DSDL_KMSDRM=OFF -DSDL_RPI=OFF -DSDL_VIVANTE=OFF \
      -DSDL_JACK=OFF -DSDL_PIPEWIRE=OFF -DSDL_PULSEAUDIO=ON -DSDL_ALSA=ON \
      -DSDL_LIBSAMPLERATE=OFF -DSDL_LIBUDEV=OFF -DSDL_DBUS=OFF -DSDL_IBUS=OFF
```

Resulting `libSDL2-2.0.so.0` requires at most `GLIBC_2.27`.

## Pitfall that costs hours

`zig cc` with no `-target` defaults to **x86_64-linux-musl**. Linking that
musl-compiled executable against the glibc SDL2 shared library produces a binary
that starts, loads a level, and then dies with a bogus indirect call
(`rt_call: NO FUNCTION at $000000`) or SIGILL. Always pass
`-target x86_64-linux-gnu`; the kit's `bin/zigcc` wrapper does.

## Rebuilding the kits

```sh
# Linux
tar -C kit -cJf benefactor-buildkit-linux-x86_64.tar.xz .
# Windows (zip at the archive root — no top-level folder)
cd kit-win && zip -qr9 ../benefactor-buildkit-windows-x86_64.zip .
```

Upload both as assets on the release the launchers point at
(`RELEASE_TAG` / `$ReleaseTag`).

## Verification performed for v0.2.0

- Linux: clean launcher run in an empty data dir downloaded source + kit,
  translated all four banks, built, and reached gameplay on levels 1 and 49.
- Windows: the same sources were cross-compiled with the kit's zig to a
  PE32+ x86-64 executable (`benefactor-pc.exe`, links SDL2.dll). The Windows
  launcher itself has not been executed on Windows yet.
