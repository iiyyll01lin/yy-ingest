#!/bin/bash
# filepath: ssh://prod@10.3.205.227/data/zqy/MinerU-v1.3.0/yy-scripts/simple_get.sh

# Check if UUID is provided
if [ "$1" = "-u" ] && [ -n "$2" ]; then
    uuid="$2"
    curl -s -X GET "http://10.3.205.227:8753/status/$uuid"
else
    echo "Usage: $0 -u <uuid>"
    exit 1
fi