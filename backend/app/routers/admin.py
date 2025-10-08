from fastapi import APIRouter
from pathlib import Path
import json
from ..services.store.memory import MEM_STORE
from ..config import settings

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/populate-memory")
async def populate_memory_from_files():
    """Populate memory store from existing uploaded files"""
    upload_path = Path(settings.UPLOAD_PATH)
    populated_count = 0
    
    if not upload_path.exists():
        return {"status": "error", "message": "Upload directory does not exist"}
    
    # Clear existing memory store first
    MEM_STORE.docs.clear()
    
    # Find all JSON files (they contain the processed data)
    for json_file in upload_path.glob("*.json"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Extract document info
            metadata = data.get("metadata", {})
            content = data.get("content", {})
            
            claim_id = metadata.get("claim_id")
            filename = metadata.get("filename")
            processed_date = metadata.get("processed_date")
            
            if not claim_id or not filename:
                continue
            
            # Create chunks from the content
            chunks = [{
                "doc_id": claim_id,
                "source": filename,
                "timestamp": processed_date,
                "text": content.get("markdown", ""),
                "title": filename,
                "slide": 0,
                "tags": ["document"]
            }]
            
            # Add to memory store
            MEM_STORE.add(claim_id, chunks)
            populated_count += 1
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue
    
    return {
        "status": "success", 
        "message": f"Populated {populated_count} documents into memory store"
    }