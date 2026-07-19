"""
FastAPI wrapper around the rag_skeleton retrieval/generation pipeline.
Run: uvicorn main:app --reload
"""

import glob
import logging
import os
import threading
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import rag_skeleton
import setup_docs
from rag_skeleton import generate, retrieve

# Importing rag_skeleton already ran its module-level load_dotenv() call,
# so .env is loaded before any request handler runs — no need to repeat it here.

logger = logging.getLogger(__name__)

app = FastAPI(title="freelance-sa-guide")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Set by the background indexing thread, read by /ask and /health. A plain
# string is fine here (no lock): CPython attribute assignment is atomic and
# there's a single writer.
_index_status = "indexing"  # "indexing" | "ready" | "error"


def _build_index() -> None:
    global _index_status
    try:
        # On a host with no persistent disk, docs/ and chroma_db/ start out empty
        # on every boot, so both steps need to run here rather than once by hand.
        if not glob.glob(os.path.join(setup_docs.DOCS_DIR, "*.pdf")):
            logger.info("docs/ is empty, downloading SARS guides...")
            setup_docs.download_all()

        collection = rag_skeleton.get_collection()
        if collection.count() == 0:
            logger.info("chroma_db collection is empty, indexing...")
            rag_skeleton.index_if_needed(collection)

        _index_status = "ready"
        logger.info("Indexing complete, /ask is now serving answers.")
    except Exception:
        logger.exception("Background indexing failed")
        _index_status = "error"


@app.on_event("startup")
def startup_event() -> None:
    # Indexing can take ~10 minutes against the free-tier embedding rate limit.
    # Running it here in the request thread would delay uvicorn's port bind
    # past Render's deploy timeout, so it runs in a background thread instead.
    threading.Thread(target=_build_index, daemon=True).start()


class AskRequest(BaseModel):
    question: str
    provider: Literal["gemini", "groq"] = "gemini"


class Source(BaseModel):
    source: str
    page: int


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    if _index_status != "ready":
        detail = (
            "Index is still building, try again in a few minutes"
            if _index_status == "indexing"
            else "Index build failed, please contact the site owner"
        )
        return JSONResponse(status_code=503, content={"detail": detail})

    # generate() reads the provider off this module-level global rather than
    # taking it as an argument (same knob rag_skeleton's own CLI uses via --provider).
    rag_skeleton._PROVIDER = request.provider

    chunks = retrieve(request.question, k=4)

    try:
        answer = generate(request.question, chunks)
    except Exception:
        logger.exception("generate() failed for question: %r", request.question)
        raise HTTPException(
            status_code=502,
            detail="The AI provider is temporarily unavailable, please try again",
        )

    sources = []
    seen = set()
    for c in chunks:
        key = (c["source"], c["page"])
        if key not in seen:
            seen.add(key)
            sources.append(Source(source=c["source"], page=c["page"]))

    return AskResponse(answer=answer, sources=sources)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "index_status": _index_status}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", reload=True)
