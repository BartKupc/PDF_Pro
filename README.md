# PDF_Pro

Local-first Linux desktop app: open a PDF, place overlay text, white-out,
cover-and-replace, images, and drawn/typed/image signatures, then export a
**new** flattened PDF. The source file is never overwritten.

Product of [BartKupc](https://github.com/BartKupc). Licence: **AGPL-3.0**
(required by PyMuPDF).

## Privacy (local-first)

- No accounts, no telemetry, **no network calls** in the application.
- Originals, overlays, exports, and the signature vault stay on this machine.
- The source PDF is opened read-only. Export always writes a different path.

## Legal positioning

Drawn, typed, and uploaded signatures in PDF_Pro are **visual / electronic
appearances**, not certificate-backed digital signatures. The app does **not**
claim legal validity, identity proof, witnessing, or tamper-proofing. You must
judge whether the recipient and jurisdiction will accept them.

**Cover-and-replace is not redaction.** Underlying PDF content may still be
extractable. The UI states this wherever covers are used.

Amending a PDF that already has a digital signature or certification **will
invalidate** that signature. PDF_Pro warns on open and never claims the old
signature survives.

## Requirements (from source)

- Linux (x86_64), Ubuntu 22.04-era glibc or newer
- Python 3.11+ (3.12 recommended)
- System packages for Qt 6 / OpenGL as needed by PySide6

```bash
cd work/pdf-amend   # or the clone of PDF_Pro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

### Run

```bash
python -m pdf_pro
# or
pdf-pro /path/to/file.pdf
```

### Tests (this milestone)

```bash
python -m unittest discover -s tests -v
# or, if pytest is installed:
pytest -q
```

Headless UI tests (CI sets `QT_QPA_PLATFORM=offscreen`; skip when PySide6/PyMuPDF are missing):

```bash
QT_QPA_PLATFORM=offscreen python -m unittest tests.test_preview_accept tests.test_qt_instance_enums tests.test_signature_studio_place tests.test_qimage_png -v
```

## Install from GitHub Release (Bart publishes tags)

`.deb` (Ubuntu/Debian) — installs `/usr/bin/pdf-pro`, `/usr/share/applications/pdf-pro.desktop`,
and hicolor icons so the app appears in the grid and is double-clickable:

```bash
sudo apt install ./pdf-pro_<version>_amd64.deb
pdf-pro
```

AppImage (no install):

```bash
chmod +x PDF_Pro-<version>-x86_64.AppImage
./PDF_Pro-<version>-x86_64.AppImage
```

**GNOME Files “Allow Launching”.** On GNOME, a downloaded AppImage is often treated as
untrusted, so double-click does nothing until you mark it executable:

1. Right-click `PDF_Pro-*-x86_64.AppImage` in Files.
2. Choose **Allow Launching** (or Properties → Permissions → “Allow executing as a program”).
3. Double-click. AppImageLauncher, if installed, will also pick up the bundled `.desktop` + icon.

To pin it in the app grid without installing the `.deb`, copy
`pdf-pro.desktop.example` from this repo to `~/.local/share/applications/pdf-pro.desktop`
and edit `Exec=` (absolute path to the AppImage) and `Icon=` if needed, then:

```bash
update-desktop-database ~/.local/share/applications
```

Verify checksums against `SHA256SUMS` on the same release. There is no
code-signing certificate in v1; provenance is GitHub Releases + SHA256.

## Signature vault

Saved signatures live under `$XDG_DATA_HOME/pdf_pro/vault/` (default
`~/.local/share/pdf_pro/vault/vault.json`) as **plain local files**. This is a
personal single-user tool; OS disk encryption is the control.

If a v0.2.1 encrypted `vault.bin` is still present, the first vault open asks
for the old passphrase **once** to migrate, then never prompts again. Cancel /
forgot passphrase: keep the encrypted file and optionally start with an empty
vault. PDF_Pro does not delete the old file silently.

## Build packages locally

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm PDF_Pro.spec
VERSION=0.2.3 ./packaging/linux/build.sh
```

Outputs: `dist/packages/pdf-pro_<ver>_amd64.deb`,
`dist/packages/PDF_Pro-<ver>-x86_64.AppImage`, and `SHA256SUMS`.

GitHub Actions (`.github/workflows/release.yml`) does the same on `v*` tags.
Do not expect this repo to push itself — Bart publishes.

## Milestone 2 status

Implemented: multi-document tabs (edits/undo isolated), find-in-doc + copy,
full text style (italic/underline/alignment/background/opacity), shapes
(rects including black boxes, lines, arrows, circles, highlights, underline,
strike-through, freehand), image/signature rotate-duplicate-layer, page
rotate/delete/reorder/duplicate, merge + extract, signature date/label,
vault rename/replace/delete, drafts + crash recovery, local history + wipe,
scan-only and missing-font notices, off-thread preview/export with progress,
atomic export writes, fitz lock around render.

**Not in M2 (see ROADMAP.md M3):** stamps, direct in-PDF text replace, OCR,
compression, image→PDF, page numbers/headers/watermarks, open/send after
export, certificate-backed signing.

## Milestone 1 status

Implemented: open (dialog + drag-drop), progressive render, thumbnails, page
nav, zoom / fit-width / fit-page, rotate **view**, password + corrupt notices,
read-only source, overlay text/white-out/cover-and-replace/images/signatures,
undo/redo, plain local vault, pre-export preview, flatten export to a new file
with validation. Ribbon (Home / Amend / Pages / Sign / Export). File dialogs use Qt's
non-native dialogs so save/open works on Ubuntu when GTK/portal dialogs fail.

## Bundled fonts

- DejaVu Sans / Serif / Mono — Bitstream Vera / DejaVu licence (`pdf_pro/fonts`)
- Dancing Script — SIL Open Font Licence (`pdf_pro/fonts/OFL-DancingScript.txt`)
