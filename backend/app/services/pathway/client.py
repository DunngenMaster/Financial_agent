from typing import Any, Dict, Optional
import httpx
from ...config import settings


class PathwayClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or str(settings.PATHWAY_URL)).rstrip("/")
        self.fallback_url = "http://localhost:8000/pathway"

    async def ingest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Try external Pathway first, fallback to local stub
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                r = await client.post(f"{self.base_url}/ingest", json=payload)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            print(f"External Pathway failed: {e}, using local fallback")
            # Use local pathway stub
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                r = await client.post(f"{self.fallback_url}/ingest", json=payload)
                r.raise_for_status()
                return r.json()

    async def query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Try external Pathway first, fallback to local stub
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                r = await client.post(f"{self.base_url}/query", json=payload)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            print(f"External Pathway query failed: {e}, using local fallback")
            # Use local pathway stub
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                r = await client.post(f"{self.fallback_url}/query", json=payload)
                r.raise_for_status()
                return r.json()

    async def clear_documents(self) -> Dict[str, Any]:
        """Clear all documents from the Pathway storage"""
        # Try external Pathway first, fallback to local stub
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                r = await client.post(f"{self.base_url}/clear")
                r.raise_for_status()
                return r.json()
        except Exception as e:
            print(f"External Pathway clear failed: {e}, using local fallback")
            # Use local pathway stub
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                r = await client.post(f"{self.fallback_url}/clear")
                r.raise_for_status()
                return r.json()
