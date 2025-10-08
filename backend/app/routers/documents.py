from fastapi import APIRouter
from typing import Dict, Any
from ..services.store.memory import MEM_STORE

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("")
async def get_documents() -> Dict[str, Any]:
    """Get all documents in the memory store"""
    documents = {}
    for doc_id, chunks in MEM_STORE.docs.items():
        if chunks and len(chunks) > 0:
            first_chunk = chunks[0]
            if first_chunk.get("source") and first_chunk.get("timestamp"):
                documents[doc_id] = {
                    "doc_id": doc_id,
                    "filename": first_chunk["source"],
                    "processed_date": first_chunk["timestamp"],
                    "content": first_chunk.get("text", ""),
                }
    return documents