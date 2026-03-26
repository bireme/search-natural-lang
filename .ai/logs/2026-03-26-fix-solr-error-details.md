# Fix Solr Error Details Not Visible in 502 Response

**Date:** 2026-03-26

## Problem

When Solr returned an error (HTTP status error), the application responded with a generic "Solr returned an error." message, hiding the actual error details needed for debugging.

## Changes

- **`search_ui/app/clients/solr.py`**: Updated the `HTTPStatusError` handler in `_send_query` to include the HTTP status code and response body (truncated to 500 chars) in the `SolrUnavailableError` message.
