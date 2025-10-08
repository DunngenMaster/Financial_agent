# app/routers/invest.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from ..services.pathway.client import PathwayClient
from ..services.store.memory import MEM_STORE
from ..services.llm.friendly_client import FriendlyClient
from ..services.research.web_research import WebResearchService

router = APIRouter(prefix="/invest", tags=["invest"])

class InvestBody(BaseModel):
    doc_ids: List[str] = Field(..., description="One or more doc_ids (e.g., pitch + regulatory PDF)")
    persona: Optional[str] = Field("general", description="Persona tone for the writeup")
    company: Optional[str] = Field(None, description="Company name for web presence check")
    top_k: int = 5

def _clean_text(txt: str) -> str:
    import re
    txt = re.sub(r"<[^>]+>", "", txt or "")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

async def _gather_context_from_docs(doc_ids: List[str], question: str, top_k: int) -> str:
    pw = PathwayClient()
    all_bits: List[str] = []

    # 1) Try Pathway per doc (preferred)
    for doc_id in doc_ids:
        try:
            resp = await pw.query({"doc_id": doc_id, "question": question, "top_k": top_k})
            answers = resp.get("answers") or []
            for a in answers:
                if a:
                    all_bits.append(_clean_text(a))
        except Exception:
            pass

    # 2) Fallback to MEM_STORE if sparse
    if not all_bits:
        for doc_id in doc_ids:
            hits = MEM_STORE.search(doc_id, question, top_k=top_k)
            for h in hits:
                all_bits.append(_clean_text(h.get("text", "")))

    # Last fallback: dump first chunk
    if not all_bits:
        for doc_id in doc_ids:
            chunks = MEM_STORE.get(doc_id)
            if chunks:
                all_bits.append(_clean_text(chunks[0].get("text", "")))

    # Concise merge
    unique_bits = []
    seen = set()
    for b in all_bits:
        key = b[:200]
        if key not in seen and b:
            unique_bits.append(b if len(b) < 800 else b[:800] + " ...")
            seen.add(key)
        if len(unique_bits) >= 8:
            break

    return "\n\n".join(unique_bits)

async def _web_presence_snippet(company: Optional[str]) -> str:
    if not company:
        return ""
    try:
        wr = WebResearchService()
        results = await wr.search_topic(f"{company} company overview traction revenue users news", max_results=3)
        snippets = []
        for r in results:
            snippets.append(f"- {r.get('title','')}: {r.get('snippet','')}")
        await wr.close()
        return "ONLINE SIGNALS:\n" + "\n".join(snippets) if snippets else ""
    except Exception:
        return ""

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_investment(body: InvestBody):
    if not body.doc_ids:
        raise HTTPException(400, "doc_ids is required")

    # Build analysis context
    question = "investment thesis, risks, catalysts, unit economics, regulatory exposure, and moat"
    doc_context = await _gather_context_from_docs(body.doc_ids, question, body.top_k)
    web_context = await _web_presence_snippet(body.company)

    if not doc_context and not web_context:
        return {
            "status": "ok",
            "decision": "insufficient_data",
            "likelihood_percent": 0,
            "rationale": "I couldn't find enough context to evaluate this investment.",
            "forecast_points": []
        }

    # Persona hint
    persona_hint = {
        "general": "balanced investor, fundamentals + risk-adjusted view",
        "tech": "tech-savvy investor; platform effects, scalability, product velocity",
        "value": "value investor; margin of safety, FCF, downside protection",
        "growth": "growth investor; TAM, execution, durable growth",
        "esg": "ESG-focused; sustainability, governance, long-term resilience",
        "institutional": "institutional PM; portfolio fit, liquidity, risk metrics",
        "retail": "retail-friendly; clarity, practical takeaways",
        "risk": "risk officer; tail risks, compliance, stress scenarios",
    }.get(body.persona or "general", "balanced investor")

    # Ask Friendly AI for a structured JSON verdict
    fc = FriendlyClient()
    system = (
        "You are an investment committee assistant. "
        "Return STRICT JSON only. Provide a clear invest/do_not_invest decision, a likelihood percent (0-100), "
        "a short rationale (<= 180 words), and exactly three forward-looking forecasting points "
        "that highlight execution or market watch items."
    )

    schema = {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["invest", "do_not_invest", "defer", "insufficient_data"]},
            "likelihood_percent": {"type": "number"},
            "rationale": {"type": "string"},
            "forecast_points": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3}
        },
        "required": ["decision", "likelihood_percent", "rationale", "forecast_points"]
    }

    merged_context = (
        f"PERSONA: {persona_hint}\n\n"
        f"RAG CONTEXT:\n{doc_context}\n\n"
        f"{web_context}"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"SCHEMA:\n{schema}\n\nBased on the following evidence, produce JSON only.\n\n{merged_context}"}
    ]

    try:
        resp = await fc.chat(messages)
        content = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(500, f"Friendly AI error: {e}")

    import json
    try:
        data = json.loads(content)
    except Exception:
        # Try to salvage any JSON substring
        import re
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise HTTPException(500, "Model returned non-JSON content")
        data = json.loads(match.group(0))

    # clamp percent
    pct = float(max(0, min(100, data.get("likelihood_percent", 0))))
    return {
        "status": "ok",
        "decision": data.get("decision", "insufficient_data"),
        "likelihood_percent": pct,
        "rationale": data.get("rationale", ""),
        "forecast_points": data.get("forecast_points", [])[:3],
        "used_docs": body.doc_ids,
        "company": body.company
    }
