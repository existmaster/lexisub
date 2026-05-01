from pathlib import Path
from lexisub.core.pdf_extractor import open_pdf, chunk_pages, PdfPage


def test_open_pdf_returns_metadata_and_pages(sample_pdf: Path):
    meta, pages = open_pdf(sample_pdf)
    assert meta.page_count == 2
    assert len(pages) == 2
    assert pages[0].page_no == 1
    assert "Guard Pass" in pages[0].text
    assert "kimura" in pages[1].text.lower()


def test_chunk_pages_combines_short_pages():
    pages = [
        PdfPage(1, "short page one"),
        PdfPage(2, "short page two"),
        PdfPage(3, "short page three"),
    ]
    chunks = chunk_pages(pages, target_chars=100)
    assert len(chunks) == 1
    assert chunks[0][0] == [1, 2, 3]


def test_chunk_pages_splits_long_pages():
    pages = [
        PdfPage(1, "x" * 2500),
        PdfPage(2, "y" * 2500),
        PdfPage(3, "z" * 2500),
    ]
    chunks = chunk_pages(pages, target_chars=3000)
    # Each page is ~2500; first chunk has page 1, then page 2 fits with
    # page 1 only if it fits in target. Actually the algorithm flushes
    # before adding the page that would exceed, so we expect 3 chunks.
    assert len(chunks) == 3
    assert chunks[0][0] == [1]
    assert chunks[1][0] == [2]
    assert chunks[2][0] == [3]
