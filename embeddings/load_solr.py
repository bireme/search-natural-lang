import argparse
import json
import logging
import os
import time

import httpx
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# Configure logging (level may be overridden by --verbose)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Configuration ---

# MongoDB Embeddings Configuration (source of embeddings)
MONGODB_EMBEDDINGS_URI = os.getenv("MONGODB_EMBEDDINGS_URI", "mongodb://localhost:27017/")
MONGODB_EMBEDDINGS_DATABASE = os.getenv("MONGODB_EMBEDDINGS_DATABASE", "embeddings_db")
MONGODB_EMBEDDINGS_COLLECTION = os.getenv("MONGODB_EMBEDDINGS_COLLECTION", "vector_store")

# Solr Configuration
SOLR_EMBEDDINGS_URL = os.getenv("SOLR_EMBEDDINGS_URL", "http://localhost:8983")
SOLR_EMBEDDINGS_COLLECTION = os.getenv("SOLR_EMBEDDINGS_COLLECTION", "embeddings")

# Fields to copy from MongoDB documents to Solr documents
SOLR_FIELDS = ['record_id', 'ti', 'vector', 'vector_size', 'model']
SOLR_FIELD_ID = 'record_id'  # The field in MongoDB that will be used as the Solr document ID (if different from '_id')

# Batch size for Solr indexing (configurable via env)
BATCH_SIZE = int(os.getenv("SOLR_BATCH_SIZE", "100"))

# Progress reporting interval in seconds
PROGRESS_INTERVAL = 10


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Load embeddings from MongoDB into Solr.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=f"Number of documents per Solr batch (default: {BATCH_SIZE}, from SOLR_BATCH_SIZE env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build Solr documents but do not send them; log what would be sent",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete all documents from the Solr collection before loading",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N documents (useful for testing)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help='MongoDB query filter as JSON string, e.g. \'{"model": "nomic-embed-text"}\'',
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Resume from this MongoDB ObjectId (processes documents with _id > value)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser.parse_args()


def send_to_solr(client, docs):
    """
    Send a batch of documents to Solr's JSON update endpoint.

    Args:
        client: An httpx.Client instance
        docs: A list of document dicts to index

    Returns:
        The HTTP response status code
    """
    url = f"{SOLR_EMBEDDINGS_URL}/{SOLR_EMBEDDINGS_COLLECTION}/update/json/docs"
    response = client.post(
        url,
        json=docs,
        params={"commit": "false"},
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return response.status_code


def build_solr_document(doc):
    """
    Build a Solr document from a MongoDB document.

    Validates the vector field before including it.

    Args:
        doc: A MongoDB document

    Returns:
        A Solr document dict
    """
    solr_doc = {"id": str(doc.get(SOLR_FIELD_ID, doc["_id"]))}
    for field in SOLR_FIELDS:
        if field in doc:
            solr_doc[field] = doc[field]

    # Validate vector field
    vector = solr_doc.get("vector")
    vector_size = solr_doc.get("vector_size")
    if vector is not None:
        if not isinstance(vector, list) or len(vector) == 0:
            logger.warning(
                "Document %s has invalid vector (not a list or empty), dropping vector field",
                solr_doc["id"],
            )
            solr_doc.pop("vector", None)
        elif vector_size and len(vector) != vector_size:
            logger.warning(
                "Document %s vector length %d != declared vector_size %d",
                solr_doc["id"],
                len(vector),
                vector_size,
            )

    return solr_doc


def flush_batch(client, batch, processed_count, error_count, current_index, total_documents, dry_run=False):
    """
    Send a Solr batch and fall back to per-document retries on failure.

    Args:
        client: An httpx.Client instance
        batch: The list of Solr documents to send
        processed_count: Current successful document count
        error_count: Current failed document count
        current_index: Current document index in the stream
        total_documents: Total number of documents expected
        dry_run: If True, skip actual HTTP sends

    Returns:
        Tuple of updated (processed_count, error_count)
    """
    if not batch:
        return processed_count, error_count

    logger.info("[%s/%s] Sending batch of %s documents...", current_index, total_documents, len(batch))

    if dry_run:
        logger.info("[DRY RUN] Would send %s documents to Solr (skipped)", len(batch))
        return processed_count + len(batch), error_count

    try:
        send_to_solr(client, batch)
        return processed_count + len(batch), error_count
    except Exception as exc:
        logger.warning(
            "Batch send failed for %s documents; retrying individually: %s",
            len(batch),
            exc,
        )

    for solr_doc in batch:
        try:
            send_to_solr(client, [solr_doc])
            processed_count += 1
        except Exception as exc:
            error_count += 1
            logger.error("Error indexing Solr document %s: %s", solr_doc.get("id"), exc)

    return processed_count, error_count


def commit_solr(client):
    """
    Commit pending Solr changes.

    Args:
        client: An httpx.Client instance
    """
    commit_url = f"{SOLR_EMBEDDINGS_URL}/{SOLR_EMBEDDINGS_COLLECTION}/update"
    response = client.post(commit_url, json={"commit": {}})
    response.raise_for_status()


def clear_solr(client):
    """
    Delete all documents from the Solr collection.

    Args:
        client: An httpx.Client instance
    """
    logger.info("Clearing all documents from Solr collection '%s'...", SOLR_EMBEDDINGS_COLLECTION)
    delete_url = f"{SOLR_EMBEDDINGS_URL}/{SOLR_EMBEDDINGS_COLLECTION}/update"
    response = client.post(
        delete_url,
        json={"delete": {"query": "*:*"}},
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    commit_solr(client)
    logger.info("Solr collection cleared and committed")


def main():
    args = parse_args()

    # Override log level if --verbose
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Resolve batch size: CLI > env > default
    batch_size = args.batch_size if args.batch_size is not None else BATCH_SIZE

    # Build MongoDB query filter
    mongo_filter = {}
    if args.filter:
        try:
            mongo_filter = json.loads(args.filter)
        except json.JSONDecodeError as exc:
            logger.error("Invalid --filter JSON: %s", exc)
            return

    if args.since:
        try:
            since_oid = ObjectId(args.since)
            mongo_filter["_id"] = {"$gt": since_oid}
            logger.info("Resuming from documents after ObjectId: %s", args.since)
        except Exception as exc:
            logger.error("Invalid --since ObjectId '%s': %s", args.since, exc)
            return

    # 1. Log configuration
    logger.info("=" * 50)
    logger.info("Starting Solr loading process")
    logger.info("=" * 50)
    logger.info(f"MongoDB Source: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}")
    logger.info(f"Solr URL: {SOLR_EMBEDDINGS_URL}")
    logger.info(f"Solr Collection: {SOLR_EMBEDDINGS_COLLECTION}")
    logger.info(f"Solr Fields: {SOLR_FIELDS}")
    logger.info(f"Batch Size: {batch_size}")
    if args.dry_run:
        logger.info("*** DRY RUN MODE — no data will be sent to Solr ***")
    if args.limit:
        logger.info(f"Limit: {args.limit} documents")
    if mongo_filter:
        logger.info(f"MongoDB Filter: {mongo_filter}")

    # 2-8. Connect, stream documents, index batches, commit, and clean up
    logger.info(f"Connecting to MongoDB Embeddings at {MONGODB_EMBEDDINGS_URI}...")

    try:
        with MongoClient(MONGODB_EMBEDDINGS_URI) as mongo_client, httpx.Client(timeout=30.0) as http_client:
            try:
                mongo_db = mongo_client[MONGODB_EMBEDDINGS_DATABASE]
                mongo_collection = mongo_db[MONGODB_EMBEDDINGS_COLLECTION]
                mongo_client.admin.command("ping")
                logger.info(
                    f"Connected to MongoDB Embeddings: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}"
                )
            except Exception as exc:
                logger.error(f"Error connecting to MongoDB Embeddings: {exc}")
                return

            logger.info("Testing Solr connectivity...")
            try:
                ping_url = f"{SOLR_EMBEDDINGS_URL}/{SOLR_EMBEDDINGS_COLLECTION}/admin/ping"
                response = http_client.get(ping_url)
                response.raise_for_status()
                logger.info("Solr ping successful")
            except Exception as exc:
                logger.error(f"Error connecting to Solr: {exc}")
                return

            # Clear Solr if requested
            if args.clear:
                if args.dry_run:
                    logger.info("[DRY RUN] Would clear all documents from Solr (skipped)")
                else:
                    try:
                        clear_solr(http_client)
                    except Exception as exc:
                        logger.error(f"Error clearing Solr collection: {exc}")
                        return

            logger.info("Querying MongoDB Embeddings collection...")
            try:
                projection = {field: 1 for field in SOLR_FIELDS}
                total_documents = mongo_collection.count_documents(mongo_filter)
                if args.limit and args.limit < total_documents:
                    total_documents = args.limit
                cursor = mongo_collection.find(mongo_filter, projection=projection).batch_size(batch_size)
                if args.limit:
                    cursor = cursor.limit(args.limit)
                logger.info(f"Found {total_documents} documents to load into Solr")
            except Exception as exc:
                logger.error(f"Error querying MongoDB Embeddings: {exc}")
                return

            processed_count = 0
            error_count = 0
            batch = []
            last_doc_id = None
            logger.info("Starting Solr indexing...")
            process_start_time = time.time()
            last_progress_time = process_start_time
            last_index = 0

            try:
                for idx, doc in enumerate(cursor, 1):
                    last_index = idx
                    last_doc_id = doc.get("_id")
                    try:
                        batch.append(build_solr_document(doc))
                    except Exception as exc:
                        error_count += 1
                        logger.error(f"Error processing document {doc.get('_id')}: {exc}")
                        continue

                    if len(batch) >= batch_size:
                        processed_count, error_count = flush_batch(
                            http_client,
                            batch,
                            processed_count,
                            error_count,
                            idx,
                            total_documents,
                            dry_run=args.dry_run,
                        )
                        batch.clear()

                    # Periodic progress reporting
                    now = time.time()
                    if now - last_progress_time >= PROGRESS_INTERVAL:
                        elapsed = now - process_start_time
                        pct = (idx / total_documents) * 100 if total_documents > 0 else 0
                        rate = processed_count / elapsed if elapsed > 0 else 0
                        eta = (total_documents - idx) / rate if rate > 0 else 0
                        logger.info(
                            "Progress: %.1f%% (%s/%s) | %.1f docs/sec | ETA: %.0fs",
                            pct, idx, total_documents, rate, eta,
                        )
                        last_progress_time = now

                if batch:
                    processed_count, error_count = flush_batch(
                        http_client,
                        batch,
                        processed_count,
                        error_count,
                        last_index or len(batch),
                        total_documents,
                        dry_run=args.dry_run,
                    )

            finally:
                cursor.close()

            if not args.dry_run:
                logger.info("Committing changes to Solr...")
                try:
                    commit_solr(http_client)
                    logger.info("Solr commit successful")
                except Exception as exc:
                    logger.error(f"Error committing to Solr: {exc}")
            else:
                logger.info("[DRY RUN] Skipping Solr commit")

            total_process_time = time.time() - process_start_time
            docs_per_sec = processed_count / total_process_time if total_process_time > 0 else 0

            logger.info("=" * 50)
            logger.info("Processing complete!")
            logger.info("=" * 50)
            logger.info(f"Successfully processed: {processed_count} documents")
            logger.info(f"Errors: {error_count} documents")
            logger.info(f"Total process time: {total_process_time:.2f}s")
            logger.info(f"Throughput: {docs_per_sec:.1f} docs/sec")
            logger.info(f"Source: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}")
            logger.info(f"Target: {SOLR_EMBEDDINGS_URL}/{SOLR_EMBEDDINGS_COLLECTION}")
            if last_doc_id:
                logger.info(f"Last processed document ID: {last_doc_id}")
            if args.dry_run:
                logger.info("*** DRY RUN — no changes were made to Solr ***")
            logger.info("=" * 50)

    except Exception as exc:
        logger.error(f"Unexpected error during Solr loading: {exc}")
        return

    logger.info("Done.")


if __name__ == "__main__":
    main()
