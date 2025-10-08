from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import pathway as pw
import pickle
from datetime import datetime
from pathlib import Path
import json
import numpy as np

# Data storage paths
DATA_DIR = Path(__file__).parent / "data"
STORAGE_PATH = DATA_DIR / "pathway_docs.pkl"

class QueryPayload(BaseModel):
    query: str
    claim_id: Optional[str] = None
    persona: Optional[str] = "analyst"

class Document:
    def __init__(self, doc_id: str, text: str, metadata: Dict = None):
        self.doc_id = doc_id
        self.text = text
        self.metadata = metadata or {}
        self.chunks = []
        self.embeddings = []

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory document store
PATHWAY_DOCS: Dict[str, Document] = {}

@app.post("/ingest")
async def ingest_document(payload: Dict[str, Any]):
    try:
        # Extract data from the payload
        doc_id = payload.get("claim_id")
        if not doc_id:
            raise ValueError("claim_id is required")
            
        # Extract text and analysis from payload
        text = payload.get("text", "")
        ade_data = payload.get("ade", {})
        
        if not text and ade_data:
            text = ade_data.get("markdown", "No content available")
            
        # Store metadata including ADE analysis
        metadata = {
            "filename": payload.get("filename"),
            "file_path": payload.get("file_path"),
            "ade_analysis": ade_data.get("analysis", {})
        }
        
        # Create document
        doc = Document(doc_id, text, metadata)
        
        # Store document
        PATHWAY_DOCS[doc_id] = doc
        
        # Save to disk
        save_documents()
        
        return {"status": "success", "doc_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")

@app.get("/documents")
async def get_documents():
    return {
        doc_id: {
            "doc_id": doc.doc_id,
            "metadata": doc.metadata,
            "chunks": len(doc.chunks)
        }
        for doc_id, doc in PATHWAY_DOCS.items()
    }

@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    if doc_id not in PATHWAY_DOCS:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = PATHWAY_DOCS[doc_id]
    return {
        "doc_id": doc.doc_id,
        "filename": doc.metadata.get("filename", "Unnamed Document"),
        "content": doc.text,
        "metadata": doc.metadata,
        "processed_date": doc.metadata.get("processed_date", datetime.now().isoformat())
    }

@app.post("/query")
async def query_documents(q: QueryPayload):
    try:
        # Get documents to search
        docs_to_search = {}
        if q.claim_id:
            if q.claim_id not in PATHWAY_DOCS:
                raise HTTPException(status_code=404, detail="Document not found")
            docs_to_search[q.claim_id] = PATHWAY_DOCS[q.claim_id]
        else:
            docs_to_search = PATHWAY_DOCS

        if not docs_to_search:
            return {"answer": "No documents available to search"}

        # Build context from documents
        context = []
        for doc_id, doc in docs_to_search.items():
            filename = doc.metadata.get('filename', 'Unnamed Document')
            
            # Prepare document content
            doc_content = [f"Content from {filename}:"]
            doc_content.append(doc.text)
            
            # Add regulatory analysis if available
            ade_analysis = doc.metadata.get('ade_analysis', {})
            if ade_analysis:
                doc_content.append("\nRegulatory Analysis:")
                if ade_analysis.get('license_requirements'):
                    doc_content.append("\nLicensing Requirements:")
                    doc_content.extend(f"- {req}" for req in ade_analysis['license_requirements'])
                if ade_analysis.get('compliance_risks'):
                    doc_content.append("\nCompliance Risks:")
                    doc_content.extend(f"- {risk}" for risk in ade_analysis['compliance_risks'])
                if ade_analysis.get('zoning_restrictions'):
                    doc_content.append("\nZoning Restrictions:")
                    doc_content.extend(f"- {restriction}" for restriction in ade_analysis['zoning_restrictions'])
                if ade_analysis.get('safety_requirements'):
                    doc_content.append("\nSafety Requirements:")
                    doc_content.extend(f"- {req}" for req in ade_analysis['safety_requirements'])
            
            context.extend(doc_content)

        # Format context for Friendli
        full_context = "\n".join(context)
        prompt = f"Based on the following document, please provide a detailed analysis from the perspective of a {q.persona}. Focus on the most relevant points for this type of reader.\n\nDocument Content:\n{full_context}\n\nQuestion: {q.query}"

        try:
            from app.services.llm.friendly_client import FriendlyClient
            fc = FriendlyClient()
            messages = [{"role": "user", "content": prompt}]
            response = await fc.chat(messages)
            answer = response['choices'][0]['message']['content']
        except Exception as e:
            print(f"Friendli error: {e}")
            # Fallback to basic response if Friendli fails
            answer = f"Based on the documents, here is the analysis:\n\n{full_context}"

        return {
            "answer": answer,
            "context": context
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

def save_documents():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STORAGE_PATH, "wb") as f:
        pickle.dump(PATHWAY_DOCS, f)

def load_documents():
    global PATHWAY_DOCS
    try:
        if STORAGE_PATH.exists():
            with open(STORAGE_PATH, "rb") as f:
                PATHWAY_DOCS = pickle.load(f)
    except Exception as e:
        print(f"Error loading documents: {e}")
        PATHWAY_DOCS = {}

@app.on_event("startup")
async def startup_event():
    load_documents()