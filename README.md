# freelance-sa-guide

A minimal RAG pipeline over SARS guides for South African freelancers (provisional tax, turnover tax, and the ITR14 company return), built with pypdf, sentence-transformers, and Chroma.

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
