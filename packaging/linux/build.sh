#!/usr/bin/env bash
# Build PDF_Pro .deb + AppImage from a PyInstaller onedir tree.
# Intended for GitHub Actions (Ubuntu 22.04) and local Linux.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
VERSION="${VERSION:-0.1.5}"
ARCH="${ARCH:-amd64}"
DIST="$ROOT/dist"
ONEDIR="$DIST/PDF_Pro"
OUT="$DIST/packages"
rm -rf "$OUT"
mkdir -p "$OUT"

if [[ ! -x "$ONEDIR/PDF_Pro" ]]; then
  echo "Missing $ONEDIR/PDF_Pro — run: pyinstaller --noconfirm PDF_Pro.spec" >&2
  exit 1
fi

# --- .deb ---
DEB_ROOT="$OUT/deb-root"
mkdir -p "$DEB_ROOT/opt/pdf-pro" \
         "$DEB_ROOT/usr/bin" \
         "$DEB_ROOT/usr/share/applications" \
         "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps" \
         "$DEB_ROOT/usr/share/icons/hicolor/128x128/apps" \
         "$DEB_ROOT/usr/share/icons/hicolor/64x64/apps" \
         "$DEB_ROOT/usr/share/icons/hicolor/48x48/apps" \
         "$DEB_ROOT/usr/share/icons/hicolor/32x32/apps" \
         "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps" \
         "$DEB_ROOT/usr/share/doc/pdf-pro" \
         "$DEB_ROOT/DEBIAN"

cp -a "$ONEDIR/." "$DEB_ROOT/opt/pdf-pro/"
cat > "$DEB_ROOT/usr/bin/pdf-pro" <<'WRAP'
#!/bin/sh
exec /opt/pdf-pro/PDF_Pro "$@"
WRAP
chmod 755 "$DEB_ROOT/usr/bin/pdf-pro"
sed 's|^Exec=.*|Exec=/usr/bin/pdf-pro %f|; s|^Icon=.*|Icon=pdf-pro|' \
  "$ROOT/packaging/linux/pdf-pro.desktop" \
  > "$DEB_ROOT/usr/share/applications/pdf-pro.desktop"
install -m 644 "$ROOT/assets/pdf_pro_icon_256.png" "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps/pdf-pro.png"
install -m 644 "$ROOT/assets/pdf_pro_icon_128.png" "$DEB_ROOT/usr/share/icons/hicolor/128x128/apps/pdf-pro.png"
install -m 644 "$ROOT/assets/pdf_pro_icon_64.png" "$DEB_ROOT/usr/share/icons/hicolor/64x64/apps/pdf-pro.png"
install -m 644 "$ROOT/assets/pdf_pro_icon_48.png" "$DEB_ROOT/usr/share/icons/hicolor/48x48/apps/pdf-pro.png"
install -m 644 "$ROOT/assets/pdf_pro_icon_32.png" "$DEB_ROOT/usr/share/icons/hicolor/32x32/apps/pdf-pro.png"
install -m 644 "$ROOT/assets/pdf_pro_icon_512.png" "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps/pdf-pro.png"
desktop-file-validate "$DEB_ROOT/usr/share/applications/pdf-pro.desktop"
cp "$ROOT/LICENSE" "$DEB_ROOT/usr/share/doc/pdf-pro/copyright"
cp "$ROOT/README.md" "$DEB_ROOT/usr/share/doc/pdf-pro/"

SIZE_KB="$(du -sk "$DEB_ROOT" | awk '{print $1}')"
cat > "$DEB_ROOT/DEBIAN/control" <<CTRL
Package: pdf-pro
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: BartKupc <https://github.com/BartKupc>
Installed-Size: ${SIZE_KB}
Depends: libc6
Homepage: https://github.com/BartKupc/PDF_Pro
Description: Local-first PDF amend-and-sign desktop app
 PDF_Pro opens a PDF, lets you place overlay text, white-out,
 cover-and-replace, images and visual signatures, then exports a
 flattened new file. The source PDF is never overwritten.
CTRL
chmod 755 "$DEB_ROOT/usr/bin/pdf-pro"
cat > "$DEB_ROOT/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
POST
chmod 755 "$DEB_ROOT/DEBIAN/postinst"
dpkg-deb --root-owner-group --build "$DEB_ROOT" "$OUT/pdf-pro_${VERSION}_${ARCH}.deb"

# --- AppImage ---
APPDIR="$OUT/PDF_Pro.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ONEDIR/." "$APPDIR/usr/bin/"
# AppRun launches the bundled binary
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/PDF_Pro" "$@"
RUN
chmod 755 "$APPDIR/AppRun"
cp "$ROOT/packaging/linux/pdf-pro.desktop" "$APPDIR/pdf-pro.desktop"
sed -i 's|^Exec=.*|Exec=PDF_Pro %f|; s|^Icon=.*|Icon=pdf-pro|' "$APPDIR/pdf-pro.desktop"
cp "$APPDIR/pdf-pro.desktop" "$APPDIR/usr/share/applications/pdf-pro.desktop"
cp "$ROOT/assets/pdf_pro_icon_256.png" "$APPDIR/pdf-pro.png"
cp "$ROOT/assets/pdf_pro_icon_256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/pdf-pro.png"
PATH="$APPDIR/usr/bin:$PATH" desktop-file-validate "$APPDIR/pdf-pro.desktop"

TOOL="${APPIMAGETOOL:-$OUT/appimagetool}"
if [[ ! -x "$TOOL" ]]; then
  curl -fsSL -o "$TOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi
ARCH=x86_64 "$TOOL" "$APPDIR" "$OUT/PDF_Pro-${VERSION}-x86_64.AppImage"

( cd "$OUT" && sha256sum pdf-pro_${VERSION}_${ARCH}.deb "PDF_Pro-${VERSION}-x86_64.AppImage" > SHA256SUMS )
echo "Built:"
cat "$OUT/SHA256SUMS"
