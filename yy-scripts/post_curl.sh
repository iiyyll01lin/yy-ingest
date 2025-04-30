# Example curl command to send a POST request to the /transform endpoint.
# This initiates a document transformation task.
curl -X POST http://127.0.0.1:8752/transform \
-H "Content-Type: application/json" \ # Specify the content type as JSON
-d '{                           # Start of JSON data payload
  "url": "https://infra-oss-fis.tao.inventec.net/km-ops/resource/files/IPC-2581C.pdf", # URL of the document to process
  "start_page": 1,             # Page number to start processing from
  "end_page": 1                # Page number to end processing at (inclusive)
}'                             # End of JSON data payload

# --- Other Example Payloads (Commented Out) ---

# Example 1: Specifying multiple chunking methods and parameters
# -d '{
#   "url": "https://infra-oss-fis.tao.inventec.net/km-ops/resource/files/IPC-2581C.pdf",
#   "chunk_method": ["cluster_semantic", "recursive_token", "fixed_token", "kamradt"],
#   "chunk_max_size": 5100,
#   "chunk_size": 2100,
#   "chunk_overlap": 1700,
#   "avg_chunk_size": 2100,
#   "encoding_name": "cl100k_base",
#   "start_page": 1,
#   "end_page": 1
# }'

# Example 2: Using only cluster_semantic chunking with a specific max size
# -d '{
#   "url": "https://infra-oss-fis.tao.inventec.net/km-ops/resource/files/IPC-2581C.pdf",
#   "chunk_method": ["cluster_semantic"],
#   "chunk_max_size": 5100,
#   "start_page": 1,
#   "end_page": 1
# }'

# Example 3: Processing multiple pages (1-20) with specific chunking parameters
# -d '{
#   "url": "https://infra-oss-fis.tao.inventec.net/km-ops/resource/files/IPC-2581C.pdf",
#   "chunk_method": ["cluster_semantic"],
#   "chunk_max_size": 2100,
#   "chunk_size": 2100,
#   "chunk_overlap": 1700,
#   "avg_chunk_size": 2100,
#   "encoding_name": "cl100k_base",
#   "start_page": 1,
#   "end_page": 20
# }'
