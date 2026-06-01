#!/usr/bin/env sh
# pptx-qa-export.sh - Export PPTX slides to PNG images for visual QA
# Usage: pptx-qa-export.sh <path/to/file.pptx> [output-dir]
#   output-dir defaults to temp/ (relative to the current working directory)
#
# Requires: LibreOffice (soffice or libreoffice) with headless support.
# Install:
#   macOS:  brew install libreoffice
#   Linux:  apt-get install libreoffice
#
# The script converts the PPTX to PDF via LibreOffice headless, then
# uses LibreOffice's draw export to render each slide to PNG.
# Output files: <output-dir>/<basename>-slide-01.png  (1-indexed, zero-padded)

set -eu

if [ $# -lt 1 ]; then
    echo "Usage: pptx-qa-export.sh <file.pptx> [output-dir]" >&2
    exit 1
fi

PPTX_PATH="$1"
OUTDIR="${2:-temp}"

# Resolve absolute path for the PPTX file.
if [ ! -f "$PPTX_PATH" ]; then
    echo "[ERROR] File not found: $PPTX_PATH" >&2
    exit 1
fi

# Detect LibreOffice binary (try soffice first, then libreoffice).
SOFFICE=""
if command -v soffice >/dev/null 2>&1; then
    SOFFICE="soffice"
elif command -v libreoffice >/dev/null 2>&1; then
    SOFFICE="libreoffice"
else
    echo "[ERROR] LibreOffice not found. Install it to use pptx-qa-export.sh:" >&2
    echo "  macOS:  brew install libreoffice" >&2
    echo "  Linux:  apt-get install libreoffice" >&2
    exit 1
fi

BASENAME="$(basename "${PPTX_PATH%.*}")"
mkdir -p "$OUTDIR"

echo "Exporting slides from $PPTX_PATH ..."

# Step 1: Convert PPTX to PDF using LibreOffice headless.
# --outdir must be an existing directory.
"$SOFFICE" --headless --convert-to pdf --outdir "$OUTDIR" "$PPTX_PATH"

PDF_FILE="$OUTDIR/${BASENAME}.pdf"
if [ ! -f "$PDF_FILE" ]; then
    echo "[ERROR] LibreOffice PDF export failed: $PDF_FILE not created." >&2
    exit 1
fi

# Step 2: Convert each PDF page to a PNG using LibreOffice draw export
# via pdftoppm (part of poppler-utils) if available, otherwise fall back
# to a per-page LibreOffice PNG export from the PDF.

if command -v pdftoppm >/dev/null 2>&1; then
    # pdftoppm is the most reliable PDF-to-PNG converter.
    pdftoppm -r 144 -png "$PDF_FILE" "$OUTDIR/${BASENAME}-slide"
    # pdftoppm names files as <prefix>-N.png (no zero-padding for small counts).
    # Rename to zero-padded two-digit form expected by QA subagent.
    for f in "$OUTDIR/${BASENAME}-slide"*.png; do
        [ -f "$f" ] || continue
        # Extract trailing digit(s) before .png.
        num="${f##*-slide}"
        num="${num%.png}"
        new_name="$OUTDIR/${BASENAME}-slide-$(printf '%02d' "$num").png"
        if [ "$f" != "$new_name" ]; then
            mv "$f" "$new_name"
        fi
        echo "$new_name"
    done
else
    # Fallback: LibreOffice PNG export of the PDF (one file per page).
    # This produces <basename>.png for a single-page PDF or
    # <basename>N.png for multi-page. Handle both.
    "$SOFFICE" --headless --convert-to png --outdir "$OUTDIR" "$PDF_FILE"
    N=0
    for f in "$OUTDIR/${BASENAME}"*.png; do
        [ -f "$f" ] || continue
        N=$((N + 1))
        new_name="$OUTDIR/${BASENAME}-slide-$(printf '%02d' "$N").png"
        mv "$f" "$new_name"
        echo "$new_name"
    done
    if [ "$N" -eq 0 ]; then
        echo "[ERROR] No PNG files produced by LibreOffice export." >&2
        exit 1
    fi
fi

echo "[OK] Slide images written to $OUTDIR/"
