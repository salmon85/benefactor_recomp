#!/usr/bin/env bash
# Benefactor launcher for Linux x86_64.
#
# Asks for the three CLS-cracked ADFs, downloads the port's source, builds it
# with a self-contained toolchain kit (cmake + ninja + zig + python + capstone +
# SDL2 -- nothing is installed system-wide), and starts the game.
#
# Usage:
#   ./benefactor-launch.sh                 pick the disks with a file dialog
#   ./benefactor-launch.sh d1 d2 d3        use these ADFs, no dialog
#   ./benefactor-launch.sh --level 12      pass game options through
#   ./benefactor-launch.sh --rebuild       force a fresh build
#   ./benefactor-launch.sh --any-disks     accept non-CLS images (loader may fail)
#
# Everything lives under ~/.local/share/benefactor-launcher (override with
# BENEFACTOR_LAUNCHER_HOME). The ADFs are copied there once, so later launches
# do not ask again.
set -euo pipefail

RELEASE_TAG=v0.2.0
REPO=salmon85/benefactor_recomp
SRC_URL="https://github.com/$REPO/releases/download/$RELEASE_TAG/benefactor-re-source.tar.gz"
KIT_URL="https://github.com/$REPO/releases/download/$RELEASE_TAG/benefactor-buildkit-linux-x86_64.tar.xz"

DATA="${BENEFACTOR_LAUNCHER_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/benefactor-launcher}"
SRC_DIR="$DATA/src"
KIT="$DATA/kit"
DISKS_DIR="$DATA/disks"
BUILD="$SRC_DIR/port/build"
LOG="$DATA/launcher.log"

# SHA-256 of the TOSEC CLS release this loader understands.
KNOWN_DISKS=(
  0b7bc60dacc4ab66bb582c51d8fd12181693749f05ac49b7d7acbc31eeee9b71
  2acbe50c90ad2302d97eaa0d18fa9eb6f8c15548817142676eb3960cb4ecd2be
  afa4b06727dbf7c0d75649d4737bc832dbbb4ff95cf8c0bdd20a37260cb25b2a
)

FORCE=0
ANY_DISKS=0
GAME_ARGS=()
ADF_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --rebuild) FORCE=1 ;;
    --any-disks) ANY_DISKS=1 ;;
    -*) GAME_ARGS+=("$arg") ;;
    *) ADF_ARGS+=("$arg") ;;
  esac
done

say()  { printf '\033[1m[benefactor]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[benefactor]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[benefactor] %s\033[0m\n' "$*" >&2; exit 1; }

mkdir -p "$DATA" "$DISKS_DIR"
: > "$LOG"
exec 3>&1
if ! exec 4>>"$LOG"; then
  warn "cannot write $LOG"
fi

need() { command -v "$1" >/dev/null 2>&1 || die "missing required system tool: $1"; }
need curl
need tar
need xz
need sha256sum

# ---------------------------------------------------------------- file picker
pick_file() {
  local title="$1"
  if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v zenity >/dev/null 2>&1; then
    zenity --file-selection --title="$title" --file-filter='Amiga disk images (*.adf) | *.adf' \
           --file-filter='All files | *' 2>/dev/null && return 0
  fi
  if [ -n "${DISPLAY:-}" ] && command -v kdialog >/dev/null 2>&1; then
    kdialog --title "$title" --getopenfilename . '*.adf' 2>/dev/null && return 0
  fi
  local reply=""
  if [ -t 0 ]; then
    read -r -e -p "$title: " reply || true
  fi
  [ -n "$reply" ] || die "$title was not provided (pass three .adf paths as arguments)"
  printf '%s\n' "${reply/#\~/$HOME}"
}

sha_of() { sha256sum "$1" | cut -d' ' -f1; }

collect_disks() {
  local have=0 d
  for d in 1 2 3; do
    [ -f "$DISKS_DIR/Disk.$d" ] && have=$((have + 1))
  done
  if [ "$have" -eq 3 ] && [ "$FORCE" -eq 0 ] && [ "${#ADF_ARGS[@]}" -eq 0 ]; then
    say "using the disks already copied into $DISKS_DIR"
    return 0
  fi

  local src=()
  if [ "${#ADF_ARGS[@]}" -ge 3 ]; then
    src=("${ADF_ARGS[0]}" "${ADF_ARGS[1]}" "${ADF_ARGS[2]}")
  else
    # a single folder argument containing the three ADFs also works
    if [ "${#ADF_ARGS[@]}" -eq 1 ] && [ -d "${ADF_ARGS[0]}" ]; then
      local dir="${ADF_ARGS[0]}"
      local n=0 f
      while IFS= read -r f; do
        n=$((n + 1)); src+=("$f")
      done < <(find "$dir" -maxdepth 1 -iname 'Disk *.adf' | sort)
      [ "$n" -eq 3 ] || die "expected 3 ADFs in $dir, found $n"
    else
      for d in 1 2 3; do
        src+=("$(pick_file "Select Benefactor Disk $d of 3 (.adf)")")
      done
    fi
  fi

  local i
  for i in 0 1 2; do
    local path="${src[$i]}"
    [ -f "$path" ] || die "not a file: $path"
    local size sum
    size=$(stat -c %s "$path")
    sum=$(sha_of "$path")
    if [ "$size" -ne 901120 ]; then
      warn "Disk.$((i + 1)) is $size bytes, expected 901120"
      [ "$ANY_DISKS" -eq 1 ] || die "not a standard Amiga ADF (pass --any-disks to override)"
    fi
    if [ "$sum" != "${KNOWN_DISKS[$i]}" ]; then
      warn "Disk.$((i + 1)) is not the TOSEC CLS image (sha256 $sum)"
      if [ "$ANY_DISKS" -ne 1 ]; then
        die "this loader only handles 'Benefactor (1994)(Psygnosis)(Disk $((i + 1)) of 3)[cr CLS].adf' (pass --any-disks to try anyway)"
      fi
    fi
    cp -f "$path" "$DISKS_DIR/Disk.$((i + 1))"
  done
  say "disks verified and copied to $DISKS_DIR"
}

# ------------------------------------------------------------------ downloads
fetch() {
  local url="$1" out="$2"
  say "downloading $(basename "$out")"
  if ! curl -fL --retry 3 --progress-bar -o "$out.part" "$url" >>"$LOG" 2>&1; then
    rm -f "$out.part"
    die "download failed: $url"
  fi
  mv -f "$out.part" "$out"
}

ensure_source() {
  local want="$DATA/source.sha256" have=""
  [ -f "$want" ] && have=$(cat "$want")
  local tar="$DATA/source.tar.gz"
  if [ ! -f "$tar" ] || { [ "$FORCE" -eq 1 ] && [ -z "${BENEFACTOR_KEEP_SOURCE:-}" ]; }; then
    fetch "$SRC_URL" "$tar"
    sha256sum "$tar" | cut -d' ' -f1 > "$want" || die "cannot record source hash"
  fi
  if [ ! -f "$SRC_DIR/port/CMakeLists.txt" ] || [ "$FORCE" -eq 1 ]; then
    say "extracting source"
    rm -rf "$SRC_DIR"
    mkdir -p "$SRC_DIR"
    tar xzf "$tar" -C "$SRC_DIR" || die "cannot extract source archive"
  fi
}

ensure_kit() {
  if [ -x "$KIT/cmake/bin/cmake" ] && [ -x "$KIT/zig/zig" ] && [ "$FORCE" -eq 0 ]; then
    say "build kit already present"
    return 0
  fi
  local tar="$DATA/kit.tar.xz"
  [ -f "$tar" ] || fetch "$KIT_URL" "$tar"
  say "unpacking build kit (cmake, ninja, zig, python, SDL2)"
  rm -rf "$KIT"; mkdir -p "$KIT"
  tar xJf "$tar" -C "$KIT" || die "cannot extract build kit"
  rm -f "$tar"
}

# ---------------------------------------------------------------------- build
build_game() {
  local py="$KIT/python/bin/python3"
  local cmake="$KIT/cmake/bin/cmake"
  local ninja="$KIT/bin/ninja"
  local zigcc="$KIT/bin/zigcc"
  [ -x "$py" ] && [ -x "$cmake" ] && [ -x "$ninja" ] && [ -x "$zigcc" ] \
    || die "build kit is incomplete; rerun with --rebuild"

  cp -f "$DISKS_DIR"/Disk.* "$SRC_DIR/port/" 2>/dev/null || true

  say "translating the game's 68000 code from your disks (about a minute)"
  ( cd "$SRC_DIR/port" \
    && PYTHON="$py" PATH="$KIT/cmake/bin:$KIT/bin:$PATH" \
       bash tools/regen.sh ) >>"$LOG" 2>&1 \
    || die "bank regeneration failed; see $LOG"

  say "building benefactor-pc"
  (
    cd "$SRC_DIR/port"
    export PATH="$KIT/cmake/bin:$KIT/python/bin:$KIT/bin:$PATH"
    export LD_LIBRARY_PATH="$KIT/sdl2/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    "$cmake" -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER="$zigcc" \
      -DSDL2_DIR="$KIT/sdl2/lib/cmake/SDL2" \
      -DSDL2_INCLUDE_DIR="$KIT/sdl2/include/SDL2" \
      -DSDL2_LIBRARY="$KIT/sdl2/lib/libSDL2.so" \
      -DCMAKE_BUILD_RPATH="$KIT/sdl2/lib" >>"$LOG" 2>&1 || exit 1
    "$cmake" --build build -j"$(nproc)" >>"$LOG" 2>&1 || exit 1
  ) || die "build failed; see $LOG"
  [ -x "$BUILD/benefactor-pc" ] || die "build produced no binary; see $LOG"
}

# ------------------------------------------------------------------------ run
main() {
  say "data directory: $DATA"
  collect_disks
  ensure_source
  ensure_kit
  if [ "$FORCE" -eq 1 ] || [ ! -x "$BUILD/benefactor-pc" ]; then
    build_game
  else
    say "binary already built (use --rebuild to force)"
  fi
  cp -f "$DISKS_DIR"/Disk.* "$SRC_DIR/port/" 2>/dev/null || true

  export LD_LIBRARY_PATH="$KIT/sdl2/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  cd "$SRC_DIR/port"
  say "starting Benefactor"
  exec ./build/benefactor-pc Disk.1 Disk.2 Disk.3 "${GAME_ARGS[@]}"
}

main
