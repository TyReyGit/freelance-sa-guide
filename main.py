"""
FastAPI wrapper around the rag_skeleton retrieval/generation pipeline.
Run: uvicorn main:app --reload
"""

import glob
import logging
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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


@app.on_event("startup")
def startup_event() -> None:
    # On a host with no persistent disk, docs/ and chroma_db/ start out empty
    # on every boot, so both steps need to run here rather than once by hand.
    if not glob.glob(os.path.join(setup_docs.DOCS_DIR, "*.pdf")):
        logger.info("docs/ is empty, downloading SARS guides...")
        setup_docs.download_all()

    collection = rag_skeleton.get_collection()
    if collection.count() == 0:
        logger.info("chroma_db collection is empty, indexing...")
        rag_skeleton.index_if_needed(collection)


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
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", reload=True)
