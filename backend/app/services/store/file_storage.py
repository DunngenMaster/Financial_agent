import os
import logging
from pathlib import Path
from fastapi import UploadFile, HTTPException
from ...config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileStorage:
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.UPLOAD_PATH)
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Storage directory initialized at {self.base_path}")
        except Exception as e:
            logger.error(f"Failed to create storage directory: {e}")
            raise HTTPException(status_code=500, detail=f"Storage initialization failed: {e}")

    async def save_file(self, file: UploadFile, claim_id: str) -> str:
        """Save an uploaded file and return its path"""
        try:
            # Validate file
            if not file.filename:
                raise ValueError("No filename provided")
            
            file_path = self.base_path / f"{claim_id}_{file.filename}"
            logger.info(f"Attempting to save file to {file_path}")
            
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the file using chunks to handle large files efficiently
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks
            try:
                with open(file_path, "wb") as f:
                    while chunk := await file.read(CHUNK_SIZE):
                        f.write(chunk)
            except Exception as e:
                # Clean up if save fails
                if file_path.exists():
                    file_path.unlink()
                raise e

            # No need to seek(0) as we'll open the file fresh for reading
            
            # Verify file was saved
            if not file_path.exists():
                raise FileNotFoundError("File was not saved successfully")
                
            file_size = file_path.stat().st_size
            logger.info(f"File saved successfully. Size: {file_size} bytes")
            
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")