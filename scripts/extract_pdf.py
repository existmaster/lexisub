"""Extract glossary terms from one or more PDFs via the local LLM.

Usage:
    uv run python scripts/extract_pdf.py <pdf> [<pdf>...] [--lang en] [--db PATH] [--csv PATH]

Writes terms to a SQLite DB (default: demos/outputs/extracted.sqlite3) and
optionally exports them to CSV. Status defaults to 'pending' so the user can
review them in the GUI's 용어집 탭 before the translator uses them.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from lexisub.core import pdf_extractor
from lexisub.db import repository


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pdfs", nargs="+", type=Path)
    p.add_argument(
        "--lang",
        default="auto",
        help="ISO source-language hint (e.g. en, ko, pt). 'auto' detects per PDF. (default: auto)",
    )
    p.add_argument(
        "--db",
        type=Path,
        default=Path("demos/outputs/extracted.sqlite3"),
        help="SQLite DB to write terms into",
    )
    p.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Optional CSV export of all terms in the DB after extraction",
    )
    args = p.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    repository.init_db(args.db)

    total_inserted = 0
    for pdf in args.pdfs:
        if not pdf.exists():
            print(f"error: PDF not found: {pdf}", file=sys.stderr)
            return 2
        print(f"\n=== {pdf.name} ===")

        last_stage = ""
        last_pct = -1

        def on_progress(stage: str, frac: float) -> None:
            nonlocal last_stage, last_pct
            pct = int(frac * 100)
            if stage != last_stage or pct != last_pct:
                print(f"  [{stage}] {pct}%", end="\r", flush=True)
                last_stage = stage
                last_pct = pct

        lang_arg = None if args.lang == "auto" else args.lang
        try:
            n = pdf_extractor.extract_terms(
                pdf, args.db, source_lang=lang_arg, progress=on_progress
            )
        except Exception as e:
            print(f"\n  failed: {e}")
            continue
        print(f"\n  → {n} term records (with sources)")
        total_inserted += n

    rows = repository.list_terms(args.db)
    print(f"\nTotal unique terms in DB: {len(rows)}  (inserted this run: {total_inserted})")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["source_lang", "source_term", "ko_term", "category", "status"])
            for r in rows:
                w.writerow(
                    [
                        r["source_lang"],
                        r["source_term"],
                        r["ko_term"],
                        r["category"] or "",
                        r["status"],
                    ]
                )
        print(f"CSV written: {args.csv}")

    print("\nReview the pending terms in the GUI 용어집 탭, then re-process the video.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
