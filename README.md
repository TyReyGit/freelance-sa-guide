# freelance-sa-guide

A minimal RAG pipeline over SARS guides for South African freelancers (provisional tax, turnover tax, and the ITR14 company return), built with pypdf, Chroma (ONNX MiniLM embeddings), and Gemini/Groq.

## Setup

Run this first, before anything else — it downloads the three source PDFs from sars.gov.za into `./docs` (they aren't checked into git):

```bash
python setup_docs.py
```

## Evaluation

Retrieval quality is tracked with `eval_retrieval.py`, which runs `retrieve()` for each question in `eval_questions.json` and checks whether the expected source document appears in the top-k hits (no LLM call — retrieval only).

**2026-07-16 baseline:**

- 15 questions built: 12 answerable (drawn from the three source PDFs) + 3 deliberately unanswerable (topics not covered by any of the docs, e.g. VAT registration, home office deductions, UIF/COIDA registration)
- Config: `k=4`, chunk size 500 tokens, overlap 50 tokens
- Result: **12/12 hit rate** on the answerable questions

Unanswerable questions (`expected_source: "none"`) are excluded from hit-rate scoring, since there's no expected source to match against — they're included in the question set to check that the pipeline doesn't fabricate an answer when the topic isn't in the documents, not to score retrieval accuracy.

Retrieval was retested at `k=2` with no degradation (still 12/12). `k=4` is kept as the default anyway, for safety margin on messier real-world questions than the eval set covers.

Run it with:

```bash
python eval_retrieval.py --k 4
```

## Lessons Learned

Getting embeddings to work reliably on Render's 512MB free-tier web service took five iterations:

1. **`sentence-transformers` OOM'd on boot.** The initial pipeline (`sentence-transformers==5.6.0` + `torch==2.13.0+cpu`, pulling wheels from `--extra-index-url https://download.pytorch.org/whl/cpu`) died before it ever reached `/health` — torch alone doesn't fit in 512MB alongside the rest of the process.
2. **Switching to Chroma's built-in ONNX embedding function (`ONNXMiniLM_L6_V2`) also OOM'd.** This dropped the torch dependency entirely, but the ONNX model load itself still pushed the process over the memory ceiling on boot — a smaller runtime wasn't small enough.
3. **Switching to Google's hosted embedding API (`gemini-embedding-001` via `GoogleGenaiEmbeddingFunction`) fixed the memory problem** but moved the bottleneck to the free-tier daily embedding quota. Indexing all 488 chunks (from 234 PDF pages across the three source guides) tripped 429s partway through, which meant retrying with backoff — `INDEX_BATCH_SIZE=10`, a 10s sleep between batches, and up to 5 retries per batch starting at a 15s wait and doubling (`"Rate limited, retrying in {wait}s..."`). That throttling pushed a from-scratch cold-start index build to roughly 10 minutes, which put it uncomfortably close to Render's deploy timeout for binding the port.
4. **Moving indexing to a background thread fixed the timeout, not the quota.** `main.py`'s `startup_event` kicks off `_build_index()` on a daemon thread so `uvicorn` binds its port immediately instead of blocking on indexing; `/ask` returns `503` with `"Index is still building, try again in a few minutes"` until `_index_status` flips to `"ready"`. That solved the port-binding timeout, but Render's free tier has no persistent disk — `chroma_db/` is empty on every single cold start, so every restart re-indexed from scratch and re-burned that same daily quota.
5. **Final fix: ship a pre-built index instead of rebuilding it on every boot.** `rebuild_index.py` now does the (quota-consuming) embedding work by hand, offline, and `--publish`es the resulting `chroma_db/` as a `chroma_db.tar.gz` GitHub Release asset. `download_index.py` pulls and extracts that tarball on startup — zero embedding calls at boot. Query-time embedding was then switched back to the local ONNX model (`ONNXMiniLM_L6_V2`, used for both indexing and querying so both sides stay in the same vector space), which removed the Google API daily-quota dependency entirely rather than just working around it.

`eval_retrieval.py` was re-run after every one of these changes and held at a steady **12/12 hit rate** throughout — proof that none of the memory/quota fixes silently degraded retrieval, and the reason building that eval harness in Week 2 paid for itself repeatedly instead of just being a one-off sanity check.

**Separately: a Gemini reasoning-model refusal bug.** Gemini would occasionally answer `"not in the documents"` even when the retrieved context clearly contained the relevant passage. Running the same question with `--debug` (which prints the full prompt and raw API response to stderr) showed the correct context was in fact being sent — and re-running the identical prompt against Groq (`llama-3.3-70b-versatile`) got a correct, grounded answer from the exact same context, confirming the issue was Gemini being overly conservative about the refusal instruction rather than a retrieval problem. The fix was softening `_build_prompt()`'s wording in `rag_skeleton.py` from an unconditional "if in doubt, refuse" framing to the current instruction: *"If the context contains relevant information that answers the question, use it and cite your sources. Only reply exactly 'not in the documents' if the context has no relevant information at all."*

## Known Limitations

Retrieval quality depends on how closely a question's phrasing overlaps with the source text — this is a plain nearest-neighbor lookup over 500-token chunks (`k=4`, 50-token overlap), with no query rewriting or hybrid keyword/vector search. Vague or compound questions can occasionally miss relevant context even when it exists in the corpus. For example, "I just started freelancing, do I need to do anything about tax right away?" missed a passage that was actually relevant, because the question doesn't share enough vocabulary with the source text's phrasing (which discusses "provisional taxpayer" registration and payment periods, not "do anything right away") to score highly against it in embedding space.

This wasn't caught by `eval_retrieval.py` — the eval set's questions were phrased with enough of the source guides' own terminology to score well, so the 12/12 hit rate doesn't fully capture this failure mode. Worth treating as a real gap, not something the eval hides: the natural next steps are hybrid search (combine vector similarity with keyword/BM25 matching so exact-term overlap isn't required) and query rewriting (expand or reformulate a vague user question into terms closer to the source vocabulary before retrieving).

## Attribution & disclaimer

The source documents indexed by this project (`GEN-PT-01-G01`, `IT-GEN-04-G01`, `TT-GEN-01-G01`) are external guides published by the **South African Revenue Service (SARS)** and remain the property of SARS. They are downloaded on demand from sars.gov.za by `setup_docs.py` rather than redistributed in this repository, and are used here strictly for educational and demonstration purposes under SARS's terms of use.

This project is not affiliated with, endorsed by, or produced by SARS. It is not a substitute for professional tax advice — for authoritative guidance, always refer to the original documents and other resources at [sars.gov.za](https://www.sars.gov.za/).
