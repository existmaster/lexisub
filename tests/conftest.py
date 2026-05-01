from pathlib import Path
import pytest
import fitz


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory) -> Path:
    """A tiny 2-page PDF with MMA terms for testing.

    Built fresh per session so we don't commit a binary fixture.
    """
    p = tmp_path_factory.mktemp("pdfs") / "sample.pdf"
    doc = fitz.open()  # new PDF
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Chapter 1: Guard Pass\n\n"
        "The guard pass is a fundamental BJJ technique used to "
        "advance from inside the opponent's guard to side control.\n"
        "Common methods include the over-under pass and toreando pass.",
        fontsize=11,
    )
    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "Chapter 2: Submissions\n\n"
        "The armbar applies hyperextension to the elbow joint. "
        "The kimura is a shoulder lock named after Masahiko Kimura.\n"
        "Rear naked choke is the highest-percentage submission in MMA.",
        fontsize=11,
    )
    doc.save(p)
    doc.close()
    return p
