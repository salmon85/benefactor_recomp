#!/usr/bin/env bash
# Build Benefactor-x86_64.AppImage from a Linux kit + source archive.
#
#   ./build-appimage.sh --kit <kit-dir> --source <benefactor-re-source.tar.gz> \
#                       --appimagetool <appimagetool> --out <file.AppImage>
#
# The AppImage bundles the portable build kit (cmake/ninja/zig/python/SDL2) and
# the source-only archive, so the launcher needs no network and installs nothing.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
KIT=""; SRC=""; TOOL=""; OUT="$PWD/Benefactor-x86_64.AppImage"
while [ $# -gt 0 ]; do
  case "$1" in
    --kit) KIT="$2"; shift 2 ;;
    --source) SRC="$2"; shift 2 ;;
    --appimagetool) TOOL="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -d "$KIT" ] || { echo "--kit must be a directory" >&2; exit 2; }
[ -f "$SRC" ] || { echo "--source must be an archive" >&2; exit 2; }
[ -x "$TOOL" ] || { echo "--appimagetool must be executable" >&2; exit 2; }

WORK="${WORK:-$(mktemp -d)}"
APPDIR="$WORK/Benefactor.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR"

echo "[appimage] staging"
cp "$HERE/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp "$HERE/benefactor.desktop" "$APPDIR/benefactor.desktop"
python3 "$HERE/make-icon.py" "$APPDIR/benefactor.png" >/dev/null
cp "$SRC" "$APPDIR/source.tar.gz"
cp -a "$KIT" "$APPDIR/kit"

# Trim things the launcher never touches.
rm -rf "$APPDIR/kit/cmake/doc" "$APPDIR/kit/cmake/man" \
       "$APPDIR/kit/python/lib/python3.12/test" 2>/dev/null || true

mkdir -p "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$HERE/benefactor.desktop" "$APPDIR/usr/share/applications/benefactor.desktop"
cp "$APPDIR/benefactor.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/benefactor.png"

echo "[appimage] packaging"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT"
ls -lh "$OUT"
echo "[appimage] sha256: $(sha256sum "$OUT" | cut -d' ' -f1)"
