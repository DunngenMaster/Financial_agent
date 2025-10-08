from typing import Any, Dict, List
import re

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def extracted_to_chunks(extracted: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    ADE extract_from_markdown → Pathway chunks (preferred if ADE returned Slides[])
    """
    slides = extracted.get("Slides") or []
    chunks: List[Dict[str, Any]] = []

    for s in slides:
        slide = s.get("SlideNumber") or 0
        title = _clean(s.get("Title") or "")
        bullets = s.get("Bullets") or []
        narrative = _clean(s.get("Narrative") or "")
        tables = s.get("TablesMarkdown") or []

        text_parts = [title] + bullets + ([narrative] if narrative else [])
        text = " | ".join([_clean(t) for t in text_parts if _clean(t)])

        chunks.append({
            "slide": slide,
            "title": title,
            "text": text,
            "tables": tables,
            "tags": ["slides"]
        })

    if extracted.get("DocTitle"):
        chunks.insert(0, {
            "slide": 0,
            "title": _clean(extracted["DocTitle"]),
            "text": f"Deck: {_clean(extracted['DocTitle'])}",
            "tables": [],
            "tags": ["summary"]
        })

    return chunks

def markdown_to_chunks(markdown: str) -> List[Dict[str, Any]]:
    """
    Fallback: split ADE markdown into slide-like chunks using simple heuristics.
    - Treat ALL-CAPS lines and common headings as boundaries.
    - Also split on 'TABLE OF CONTENT|ABOUT US|PROBLEM|SOLUTION|MARKET|FUNDING|TEAM|FINANCIAL|GO TO MARKET' etc.
    """
    md = markdown.replace("\r", "")
    lines = md.split("\n")

    # candidate headings (tuned for pitch decks)
    heading_re = re.compile(
        r"^\s*(?:#{1,3}\s*)?("
        r"[A-Z][A-Z0-9 &/\-]{3,}"
        r"|(?:\d{1,2}\.?\s+)?(ABOUT US|PROBLEM|PROBLEMS|SOLUTION|SOLUTIONS|GO TO MARKET|MARKET OPPORTUNITY|BUSINESS MODEL|COMPETITIVE ADVANTAGE|FUNDING|FINANCIALS|OUR TEAM|TEAM|INVESTORS|SUMMARY|OVERVIEW|TABLE OF CONTENTS?)"
        r")\s*$"
    )

    sections: List[Dict[str, Any]] = []
    current_title = "Slide"
    current_buf: List[str] = []
    slide_no = 1

    def _flush():
        nonlocal slide_no, current_title, current_buf
        text = _clean(" ".join(current_buf))
        if text:
            sections.append({
                "slide": slide_no,
                "title": _clean(current_title),
                "text": text,
                "tables": [],
                "tags": ["slides"]
            })
            slide_no += 1
        current_title, current_buf = "Slide", []

    for ln in lines:
        if heading_re.match(ln.strip()):
            _flush()
            current_title = ln.strip().lstrip("#").strip()
        else:
            # collect bullets & narrative; strip figure placeholders
            if "::figure::" in ln.lower() or ":: scene ::" in ln.lower():
                continue
            current_buf.append(ln)

    _flush()
    # Add a summary chunk from the first heading if present
    if sections:
        sections.insert(0, {
            "slide": 0,
            "title": "Deck Summary",
            "text": _clean(sections[1]["title"]) if len(sections) > 1 else "Pitch Deck",
            "tables": [],
            "tags": ["summary"]
        })
    return sections
