from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/pathway", tags=["pathway"])

# Simple in-memory store for pathway stub
_PATHWAY_DOCS: Dict[str, Any] = {}

@router.post("/ingest")
async def pathway_ingest(payload: Dict[str, Any]):
    """Mock pathway ingest endpoint"""
    doc_id = payload.get("doc_id", "unknown")
    chunks = payload.get("chunks", [])
    
    _PATHWAY_DOCS[doc_id] = {
        "doc_id": doc_id,
        "chunks": chunks,
        "metadata": payload
    }
    
    return {
        "status": "success",
        "message": f"Document {doc_id} ingested successfully",
        "doc_id": doc_id,
        "chunk_count": len(chunks)
    }

@router.post("/query")
async def pathway_query(payload: Dict[str, Any]):
    """Mock pathway query endpoint"""
    doc_id = payload.get("doc_id")
    question = payload.get("question", "")
    
    print(f"Pathway stub query: doc_id={doc_id}, question={question}")
    
    if doc_id not in _PATHWAY_DOCS:
        return {
            "answers": ["I couldn't find the requested document. Please make sure the document was uploaded successfully."],
            "citations": []
        }
    
    doc_data = _PATHWAY_DOCS[doc_id]
    chunks = doc_data.get("chunks", [])
    
    print(f"Pathway stub found {len(chunks)} chunks")
    
    # Enhanced keyword matching
    question_lower = question.lower()
    question_words = [w for w in question_lower.split() if len(w) > 2]
    
    scored_chunks = []
    for chunk in chunks:
        text = chunk.get("text", "").lower()
        title = chunk.get("title", "").lower()
        
        # Score based on keyword matches
        score = 0
        for word in question_words:
            if word in text:
                score += text.count(word) * 2
            if word in title:
                score += 3
        
        if score > 0:
            scored_chunks.append((score, chunk))
    
    # Sort by relevance score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    if scored_chunks:
        # Return content from most relevant chunk
        best_chunk = scored_chunks[0][1]
        text = best_chunk.get('text', '')
        
        # Provide a more natural response
        if len(text) > 300:
            answer = f"Based on the document: {text[:300]}..."
        else:
            answer = f"Based on the document: {text}"
            
        return {
            "answers": [answer],
            "citations": [{"doc_id": doc_id, "title": best_chunk.get('title', 'Document')}]
        }
    else:
        # If no keyword matches, provide general content
        if chunks:
            general_content = " ".join([c.get('text', '')[:100] for c in chunks[:2] if c.get('text')])
            return {
                "answers": [f"I found the document but no specific matches for '{question}'. Here's some content from the document: {general_content}..."],
                "citations": [{"doc_id": doc_id, "title": chunks[0].get('title', 'Document')}]
            }
        else:
            return {
                "answers": ["The document appears to be empty or couldn't be processed properly."],
                "citations": []
            }

@router.post("/clear")
async def pathway_clear():
    """Clear all documents from pathway storage"""
    _PATHWAY_DOCS.clear()
    return {"status": "success", "message": "All documents cleared from pathway storage"}

@router.get("/documents")
async def pathway_documents():
    """Get all documents in pathway storage"""
    return {
        "documents": list(_PATHWAY_DOCS.keys()),
        "count": len(_PATHWAY_DOCS)
    }