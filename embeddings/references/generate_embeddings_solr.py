import os

import pysolr
from langchain_ollama import OllamaEmbeddings
from pymongo import MongoClient

# --- Configuration ---
SOLR_URL = os.getenv("SOLR_URL", "http://localhost:8983/solr/my_core")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
QUERY = "*:*"  # Query to fetch documents (change as needed)
ROWS = 1000  # Number of documents to fetch per batch
TEXT_FIELD = os.getenv("TEXT_FIELD", "ti")  # Field to generate embeddings from

# MongoDB Configuration from environment variables
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "embeddings_db")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "document_embeddings")


def generate_embedding(text, embeddings):
    """
    Generate embedding vector for the given text.

    Args:
        text: The text content to embed
        embeddings: OllamaEmbeddings instance

    Returns:
        List of floats representing the embedding vector
    """
    return embeddings.embed_query(text)


def main():
    # 1. Initialize LangChain Embedding Model
    print(f"Loading Ollama model: {EMBEDDING_MODEL}...")
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

    # 2. Connect to Solr (for reading documents)
    print(f"Connecting to Solr at {SOLR_URL}...")
    solr = pysolr.Solr(SOLR_URL, always_commit=True)

    # 3. Connect to MongoDB (for saving embeddings)
    print(f"Connecting to MongoDB at {MONGODB_URI}...")
    try:
        mongo_client = MongoClient(MONGODB_URI)
        db = mongo_client[MONGODB_DATABASE]
        collection = db[MONGODB_COLLECTION]
        # Test connection
        mongo_client.admin.command("ping")
        print(
            f"✓ Connected to MongoDB database: {MONGODB_DATABASE}, collection: {MONGODB_COLLECTION}"
        )
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return

    # 4. Query Solr for documents
    print(f"Querying Solr with: '{QUERY}'...")
    try:
        results = solr.search(QUERY, rows=ROWS)
        print(f"Found {len(results)} documents to process.")
    except Exception as e:
        print(f"Error querying Solr: {e}")
        return

    # 5. Loop through results and generate embeddings
    processed_count = 0
    error_count = 0

    for doc in results:
        doc_id = doc.get("id")
        text_content = doc.get(TEXT_FIELD)

        if not text_content:
            print(
                f"Warning: Document {doc_id} has no '{TEXT_FIELD}' field, skipping..."
            )
            continue

        try:
            # Generate embedding for this document
            print(f"Processing document {doc_id}...")
            vector = generate_embedding(text_content, embeddings)

            # 6. Save the embedding to MongoDB
            embedding_doc = {
                "document_id": doc_id,
                "text_content": text_content,
                "vector_embedding": vector,
                "source": "solr",
                "model": EMBEDDING_MODEL,
            }

            # Use upsert to update if exists or insert if new
            collection.update_one(
                {"document_id": doc_id}, {"$set": embedding_doc}, upsert=True
            )

            processed_count += 1
            print(f"  ✓ Saved embedding for document {doc_id} to MongoDB")

        except Exception as e:
            error_count += 1
            print(f"  ✗ Error processing document {doc_id}: {e}")

    # 7. Summary
    print(f"\n{'=' * 50}")
    print("Processing complete!")
    print(f"Successfully processed: {processed_count} documents")
    print(f"Errors: {error_count} documents")
    print(f"MongoDB Collection: {MONGODB_DATABASE}.{MONGODB_COLLECTION}")
    print(f"{'=' * 50}")

    # Close MongoDB connection
    mongo_client.close()


if __name__ == "__main__":
    main()
