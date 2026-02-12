import pysolr
from langchain_ollama import OllamaEmbeddings

# --- Configuration ---
SOLR_URL = 'http://localhost:8983/solr/my_core'
OLLAMA_MODEL = "nomic-embed-text"
QUERY = "*:*"  # Query to fetch documents (change as needed)
ROWS = 1000    # Number of documents to fetch per batch
TEXT_FIELD = "text_t"  # Field to generate embeddings from

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
    print(f"Loading Ollama model: {OLLAMA_MODEL}...")
    embeddings = OllamaEmbeddings(model=OLLAMA_MODEL)

    # 2. Connect to Solr
    print(f"Connecting to Solr at {SOLR_URL}...")
    solr = pysolr.Solr(SOLR_URL, always_commit=True)

    # 3. Query Solr for documents
    print(f"Querying Solr with: '{QUERY}'...")
    try:
        results = solr.search(QUERY, rows=ROWS)
        print(f"Found {len(results)} documents to process.")
    except Exception as e:
        print(f"Error querying Solr: {e}")
        return

    # 4. Loop through results and generate embeddings
    processed_count = 0
    error_count = 0

    for doc in results:
        doc_id = doc.get('id')
        text_content = doc.get(TEXT_FIELD)

        if not text_content:
            print(f"Warning: Document {doc_id} has no '{TEXT_FIELD}' field, skipping...")
            continue

        try:
            # Generate embedding for this document
            print(f"Processing document {doc_id}...")
            vector = generate_embedding(text_content, embeddings)

            # 5. Update the document in Solr with the embedding
            update_doc = {
                "id": doc_id,
                "vector_embedding": {"set": vector}  # Atomic update syntax
            }

            solr.add([update_doc])
            processed_count += 1
            print(f"  ✓ Updated document {doc_id} with embedding vector")

        except Exception as e:
            error_count += 1
            print(f"  ✗ Error processing document {doc_id}: {e}")

    # 6. Summary
    print(f"\n{'='*50}")
    print(f"Processing complete!")
    print(f"Successfully processed: {processed_count} documents")
    print(f"Errors: {error_count} documents")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()