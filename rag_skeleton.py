"""
Minimal RAG pipeline: pypdf -> chunk -> Gemini embeddings -> Chroma -> Gemini/Groq.
No frameworks. Run: python rag_skeleton.py "your question" [--provider gemini|groq]
"""

import os
import sys
import glob
import time

from dotenv import load_dotenv
from pypdf import PdfReader
import chromadb
from chromadb.utils import embedding_functions
import tiktoken

load_dotenv()

# --- config -----------------------------------------------------------
DOCS_DIR = "./docs"
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "docs"
CHUNK_TOKENS = 500
OVERLAP_TOKENS = 50
TOKENIZER = tiktoken.get_encoding("cl100k_base")
GROQ_MODEL = "llama-3.3-70b-versatile"

DEFAULT_PROVIDER = "gemini"


# --- load -------------------------------------------------------------
def load_pdfs(docs_dir):
    """Return one dict per page: {text, source filename, page number}."""
    pages = []
    for path in sorted(glob.glob(os.path.join(docs_dir, "*.pdf"))):
        reader = PdfReader(path)
        filename = os.path.basename(path)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"text": text, "source": filename, "page": page_num})
    return pages


# --- chunk --------------------------------------------------------------
def chunk_page(text):
    """Slide a 500-token window with 50-token overlap over one page's tokens."""
    tokens = TOKENIZER.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + CHUNK_TOKENS
        chunks.append(TOKENIZER.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start = end - OVERLAP_TOKENS
    return chunks


def build_chunks(pages):
    """Flatten pages into (chunks, metadatas, ids) ready for Chroma."""
    chunks, metadatas, ids = [], [], []
    for page in pages:
        for i, chunk in enumerate(chunk_page(page["text"])):
            chunks.append(chunk)
            metadatas.append({"source": page["source"], "page": page["page"]})
            ids.append(f"{page['source']}_p{page['page']}_c{i}")
    return chunks, metadatas, ids


# --- store / index --------------------------------------------------------
EMBEDDING_MODEL = "gemini-embedding-001"


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    # google-generativeai is deprecated (EOL Nov 2025); GoogleGenaiEmbeddingFunction
    # is chromadb's wrapper around the current google-genai SDK.
    embed_fn = embedding_functions.GoogleGenaiEmbeddingFunction(
        model_name=EMBEDDING_MODEL, api_key_env_var="GOOGLE_API_KEY"
    )
    return client.get_or_create_collection(COLLECTION_NAME, embedding_function=embed_fn)


INDEX_BATCH_SIZE = 10
INDEX_BATCH_SLEEP_SECONDS = 10
INDEX_MAX_RETRIES = 5


def _add_batch_with_retry(collection, documents, metadatas, ids):
    """The free-tier Gemini embedding quota is easy to trip mid-index; back off
    and retry the same batch on 429s instead of losing the whole indexing run."""
    wait = 15
    for attempt in range(INDEX_MAX_RETRIES):
        try:
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            return
        except ValueError as e:
            if "429" not in str(e) or attempt == INDEX_MAX_RETRIES - 1:
                raise
            print(f"Rate limited, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            wait *= 2


def index_if_needed(collection):
    if collection.count() > 0:
        return
    pages = load_pdfs(DOCS_DIR)
    chunks, metadatas, ids = build_chunks(pages)
    num_batches = (len(chunks) + INDEX_BATCH_SIZE - 1) // INDEX_BATCH_SIZE
    for batch_num, start in enumerate(range(0, len(chunks), INDEX_BATCH_SIZE)):
        end = start + INDEX_BATCH_SIZE
        _add_batch_with_retry(
            collection, chunks[start:end], metadatas[start:end], ids[start:end]
        )
        if batch_num + 1 < num_batches:
            time.sleep(INDEX_BATCH_SLEEP_SECONDS)
    print(f"Indexed {len(chunks)} chunks from {len(pages)} pages.", file=sys.stderr)


# --- retrieve ---------------------------------------------------------
def retrieve(question, k=4):
    collection = get_collection()
    index_if_needed(collection)
    results = collection.query(query_texts=[question], n_results=k)
    hits = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        hits.append({"text": doc, "source": meta["source"], "page": meta["page"]})
    return hits


# --- diagnostics --------------------------------------------------------
def check_available_models():
    """Print model names on this API key that support generateContent."""
    import requests

    api_key = os.environ["GOOGLE_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    for model in resp.json().get("models", []):
        if "generateContent" in model.get("supportedGenerationMethods", []):
            print(model["name"])


# --- generate -------------------------------------------------------------
def _build_prompt(question, chunks):
    context = "\n\n".join(
        f"[{c['source']} p.{c['page']}]\n{c['text']}" for c in chunks
    )
    return (
        "Answer the question using ONLY the context below. Do not use outside "
        "knowledge. Cite the source for every claim like (file.pdf, p.3). "
        "If the context contains relevant information that answers the question, "
        "use it and cite your sources. Only reply exactly \"not in the documents\" "
        "if the context has no relevant information at all.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
    )


def _generate_gemini(question, chunks):
    import time

    import requests  # local import: only needed if this function runs

    api_key = os.environ["GOOGLE_API_KEY"]
    prompt = _build_prompt(question, chunks)
    if _DEBUG:
        print("\n=== FULL PROMPT SENT TO LLM ===\n", file=sys.stderr)
        print(prompt, file=sys.stderr)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-flash-latest:generateContent?key={api_key}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    wait = 2
    for attempt in range(3):
        resp = requests.post(url, json=body, timeout=60)
        if resp.status_code == 503 and attempt < 2:
            time.sleep(wait)
            wait *= 2
            continue
        resp.raise_for_status()
        if _DEBUG:
            print("\n=== RAW API RESPONSE ===\n", file=sys.stderr)
            print(resp.text, file=sys.stderr)
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _generate_groq(question, chunks):
    import requests  # local import: only needed if this function runs

    api_key = os.environ["GROQ_API_KEY"]
    prompt = _build_prompt(question, chunks)
    if _DEBUG:
        print("\n=== FULL PROMPT SENT TO LLM ===\n", file=sys.stderr)
        print(prompt, file=sys.stderr)
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    body = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = requests.post(url, json=body, headers=headers, timeout=60)
    resp.raise_for_status()
    if _DEBUG:
        print("\n=== RAW API RESPONSE ===\n", file=sys.stderr)
        print(resp.text, file=sys.stderr)
    return resp.json()["choices"][0]["message"]["content"]


# provider selection lives here so generate()'s own signature never changes
_PROVIDER = DEFAULT_PROVIDER
_DEBUG = False


def generate(question, chunks):
    if _PROVIDER == "groq":
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("--provider groq requires GROQ_API_KEY to be set in .env")
        return _generate_groq(question, chunks)
    return _generate_gemini(question, chunks)


# --- CLI ----------------------------------------------------------------
def main():
    import argparse

    global _PROVIDER, _DEBUG

    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument(
        "--provider", choices=["gemini", "groq"], default=DEFAULT_PROVIDER
    )
    parser.add_argument(
        "--debug", action="store_true", help="print full retrieved chunk text before generation"
    )
    args = parser.parse_args()

    _PROVIDER = args.provider
    _DEBUG = args.debug
    chunks = retrieve(args.question, k=4)

    if args.debug:
        print("\n=== RETRIEVED CHUNKS ===\n", file=sys.stderr)
        for i, c in enumerate(chunks, start=1):
            print(f"--- chunk {i}: {c['source']} p.{c['page']} ---", file=sys.stderr)
            print(c["text"], file=sys.stderr)
            print(file=sys.stderr)

    answer = generate(args.question, chunks)

    print("\n=== ANSWER ===\n")
    print(answer)

    print("\n=== SOURCES ===")
    seen = set()
    for c in chunks:
        key = (c["source"], c["page"])
        if key not in seen:
            seen.add(key)
            print(f"- {c['source']}, page {c['page']}")


if __name__ == "__main__":
    main()
