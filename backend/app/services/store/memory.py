# backend/app/services/store/memory.py
from typing import Dict, Any, List
from collections import defaultdict
import re

class MemoryStore:
    """
    Very light in-memory store so the QA agent can query chunks even if you're
    still on the stub instead of a real Pathway index.
    """
    def __init__(self):
        # doc_id -> list of chunks
        self.docs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def add(self, doc_id: str, chunks: List[Dict[str, Any]]):
        self.docs[doc_id] = list(chunks or [])

    def get(self, doc_id: str) -> List[Dict[str, Any]]:
        return self.docs.get(doc_id, [])
        
    def remove(self, doc_id: str) -> None:
        """Remove a document and its chunks from the store"""
        if doc_id in self.docs:
            del self.docs[doc_id]

    def search(self, doc_id: str, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        naive keyword score: count of overlaps of words (case-insensitive)
        """
        chunks = self.get(doc_id)
        if not chunks:
            return []
        q_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
        scored = []
        for ch in chunks:
            txt = f"{ch.get('title','')} {ch.get('text','')}".lower()
            c_tokens = set(re.findall(r"[a-z0-9]+", txt))
            score = len(q_tokens & c_tokens)
            if score > 0:
                scored.append((score, ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

# singleton
MEM_STORE = MemoryStore()
