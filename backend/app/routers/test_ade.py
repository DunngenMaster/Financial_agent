import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from ..services.ade.client import ADEClient
from ..models.ingestion import ADEOutput

router = APIRouter(prefix="/test", tags=["test"])

# hardcoded demo file: backend/test.pdf
PDF_PATH = (Path(__file__).resolve().parents[2] / "test.pdf")

@router.get("/pdf_markdown")
async def pdf_markdown():
    if not PDF_PATH.exists():
        raise HTTPException(404, f"PDF not found at {PDF_PATH}")
    ade = ADEClient()
    parsed = await ade.parse_pdf_to_markdown(PDF_PATH.name, PDF_PATH.read_bytes())
    doc_md = parsed.get("document_markdown") or parsed.get("markdown") or ""
    preview = (doc_md[:4000] + "...") if doc_md else None
    return {"status": "ok", "pdf_path": str(PDF_PATH), "chars": len(doc_md), "preview": preview}

# simple slide schema for direct extract-from-markdown
SLIDES_SCHEMA = {
    "type": "object",
    "properties": {
        "DocTitle": {"type": "string"},
        "SlideCount": {"type": "number"},
        "Slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "SlideNumber": {"type": "number"},
                    "Title": {"type": "string"},
                    "Bullets": {"type": "array", "items": {"type": "string"}},
                    "Narrative": {"type": "string"},
                    "TablesMarkdown": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    }
}

@router.get("/pdf_slides")
async def pdf_slides():
    if not PDF_PATH.exists():
        raise HTTPException(404, f"PDF not found at {PDF_PATH}")
    ade = ADEClient()
    parsed = await ade.parse_pdf_to_markdown(PDF_PATH.name, PDF_PATH.read_bytes())
    document_markdown = parsed.get("document_markdown") or parsed.get("markdown")
    if not document_markdown:
        raise HTTPException(500, "Parse returned no markdown")
    extracted = await ade.extract_from_markdown(document_markdown, SLIDES_SCHEMA)
    # try to coerce; if shape differs, return raw
    try:
        ade_model = ADEOutput.model_validate({
            "document_id": extracted.get("document_id") or str(uuid.uuid4()),
            "doc_type": extracted.get("doc_type"),
            "fields": extracted.get("fields", {}),
            "tables": extracted.get("tables", {}),
        })
        return {"status": "ok", "pdf_path": str(PDF_PATH), "ade_output": ade_model}
    except Exception:
        return {"status": "ok", "pdf_path": str(PDF_PATH), "raw": extracted}
