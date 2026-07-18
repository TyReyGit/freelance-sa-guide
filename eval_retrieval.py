"""
Retrieval-only eval: for each question in eval_questions.json, run retrieve()
(no LLM call) and check whether expected_source shows up anywhere in the
top-k hits. Prints a per-question pass/fail table plus a hit-rate summary.

Run: python eval_retrieval.py [--k 4] [--questions eval_questions.json]
"""

import argparse
import json
import sys

from rag_skeleton import retrieve

UNANSWERABLE = "none"


def load_questions(path):
    with open(path) as f:
        return json.load(f)


def evaluate(questions, k):
    rows = []
    for q in questions:
        expected = q["expected_source"]
        hits = retrieve(q["question"], k=k)
        retrieved_sources = [h["source"] for h in hits]

        if expected == UNANSWERABLE:
            status = "N/A"
        elif expected in retrieved_sources:
            status = "PASS"
        else:
            status = "FAIL"

        rows.append(
            {
                "question": q["question"],
                "expected": expected,
                "retrieved": retrieved_sources,
                "status": status,
            }
        )
    return rows


def truncate(text, width):
    return text if len(text) <= width else text[: width - 1] + "…"


def print_table(rows):
    q_width = 60
    src_width = 46
    header = f"{'#':<3} {'STATUS':<6} {'QUESTION':<{q_width}} {'EXPECTED SOURCE':<{src_width}}"
    print(header)
    print("-" * len(header))
    for i, row in enumerate(rows, start=1):
        q = truncate(row["question"], q_width)
        expected = row["expected"] if row["expected"] != UNANSWERABLE else "(unanswerable)"
        expected = truncate(expected, src_width)
        print(f"{i:<3} {row['status']:<6} {q:<{q_width}} {expected:<{src_width}}")
        if row["status"] == "FAIL":
            for src in dict.fromkeys(row["retrieved"]):
                print(f"    {'':<6} retrieved: {src}")


def print_summary(rows):
    scored = [r for r in rows if r["status"] != "N/A"]
    passed = [r for r in scored if r["status"] == "PASS"]
    skipped = [r for r in rows if r["status"] == "N/A"]

    print()
    print(f"Hit rate: {len(passed)}/{len(scored)} correct "
          f"({len(scored)} answerable questions scored)")
    if skipped:
        print(f"({len(skipped)} unanswerable question(s) excluded from hit-rate "
              f"— expected_source is 'none', so source-match isn't meaningful)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="eval_questions.json")
    parser.add_argument("--k", type=int, default=4, help="top-k results from retrieve()")
    args = parser.parse_args()

    questions = load_questions(args.questions)
    rows = evaluate(questions, k=args.k)

    print_table(rows)
    print_summary(rows)

    scored = [r for r in rows if r["status"] != "N/A"]
    if any(r["status"] == "FAIL" for r in scored):
        sys.exit(1)


if __name__ == "__main__":
    main()
