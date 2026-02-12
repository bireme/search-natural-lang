#!/bin/bash
export UV_PROJECT_ENVIRONMENT=/var/lib/python-env/search-natural-lang

# Source .env file and export variables
if [ -f .env ]; then
    # Export all variables from .env, ignoring comments and empty lines
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
else
    echo "Warning: .env file not found"
fi