"""
Downloads the pre-built chroma_db/ index from this repo's latest GitHub
Release asset, avoiding the embedding API calls a from-scratch rebuild
would need. Used by main.py's startup event on a fresh checkout/cold start.

Run standalone: python download_index.py

For rebuilding the index itself (source docs changed), see rebuild_index.py.
"""

import io
import logging
import os
import sys
import tarfile

import requests

import rag_skeleton

logger = logging.getLogger(__name__)

RELEASE_ASSET_URL = (
    "https://github.com/TyReyGit/freelance-sa-guide/releases/latest/download/chroma_db.tar.gz"
)


def download_and_extract(url: str = RELEASE_ASSET_URL, dest: str = rag_skeleton.CHROMA_DIR) -> None:
    """Fetch the release tarball and extract it in place of dest.

    The tarball's top-level entry is "chroma_db/", so extracting into dest's
    parent directory reproduces dest/ directly.
    """
    logger.info("Downloading pre-built index from %s", url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()

    parent = os.path.dirname(os.path.abspath(dest)) or "."
    with tarfile.open(fileobj=io.BytesIO(resp.content)) as tar:
        tar.extractall(parent, filter="data")
    logger.info("Extracted index into %s", dest)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    download_and_extract()
