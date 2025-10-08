from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class Grounding(BaseModel):
    page: Optional[int] = None
    box: Optional[List[float]] = None  # [x1, y1, x2, y2]


class ADEField(BaseModel):
    value: Any
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    grounding: Optional[Grounding] = None


class ADEOutput(BaseModel):
    document_id: str
    doc_type: Optional[str] = None
    fields: Dict[str, ADEField] = Field(default_factory=dict)
    tables: Dict[str, Any] = Field(default_factory=dict)


class IngestPayload(BaseModel):
    claim_id: str
    filename: str
    file_path: str
    ade: ADEOutput


class UploadResponse(BaseModel):
    claim_id: str
    filename: str
    ade: ADEOutput
    pathway: Dict[str, Any]
