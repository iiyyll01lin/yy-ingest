#!/bin/bash

# Script to poll the status of a MinerU task using its UUID.
# Usage: ./get_status_curl.sh -u <UUID> [-i <interval>] [-t <timeout>]

# Parse input arguments
while getopts u:i:t: flag
do
    case "${flag}" in
        u) uuid=${OPTARG};;
        i) interval=${OPTARG};;
        t) timeout=${OPTARG};;
    esac
done

# Set defaults
interval=${interval:-0.1}  # Default polling interval: 0.1 seconds
timeout=${timeout:-600}  # Default timeout: 10 minutes (600 seconds)

# Check if UUID is provided
if [ -z "$uuid" ]; then
    echo "Usage: ./get_status_curl.sh -u <UUID> [-i <interval>] [-t <timeout>]"
    echo "  -u: Task UUID (required)"
    echo "  -i: Polling interval in seconds (default: 0.1)"
    echo "  -t: Maximum polling time in seconds (default: 600)"
    exit 1
fi

echo "Starting polling for task: $uuid"
echo "Polling interval: ${interval}s, Timeout: ${timeout}s"
echo "Press Ctrl+C to stop polling"

start_time=$(date +%s)
end_time=$((start_time + timeout))
previous_progress=""
previous_step=""

while true; do
    current_time=$(date +%s)

    # Check if timeout reached
    if [ $current_time -gt $end_time ]; then
        echo "Timeout reached after ${timeout} seconds. Exiting."
        exit 1
    fi

    # Make the API call and store the response
    # -s: silent mode
    response=$(curl -s -X GET "http://127.0.0.1:8752/status/$uuid")

    # Extract status from response using grep and cut
    status=$(echo "$response" | grep -o '"msg":"[^"]*"' | cut -d '"' -f 4)

    # Extract progress from response
    progress=$(echo "$response" | grep -o '"progress":[0-9.]*' | cut -d ':' -f 2)

    # Extract current step from response
    current_step=$(echo "$response" | grep -o '"current_step":"[^"]*"' | cut -d '"' -f 4)

    # Extract estimated remaining time from response
    est_remaining=$(echo "$response" | grep -o '"estimated_remaining":[0-9.]*' | cut -d ':' -f 2)

    # Format remaining time nicely if available, otherwise show 'unknown'
    if [[ "$est_remaining" != "null" && "$est_remaining" != "" ]]; then
        est_remaining_formatted=$(printf "%.1f seconds" $est_remaining)
    else
        est_remaining_formatted="unknown"
    fi

    # Combine progress and step to check for changes
    current_info="${progress}-${current_step}"
    # Only print when there's a change in progress or step to avoid flooding the terminal
    if [[ "$current_info" != "$previous_progress" ]]; then
        echo "$(date '+%H:%M:%S') | Status: $status | Progress: $progress% | Step: $current_step | Est. remaining: $est_remaining_formatted"
        previous_progress="$current_info" # Update the last known state
    fi

    # If task has completed (success) or failed, print final status and full response, then exit
    if [[ "$status" == "success" || "$status" == "failed" ]]; then
        echo "Task completed with status: $status"
        echo "Full response:"
        # Pretty-print the JSON response
        echo "$response" | python3 -m json.tool
        break # Exit the loop
    fi

    # Wait for the specified interval before the next poll
    sleep $interval
done