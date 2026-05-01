"""OCR a scanned PDF using Apple Vision and produce a text-layer PDF.

Usage:
    uv run python scripts/ocr_pdf.py <input.pdf> [-o <output.pdf>]
                                     [--lang ko en] [--dpi 200]

The output PDF preserves the page count and order. Each page contains
just the OCR'd text (image-free), which is enough for downstream use
in Lexisub (which only reads text via PyMuPDF for term extraction).

Apple Vision is macOS-only. Korean accuracy is excellent.
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

import fitz  # pymupdf
from PIL import Image


def ocr_pdf(
    src: Path,
    dst: Path,
    languages: list[str],
    dpi: int = 200,
    on_progress=None,
) -> tuple[int, int, float]:
    """OCR every page of `src` via Apple Vision and write a text-only PDF
    to `dst`.

    Returns (page_count, total_chars, elapsed_seconds).
    """
    from ocrmac import ocrmac

    src_doc = fitz.open(str(src))
    dst_doc = fitz.open()

    start = time.monotonic()
    total_chars = 0
    page_count = src_doc.page_count

    for i in range(page_count):
        if on_progress:
            on_progress(i, page_count)

        page = src_doc[i]
        # Render page → PIL Image (ocrmac requires path or PIL Image)
        zoom = dpi / 72  # PDF unit is 72 DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # Apple Vision OCR — returns list of (text, confidence, bbox)
        try:
            results = ocrmac.OCR(
                img,
                language_preference=languages,
                recognition_level="accurate",
            ).recognize()
        except Exception as e:
            print(f"\n  page {i + 1}: OCR failed ({e}); inserting blank")
            results = []

        text = "\n".join(r[0] for r in results)
        total_chars += len(text)

        # Write a same-sized page with the OCR text. Layout is approximate:
        # we just dump text top-to-bottom in reading order.
        new_page = dst_doc.new_page(width=page.rect.width, height=page.rect.height)
        if text:
            # Insert as a textbox so long text wraps within page width.
            margin = 36
            rect = fitz.Rect(
                margin, margin,
                page.rect.width - margin, page.rect.height - margin,
            )
            new_page.insert_textbox(rect, text, fontsize=9, fontname="helv")

    if on_progress:
        on_progress(page_count, page_count)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst_doc.save(str(dst))
    dst_doc.close()
    src_doc.close()

    return page_count, total_chars, time.monotonic() - start


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path, help="Source PDF (scanned, no text layer)")
    p.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output text-layer PDF (default: <input>.ocr.pdf in same dir)",
    )
    p.add_argument(
        "--lang",
        nargs="+",
        default=["ko-KR", "en-US"],
        help="Apple Vision language preferences in priority order "
        "(default: ko-KR en-US). Use BCP-47 codes.",
    )
    p.add_argument("--dpi", type=int, default=200, help="Render DPI (default 200)")
    args = p.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    out = args.output or args.input.with_suffix(".ocr.pdf")

    last_pct = -1

    def progress(i: int, total: int) -> None:
        nonlocal last_pct
        pct = int(i / total * 100) if total else 0
        if pct != last_pct:
            elapsed = ""  # filled in by counter
            print(f"  page {i}/{total}  ({pct}%)", end="\r", flush=True)
            last_pct = pct

    print(f"OCR {args.input.name} → {out.name}")
    print(f"  languages: {args.lang}, dpi: {args.dpi}")

    pages, chars, elapsed = ocr_pdf(
        args.input, out, languages=args.lang, dpi=args.dpi, on_progress=progress,
    )

    print()
    print(f"  done in {elapsed:.1f}s ({pages / elapsed:.2f} pages/sec)")
    print(f"  pages: {pages}, total chars extracted: {chars:,}")
    print(f"  avg chars/page: {chars // max(1, pages)}")
    print(f"  output: {out}")
    print()
    print("Test the result:")
    print(
        f'  uv run python -c "import fitz; d = fitz.open(\\"{out}\\"); '
        f'print(d[0].get_text()[:300])"'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
