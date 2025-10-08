import json, uuid
from typing import Any, Dict, Optional
import httpx
from ...config import settings


class ADEClient:
    """
    LandingAI ADE client with two flows:
    1) parse_pdf_to_markdown -> returns markdown
    2) extract_from_markdown(markdown, schema) -> returns structured fields
    """

    def __init__(self, api_key: Optional[str] = None, base_host: Optional[str] = None):
        self.api_key = api_key or settings.ADE_API_KEY
        if not self.api_key:
            raise RuntimeError("ADE_API_KEY not set.")
        self.host = (base_host or str(settings.ADE_BASE_URL)).rstrip("/")
        # Use Bearer; swap to Basic if your tenant requires it
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        # If your tenant requires a model param, set it here; otherwise keep None
        self.model: Optional[str] = None  # e.g., "dpt-2-20250919"

    async def parse_pdf_to_markdown(self, file_name: str, file_bytes: bytes) -> Dict[str, Any]:
        """
        POST {host}/v1/ade/parse
        multipart: document (application/pdf)
        form: output_format = markdown, [model]
        """
        url = f"{self.host}/v1/ade/parse"
        files = {"document": (file_name, file_bytes, "application/pdf")}
        data = {"output_format": "markdown", "request_id": str(uuid.uuid4())}
        if self.model:
            data["model"] = self.model

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=self.headers, files=files, data=data)
            if resp.status_code != 200:
                raise RuntimeError(f"PARSE {url} -> {resp.status_code} :: {resp.text}")
            return resp.json()

    async def extract_from_markdown(self, document_markdown: str, fields_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST {host}/v1/ade/extract
        json: markdown, fields_schema, [model]
        """
        url = f"{self.host}/v1/ade/extract"
        
        # Validate input
        if not document_markdown:
            raise ValueError("document_markdown cannot be empty")
        
        if not fields_schema:
            raise ValueError("fields_schema cannot be empty")
            
        payload = {
            "markdown": document_markdown,
            "fields_schema": fields_schema,
            "request_id": str(uuid.uuid4()),
        }
        if self.model:
            payload["model"] = self.model

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                resp = await client.post(url, headers=self.headers, json=payload)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                error_detail = str(e)
                try:
                    error_json = e.response.json()
                    if isinstance(error_json, dict):
                        error_detail = error_json.get("message", str(e))
                except:
                    pass
                raise RuntimeError(f"EXTRACT {url} -> {e.response.status_code} :: {error_detail}")
            except Exception as e:
                raise RuntimeError(f"EXTRACT request failed: {str(e)}")

    async def one_shot_pdf_extract(self, file_name: str, file_bytes: bytes, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy one-shot: POST {host}/v1/tools/agentic-document-analysis
        multipart: pdf, form: fields_schema
        """
        url = f"{self.host}/v1/tools/agentic-document-analysis"
        files = {"pdf": (file_name, file_bytes, "application/pdf")}
        data = {"fields_schema": json.dumps(schema), "request_id": str(uuid.uuid4())}
        
        # Increased timeout for large files (5 minutes)
        timeout = httpx.Timeout(300.0, connect=60.0, read=300.0, write=300.0)
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=self.headers, files=files, data=data)
                if resp.status_code != 200:
                    error_msg = resp.text
                    try:
                        error_json = resp.json()
                        if isinstance(error_json, dict):
                            error_msg = error_json.get("message", error_msg)
                    except:
                        pass
                    raise RuntimeError(f"Document processing failed: {error_msg}")
                return resp.json()
        except httpx.TimeoutException:
            raise RuntimeError("Document processing timed out. The file may be too large or the server is busy.")
        except Exception as e:
            raise RuntimeError(f"Document processing failed: {str(e)}")
