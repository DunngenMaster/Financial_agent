from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from pathlib import Path
import json

from ..services.pathway.client import PathwayClient
from ..services.store.memory import MEM_STORE
from ..services.llm.friendly_client import FriendlyClient  # <-- correct path

router = APIRouter(prefix="/qa", tags=["qa"])

# Resolve to the app/ folder and keep uploads inside it
APP_DIR = Path(__file__).resolve().parents[1]  # backend/app
UPLOADS_DIR = APP_DIR / "uploads"
LOG_DIR = UPLOADS_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ---------- existing tiny session store kept (optional) ----------
_SESS: Dict[str, Dict] = {}  # session_id -> {"doc_id": "...", "history": [...]}

class CreateSessionBody(BaseModel):
    doc_id: str

class AskBody(BaseModel):
    session_id: str
    question: str
    top_k: int = 5

class ChatBody(BaseModel):
    doc_id: str
    question: str
    top_k: int = 5

@router.post("/session", response_model=dict)
async def create_session(body: CreateSessionBody):
    import uuid
    sid = str(uuid.uuid4())
    _SESS[sid] = {"doc_id": body.doc_id, "history": []}
    return {"status": "ok", "session_id": sid}

@router.post("/ask", response_model=dict)
async def ask(body: AskBody):
    s = _SESS.get(body.session_id)
    if not s:
        raise HTTPException(404, "Unknown session_id")
    # Reuse the chat logic with the session's doc_id
    resp = await chat(ChatBody(doc_id=s["doc_id"], question=body.question, top_k=body.top_k))
    # Track simple history
    s["history"].append({"q": body.question, "a": resp.get("answer")})
    resp["session_id"] = body.session_id
    return resp

@router.post("/chat", response_model=Dict[str, Any])
async def chat(body: ChatBody):
    pw = PathwayClient()
    fc = FriendlyClient()

    # Step 1: try Pathway retrieval
    context = ""
    citations = []
    try:
        resp = await pw.query({
            "doc_id": body.doc_id,
            "question": body.question,
            "top_k": body.top_k
        })
        answers = resp.get("answers", [])
        citations = resp.get("citations", [])
        if answers:
            context = "\n".join(a for a in answers if a)
    except Exception:
        pass

    # Step 2: fallback to local MEM_STORE
    if not context:
        hits = MEM_STORE.search(body.doc_id, body.question, top_k=body.top_k)
        if hits:
            context = "\n".join([h.get("text", "") for h in hits])
            citations = [{"slide": h.get("slide"), "title": h.get("title")} for h in hits]
        else:
            return {
                "status": "ok",
                "answer": "Sorry, I couldn't find anything relevant.",
                "citations": [],
                "log_file": str(LOG_DIR / f"{body.doc_id}.json")
            }

    # Step 3: Friendly AI answer
    try:
        friendly_answer = await fc.ask(question=body.question, context=context)
    except Exception as e:
        friendly_answer = f"(Friendly AI error: {e})"

    # Step 4: persist the turn
    log_file = LOG_DIR / f"{body.doc_id}.json"
    turn = {"q": body.question, "a": friendly_answer, "citations": citations}
    try:
        if log_file.exists():
            existing = json.loads(log_file.read_text(encoding="utf-8"))
            if isinstance(existing, list):
                existing.append(turn)
                log_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            else:
                log_file.write_text(json.dumps([existing, turn], indent=2), encoding="utf-8")
        else:
            log_file.write_text(json.dumps([turn], indent=2), encoding="utf-8")
    except Exception as e:
        # don't fail the API on logging error—just report the path + error
        return {
            "status": "ok",
            "answer": friendly_answer,
            "citations": citations,
            "doc_id": body.doc_id,
            "log_file": str(log_file),
            "log_error": str(e)
        }

    return {
        "status": "ok",
        "answer": friendly_answer,
        "citations": citations,
        "doc_id": body.doc_id,
        "log_file": str(log_file)
    }
