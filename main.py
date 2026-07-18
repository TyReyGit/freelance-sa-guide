"""
FastAPI wrapper around the rag_skeleton retrieval/generation pipeline.
Run: uvicorn main:app --reload
"""

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import rag_skeleton
from rag_skeleton import generate, retrieve

# Importing rag_skeleton already ran its module-level load_dotenv() call,
# so .env is loaded before any request handler runs — no need to repeat it here.

logger = logging.getLogger(__name__)

app = FastAPI(title="freelance-sa-guide")


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
