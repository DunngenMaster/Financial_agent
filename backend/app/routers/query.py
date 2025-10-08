# backend/app/routers/query.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from ..services.pathway.client import PathwayClient
from ..services.store.memory import MEM_STORE
from ..services.qa.service import qa_service

router = APIRouter(prefix="/query", tags=["query"])

class QueryBody(BaseModel):
    doc_id: str = Field(..., description="The ingested doc_id you got from /process/pdf")
    question: str
    top_k: int = 5
    timestamp: Optional[int] = Field(None, description="Timestamp to prevent caching")
    persona: Optional[str] = Field("general", description="Investor persona for tailored analysis")

class MultiQueryBody(BaseModel):
    doc_ids: List[str] = Field(..., description="List of document IDs to search across")
    question: str
    top_k: int = 5
    timestamp: Optional[int] = Field(None, description="Timestamp to prevent caching")
    persona: Optional[str] = Field("general", description="Investor persona for tailored analysis")

@router.post("", response_model=Dict[str, Any])
async def query(body: QueryBody):
    print(f"Query received: doc_id={body.doc_id}, question='{body.question}', timestamp={body.timestamp}")
    
    # First check if document exists in memory store
    chunks = MEM_STORE.get(body.doc_id)
    if not chunks:
        return {
            "status": "error", 
            "answers": ["Document not found. Please make sure the document was uploaded successfully."], 
            "citations": []
        }
    
    print(f"Found {len(chunks)} chunks in memory store")
    
    try:
        # Use Friendli AI for intelligent Q&A
        print(f"Using Friendli AI for Q&A with {body.persona} persona...")
        answer = await qa_service.answer_question(body.doc_id, body.question, body.persona)
        
        if answer and len(answer.strip()) > 10:
            print(f"Friendli AI returned: {answer[:100]}...")
            return {
                "status": "ok", 
                "answers": [answer], 
                "citations": [{"title": "Document Analysis", "source": "AI Generated"}]
            }
    except Exception as e:
        print(f"Friendli AI Q&A failed: {e}")
    
    # Fallback 1: Try Pathway
    try:
        print("Trying Pathway as fallback...")
        pw = PathwayClient()
        resp = await pw.query({
            "doc_id": body.doc_id,
            "question": body.question,
            "top_k": body.top_k
        })
        answers = resp.get("answers", [])
        citations = resp.get("citations", [])
        if answers and len(answers) > 0 and answers[0].strip():
            print(f"Pathway returned: {answers[0][:100]}...")
            return {"status": "ok", "answers": answers, "citations": citations}
    except Exception as e:
        print(f"Pathway query failed: {e}")

    # Fallback 2: Simple keyword search
    print("Using simple keyword search as final fallback...")
    hits = MEM_STORE.search(body.doc_id, body.question, top_k=body.top_k)
    print(f"Memory search found {len(hits)} hits")
    
    if hits:
        # Clean and format the best hit
        best_hit = hits[0]
        text = best_hit.get('text', '').strip()
        
        # Remove HTML tags and clean up
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        answer = f"Based on the document content: {text}"
        cits = [{"slide": best_hit.get("slide", 0), "title": best_hit.get("title", "Document")}]
        return {"status": "ok", "answers": [answer], "citations": cits}
    else:
        # Last resort: provide general document content
        first_chunk = chunks[0] if chunks else {}
        text = first_chunk.get('text', '').strip()
        
        # Clean HTML tags
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) > 300:
            text = text[:300] + "..."
        
        answer = f"I couldn't find specific information about '{body.question}', but here's some content from the document: {text}"
        return {
            "status": "ok", 
            "answers": [answer], 
            "citations": [{"title": first_chunk.get('title', 'Document')}]
        }

@router.post("/multi", response_model=Dict[str, Any])
async def multi_query(body: MultiQueryBody):
    """Query across multiple documents"""
    print(f"Multi-document query: doc_ids={body.doc_ids}, question='{body.question}', timestamp={body.timestamp}")
    
    if not body.doc_ids:
        return {
            "status": "error", 
            "answers": ["No documents specified for search."], 
            "citations": []
        }
    
    # Check which documents exist
    available_docs = []
    all_chunks = []
    
    for doc_id in body.doc_ids:
        chunks = MEM_STORE.get(doc_id)
        if chunks:
            available_docs.append(doc_id)
            all_chunks.extend([(doc_id, chunk) for chunk in chunks])
    
    if not available_docs:
        return {
            "status": "error", 
            "answers": ["None of the specified documents were found."], 
            "citations": []
        }
    
    print(f"Found {len(available_docs)} available documents with {len(all_chunks)} total chunks")
    
    try:
        # Use enhanced QA service for multi-document search
        print(f"Using multi-document Q&A with {body.persona} persona...")
        answer = await qa_service.answer_multi_document_question(available_docs, body.question, body.persona)
        
        if answer and len(answer.strip()) > 10:
            print(f"Multi-doc Friendli AI returned: {answer[:100]}...")
            return {
                "status": "ok", 
                "answers": [answer], 
                "citations": [{"title": f"Analysis across {len(available_docs)} documents", "source": "AI Generated"}]
            }
    except Exception as e:
        print(f"Multi-document Friendli AI Q&A failed: {e}")
    
    # Fallback: Search across all chunks
    print("Using fallback multi-document search...")
    
    # Score all chunks across all documents
    question_words = set(body.question.lower().split())
    scored_chunks = []
    
    for doc_id, chunk in all_chunks:
        text = chunk.get('text', '').lower()
        title = chunk.get('title', '').lower()
        
        # Score based on keyword matches
        text_score = sum(1 for word in question_words if word in text and len(word) > 2)
        title_score = sum(1 for word in question_words if word in title and len(word) > 2) * 2
        
        total_score = text_score + title_score
        if total_score > 0:
            scored_chunks.append((total_score, doc_id, chunk))
    
    if scored_chunks:
        # Sort by relevance and get best matches
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        best_chunks = scored_chunks[:3]  # Top 3 matches across all documents
        
        # Build comprehensive answer
        answer_parts = []
        citations = []
        
        for score, doc_id, chunk in best_chunks:
            text = chunk.get('text', '').strip()
            # Clean HTML tags
            import re
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            if len(text) > 150:
                text = text[:150] + "..."
            
            answer_parts.append(text)
            citations.append({
                "doc_id": doc_id,
                "title": chunk.get('title', 'Document'),
                "score": score
            })
        
        answer = f"Based on your {len(available_docs)} documents: " + " | ".join(answer_parts)
        return {"status": "ok", "answers": [answer], "citations": citations}
    
    else:
        # No specific matches, provide general content
        sample_chunks = [chunk for _, chunk in all_chunks[:2]]
        texts = []
        
        for chunk in sample_chunks:
            text = chunk.get('text', '').strip()
            import re
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 100:
                text = text[:100] + "..."
            texts.append(text)
        
        answer = f"I searched across {len(available_docs)} documents but couldn't find specific matches for '{body.question}'. Here's some general content: {' | '.join(texts)}"
        return {
            "status": "ok", 
            "answers": [answer], 
            "citations": [{"title": f"General content from {len(available_docs)} documents"}]
        }
