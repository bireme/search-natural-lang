# Embedding Generator

This project generates embeddings for documents stored in Solr and saves them to MongoDB.

## Features

- Fetches documents from Solr
- Generates embeddings using Ollama (nomic-embed-text model)
- Stores embeddings in MongoDB with document metadata

## Setup

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Configure your MongoDB connection in `.env`:
```bash
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DATABASE=embeddings_db
MONGODB_COLLECTION=document_embeddings
```

3. Install dependencies:
```bash
uv sync
```

## Usage

Source the environment variables and run the embedding generator:

```bash
source set_env.sh
python generate_embeddings.py
```

## MongoDB Document Structure

Each document stored in MongoDB has the following structure:
```json
{
  "document_id": "unique_id_from_solr",
  "text_content": "original text content",
  "vector": [0.123, 0.456, ...],
  "source": "solr",
  "model": "nomic-embed-text"
}
```

## Requirements

- Solr instance running with documents
- MongoDB instance running
- Ollama with nomic-embed-text model installed
