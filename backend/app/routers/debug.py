from fastapi import APIRouter
from ..services.store.memory import MEM_STORE

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/memory")
async def debug_memory():
    """Debug endpoint to check what's in memory store"""
    return {
        "doc_count": len(MEM_STORE.docs),
        "doc_ids": list(MEM_STORE.docs.keys()),
        "docs": {
            doc_id: {
                "chunk_count": len(chunks),
                "first_chunk": chunks[0] if chunks else None,
                "all_chunks": chunks[:3] if chunks else []  # Show first 3 chunks for debugging
            }
            for doc_id, chunks in MEM_STORE.docs.items()
        }
    }