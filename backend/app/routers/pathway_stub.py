from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/pathway_stub", tags=["pathway_stub"])

# in-memory store (very simple) so you can see what was ingested
_DB: Dict[str, Any] = {"docs": {}}

@router.post("/ingest")
async def ingest(payload: Dict[str, Any]):
    doc_id = payload.get("doc_id", "unknown")
    chunks = payload.get("chunks", [])
    _DB["docs"][doc_id] = {"doc": payload, "count": len(chunks)}
    return {"status": "ok", "ingested": len(chunks), "doc_id": doc_id}

@router.post("/query")
async def query(q: Dict[str, Any]):
    # naive echo to prove wiring; replace with real Pathway later
    return {"answers": ["stubbed response"], "citations": [], "query": q}

@router.get("/debug/docs")
async def debug_docs():
    return {"count": len(_DB["docs"]), "ids": list(_DB["docs"].keys())}
