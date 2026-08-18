# Current Feature

## Status

Not Started

## Goals

<!-- Add feature goals here via /feature load or /feature spec -->

## Notes

<!-- Add context, constraints, or spec details here -->

## History

- 2026-07-29: Starting Select Solr Collection in Search UI
- 2026-07-29: Completed Select Solr Collection in Search UI — `SOLR_COLLECTION` now accepts a comma-separated list; the UI gained a collection selector fed by `/config`, `/search` validates and echoes the chosen collection, and the Solr client builds a per-collection select URL. Log: [2026-07-29-search-ui-collection-selector.md](.ai/logs/2026-07-29-search-ui-collection-selector.md)
- 2026-07-29: Starting Configurable EMBEDDING_FIELDS in generate_embeddings
- 2026-07-29: Completed Configurable EMBEDDING_FIELDS in generate_embeddings — `TEXT_IN_FIELDS` became `EMBEDDING_FIELDS`, read from the env var and overridable per run with `--embedding-fields`; empty values are rejected with a clear error. Log: [2026-07-29-generate-embeddings-embedding-fields-arg.md](.ai/logs/2026-07-29-generate-embeddings-embedding-fields-arg.md)
