from fastapi import APIRouter, HTTPException, UploadFile, File
import uuid
from pathlib import Path

from ..services.ade.client import ADEClient
from ..services.pathway.client import PathwayClient
from ..pipeline.ingest.slide_transform import extracted_to_chunks, markdown_to_chunks
from ..services.store.memory import MEM_STORE

router = APIRouter(prefix="/process", tags=["process"])

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

from fastapi import status

@router.post("/pdf", response_model=dict)
async def process_pdf(file: UploadFile = File(...)):
    # Validate file type
    if not file.content_type or 'pdf' not in file.content_type.lower():
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are allowed"
        )

    # Initialize clients
    try:
        ade = ADEClient()
        pw = PathwayClient()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to initialize services: {str(e)}"
        )

    # 1) Read file
    try:
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 10MB limit"
            )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )

    # 2) Parse to markdown
    try:
        parsed = await ade.parse_pdf_to_markdown(file.filename, file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to parse PDF: {str(e)}"
        )

    document_markdown = parsed.get("document_markdown") or parsed.get("markdown")
    if not document_markdown:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No content extracted from PDF"
        )

    # 3) Extract structured chunks
    try:
        extracted = await ade.extract_from_markdown(document_markdown, SLIDES_SCHEMA)
        chunks = extracted_to_chunks(extracted)
    except Exception as e:
        print(f"Structured extraction failed, falling back to markdown chunks: {e}")
        chunks = []

    if not chunks:
        try:
            chunks = markdown_to_chunks(document_markdown)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to extract content: {str(e)}"
            )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No processable content found in document"
        )

    # 4) Assign doc_id and store
    try:
        from datetime import datetime
        doc_id = str(uuid.uuid4())
        
        # Add metadata to chunks
        for chunk in chunks:
            chunk["timestamp"] = datetime.utcnow().isoformat()
            chunk["source"] = file.filename
            chunk["doc_id"] = doc_id
        
        payload = {
            "doc_id": doc_id,
            "doc_type": "slides",
            "source": file.filename,
            "chunks": chunks
        }
        MEM_STORE.add(doc_id, chunks)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store document: {str(e)}"
        )

    # 5) Send to Pathway (optional - don't fail if Pathway is not available)
    pw_resp = {"status": "pathway_unavailable", "message": "Pathway service not available"}
    try:
        pw_resp = await pw.ingest(payload)
    except Exception as e:
        print(f"Warning: Pathway ingestion failed: {e}")
        # Don't fail the entire upload if Pathway is unavailable
        # Just store in memory and continue
        pw_resp = {"status": "pathway_failed", "error": str(e)}

    preview_chunk = chunks[0] if chunks else None
    summary = next((c for c in chunks if "summary" in c.get("tags", [])), None)
    slides = [
        {
            "slide": c["slide"],
            "title": c["title"],
            "snippet": c["text"][:150]
        }
        for c in chunks if c.get("slide", 0) > 0
    ]

    return {
        "status": "success",
        "metadata": {
            "claim_id": doc_id,
            "filename": file.filename,
            "chunk_count": len(chunks),
            "file_size": len(file_bytes),
        },
        "content_preview": {
            "preview_chunk": preview_chunk,
            "summary": summary,
            "slides": slides
        },
        "pathway_response": pw_resp
    }

