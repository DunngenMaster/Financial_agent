import os
import shutil
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..services.store.memory import MEM_STORE
from ..config import settings
from ..services.pathway.client import PathwayClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clear", tags=["clear"])

@router.post("/documents")
async def clear_documents():
    """
    Clear all documents and associated data from the system.
    This includes:
    1. In-memory document store
    2. Uploaded files (PDFs and JSONs)
    3. Pathway document storage
    """
    try:
        # 1. Clear in-memory store
        MEM_STORE.docs.clear()
        logger.info("Cleared in-memory document store")

        # 2. Clear uploaded files
        upload_path = Path(settings.UPLOAD_PATH)
        if upload_path.exists():
            try:
                # Clear all files in the directory
                for item in upload_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                logger.info(f"Cleared all files from {upload_path}")
            except Exception as e:
                logger.error(f"Error clearing upload directory: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to clear upload directory: {str(e)}"
                )

        # 3. Clear Pathway storage
        try:
            pathway_client = PathwayClient()
            await pathway_client.clear_documents()
            logger.info("Cleared Pathway document storage")
        except Exception as e:
            logger.error(f"Error clearing Pathway storage: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to clear Pathway storage: {str(e)}"
            )

        return {
            "status": "success",
            "message": "All documents and associated data have been cleared"
        }

    except Exception as e:
        logger.error(f"Error during clear operation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear documents: {str(e)}"
        )