"""
Rebuilds chroma_db/ from scratch: downloads the source PDFs (if missing) and
re-embeds every chunk via the Gemini embedding API. This is the path
main.py's startup event used to run on every cold start, which burned
through the free-tier daily quota — it now only runs when you call it here
by hand, after source docs actually change.

Run: python rebuild_index.py [--publish]

--publish uploads the resulting chroma_db/ as a new GitHub Release asset
(via `gh release create`) so download_index.py picks it up on the next
deploy. Requires the gh CLI to be authenticated.
"""

import argparse
import logging
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

import rag_skeleton
import setup_docs

logger = logging.getLogger(__name__)

REPO = "TyReyGit/freelance-sa-guide"
ASSET_NAME = "chroma_db.tar.gz"


def rebuild() -> None:
    logger.info("Downloading source PDFs (skips any already present)...")
    setup_docs.download_all()

    logger.info("Wiping existing chroma_db/ so indexing starts clean...")
    shutil.rmtree(rag_skeleton.CHROMA_DIR, ignore_errors=True)

    collection = rag_skeleton.get_collection()
    rag_skeleton.index_if_needed(collection)
    logger.info("Rebuilt index: %d chunks.", collection.count())


def publish() -> None:
    tag = f"chroma-index-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    archive_path = f"/tmp/{ASSET_NAME}"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(rag_skeleton.CHROMA_DIR, arcname="chroma_db")

    logger.info("Publishing %s as GitHub Release %s...", archive_path, tag)
    subprocess.run(
        [
            "gh", "release", "create", tag, archive_path,
            "-R", REPO,
            "--title", f"Chroma index {tag}",
            "--notes", "Rebuilt via rebuild_index.py.",
        ],
        check=True,
    )
    logger.info("Published. download_index.py's 'latest' URL now serves this index.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish", action="store_true",
        help="upload the rebuilt index as a new GitHub Release asset",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    rebuild()
    if args.publish:
        publish()


if __name__ == "__main__":
    main()
