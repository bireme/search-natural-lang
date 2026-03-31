import argparse
import json
import logging
import os
import time

import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import CursorNotFound

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

# MongoDB Source Configuration (for reading documents)
MONGODB_SOURCE_URI = os.getenv("MONGODB_SOURCE_URI", "mongodb://localhost:27017/")
MONGODB_SOURCE_DATABASE = os.getenv("MONGODB_SOURCE_DATABASE", "embeddings_db")
MONGODB_SOURCE_COLLECTION = os.getenv("MONGODB_SOURCE_COLLECTION", "document_embeddings")

# MongoDB Embeddings Configuration (for saving embeddings)
MONGODB_EMBEDDINGS_URI = os.getenv("MONGODB_EMBEDDINGS_URI", "mongodb://localhost:27017/")
MONGODB_EMBEDDINGS_DATABASE = os.getenv("MONGODB_EMBEDDINGS_DATABASE", "embeddings_db")
MONGODB_EMBEDDINGS_COLLECTION = os.getenv("MONGODB_EMBEDDINGS_COLLECTION", "vector_store")

# Embedding Model Configuration
EMBEDDINGS_API_URL = os.getenv("EMBEDDINGS_API_URL", "http://localhost:11434/api/embed")
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "nomic-embed-text")
EMBEDDINGS_VECTOR_SIZE = int(os.getenv("EMBEDDINGS_VECTOR_SIZE", "768"))

# Text fields to generate embeddings from (will be combined)
TEXT_IN_FIELDS = ['ti', 'ti_pt', 'ti_es', 'ti_en']

# Text field to store in the embeddings collection (for reference)
TEXT_OUT_FIELD = 'ti'

# Progress reporting interval in seconds
PROGRESS_INTERVAL = 10

# Default progress file path
PROGRESS_FILE = ".embeddings_progress.json"


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate embeddings from MongoDB documents and store them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate embeddings but do not save them to MongoDB",
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
        "--max-retries",
        type=int,
        default=10,
        help="Max cursor re-creation attempts on CursorNotFound errors (default: 10)",
    )
    parser.add_argument(
        "--save-progress",
        action="store_true",
        help="Periodically save last processed document ID to a progress file",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from saved progress file (overrides --since)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser.parse_args()


def generate_embedding(text):
    """
    Generate embedding vector for the given text using the embeddings API.

    Args:
        text: The text content to embed

    Returns:
        Tuple of (embedding vector, elapsed time in seconds)
    """
    api_url = EMBEDDINGS_API_URL

    payload = {
        "model": EMBEDDINGS_MODEL,
        "input": text
    }
    logger.debug(f"Requesting embedding for text of length {len(text)} characters")
    logger.debug(f"Payload: {payload}")
    logger.debug(f"API URL: {api_url}")
    logger.debug(f"MODEL: {EMBEDDINGS_MODEL}")

    start_time = time.time()
    response = requests.post(api_url, json=payload)
    response.raise_for_status()
    elapsed_time = time.time() - start_time
    result = response.json()
    logger.debug(f"Received response: {result}")

    # Extract the embeddings array - the API returns a list of embeddings
    embeddings_list = result.get("embeddings", [])

    # Get the first embedding vector (for single text input)
    embedding_vector = embeddings_list[0] if embeddings_list else []

    return embedding_vector, elapsed_time


def _save_progress(last_doc_id, processed_count, current_idx, total_documents):
    """Save current processing progress to a JSON file."""
    progress_data = {
        "last_doc_id": str(last_doc_id),
        "processed_count": processed_count,
        "current_idx": current_idx,
        "total_documents": total_documents,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress_data, f, indent=2)
        logger.debug("Progress saved: %s", progress_data)
    except Exception as exc:
        logger.warning("Failed to save progress file: %s", exc)


def main():
    args = parse_args()

    # Override log level if --verbose
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Build MongoDB query filter
    mongo_filter = {}
    if args.filter:
        try:
            mongo_filter = json.loads(args.filter)
        except json.JSONDecodeError as exc:
            logger.error("Invalid --filter JSON: %s", exc)
            return

    if args.resume:
        try:
            with open(PROGRESS_FILE) as f:
                progress_data = json.load(f)
            since_oid = ObjectId(progress_data["last_doc_id"])
            mongo_filter["_id"] = {"$gt": since_oid}
            logger.info("Resuming from progress file, after ObjectId: %s", progress_data["last_doc_id"])
        except FileNotFoundError:
            logger.warning("Progress file %s not found, starting from the beginning", PROGRESS_FILE)
        except Exception as exc:
            logger.error("Error reading progress file: %s", exc)
            return
    elif args.since:
        try:
            since_oid = ObjectId(args.since)
            mongo_filter["_id"] = {"$gt": since_oid}
            logger.info("Resuming from documents after ObjectId: %s", args.since)
        except Exception as exc:
            logger.error("Invalid --since ObjectId '%s': %s", args.since, exc)
            return

    # 1. Log configuration
    logger.info("=" * 50)
    logger.info("Starting embedding generation process")
    logger.info("=" * 50)
    logger.info(f"Embedding Model: {EMBEDDINGS_MODEL}")
    logger.info(f"Embedding API URL: {EMBEDDINGS_API_URL}")
    logger.info(f"Expected Vector Size: {EMBEDDINGS_VECTOR_SIZE}")
    logger.info(f"Text Fields: {TEXT_IN_FIELDS}")
    logger.info(f"Output Field: {TEXT_OUT_FIELD}")
    if args.dry_run:
        logger.info("*** DRY RUN MODE — embeddings will not be saved ***")
    if args.limit:
        logger.info(f"Limit: {args.limit} documents")
    if mongo_filter:
        logger.info(f"MongoDB Filter: {mongo_filter}")

    try:
        with MongoClient(MONGODB_SOURCE_URI) as source_client, \
             MongoClient(MONGODB_EMBEDDINGS_URI) as embeddings_client:

            # 2. Connect to MongoDB Source (for reading documents)
            logger.info(f"Connecting to MongoDB Source at {MONGODB_SOURCE_URI}...")
            try:
                source_db = source_client[MONGODB_SOURCE_DATABASE]
                source_collection = source_db[MONGODB_SOURCE_COLLECTION]
                source_client.admin.command("ping")
                logger.info(
                    f"Connected to MongoDB Source: {MONGODB_SOURCE_DATABASE}.{MONGODB_SOURCE_COLLECTION}"
                )
            except Exception as e:
                logger.error(f"Error connecting to MongoDB Source: {e}")
                return

            # 3. Connect to MongoDB Embeddings (for saving embeddings)
            logger.info(f"Connecting to MongoDB Embeddings at {MONGODB_EMBEDDINGS_URI}...")
            try:
                embeddings_db = embeddings_client[MONGODB_EMBEDDINGS_DATABASE]
                embeddings_collection = embeddings_db[MONGODB_EMBEDDINGS_COLLECTION]
                embeddings_client.admin.command("ping")
                logger.info(
                    f"Connected to MongoDB Embeddings: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}"
                )
            except Exception as e:
                logger.error(f"Error connecting to MongoDB Embeddings: {e}")
                return

            # 4. Query MongoDB Source for documents
            logger.info("Querying MongoDB Source collection...")
            try:
                total_documents = source_collection.count_documents(mongo_filter)
                if args.limit and args.limit < total_documents:
                    total_documents = args.limit
                logger.info(f"Found {total_documents} documents to process")
            except Exception as e:
                logger.error(f"Error querying MongoDB Source: {e}")
                return

            # 5. Loop through results and generate embeddings
            processed_count = 0
            error_count = 0
            total_embedding_time = 0.0
            last_doc_id = None
            retry_count = 0
            idx = 0

            logger.info("Starting embedding generation...")
            process_start_time = time.time()
            last_progress_time = process_start_time

            while retry_count <= args.max_retries:
                # Build query — resume from last_doc_id if retrying after CursorNotFound
                query = dict(mongo_filter)
                if last_doc_id is not None:
                    query["_id"] = {"$gt": last_doc_id}

                remaining = (args.limit - idx) if args.limit else 0
                cursor = source_collection.find(query).sort("_id", 1).batch_size(500)
                if args.limit:
                    cursor = cursor.limit(remaining)

                try:
                    for doc in cursor:
                        idx += 1
                        document_id = doc.get("_id")
                        record_id = doc.get("id")
                        last_doc_id = document_id

                        # Collect text from all specified fields
                        text_parts = []
                        for field in TEXT_IN_FIELDS:
                            field_content = doc.get(field)
                            if field_content:
                                # Handle case where field_content might be a list
                                if isinstance(field_content, list):
                                    field_text = " ".join(str(item) for item in field_content if item)
                                else:
                                    field_text = str(field_content)
                                if field_text:
                                    text_parts.append(field_text)

                        # Combine all text parts
                        text_content = " ".join(text_parts)

                        if not text_content:
                            logger.warning(
                                f"Document {record_id} has no content in any of the fields {TEXT_IN_FIELDS}, skipping"
                            )
                            continue

                        try:
                            # Generate embedding for this document
                            logger.debug(f"[{idx}/{total_documents}] Processing document {record_id}...")
                            text_length = len(text_content)
                            vector, embedding_time = generate_embedding(text_content)
                            total_embedding_time += embedding_time

                            logger.debug(
                                f"  Generated embedding in {embedding_time:.3f}s "
                                f"(text length: {text_length} chars, vector size: {len(vector)})"
                            )

                            # Validate vector size
                            if len(vector) != EMBEDDINGS_VECTOR_SIZE:
                                logger.warning(
                                    f"  Vector size {len(vector)} differs from expected {EMBEDDINGS_VECTOR_SIZE}"
                                )

                            # 6. Save the embedding to MongoDB Embeddings
                            if args.dry_run:
                                logger.debug(f"[DRY RUN] Would save embedding for document {record_id} (skipped)")
                            else:
                                embedding_doc = {
                                    "document_id": document_id,
                                    "record_id": str(record_id),
                                    TEXT_OUT_FIELD: text_content,
                                    "vector": vector,
                                    "vector_size": len(vector),
                                    "model": EMBEDDINGS_MODEL,
                                }

                                # Use upsert to update if exists or insert if new
                                embeddings_collection.update_one(
                                    {"document_id": document_id}, {"$set": embedding_doc}, upsert=True
                                )
                                logger.debug(f"  Saved embedding for document {record_id}")

                            processed_count += 1

                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error processing document {record_id}: {e}")

                        # Periodic progress reporting and save progress
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

                            # Save progress to file
                            if args.save_progress and last_doc_id is not None:
                                _save_progress(last_doc_id, processed_count, idx, total_documents)

                    # Completed successfully — exit retry loop
                    break

                except CursorNotFound:
                    retry_count += 1
                    if retry_count > args.max_retries:
                        logger.error(
                            "Max retries (%d) exceeded after CursorNotFound. "
                            "Last processed document ID: %s. "
                            "Use --since %s to resume manually.",
                            args.max_retries, last_doc_id, last_doc_id,
                        )
                        break
                    logger.warning(
                        "CursorNotFound — re-creating cursor from document %s (retry %d/%d)",
                        last_doc_id, retry_count, args.max_retries,
                    )
                    # Save progress before retrying
                    if args.save_progress and last_doc_id is not None:
                        _save_progress(last_doc_id, processed_count, idx, total_documents)

                finally:
                    cursor.close()

            # Final progress save
            if args.save_progress and last_doc_id is not None:
                _save_progress(last_doc_id, processed_count, idx, total_documents)

            # 7. Summary
            total_process_time = time.time() - process_start_time
            avg_embedding_time = total_embedding_time / processed_count if processed_count > 0 else 0
            docs_per_sec = processed_count / total_process_time if total_process_time > 0 else 0

            logger.info("=" * 50)
            logger.info("Processing complete!")
            logger.info("=" * 50)
            logger.info(f"Successfully processed: {processed_count} documents")
            logger.info(f"Errors: {error_count} documents")
            logger.info(f"Total embedding time: {total_embedding_time:.2f}s")
            logger.info(f"Average embedding time: {avg_embedding_time:.3f}s per document")
            logger.info(f"Total process time: {total_process_time:.2f}s")
            logger.info(f"Throughput: {docs_per_sec:.1f} docs/sec")
            logger.info(f"Source: {MONGODB_SOURCE_DATABASE}.{MONGODB_SOURCE_COLLECTION}")
            logger.info(f"Target: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}")
            if last_doc_id:
                logger.info(f"Last processed document ID: {last_doc_id}")
            if args.dry_run:
                logger.info("*** DRY RUN — no changes were made ***")
            logger.info("=" * 50)

    except Exception as exc:
        logger.error(f"Unexpected error during embedding generation: {exc}")
        return

    logger.info("Done.")


if __name__ == "__main__":
    main()
