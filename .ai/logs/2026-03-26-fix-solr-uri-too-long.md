# Fix Solr 414 URI Too Long Error

**Date:** 2026-03-26

## Problem

Sending vector search queries to Solr resulted in `HTTP/1.1 414 URI Too Long` because embedding vectors (hundreds of float values) were being sent as URL query parameters via a GET request.

## Changes

- **`search_ui/app/clients/solr.py`**: Changed `_send_query` from `client.get(url, params=...)` to `client.post(url, data=...)`. This sends the query parameters in the request body as `application/x-www-form-urlencoded` instead of in the URL, avoiding the URI length limit.

## Details

Solr's `/select` endpoint supports both GET and POST. Using POST with form-encoded body is the standard approach for large queries like KNN vector searches.
