import logging
import os
import time

import requests
from dotenv import load_dotenv
from pymongo import MongoClient
import json

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

# MongoDB Source Configuration (for reading documents)
MONGODB_SOURCE_URI = os.getenv("MONGODB_SOURCE_URI", "mongodb://localhost:27017/")
MONGODB_SOURCE_DATABASE = os.getenv("MONGODB_SOURCE_DATABASE", "embeddings_db")
MONGODB_SOURCE_COLLECTION = os.getenv("MONGODB_SOURCE_COLLECTION", "document_embeddings")
MONGODB_SOURCE_FILTER = {}

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

def generate_embedding(text):
    """
    Generate embedding vector for the given text using the embeddings API.

    Args:
        text: The text content to embed

    Returns:
        Tuple of (embedding vector, elapsed time in seconds)
    """
    # Use the Ollama API format for embeddings
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
    result = response.json()
    logger.debug(f"Received response: {result}")
    return result.get("embeddings", []), elapsed_time


def main():
    # 1. Log configuration
    logger.info("=" * 50)
    logger.info("Starting embedding generation process")
    logger.info("=" * 50)
    logger.info(f"Embedding Model: {EMBEDDINGS_MODEL}")
    logger.info(f"Embedding API URL: {EMBEDDINGS_API_URL}")
    logger.info(f"Expected Vector Size: {EMBEDDINGS_VECTOR_SIZE}")
    logger.info(f"Text Fields: {TEXT_IN_FIELDS}")
    logger.info(f"Output Field: {TEXT_OUT_FIELD}")

    # 2. Connect to MongoDB Source (for reading documents)
    logger.info(f"Connecting to MongoDB Source at {MONGODB_SOURCE_URI}...")
    try:
        source_client = MongoClient(MONGODB_SOURCE_URI)
        source_db = source_client[MONGODB_SOURCE_DATABASE]
        source_collection = source_db[MONGODB_SOURCE_COLLECTION]
        # Test connection
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
        embeddings_client = MongoClient(MONGODB_EMBEDDINGS_URI)
        embeddings_db = embeddings_client[MONGODB_EMBEDDINGS_DATABASE]
        embeddings_collection = embeddings_db[MONGODB_EMBEDDINGS_COLLECTION]
        # Test connection
        embeddings_client.admin.command("ping")
        logger.info(
            f"Connected to MongoDB Embeddings: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}"
        )
    except Exception as e:
        logger.error(f"Error connecting to MongoDB Embeddings: {e}")
        source_client.close()
        return

    # 4. Query MongoDB Source for documents
    logger.info(f"Querying MongoDB Source collection... Filter: {MONGODB_SOURCE_FILTER}")
    try:
        documents = list(source_collection.find(MONGODB_SOURCE_FILTER))
        logger.info(f"Found {len(documents)} documents to process")
    except Exception as e:
        logger.error(f"Error querying MongoDB Source: {e}")
        source_client.close()
        embeddings_client.close()
        return

    # 5. Loop through results and generate embeddings
    processed_count = 0
    error_count = 0
    total_embedding_time = 0.0
    total_documents = len(documents)

    logger.info("Starting embedding generation...")
    process_start_time = time.time()

    for idx, doc in enumerate(documents, 1):
        document_id = doc.get("_id")
        record_id = doc.get("id")

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
            logger.info(f"[{idx}/{total_documents}] Processing document {record_id}...")
            text_length = len(text_content)
            vector, embedding_time = generate_embedding(text_content)
            total_embedding_time += embedding_time

            logger.info(
                f"  Generated embedding in {embedding_time:.3f}s "
                f"(text length: {text_length} chars, vector size: {len(vector)})"
            )

            # Validate vector size
            if len(vector) != EMBEDDINGS_VECTOR_SIZE:
                logger.warning(
                    f"  Vector size {len(vector)} differs from expected {EMBEDDINGS_VECTOR_SIZE}"
                )

            # 6. Save the embedding to MongoDB Embeddings
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

            processed_count += 1
            logger.info(f"  Saved embedding for document {record_id}")

        except Exception as e:
            error_count += 1
            logger.error(f"  Error processing document {record_id}: {e}")

    # 7. Summary
    total_process_time = time.time() - process_start_time
    avg_embedding_time = total_embedding_time / processed_count if processed_count > 0 else 0

    logger.info("=" * 50)
    logger.info("Processing complete!")
    logger.info("=" * 50)
    logger.info(f"Successfully processed: {processed_count} documents")
    logger.info(f"Errors: {error_count} documents")
    logger.info(f"Total embedding time: {total_embedding_time:.2f}s")
    logger.info(f"Average embedding time: {avg_embedding_time:.3f}s per document")
    logger.info(f"Total process time: {total_process_time:.2f}s")
    logger.info(f"Source: {MONGODB_SOURCE_DATABASE}.{MONGODB_SOURCE_COLLECTION}")
    logger.info(f"Target: {MONGODB_EMBEDDINGS_DATABASE}.{MONGODB_EMBEDDINGS_COLLECTION}")
    logger.info("=" * 50)

    # Close MongoDB connections
    logger.info("Closing MongoDB connections...")
    source_client.close()
    embeddings_client.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
