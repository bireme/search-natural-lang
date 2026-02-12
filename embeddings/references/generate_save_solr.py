import pysolr
from langchain_ollama import OllamaEmbeddings

# --- Configuration ---
SOLR_URL = 'http://localhost:8983/solr/my_core'
OLLAMA_MODEL = "nomic-embed-text"

def main():
    # 1. Initialize LangChain Embedding Model
    print(f"Loading Ollama model: {OLLAMA_MODEL}...")
    embeddings = OllamaEmbeddings(model=OLLAMA_MODEL)

    # 2. Prepare Data
    # In a real app, this would come from PDFs, databases, etc.
    documents = [
        {
            "id": "doc_1",
            "title": "Paris Info",
            "text": "Paris is the capital of France and is known for the Eiffel Tower."
        },
        {
            "id": "doc_2",
            "title": "Berlin Info",
            "text": "Berlin is the vibrant capital of Germany."
        },
        {
            "id": "doc_3",
            "title": "Solar System",
            "text": "Jupiter is the largest planet in our solar system."
        }
    ]

    # 3. Generate Embeddings & Prepare for Solr
    print("Generating embeddings...")
    solr_docs = []

    for doc in documents:
        # Generate vector for the text content
        vector = embeddings.embed_query(doc["text"])

        # Create the Solr document object
        solr_doc = {
            "id": doc["id"],
            "title_t": doc["title"],       # '_t' is a dynamic field for text in default config
            "text_t": doc["text"],
            "vector_embedding": vector     # This matches the field we created in Part 1
        }
        solr_docs.append(solr_doc)

    # 4. Push to Solr
    print(f"Indexing {len(solr_docs)} documents to Solr...")
    solr = pysolr.Solr(SOLR_URL, always_commit=True)

    try:
        solr.add(solr_docs)
        print("Success! Documents indexed.")
    except Exception as e:
        print(f"Error indexing to Solr: {e}")

    # 5. Example: How to Search (Hybrid Search)
    # We search for "capital cities" using the vector
    query_text = "capital cities in Europe"
    query_vector = embeddings.embed_query(query_text)

    # Solr 9 KNN Query Syntax: {!knn f=vector_field topK=10}vector_array
    # We format the vector list as a string like [0.1, 0.2, ...]
    vector_str = str(query_vector).replace(" ", "")

    print(f"\nSearching for: '{query_text}'")
    results = solr.search(f'{{!knn f=vector_embedding topK=5}}{vector_str}')

    print(f"Found {len(results)} results:")
    for result in results:
        print(f" - {result['title_t']}: {result['text_t']}")

if __name__ == "__main__":
    main()