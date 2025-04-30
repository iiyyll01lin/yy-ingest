#!/bin/bash
# Simple script to perform a GET request to the /status endpoint for a given UUID.

# Check if the first argument is '-u' and the second argument (UUID) is provided
if [ "$1" = "-u" ] && [ -n "$2" ]; then
    uuid="$2" # Assign the second argument to the uuid variable
    # Perform a curl GET request to the status endpoint, substituting the UUID
    # -s: Silent mode (no progress meter or error messages)
    # -X GET: Explicitly specify the GET method (though it's the default)
    curl -s -X GET "http://127.0.0.1:8752/status/$uuid"
else
    # Print usage instructions if arguments are incorrect
    echo "Usage: $0 -u <uuid>"
    exit 1 # Exit with an error code
fi