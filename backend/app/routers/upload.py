import uuid
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..services.store.file_storage import FileStorage
from ..services.ade.client import ADEClient
from ..services.pathway.client import PathwayClient

router = APIRouter(prefix="/process", tags=["process"])

ADE_SCHEMA = {
    "type": "object",
    "properties": {
        # Licensing and Compliance
        "license_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required licenses and permits"
        },
        "compliance_risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Potential compliance risks and penalties"
        },
        
        # Zoning and Location
        "zoning_restrictions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Local zoning laws and restrictions"
        },
        "affected_locations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Cities or regions with specific regulations"
        },
        
        # Safety and Insurance
        "safety_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required safety measures"
        },
        "insurance_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required insurance coverage"
        },
        
        # Legal and Privacy
        "data_privacy_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Data protection and privacy requirements"
        },
        "legal_risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Potential legal risks and litigation exposure"
        },
        
        # Financial Impact
        "potential_costs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Potential financial impacts and costs"
        },
        "tax_obligations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tax requirements and obligations"
        }
    }
}

import logging
from typing import List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add allowed file types
ALLOWED_EXTENSIONS = {'.pdf'}

def validate_file(file: UploadFile) -> None:
    """Validate the uploaded file"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check content type
    if not file.content_type or 'application/pdf' not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="Invalid content type. Must be PDF")

from fastapi.responses import JSONResponse
import aiofiles
import asyncio

@router.post("/pdf")
async def upload_pdf(
    file: UploadFile = File(...)
):
    logger.info(f"Received upload request for file: {file.filename}")
    
    # Validate file
    try:
        validate_file(file)
    except HTTPException as e:
        logger.error(f"File validation failed: {e.detail}")
        raise

    try:
        # Generate a unique claim ID
        claim_id = str(uuid.uuid4())
        logger.info(f"Generated claim_id: {claim_id}")
        
        # Save the file
        storage = FileStorage()
        file_path = await storage.save_file(file, claim_id)
        logger.info(f"File saved successfully at: {file_path}")
        
        # Process with Landing AI
        ade_client = ADEClient()
        
        # Read the saved file
        file_size = Path(file_path).stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"Large file detected ({file_size/1024/1024:.1f}MB). Processing may take longer.")
            
        async with aiofiles.open(file_path, 'rb') as f:
            file_bytes = await f.read()
            
        # Use one-shot extraction with progress tracking
        logger.info("Processing PDF with Landing AI...")
        try:
            ade_result = await ade_client.one_shot_pdf_extract(
                file_name=file.filename,
                file_bytes=file_bytes,
                schema=ADE_SCHEMA
            )
            logger.info("Successfully processed PDF with Landing AI")
        except Exception as e:
            logger.error(f"ADE processing failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )
        
        # Store the raw response for debugging
        markdown = ade_result.get("markdown", "")
        
        # Save Landing AI results next to the PDF
        results_path = Path(file_path).with_suffix('.json')
        
        # Organize the extracted data into categories
        organized_results = {
            "metadata": {
                "claim_id": claim_id,
                "filename": file.filename,
                "pdf_path": str(file_path),
                "processed_date": str(datetime.now())
            },
            "content": {
                "markdown": markdown,
                "raw_extraction": ade_result
            },
            "regulatory_analysis": {
                "licensing_and_compliance": {
                    "requirements": ade_result.get("data", {}).get("extracted_schema", {}).get("license_requirements", []),
                    "risks": ade_result.get("data", {}).get("extracted_schema", {}).get("compliance_risks", [])
                },
                "zoning": {
                    "restrictions": ade_result.get("data", {}).get("extracted_schema", {}).get("zoning_restrictions", []),
                    "affected_locations": ade_result.get("data", {}).get("extracted_schema", {}).get("affected_locations", [])
                },
                "safety_and_insurance": {
                    "safety": ade_result.get("data", {}).get("extracted_schema", {}).get("safety_requirements", []),
                    "insurance": ade_result.get("data", {}).get("extracted_schema", {}).get("insurance_requirements", [])
                },
                "legal_and_privacy": {
                    "privacy": ade_result.get("data", {}).get("extracted_schema", {}).get("data_privacy_requirements", []),
                    "legal_risks": ade_result.get("data", {}).get("extracted_schema", {}).get("legal_risks", [])
                },
                "financial": {
                    "costs": ade_result.get("data", {}).get("extracted_schema", {}).get("potential_costs", []),
                    "tax_obligations": ade_result.get("data", {}).get("extracted_schema", {}).get("tax_obligations", [])
                }
            }
        }

        # Save results locally
        async with aiofiles.open(results_path, 'w') as f:
            await f.write(json.dumps(organized_results, indent=2))
        
        logger.info(f"Results saved to: {results_path}")
        
        # Send to Pathway for RAG processing
        logger.info("Sending to Pathway for processing...")
        pw_client = PathwayClient()
        try:
            # Extract markdown and analysis from ADE result
            raw_extraction = ade_result.get("data", {})
            markdown = raw_extraction.get("markdown", "")
            extracted_schema = raw_extraction.get("extracted_schema", {})
            
            # Send to Pathway for processing
            pathway_response = await pw_client.ingest({
                "claim_id": claim_id,
                "filename": file.filename,
                "file_path": str(file_path),
                "text": markdown,
                "ade": {
                    "markdown": markdown,
                    "analysis": extracted_schema
                }
            })
            logger.info("Successfully processed by Pathway")
        except Exception as e:
            logger.error(f"Pathway processing failed: {e}")
            pathway_response = {"status": "failed", "error": str(e)}
        
        return {
            "status": "success",
            "message": "File uploaded and processed successfully",
            "metadata": organized_results["metadata"],
            "results_path": str(results_path),
            "regulatory_analysis": organized_results["regulatory_analysis"],
            "pathway_status": pathway_response
        }
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
