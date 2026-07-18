"""
Downloads the three SARS guides this project indexes into ./docs.
Run this first, before rag_skeleton.py or main.py, on a fresh checkout.

Run: python setup_docs.py [--force]
"""

import argparse
import os
import sys

import requests

DOCS_DIR = "./docs"

# (filename, official SARS URL) — filenames match SARS's own naming exactly.
GUIDES = [
    (
        "GEN-PT-01-G01-Guide-for-Provisional-Tax-External-Guide.pdf",
        "https://www.sars.gov.za/wp-content/uploads/Ops/Guides/"
        "GEN-PT-01-G01-Guide-for-Provisional-Tax-External-Guide.pdf",
    ),
    (
        "IT-GEN-04-G01-How-to-complete-the-Income-Tax-Return-ITR14-for-Companies-External-Guide.pdf",
        "https://www.sars.gov.za/wp-content/uploads/"
        "IT-GEN-04-G01-How-to-complete-the-Income-Tax-Return-ITR14-for-Companies-External-Guide.pdf",
    ),
    (
        "TT-GEN-01-G01-Administration-of-Turnover-Tax-External-Guide.pdf",
        "https://www.sars.gov.za/wp-content/uploads/Ops/Guides/"
        "TT-GEN-01-G01-Administration-of-Turnover-Tax-External-Guide.pdf",
    ),
]

# A plain requests User-Agent gets blocked by SARS's WAF; a browser-like one doesn't.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def download(filename, url, force):
    path = os.path.join(DOCS_DIR, filename)
    if os.path.exists(path) and not force:
        print(f"skip (already present): {filename}", file=sys.stderr)
        return True

    print(f"downloading: {filename}", file=sys.stderr)
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    if not resp.content.startswith(b"%PDF"):
        print(
            f"  failed: response wasn't a PDF (got {resp.headers.get('content-type')}). "
            f"SARS may have moved the file — check {url} in a browser.",
            file=sys.stderr,
        )
        return False

    with open(path, "wb") as f:
        f.write(resp.content)
    print(f"  saved: {path} ({len(resp.content):,} bytes)", file=sys.stderr)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true", help="re-download even if the file already exists"
    )
    args = parser.parse_args()

    os.makedirs(DOCS_DIR, exist_ok=True)

    results = [download(filename, url, args.force) for filename, url in GUIDES]
    if not all(results):
        print("\nOne or more guides failed to download.", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll {len(GUIDES)} guides present in {DOCS_DIR}/.", file=sys.stderr)


if __name__ == "__main__":
    main()
