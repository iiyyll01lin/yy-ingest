curl -X POST http://10.3.205.227:8752/transform \
-H "Content-Type: application/json" \
-d '{
  "url": "https://infra-oss-fis.tao.inventec.net/km-ops/resource/files/IPC-2581C.pdf",
  "chunk_method": ["cluster_semantic"],
  "chunk_max_size": 6800,
  "start_page": 1,
  "end_page": 34
}'


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
