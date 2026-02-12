from langchain_ollama import OllamaEmbeddings

def main():
    # 1. Initialize the Ollama Embeddings model
    # Ensure the 'model' matches what you pulled in Ollama (e.g., 'nomic-embed-text')
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
    )

    print("--- Generating Query Embedding ---")
    # 2. Embed a single query
    # Use this for the user's search question/prompt
    text_to_embed = "What is the capital of France?"
    query_vector = embeddings.embed_query(text_to_embed)

    print(f"Text: '{text_to_embed}'")
    print(f"Vector length: {len(query_vector)}")
    print(f"First 5 dimensions: {query_vector[:5]}")

    print("\n--- Generating Document Embeddings ---")
    # 3. Embed a list of documents
    # Use this for the data you want to store in your Vector Database
    documents = [
        "Paris is the capital of France.",
        "Berlin is the capital of Germany.",
        "Madrid is the capital of Spain."
    ]
    doc_vectors = embeddings.embed_documents(documents)

    print(f"Number of documents embedded: {len(doc_vectors)}")
    print(f"First document vector length: {len(doc_vectors[0])}")
    print(f"First 5 dimensions of first doc: {doc_vectors[0][:5]}")

if __name__ == "__main__":
    main()