import logging
import os
import time

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# Configure logging
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

# Batch size for Solr indexing
BATCH_SIZE = 100


def send_to_solr(client, docs):
    """
    Send a batch of documents to Solr's JSON update endpoint.

    Args:
        client: An httpx.Client instance
        docs: A list of document dicts to index

    Returns:
        The HTTP response status code
    """
    url = f"{SOLR_EMBEDDINGS_URL}/solr/{SOLR_EMBEDDINGS_COLLECTION}/update/json/docs"
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

    Args:
        doc: A MongoDB document

    Returns:
        A Solr document dict
    """
    solr_doc = {"id": str(doc["_id"])}
    for field in SOLR_FIELDS:
        if field in doc:
            solr_doc[field] = doc[field]
    return solr_doc


def flush_batch(client, batch, processed_count, error_count, current_index, total_documents):
    """
    Send a Solr batch and fall back to per-document retries on failure.

    Args:
        client: An httpx.Client instance
        batch: The list of Solr documents to send
        processed_count: Current successful document count
        error_count: Current failed document count
        current_index: Current document index in the stream
        total_documents: Total number of documents expected

    Returns:
        Tuple of updated (processed_count, error_count)
    """
    if not batch:
        return processed_count, error_count

    logger.info("[%s/%s] Sending batch of %s documents...", current_index, total_documents, len(batch))

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
    commit_url = f"{SOLR_EMBEDDINGS_URL}/solr/{SOLR_EMBEDDINGS_COLLECTION}/update"
    response = client.post(commit_url, json={"commit": {}})
    response.raise_for_status()


def main():
    # 1. Log configuration
    logger.info("=" * 50)
    logger.info("Starting Solr loading process")
    logger.info("=" * 50)
    logger.info(f"MongoDB Source: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}")
    logger.info(f"Solr URL: {SOLR_EMBEDDINGS_URL}")
    logger.info(f"Solr Collection: {SOLR_EMBEDDINGS_COLLECTION}")
    logger.info(f"Solr Fields: {SOLR_FIELDS}")
    logger.info(f"Batch Size: {BATCH_SIZE}")

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
                ping_url = f"{SOLR_EMBEDDINGS_URL}/solr/{SOLR_EMBEDDINGS_COLLECTION}/admin/ping"
                response = http_client.get(ping_url)
                response.raise_for_status()
                logger.info("Solr ping successful")
            except Exception as exc:
                logger.error(f"Error connecting to Solr: {exc}")
                return

            logger.info("Querying MongoDB Embeddings collection...")
            try:
                projection = {field: 1 for field in SOLR_FIELDS}
                total_documents = mongo_collection.count_documents({})
                cursor = mongo_collection.find({}, projection=projection).batch_size(BATCH_SIZE)
                logger.info(f"Found {total_documents} documents to load into Solr")
            except Exception as exc:
                logger.error(f"Error querying MongoDB Embeddings: {exc}")
                return

            processed_count = 0
            error_count = 0
            batch = []
            logger.info("Starting Solr indexing...")
            process_start_time = time.time()
            last_index = 0

            try:
                for idx, doc in enumerate(cursor, 1):
                    last_index = idx
                    try:
                        batch.append(build_solr_document(doc))
                    except Exception as exc:
                        error_count += 1
                        logger.error(f"Error processing document {doc.get('_id')}: {exc}")
                        continue

                    if len(batch) >= BATCH_SIZE:
                        processed_count, error_count = flush_batch(
                            http_client,
                            batch,
                            processed_count,
                            error_count,
                            idx,
                            total_documents,
                        )
                        batch.clear()

                if batch:
                    processed_count, error_count = flush_batch(
                        http_client,
                        batch,
                        processed_count,
                        error_count,
                        last_index or len(batch),
                        total_documents,
                    )

            finally:
                cursor.close()

            logger.info("Committing changes to Solr...")
            try:
                commit_solr(http_client)
                logger.info("Solr commit successful")
            except Exception as exc:
                logger.error(f"Error committing to Solr: {exc}")

            total_process_time = time.time() - process_start_time

            logger.info("=" * 50)
            logger.info("Processing complete!")
            logger.info("=" * 50)
            logger.info(f"Successfully processed: {processed_count} documents")
            logger.info(f"Errors: {error_count} documents")
            logger.info(f"Total process time: {total_process_time:.2f}s")
            logger.info(f"Source: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}")
            logger.info(f"Target: {SOLR_EMBEDDINGS_URL}/solr/{SOLR_EMBEDDINGS_COLLECTION}")
            logger.info("=" * 50)

    except Exception as exc:
        logger.error(f"Unexpected error during Solr loading: {exc}")
        return

    logger.info("Done.")


if __name__ == "__main__":
    main()
