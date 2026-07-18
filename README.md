# freelance-sa-guide

A minimal RAG pipeline over SARS guides for South African freelancers (provisional tax, turnover tax, and the ITR14 company return), built with pypdf, sentence-transformers, and Chroma.

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

## Status

**Week 2 complete:** corpus of 3 SARS guides, 15-question eval set, retrieval scoring script, dual-provider generation (Gemini + Groq) with automatic retry on Gemini and manual provider override via CLI flag.

## Attribution & disclaimer

The source documents indexed by this project (`GEN-PT-01-G01`, `IT-GEN-04-G01`, `TT-GEN-01-G01`) are external guides published by the **South African Revenue Service (SARS)** and remain the property of SARS. They are downloaded on demand from sars.gov.za by `setup_docs.py` rather than redistributed in this repository, and are used here strictly for educational and demonstration purposes under SARS's terms of use.

This project is not affiliated with, endorsed by, or produced by SARS. It is not a substitute for professional tax advice — for authoritative guidance, always refer to the original documents and other resources at [sars.gov.za](https://www.sars.gov.za/).
